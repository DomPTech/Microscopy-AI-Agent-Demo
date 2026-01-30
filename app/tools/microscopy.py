import subprocess
import time
import sys
import os
import socket
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

def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    """Wait for a port to become available (server listening)."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((host, port))
            sock.close()
            return True
        except (socket.error, ConnectionRefusedError):
            time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    return False

# Define the microscope servers and their twins
class MicroscopeServer(Enum):
    Central = {
        "server": "asyncroscopy.servers.protocols.central_server",
        "port": 9000
    }
    AS = {
        "server": "asyncroscopy.servers.AS_server",
        "twin": "asyncroscopy.servers.AS_server_twin",
        "port": 9001
    }
    Ceos = {
        "server": "asyncroscopy.servers.Ceos_server",
        "twin": "asyncroscopy.servers.Ceos_server_twin",
        "port": 9003
    }

@tool
def start_server(mode: str = "mock", servers: Optional[list[MicroscopeServer]] = None) -> str:
    """
    Starts the microscope servers (Twisted architecture).
    
    Args:
        mode: "mock" for testing/simulation (uses twin servers), "real" for actual hardware.
        servers: List of server modules to start. Available options:
            - MicroscopeServer.Central: The main control server (Port 9000).
            - MicroscopeServer.AS: The AS server or its twin (Port 9001).
            - MicroscopeServer.Ceos: The Ceos server or its twin (Port 9003).
            Defaults to starting all three [Central, AS, Ceos] if None.
    """

    global SERVER_PROCESSES
    if servers is None:
        servers = [MicroscopeServer.Central, MicroscopeServer.AS, MicroscopeServer.Ceos]
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    repo_path = os.path.join(base_dir, "external", "asyncroscopy")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_path}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["AUTOSCRIPT_PATH"] = settings.autoscript_path

    started = []
    ports_to_wait = []
    
    try:
        for server in servers:
            server_name = server.value.get("server")
            module = server_name
            port = server.value.get("port")
            if mode == "mock":
                module = server.value.get("twin", server_name)
            
            # Check if this specific module is already tracked and running
            if module in SERVER_PROCESSES and SERVER_PROCESSES[module].poll() is None:
                print(f"Server {module} already running (tracked).")
                started.append(f"{module} (already running)")
                continue

            # Check if something is already listening on the port (might be an orphaned process)
            if _wait_for_port("localhost", port, timeout=0.2):
                print(f"Server port {port} already listening. Assuming it's the correct server.")
                started.append(f"{module} (already listening)")
                continue

            cmd = [sys.executable, "-m", module, str(port)]

            print(f"Starting server: {module} on port {port}")
            proc = subprocess.Popen(
                cmd,
                cwd=base_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            SERVER_PROCESSES[module] = proc
            started.append(module)
            ports_to_wait.append(port)
        
        if not started:
            return "All requested servers are already running."

        # Wait for newly started servers to be ready
        if ports_to_wait:
            print(f"Waiting for servers on ports {ports_to_wait} to be ready...")
            for port in ports_to_wait:
                if not _wait_for_port("localhost", port, timeout=10.0):
                    return f"Failed to start server on port {port} - timeout waiting for it to listen"
        
        return f"Servers status: {', '.join(started)} in {mode} mode."

    except Exception as e:
        return f"Failed to start servers: {e}"

@tool
def connect_client(host: str = "localhost", port: int = 9000) -> str:
    """
    Connects the client to the central server and sets up routing.
    
    Args:
        host: Central server host.
        port: Central server port.
    """
    global CLIENT
    from asyncroscopy.clients.notebook_client import NotebookClient
    
    routing_table = {
        "Central": ("localhost", MicroscopeServer.Central.value.get("port")),
        "AS": ("localhost", MicroscopeServer.AS.value.get("port")),
        "Ceos": ("localhost", MicroscopeServer.Ceos.value.get("port"))
    }

    try:
        CLIENT = NotebookClient.connect(host=host, port=port)
        if not CLIENT:
            return "Failed to connect to central server."
        
        # Configure routing on the central server
        resp = CLIENT.send_command("Central", "set_routing_table", routing_table)
        if isinstance(resp, str) and "ERROR" in resp:
            return f"Failed to set routing table: {resp}"
        
        # Initialize AS server
        as_resp = CLIENT.send_command("AS", "connect_AS", {
            "host": settings.instrument_host, 
            "port": settings.instrument_port
        })
        if isinstance(as_resp, str) and "ERROR" in as_resp:
            return f"Failed to reach AS server: {as_resp}. Did you start all servers?"
        
        return f"Connected successfully. Routing: {resp}, AS: {as_resp}"
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
