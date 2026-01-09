from smolagents import tool

@tool
def adjust_magnification(amount: float) -> dict:
    """
    Adjusts the microscope magnification level.
    
    Args:
        amount: The magnification level to set (e.g., 10.0, 40.0).
    """
    print(f"Adjusting magnification by {amount}")
    return {"status": "success", "magnification": amount}

@tool
def capture_image() -> dict:
    """
    Captures an image from the current microscope view.
    """
    print("Capturing image")
    return {"status": "success", "image_path": "/tmp/dummy_capture.png"}

@tool
def close_microscope() -> dict:
    """
    Safely closes the microscope connection.
    """
    print("Closing microscope")
    return {"status": "success"}
