import torch
from smolagents import CodeAgent, TransformersModel, DuckDuckGoSearchTool
from app.tools.microscopy import TOOLS
from app.utils.helpers import get_total_ram_gb

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
            additional_authorized_imports=[
                "app.tools.microscopy", "app.config", 
                "numpy", "time", "os", "scipy", "matplotlib", "skimage"
            ],
            instructions="""
            You are an expert microscopy AI assistant. 
            You can control the microscope by starting the server, connecting the client, and then using tools to:
            - Adjust magnification and capture images.
            - Move the stage and check status.
            - Control the electron beam (blank/unblank, place beam).
            - Calibrate and set screen current.
            
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
            
            Available servers: MicroscopeServer.Central, MicroscopeServer.AS, MicroscopeServer.Ceos.
            """,
            stream_outputs=True
        )

    def chat(self, query: str) -> str:
        """
        Process user input and return a response.
        """
        response = self.agent.run(query)
        return response
