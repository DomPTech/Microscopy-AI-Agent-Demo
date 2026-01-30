import time
import os
import sys
from app.tools.microscopy import MicroscopeServer, start_server, connect_client, adjust_magnification, capture_image, close_microscope, get_stage_position
from app.config import settings

def run_test():
    settings.instrument_host = "localhost"
    settings.instrument_port = 9001
    settings.autoscript_port = 9001
    
    print("--- Starting Integration Test ---")
    
    # Start server (Mock)
    print("\n1. Starting Mock Server...")
    res = start_server(mode="mock", servers=[MicroscopeServer.Central, MicroscopeServer.AS, MicroscopeServer.Ceos])
    print(res)
    if "Failed" in res:
        return

    # Connect
    print("\n2. Connecting Client...")
    # Give it a sec
    time.sleep(1)
    res = connect_client(host=settings.server_host)
    print(res)
    if "Failed" in res or "error" in res.lower():
        close_microscope()
        return

    # Get status/stage
    print("\n3. Getting Stage Position...")
    res = get_stage_position()
    print(res)

    # Adjust magnification
    print("\n4. Adjusting Magnification...")
    res = adjust_magnification(5000.0)
    print(res)

    # Capture image
    print("\n5. Capturing Image...")
    capture_result = capture_image(detector="Ceta")
    print(capture_result)

    # Close microscope
    print("\n6. Closing Microscope...")
    res = close_microscope()
    print(res)
    
    print("\n--- Test Finished ---")

if __name__ == "__main__":
    run_test()
