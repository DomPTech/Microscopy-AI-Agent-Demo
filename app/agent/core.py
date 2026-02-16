import sys
from pathlib import Path

# Ensure project root is on sys.path for reliable imports
_PROJECT_ROOT = None
for _parent in Path(__file__).resolve().parents:
    if (_parent / "pyproject.toml").exists():
        _PROJECT_ROOT = _parent
        break
if _PROJECT_ROOT is None:
    _PROJECT_ROOT = Path.cwd()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import torch
from smolagents import CodeAgent, TransformersModel, DuckDuckGoSearchTool, PlanningStep, ActionStep
from smolagents.agents import ActionOutput
from smolagents.memory import FinalAnswerStep
from smolagents.models import ChatMessageStreamDelta
from app.tools.microscopy import TOOLS, MicroscopeServer
from app.utils.helpers import get_total_ram_gb
from app.agent.supervised_executor import SupervisedExecutor
try:
    import pyTEMlib.probe_tools as pt
except ImportError:
    pt = None
import numpy as np
from app.tools import microscopy

class MicroscopeClientProxy:
    """Proxy to forward calls to the active global CLIENT instance."""
    def __getattr__(self, name):
        if microscopy.CLIENT is None:
             raise RuntimeError("Microscope client is not connected. Please call 'connect_client()' first.")
        return getattr(microscopy.CLIENT, name)

class Agent:
    def __init__(self, model_id: str = "Auto"):
        ram_gb = get_total_ram_gb()
        load_in_8bit = False
        low_cpu_mem_usage = True

        # Auto-select model based on available RAM
        if model_id == "Auto" or not model_id:
            if ram_gb < 16:
                model_id = "Qwen/Qwen2.5-0.5B-Instruct"
                # bitsandbytes 8-bit isn't stable on MPS yet
                load_in_8bit = False if torch.backends.mps.is_available() else True
            elif ram_gb > 48:
                # 14B fits comfortably under 50GB (approx 28GB in FP16)
                model_id = "Qwen/Qwen2.5-14B-Instruct" 
            else:
                model_id = "Qwen/Qwen2.5-7B-Instruct" # ~15GB

        if ram_gb > 16:
            low_cpu_mem_usage = False

        self.model = TransformersModel(
            model_id=model_id,
            max_new_tokens=1024,
            device_map="mps" if torch.backends.mps.is_available() else "auto",
            torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.float32,
            trust_remote_code=True,
            model_kwargs={
                "low_cpu_mem_usage": low_cpu_mem_usage,
                "use_cache": True,
                "load_in_8bit": load_in_8bit,
            }
        )
        # Full tool suite for the microscopy agent
        self.agent = CodeAgent(
            tools=TOOLS, 
            model=self.model, 
            planning_interval=5,
            step_callbacks={PlanningStep: self.interrupt_after_plan},
            executor=SupervisedExecutor(additional_authorized_imports=[
                "app.tools.microscopy", "app.config", 
                "numpy", "time", "os", "scipy", "matplotlib", "skimage"
            ]),
            instructions="""
            You are an expert microscopy AI assistant. 
            You can control the microscope by starting the server, connecting the client, and then using tools to:
            - Adjust magnification and capture images.
            - Move the stage and check status.
            - Control the electron beam (blank/unblank, place beam).
            - Calibrate and set screen current.
            - And more.

            You can also design structuered Experiments using submit_experiment.
            
            Default context & assumptions (use these unless the user specifies otherwise):
            - Always start servers and connect to the client when asked to do anything on the microscope.
            - If no server list is provided, start ALL servers: MicroscopeServer.Central, MicroscopeServer.AS, MicroscopeServer.Ceos.
            - After starting servers, wait 1 second, then connect the client using settings.
            - Use mode='mock' unless the user explicitly requests real hardware.
            
            Guidelines:
            1. Use 'app.config.settings' for configuration:
               - Import 'settings' from 'app.config'.
               - Use 'settings.server_host' and 'settings.server_port' for connections.
               - Use 'settings.autoscript_path' if needed for server startup.
            2. Reliability:
               - Always wait at least 1 second (`time.sleep(1)`) after starting servers before attempting to connect the client.
               - Use mode='mock' for simulations unless 'real' is explicitly requested.
            3. Housekeeping:
               - Always call 'close_microscope()' when the task is finished.
            4. Decide whether or not to construct structured Experiments or just execute tools quickly.
            
            Available servers: MicroscopeServer.Central, MicroscopeServer.AS, MicroscopeServer.Ceos.
            """,
            stream_outputs=True
        )

        # Preload common classes into the Python executor context
        try:
            self.agent.python_executor.send_variables({
                "MicroscopeServer": MicroscopeServer,
                "tem": MicroscopeClientProxy(),
                "pt": pt,
                "np": np
            })
        except Exception:
            # Non-fatal: some executors may not support variable injection
            pass

    def chat(self, query: str) -> str:
        """
        Process user input and return a response.
        """
        response = self.agent.run(query)
        return response

    def stream_chat(self, query: str):
        """
        Stream user input processing as a sequence of events.
        Yields dicts with keys: type ("delta"|"final") and content.
        """
        final_output = None
        for event in self.agent.run(query, stream=True):
            if isinstance(event, ChatMessageStreamDelta) and event.content:
                yield {"type": "delta", "content": event.content}
            elif isinstance(event, ActionOutput) and event.is_final_answer:
                final_output = event.output
            elif isinstance(event, FinalAnswerStep):
                final_output = event.output

        if final_output is not None:
            yield {"type": "final", "content": str(final_output)}

    def interrupt_after_plan(self, memory_step, agent):
        """
        An interrupt callback to stop the agent after the planning step.
        """
        if isinstance(memory_step, PlanningStep):
            while True:
                print("User choices: ")
                print("1. Approve plan")
                print("2. Modify plan")
                print("3. Reject plan and stop execution")
                choice = input("Enter your choice (1/2/3): ").strip()
                if choice == '1':
                    break
                elif choice == '2':
                    new_plan = input("Enter your modifications to the plan: ")
                    if new_plan.strip():
                        memory_step.plan = new_plan
                        print("Plan updated. Continuing execution.")
                    else:
                        print("No modifications entered. Continuing with original plan.")
                    break
                elif choice == '3':
                    print("Execution interrupted by user.")
                    raise KeyboardInterrupt("Execution interrupted by user during planning.")
                else:
                    print("Invalid choice. Please enter 1, 2, or 3.")
            return True
        return False