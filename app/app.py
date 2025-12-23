import uvicorn
import webview
import threading
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class ChatMessage(BaseModel):
    message: str
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/control/{action}")
async def microscope_control(action: str):
    print(f"Microscope Command Received: {action}")
    return {"status": "success", "command": action}

@app.post("/chat")
async def supercomputer_chat(data: ChatMessage):
 #supercomputer api goes here
    user_text = data.message
    bot_response = f"Supercomputer analyzed: '{user_text}'. Result: Optimizing focus..."
    return {"reply": bot_response}

def run_fastapi():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()
    webview.create_window(
        title='Microscopy AI Agent Control',
        url='http://127.0.0.1:8000',
        width=1400,
        height=900,
        resizable=True
    )
    webview.start()