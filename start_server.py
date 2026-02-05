import uvicorn
import argparse

def main():
    parser = argparse.ArgumentParser(description="Start the Microscopy AI Agent API server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    
    args = parser.parse_args()
    
    print(f"Starting server on {args.host}:{args.port}...")
    uvicorn.run("app.api.server:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
