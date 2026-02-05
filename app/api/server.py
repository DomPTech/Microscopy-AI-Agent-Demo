from fastapi import FastAPI, HTTPException, Depends
from typing import Optional
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
