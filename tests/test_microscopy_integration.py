import time
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.getcwd())

from app.tools.microscopy import start_server, connect_client, adjust_magnification, capture_image, close_microscope, get_stage_position

def run_test():
    print("--- Starting Integration Test ---")
    
    # Start server (Mock)
    print("\n1. Starting Mock Server...")
    res = start_server(mode="mock", port=9093)
    print(res)
    if "Failed" in res:
        return

    # Connect
    print("\n2. Connecting Client...")
    # Give it a sec
    time.sleep(1)
    res = connect_client(host="127.0.0.1", port=9093)
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
    res = capture_image(size=256, dwell_time=1e-6)
    print(res)

    # Close microscope
    print("\n6. Closing Microscope...")
    res = close_microscope()
    print(res)
    
    print("\n--- Test Finished ---")

if __name__ == "__main__":
    run_test()
