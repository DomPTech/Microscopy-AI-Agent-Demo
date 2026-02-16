import time
import pytest
import numpy as np
import sys
import os
from app.tools.microscopy import (
    start_server, connect_client, close_microscope,
    discover_commands, get_ceos_info, calibrate_screen_current,
    set_beam_current, capture_image, get_atom_count,
    tune_C1A1, acquire_tableau
)
from app.config import settings

# Based on the fluence notebook in asyncroscopy

# Handle pyTEMlib availability and version differences
try:
    import pyTEMlib.probe_tools as pt
    if not hasattr(pt, 'aberrations'):
        if hasattr(pt, 'get_probe'):
            pt.aberrations = pt.get_probe
        else:
            print("Warning: Neither pt.aberrations nor pt.get_probe found. Using mock fallback.")
            def mock_aberrations(tableau, size_x, size_y, verbose=False):
                return np.random.rand(size_x, size_y), {}, 0.1
            pt.aberrations = mock_aberrations
except ImportError:
    from unittest.mock import MagicMock
    print("Warning: pyTEMlib library not found. Using MagicMock.")
    pt = MagicMock()
    def mock_aberrations(tableau, size_x, size_y, verbose=False):
        return np.random.rand(size_x, size_y), {}, 0.1
    pt.aberrations = mock_aberrations

@pytest.fixture(scope="module", autouse=True)
def microscope_setup():
    """Setup and teardown for the fluence calibration workflow test."""
    print("\n--- Initializing Fluence Calibration Test Environment ---")
    start_res = start_server(mode="mock")
    print(f"Start Server: {start_res}")
    
    time.sleep(2)
    
    conn_res = connect_client(host="localhost")
    print(f"Connect Client: {conn_res}")
    
    yield
    
    print("\n--- Tearing Down Fluence Calibration Test Environment ---")
    close_microscope()

def test_fluence_calibration_workflow():
    print("\n--- Testing Fluence Calibration Workflow ---")
    
    cmds = discover_commands('AS')
    print(f"Discovered AS commands: {cmds}")
    assert "set_beam_current" in cmds
    assert "tune_C1A1" in cmds
    assert "get_atom_count" in cmds
    
    ceos_info = get_ceos_info()
    print(f"Ceos Info: {ceos_info}")
    assert "CEOS" in ceos_info
    
    cal_res = calibrate_screen_current()
    print(f"Calibration: {cal_res}")
    assert "calibrated" in cal_res.lower()
    
    beam_current = 100.0
    set_res = set_beam_current(beam_current)
    print(f"Set beam current: {set_res}")
    assert f"{beam_current}" in set_res
    
    img_res = capture_image(detector="HAADF")
    print(f"Capture image: {img_res}")
    assert ".npy" in img_res
    
    atom_res = get_atom_count()
    print(f"Atom count: {atom_res}")
    assert "Current atom count" in atom_res
    
    # Fluence Calibration Loop (Experiment)
    print("\n--- Running Fluence Calibration Loop (1 iteration) ---")
    current_vals = [10.0, 30.0]
    probes = []
    ab_list = []
    
    for current in current_vals:
        print(f"Processing current: {current} pA")
        
        set_beam_current(current)
        
        tune_C1A1()
        
        aberrations = acquire_tableau(tab_type="Fast", angle=18)
        print(f"Acquired aberrations, type: {type(aberrations)}")
        assert isinstance(aberrations, dict)
        
        ab_list.append(aberrations)
        
        probe, A_k, chi = pt.aberrations(aberrations, 128, 128, verbose=True)

        probes.append(probe)
        
        break
        
    profiles = [np.sum(p, axis=0) for p in probes]
    print(f"Generated {len(profiles)} profiles")
    assert len(profiles) == 1
    
    print("Fluence calibration workflow test passed!")

if __name__ == "__main__":
    pytest.main([__file__])
