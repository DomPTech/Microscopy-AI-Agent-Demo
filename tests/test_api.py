import sys
from unittest.mock import MagicMock, patch

# Mock heavy dependencies BEFORE any app imports
mock_torch = MagicMock()
mock_torch.backends.mps.is_available.return_value = False
sys.modules["torch"] = mock_torch
sys.modules["smolagents"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from app.api.server import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_agent():
    import app.api.server
    app.api.server._agent = None
    yield

def test_health_before_init():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "agent_not_initialized"

def test_chat_before_init():
    response = client.post("/chat", json={"query": "hello"})
    assert response.status_code == 400
    assert "Agent not initialized" in response.json()["detail"]

def test_initialize():
    with patch("app.api.server.Agent") as mock_agent_class:
        instance = mock_agent_class.return_value
        instance.model.model_id = "mock-model"
        
        response = client.post("/initialize", json={"model_id": "mock-model"})
        assert response.status_code == 200
        assert response.json()["status"] == "initialized"

def test_health_after_init():
    import app.api.server
    # Manually set state to avoid "actually initializing" via the endpoint
    mock_inst = MagicMock()
    mock_inst.model.model_id = "mock-model"
    app.api.server._agent = mock_inst
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["model_id"] == "mock-model"

def test_chat():
    import app.api.server
    mock_inst = MagicMock()
    mock_inst.chat.return_value = "Mocked response"
    app.api.server._agent = mock_inst
    
    response = client.post("/chat", json={"query": "Say 'test successful'"})
    assert response.status_code == 200
    assert response.json()["response"] == "Mocked response"
