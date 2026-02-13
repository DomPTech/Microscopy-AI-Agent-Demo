import pytest
import time
import sys
import os
from app.tools.microscopy import submit_experiment, start_server, connect_client, close_microscope

# Ensure we are in the right directory context
sys.path.append(os.getcwd())

@pytest.fixture(scope="module")
def setup_microscope():
    """
    Fixture to start mock servers before tests and shut them down after.
    """
    print("Starting mock servers...")
    status = start_server(mode="mock")
    print(status)
    
    # Give servers time to spin up
    time.sleep(5)
    
    print("Connecting client...")
    conn_status = connect_client()
    print(conn_status)
    
    yield
    
    print("Closing microscope...")
    close_microscope()

def test_submit_valid_experiment(setup_microscope):
    """
    Test submitting a valid experiment with actions, constraints, and reward.
    """
    experiment = {
        "id": "test_exp_pytest_01",
        "description": "Test experiment with one action and entropy reward",
        "actions": [
            {
                "name": "adjust_magnification", 
                "params": {"amount": 5000}
            },
            {
                "name": "capture_image", 
                "params": {"detector": "HAADF"}
            }
        ],
        "constraints": [
            {
                "parameter": "screen_current",
                "max_value": 200.0 
            }
        ],
        "observables": ["image"],
        "reward": {
            "metric_type": "image_entropy"
        }
    }
    
    result_str = submit_experiment(experiment)
    print(f"Result: {result_str}")
    
    # Check for success indicators in the string output
    assert "Experiment 'test_exp_pytest_01' completed." in result_str
    assert "Success: True" in result_str
    assert "Reward:" in result_str
    # Check that logs indicate actions were executed
    assert "Action adjust_magnification executed" in result_str
    assert "Action capture_image executed" in result_str

def test_experiment_constraint_violation(setup_microscope):
    """
    Test that an experiment is rejected if constraints are violated.
    """
    # In our mock, screen_current is hardcoded to 100.0 in submit_experiment validation
    # So we set max_value < 100 to trigger failure
    experiment = {
        "id": "test_exp_fail_01",
        "description": "Should fail due to constraints",
        "actions": [],
        "constraints": [
            {
                "parameter": "screen_current",
                "max_value": 50.0 
            }
        ],
        "observables": [],
    }
    
    result_str = submit_experiment(experiment)
    assert "Experiment rejected due to constraints" in result_str
