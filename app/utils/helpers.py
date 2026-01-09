import psutil
import os

def get_total_ram_gb():
    """
    Returns the total system RAM in gigabytes.
    """
    try:
        total_ram_bytes = psutil.virtual_memory().total
        return total_ram_bytes / (1024**3)
    except Exception:
        # Fallback for macOS if psutil fails for some reason
        try:
            return int(os.popen("sysctl -n hw.memsize").read()) / (1024**3)
        except Exception:
            return 8.0  # Safe default
