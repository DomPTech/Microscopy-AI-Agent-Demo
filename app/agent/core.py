import torch
from smolagents import CodeAgent, TransformersModel, DuckDuckGoSearchTool
from app.tools.microscopy import adjust_magnification, capture_image, close_microscope
from app.utils.helpers import get_total_ram_gb

class Agent:
    def __init__(self, model_id: str = "Auto"):
        ram_gb = get_total_ram_gb()
        load_in_8bit = False

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

        self.model = TransformersModel(
            model_id=model_id,
            max_new_tokens=1024,
            device_map="mps" if torch.backends.mps.is_available() else "auto",
            torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.float32,
            trust_remote_code=True,
            model_kwargs={
                "low_cpu_mem_usage": True,
                "use_cache": True,
                "load_in_8bit": load_in_8bit,
            }
        )
        # Full tool suite for the microscopy agent
        self.agent = CodeAgent(
            tools=[
                DuckDuckGoSearchTool(), 
                adjust_magnification,
                capture_image,
                close_microscope
            ], 
            model=self.model, 
            stream_outputs=True
        )

    def chat(self, query: str) -> str:
        """
        Process user input and return a response.
        """
        response = self.agent.run(query)
        return response
