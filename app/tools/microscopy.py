import subprocess
import time
import sys
import os
from typing import Optional
from smolagents import tool
import Pyro5.api
import Pyro5.errors
import numpy as np

# Global state for the client and server process
# PROXY is the Pyro5 proxy object
PROXY: Optional[object] = None
SERVER_PROCESS: Optional[subprocess.Popen] = None

@tool
def start_server(mode: str = "mock", port: int = 9093) -> str:
    """
    Starts the microscope server (Smart Proxy).
    
    Args:
        mode: "mock" for testing/simulation, "real" for actual hardware.
        port: Port to run the server on (default 9093).
    """
    global SERVER_PROCESS
    if SERVER_PROCESS and SERVER_PROCESS.poll() is None:
        return "Server is already running."

    # Using asyncroscopy package servers
    # Derive path relative to this file's directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    if mode == "mock":
        script_path = os.path.join(base_dir, "asyncroscopy_repo/asyncroscopy/smart_proxy/smart_proxy.py")
    else:
        script_path = os.path.join(base_dir, "asyncroscopy_repo/asyncroscopy/smart_proxy/smart_proxy.py")
        
    if not os.path.exists(script_path):
        return f"Error: Server script not found at {script_path}"

    try:
        # Prepare env
        env = os.environ.copy()
        # Add the repo and mocks to PYTHONPATH
        repo_path = os.path.join(base_dir, "asyncroscopy_repo")
        mocks_path = os.path.join(base_dir, "tests/mocks")
        env["PYTHONPATH"] = f"{repo_path}{os.pathsep}{mocks_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        # Start server - smart_proxy.py from asyncroscopy repo
        # usage: smart_proxy.py [host] [port]
        SERVER_PROCESS = subprocess.Popen(
            [sys.executable, "-u", script_path, "127.0.0.1", str(port)],
            cwd=base_dir,
            env=env,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True
        )
        
        start_time = time.time()
        output_buffer = []
        while time.time() - start_time < 30:
            if SERVER_PROCESS.poll() is not None:
                 rest_out, _ = SERVER_PROCESS.communicate()
                 all_out = "".join(output_buffer) + (rest_out if rest_out else "")
                 return f"Failed to start server. Exit code: {SERVER_PROCESS.returncode}. Output: {all_out}"
            
            line = SERVER_PROCESS.stdout.readline()
            if line:
                output_buffer.append(line)
                if "Server is ready" in line:
                    return f"Server started in {mode} mode on port {port}."
            else:
                time.sleep(0.1)
        
        SERVER_PROCESS.terminate()
        return f"Failed to start server: Timeout. Captured Output: {''.join(output_buffer)}"

    except Exception as e:
        return f"Failed to start server: {e}"

@tool
def connect_client(host: str = "127.0.0.1", port: int = 9093) -> str:
    """
    Connects the client to the microscope server using Pyro5.
    
    Args:
        host: Server host (default "127.0.0.1").
        port: Server port (default 9093).
    """
    global PROXY
    try:
        uri = f"PYRO:tem.server@{host}:{port}"
        PROXY = Pyro5.api.Proxy(uri)
        # Check if it responds
        try:
            status = PROXY.get_instrument_status()
            return f"Connected successfully. Microscope Status: {status}"
        except:
             # If it doesn't respond immediately, it might be setting up
             return f"Connected to {uri}. (Status check failed, but proxy created)"
    except Exception as e:
        PROXY = None
        return f"Connection error: {e}"

@tool
def adjust_magnification(amount: float) -> str:
    """
    Adjusts the microscope magnification level.
    
    Args:
        amount: The magnification level to set.
    """
    global PROXY
    if not PROXY:
        return "Error: Client not connected."
    
    try:
        PROXY.set_microscope_status(parameter='magnification', value=amount)
        return f"Magnification set to {amount}"
    except Exception as e:
        return f"Error adjusting magnification: {e}"

@tool
def capture_image(size: int = 512, dwell_time: float = 2e-6) -> str:
    """
    Captures an image and saves it.
    
    Args:
        size: Image size (width/height).
        dwell_time: Dwell time in seconds.
    """
    global PROXY
    if not PROXY:
        return "Error: Client not connected."
        
    try:
        # asyncroscopy smart_proxy returns (data_list, shape, dtype_str)
        result = PROXY.acquire_image(device_name='ceta_camera') # size/dwell passed via device_settings in real asyncroscopy
        
        if not result:
            return "Failed to capture image (None returned)."
            
        data_list, shape, dtype_str = result
        arr = np.array(data_list, dtype=dtype_str).reshape(shape)

        output_path = f"/tmp/microscope_capture_{int(time.time())}.npy"
        np.save(output_path, arr)
        return f"Image captured and saved to {output_path} (Shape: {arr.shape})"
    except Exception as e:
        return f"Error capturing image: {e}"

@tool
def close_microscope() -> str:
    """
    Safely closes the microscope connection and stops the server.
    """
    global SERVER_PROCESS, PROXY
    resp = "Microscope closed."
    
    if PROXY:
        try:
            PROXY.close()
        except:
            pass
        PROXY = None
    
    if SERVER_PROCESS:
        SERVER_PROCESS.terminate()
        SERVER_PROCESS = None
        resp += " Server stopped."
        
    return resp

@tool
def get_stage_position() -> str:
    """
    Get the current stage position (x, y, z).
    """
    global PROXY
    if not PROXY:
        return "Error: Client not connected."
    
    try:
        pos = PROXY.get_stage()
        return f"Stage Position: {pos}"
    except Exception as e:
        return f"Error getting stage position: {e}"
