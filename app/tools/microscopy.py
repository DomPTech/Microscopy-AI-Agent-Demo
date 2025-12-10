def adjust_magnification(amount: float):
    """
    Adjust the microscope magnification.
    
    Args:
        amount: The amount to adjust the magnification
    """
    print(f"Adjusting magnification by {amount}")
    return {"status": "success", "magnification": amount}

def capture_image():
    """
    Capture an image from the microscope.
    """
    print("Capturing image")
    return {"status": "success", "image_path": "/tmp/dummy_capture.png"}

def close_microscope():
    """
    Close the microscope.
    """
    print("Closing microscope")
    return {"status": "success"}
