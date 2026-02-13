from typing import List, Dict, Any, Optional, Union, Callable
from pydantic import BaseModel, Field, validator
import time
import numpy as np

class ExperimentAction(BaseModel):
    """
    Serializes tool calls for reproducibility.
    """
    name: str = Field(..., description="Name of the tool/function to call (e.g., 'adjust_magnification')")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")
    
class ExperimentConstraint(BaseModel):
    """
    Safety gate: prevents hardware damage by enforcing bounds before execution.
    """
    parameter: str = Field(..., description="The parameter to check (e.g., 'screen_current')")
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    target_value: Optional[float] = None
    
    def check(self, current_value: float) -> bool:
        if self.min_value is not None and current_value < self.min_value:
            return False
        if self.max_value is not None and current_value > self.max_value:
            return False
        if self.target_value is not None and current_value != self.target_value:
            return False
        return True

class RewardMetric(BaseModel):
    """
    Quantifies success; central bottleneck for information-efficient loops.
    """
    metric_type: str = Field(..., description="Type of metric (e.g., 'image_entropy', 'target_value')")
    target: Optional[str] = Field(None, description="What to measure (e.g., 'image', 'stage_position')")
    params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters for the metric")
    def evaluate(self, result: Any) -> float:
        if self.metric_type == "image_entropy":
            if isinstance(result, np.ndarray):
                hist, _ = np.histogram(result.flatten(), bins=256, range=(0, 256))
                prob = hist / result.size
                prob = prob[prob > 0]
                return -np.sum(prob * np.log2(prob))
            return 0.0
        
        elif self.metric_type == "value_match":
            target_val = self.params.get("target_value")
            if result == target_val:
                return 1.0
            return 0.0
            
        return 0.0

class ExperimentFootprint(BaseModel):
    """
    Compels the agent to compile a hypothesis into an executable plan.
    """
    id: str = Field(..., description="Unique ID for this experiment")
    description: str = Field("", description="Human-readable description of the hypothesis")
    actions: List[ExperimentAction] = Field(..., description="Sequence of actions to execute")
    constraints: List[ExperimentConstraint] = Field(default_factory=list, description="Safety constraints")
    observables: List[str] = Field(default_factory=list, description="Keys expected in the output (e.g. 'image')")
    reward: Optional[RewardMetric] = Field(None, description="How to evaluate the result")

class ExperimentExecutor:
    """
    Driver for compiling abstract footprints into hardware API calls.
    """
    def __init__(self, tool_map: Dict[str, Callable]):
        self.tools = tool_map
        
    def validate_constraints(self, footprint: ExperimentFootprint, current_state: Dict[str, Any]) -> List[str]:
        """
        Final safety check before hardware interaction.
        """
        violations = []
        for constraint in footprint.constraints:
            if constraint.parameter in current_state:
                val = current_state[constraint.parameter]
                if not constraint.check(val):
                    violations.append(f"Constraint failed for {constraint.parameter}: value {val} outside bounds.")
        return violations

    def execute(self, footprint: ExperimentFootprint) -> Dict[str, Any]:
        results = {
            "experiment_id": footprint.id,
            "log": [],
            "data": {},
            "reward": 0.0,
            "success": True
        }
        
        # Pre-check state to avoid wasting expensive beam time
        
        # Sequential execution; failure early-aborts to prevent state corruption
        for action in footprint.actions:
            if action.name not in self.tools:
                results["log"].append(f"ERROR: Tool {action.name} not found.")
                results["success"] = False
                break
            
            try:
                tool_func = self.tools[action.name]
                output = tool_func(**action.params)
                
                results["log"].append(f"Action {action.name} executed. Output length: {len(str(output))}")
                
                # Crude mapping for demo
                results["data"]["last_output"] = output
                
            except Exception as e:
                results["log"].append(f"ERROR executing {action.name}: {e}")
                results["success"] = False
                break
                
        # Reward calculation loop
        if footprint.reward and results["success"]:
            # Round-trip needed because file-based tools return paths not raw buffers
            last_out = results["data"].get("last_output", "")
            if isinstance(last_out, str) and ".npy" in last_out and "saved to" in last_out:
                try:
                    path = last_out.split("saved to ")[1].split(" ")[0].strip()
                    data = np.load(path)
                    reward_val = footprint.reward.evaluate(data)
                    results["reward"] = reward_val
                except:
                    results["log"].append("Could not load image for reward calculation.")
            elif isinstance(last_out, (int, float, np.number)):
                 reward_val = footprint.reward.evaluate(last_out)
                 results["reward"] = reward_val
                 
        return results
