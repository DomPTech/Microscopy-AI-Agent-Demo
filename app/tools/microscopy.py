import subprocess
import time
import sys
import os
from typing import Optional, Dict
from smolagents import tool
import Pyro5.api
import Pyro5.errors
import numpy as np
from app.config import settings
from enum import Enum

# Global state for the client and server process
CLIENT: Optional[object] = None # asyncroscopy.clients.notebook_client.NotebookClient
SERVER_PROCESSES: Dict[str, subprocess.Popen] = {}

# Define the microscope servers and their twins
class MicroscopeServer(Enum):
    Central = {
        "server": "asyncroscopy.servers.protocols.central_server"
    }
    AS = {
        "server": "asyncroscopy.servers.AS_server",
        "twin": "asyncroscopy.servers.AS_server_twin"
    }
    Ceos = {
        "server": "asyncroscopy.servers.Ceos_server",
        "twin": "asyncroscopy.servers.Ceos_server_twin"
    }

@tool
def start_server(mode: str = "mock", servers: list[MicroscopeServer] = [MicroscopeServer.Central]) -> str:
    """
    Starts the microscope servers (Twisted architecture).
    
    Args:
        mode: "mock" for testing/simulation (uses twin servers), "real" for actual hardware.
        servers: List of server modules to start. Defaults to Central, and Ceos_Twin.
    """
    global SERVER_PROCESSES
    
    # Check if any are already running
    running = [s for s, p in SERVER_PROCESSES.items() if p.poll() is None]
    if running:
        return f"Servers already running: {', '.join(running)}"

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    repo_path = os.path.join(base_dir, "asyncroscopy_repo")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

    started = []
    port = 9000
    try:
        for server in servers:
            server_name = server.value.get("server")
            module = server_name
            if mode == "mock":
                module = server.value.get("twin", server_name)
            cmd = [sys.executable, "-m", module]
            cmd.append(str(port))

            print(f"Starting server: {module} on port {port}")
            proc = subprocess.Popen(
                cmd,
                cwd=base_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            SERVER_PROCESSES[module] = proc
            started.append(module)
            # Give it a tiny bit to breathe
            time.sleep(1)

            port += 1
        
        return f"Started servers: {', '.join(started)} in {mode} mode."

    except Exception as e:
        return f"Failed to start servers: {e}"

@tool
def connect_client(host: str = "localhost", port: int = 9000, routing_table: Optional[dict] = None) -> str:
    """
    Connects the client to the central server and sets up routing.
    
    Args:
        host: Central server host.
        port: Central server port.
        routing_table: Dict mapping prefixes (AS, Ceos) to (host, port).
    """
    global CLIENT
    from asyncroscopy.clients.notebook_client import NotebookClient
    
    if routing_table is None:
        routing_table = {
            "Central": ("localhost", 9000),
            "Ceos": ("localhost", 9001)
        }

    try:
        CLIENT = NotebookClient.connect(host=host, port=port)
        if not CLIENT:
            return "Failed to connect to central server."
        
        # Configure routing on the central server
        resp = CLIENT.send_command("Central", "set_routing_table", routing_table)
        
        # Initialize AS server
        CLIENT.send_command("AS", "connect_AS", {"host": "localhost", "port": 9001})
        
        return f"Connected successfully. Routing: {resp}"
    except Exception as e:
        CLIENT = None
        return f"Connection error: {e}"

@tool
def adjust_magnification(amount: float, destination: str = "AS") -> str:
    """
    Adjusts the microscope magnification level.
    
    Args:
        amount: The magnification level to set.
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        # AS server might not have 'set_microscope_status' directly, needs investigation of command list
        # Based on AS_server_AtomBlastTwin, we might need a different command
        resp = CLIENT.send_command(destination, "set_magnification", {"value": amount})
        return f"Magnification command sent to {destination}: {resp}"
    except Exception as e:
        return f"Error adjusting magnification: {e}"

@tool
def capture_image(detector: str = "Ceta", destination: str = "AS") -> str:
    """
    Captures an image and saves it.
    
    Args:
        detector: The detector to use.
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
        
    try:
        # Twisted servers return numpy arrays wrapped in package_message
        print(f"[TOOLS DEBUG] Requesting image from {destination}...")
        img = CLIENT.send_command(destination, "get_scanned_image", {
            "scanning_detector": detector,
            "size": 512,
            "dwell_time": 2e-6
        })
        print(f"[TOOLS DEBUG] Received response of type: {type(img)}")
        
        if img is None:
            return "Failed to capture image (None returned)."
            
        if isinstance(img, str):
            return f"Failed to capture image. Error from server: {img}"

        output_path = f"/tmp/microscope_capture_{int(time.time())}.npy"
        np.save(output_path, img)
        return f"Image captured from {destination} and saved to {output_path} (Shape: {img.shape})"
    except Exception as e:
        return f"Error capturing image: {e}"

@tool
def close_microscope() -> str:
    """
    Safely closes the microscope connection and stops the servers.
    """
    global SERVER_PROCESSES, CLIENT
    resp = "Microscope closed."
    
    CLIENT = None
    
    for module, proc in SERVER_PROCESSES.items():
        proc.terminate()
        resp += f" {module} stopped."
    SERVER_PROCESSES.clear()
        
    return resp

@tool
def get_stage_position(destination: str = "AS") -> str:
    """
    Get the current stage position (x, y, z).
    
    Args:
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        pos = CLIENT.send_command(destination, "get_stage")
        return f"Stage Position from {destination}: {pos}"
    except Exception as e:
        return f"Error getting stage position: {e}"
