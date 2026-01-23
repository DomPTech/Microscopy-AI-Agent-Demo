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

    if mode == "mock":
        script_path = "app/services/smart_proxy/server_mock.py"
    else:
        script_path = "app/services/smart_proxy/server.py"
        
    abs_path = os.path.abspath(script_path)
    if not os.path.exists(abs_path):
        return f"Error: Server script not found at {abs_path}"

    try:
        # Prepare env with CWD in PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(os.getcwd(), env.get("PYTHONPATH", ""))

        # Start server as a background process with unbuffered output
        SERVER_PROCESS = subprocess.Popen(
            [sys.executable, "-u", abs_path, str(port)],
            cwd=os.getcwd(),
            env=env,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True
        )
        
        start_time = time.time()
        output_buffer = []
        while time.time() - start_time < 20:
            if SERVER_PROCESS.poll() is not None:
                 rest_out, _ = SERVER_PROCESS.communicate()
                 all_out = "".join(output_buffer) + (rest_out if rest_out else "")
                 return f"Failed to start server. Exit code: {SERVER_PROCESS.returncode}. CMD: {[sys.executable, '-u', abs_path, str(port)]}. Output: {all_out}"
            
            line = SERVER_PROCESS.stdout.readline()
            if line:
                output_buffer.append(line)
                if "Server ready" in line:
                    return f"Server started in {mode} mode on port {port}."
            else:
                time.sleep(0.1)
        
        SERVER_PROCESS.terminate()
        return f"Failed to start server: Timeout waiting for readiness signal. Captured Output: {''.join(output_buffer)}"

    except Exception as e:
        return f"Failed to start server: {e}"

@tool
def connect_client(host: str = "127.0.0.1", port: int = 9093) -> str:
    """
    Connects the client to the microscope server using Pyro5.
    
    Args:
        host: Server host.
        port: Server port.
    """
    global PROXY
    try:
        uri = f"PYRO:tem.server@{host}:{port}"
        PROXY = Pyro5.api.Proxy(uri)
        status = PROXY.get_instrument_status()
        return f"Connected successfully. Microscope Status: {status}"
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
        return "Error: Client not connected. Use connect_client first."
    
    try:
        # smart_proxy.py doesn't have set_magnification directly
        PROXY.set_microscope_status(parameter='magnification', value=amount)
        return f"Magnification set to {amount}"
    except Exception as e:
        return f"Error adjusting magnification: {e}"

@tool
def capture_image(size: int = 512, dwell_time: float = 2e-6) -> str:
    """
    Captures an image from the current microscope view.
    
    Args:
        size: Image size (width/height).
        dwell_time: Dwell time in seconds.
    """
    global PROXY
    if not PROXY:
        return "Error: Client not connected. Use connect_client first."
        
    try:
        result = PROXY.acquire_image(device_name='ceta_camera', size=size)
        
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
