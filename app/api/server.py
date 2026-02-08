from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import json
from app.api.models import InitializeRequest, ChatRequest, ChatResponse, HealthResponse
from app.agent.core import Agent

app = FastAPI(title="Microscopy AI Agent API")

# Global agent instance
_agent: Optional[Agent] = None

def get_agent() -> Agent:
    global _agent
    if _agent is None:
        raise HTTPException(status_code=400, detail="Agent not initialized. Call /initialize first.")
    return _agent

@app.post("/initialize", response_model=HealthResponse)
async def initialize(req: InitializeRequest):
    """
    Initialize or re-initialize the agent with a specific model.
    """
    global _agent
    try:
        _agent = Agent(model_id=req.model_id)
        return HealthResponse(status="initialized", model_id=req.model_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, agent: Agent = Depends(get_agent)):
    """
    Send a query to the agent and get a response.
    """
    try:
        response = agent.chat(req.query)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _format_sse(event: str, data: str) -> str:
    lines = data.splitlines() or [""]
    payload = ""
    if event:
        payload += f"event: {event}\n"
    for line in lines:
        payload += f"data: {line}\n"
    return payload + "\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, agent: Agent = Depends(get_agent)):
    """
    Stream the agent response as server-sent events.
    """

    def event_generator():
        try:
            for event in agent.stream_chat(req.query):
                event_type = event.get("type", "delta")
                content = event.get("content", "")
                payload = json.dumps({"content": content})
                yield _format_sse(event_type, payload)
            yield _format_sse("done", "[DONE]")
        except Exception as e:
            yield _format_sse("error", json.dumps({"detail": str(e)}))

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Check the health of the API and agent status.
    """
    model_id = _agent.model.model_id if _agent else None
    return HealthResponse(
        status="ok" if _agent else "agent_not_initialized",
        model_id=model_id
    )
