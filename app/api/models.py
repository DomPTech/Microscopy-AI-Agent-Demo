from pydantic import BaseModel, Field
from typing import Optional, List, Any

class InitializeRequest(BaseModel):
    model_id: str = Field(default="Auto", description="The ID of the model to use for the agent.")

class ChatRequest(BaseModel):
    query: str = Field(..., description="The query string to send to the agent.")

class ChatResponse(BaseModel):
    response: str = Field(..., description="The agent's response to the query.")

class HealthResponse(BaseModel):
    status: str = "ok"
    model_id: Optional[str] = None
