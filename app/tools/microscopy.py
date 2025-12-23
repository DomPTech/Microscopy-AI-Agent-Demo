def adjust_magnification(amount: float):

    print(f"Adjusting magnification by {amount}")
    return {"status": "success", "magnification": amount}

def capture_image():

    print("Capturing image")
    return {"status": "success", "image_path": "/tmp/dummy_capture.png"}

def close_microscope():

    print("Closing microscope")
    return {"status": "success"}
