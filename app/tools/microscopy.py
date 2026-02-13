import subprocess
import time
import sys
import os
import socket
from typing import Optional, Dict, Any, Union
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
def connect_client(host: Optional[str] = None, port: Optional[int] = None) -> str:
    """
    Connects the client to the central server and sets up routing.
    
    Args:
        host: Central server host (defaults to settings.server_host).
        port: Central server port (defaults to settings.server_port).
    """
    global CLIENT
    from asyncroscopy.clients.notebook_client import NotebookClient

    # Use settings defaults if not provided
    host = host or settings.server_host
    port = port or settings.server_port

    # Safety delay to ensure servers are ready
    time.sleep(1)
    
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

@tool
def calibrate_screen_current(destination: str = "AS") -> str:
    """
    Calibrates the gun lens values to screen current.
    Start with screen current at ~100 pA. Screen must be inserted.
    
    Args:
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        resp = CLIENT.send_command(destination, "calibrate_screen_current")
        return f"Screen current calibration: {resp}"
    except Exception as e:
        return f"Error calibrating screen current: {e}"

@tool
def set_screen_current(current_pa: float, destination: str = "AS") -> str:
    """
    Sets the screen current (via gun lens). Must have screen current calibrated first.
    
    Args:
        current_pa: The target current in picoamperes (pA).
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        resp = CLIENT.send_command(destination, "set_current", {"current": current_pa})
        return f"Set current response: {resp}"
    except Exception as e:
        return f"Error setting current: {e}"

@tool
def place_beam(x: float, y: float, destination: str = "AS") -> str:
    """
    Sets the resting beam position.
    
    Args:
        x: Normalized X position [0:1].
        y: Normalized Y position [0:1].
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        resp = CLIENT.send_command(destination, "place_beam", {"x": x, "y": y})
        return f"Beam move response: {resp}"
    except Exception as e:
        return f"Error placing beam: {e}"

@tool
def blank_beam(destination: str = "AS") -> str:
    """
    Blanks the electron beam.
    
    Args:
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        resp = CLIENT.send_command(destination, "blank_beam")
        return f"Blank beam response: {resp}"
    except Exception as e:
        return f"Error blanking beam: {e}"

@tool
def unblank_beam(duration: Optional[float] = None, destination: str = "AS") -> str:
    """
    Unblanks the electron beam.
    
    Args:
        duration: Optional dwell time in seconds. If provided, the beam will auto-blank after this time.
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    args = {}
    if duration is not None:
        args["duration"] = duration
    
    try:
        resp = CLIENT.send_command(destination, "unblank_beam", args)
        return f"Unblank beam response: {resp}"
    except Exception as e:
        return f"Error unblanking beam: {e}"

@tool
def get_microscope_status(destination: str = "AS") -> str:
    """
    Returns the current status of the microscope server.
    
    Args:
        destination: The server to query (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        return CLIENT.send_command(destination, "get_status")
    except Exception as e:
        return f"Error getting status: {e}"

@tool
def get_microscope_state(destination: str = "AS") -> Dict[str, Any]:
    """
    Returns the full state of the microscope as a dictionary of variables.
    Use this for validating constraints or checking specific values.
    
    Args:
        destination: The server to query (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return {"error": "Client not connected."}
    
    try:
        state = CLIENT.send_command(destination, "get_state")
        if isinstance(state, dict):
            return state
        # Fallback for older servers that don't have get_state
        return {"status": CLIENT.send_command(destination, "get_status")}
    except Exception as e:
        return {"error": str(e)}

@tool
def set_column_valve(state: str, destination: str = "AS") -> str:
    """
    Sets the state of the column valve.
    
    Args:
        state: "open" or "closed".
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        resp = CLIENT.send_command(destination, "set_microscope_status", {"parameter": "column_valve", "value": state})
        return f"Column valve command sent to {destination}: {resp}"
    except Exception as e:
        return f"Error setting column valve: {e}"

@tool
def set_optics_mode(mode: str, destination: str = "AS") -> str:
    """
    Sets the optical mode (TEM or STEM).
    
    Args:
        mode: "TEM" or "STEM".
        destination: The server to send the command to (default 'AS').
    """
    global CLIENT
    if not CLIENT:
        return "Error: Client not connected."
    
    try:
        resp = CLIENT.send_command(destination, "set_microscope_status", {"parameter": "optics_mode", "value": mode})
        return f"Optics mode command sent to {destination}: {resp}"
    except Exception as e:
        return f"Error setting optics mode: {e}"

# Collection of all tools for the agent
TOOLS = [
    adjust_magnification,
    capture_image,
    close_microscope,
    start_server,
    connect_client,
    get_stage_position,
    calibrate_screen_current,
    set_screen_current,
    place_beam,
    blank_beam,
    unblank_beam,
    get_microscope_status,
    get_microscope_state,
    set_column_valve,
    set_optics_mode,
]

# Experiment Framework Integration
from app.tools.experiment_framework import ExperimentFootprint, ExperimentExecutor, ExperimentAction, ExperimentConstraint, RewardMetric

@tool
def submit_experiment(experiment_design: Dict[str, Any]) -> str:
    """
    Submits a structured experiment to the autonomous scientist framework.
    
    This tool allows you to define a hypothesis as an 'Experimental Footprint' containing:
    1. A sequence of actions.
    2. Constraints to ensure safety/validity.
    3. A reward metric to evaluate success.
    
    Args:
        experiment_design: A dictionary matching the ExperimentFootprint structure. 
                           Example:
                           {
                               "id": "exp_001",
                               "description": "Optimize focus",
                               "actions": [
                                    {"name": "adjust_magnification", "params": {"amount": 5000}}
                               ],
                               "constraints": [],
                               "observables": ["image"],
                               "reward": {"metric_type": "image_entropy"}
                           }
    """
    global TOOLS
    
    try:
        # Parse the input dictionary into an ExperimentFootprint object
        footprint = ExperimentFootprint(**experiment_design)
        
        # Create the executor with a map of available tools
        tool_map = {t.name: t for t in TOOLS}
        
        executor = ExperimentExecutor(tool_map)
        
        if not CLIENT:
            return "Error: Client not connected. Cannot execute experiment."

        # Fetch full state for validation
        current_state = get_microscope_state("AS")
        
        if "error" in current_state:
            return f"Failed to validate experiment: could not fetch state. Error: {current_state['error']}"

        violations = executor.validate_constraints(footprint, current_state)
        if violations:
            return f"Experiment rejected due to constraints: {violations}"
            
        # Execute
        results = executor.execute(footprint)
        
        return f"Experiment '{footprint.id}' completed.\\nSuccess: {results['success']}\\nReward: {results['reward']}\\nLog: {results['log']}"
        
    except Exception as e:
        return f"Failed to submit experiment: {e}"

# Add the new tool to the exported list
TOOLS.append(submit_experiment)
