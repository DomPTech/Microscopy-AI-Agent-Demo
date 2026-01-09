import torch
from smolagents import CodeAgent, TransformersModel, DuckDuckGoSearchTool
from app.tools.microscopy import adjust_magnification, capture_image, close_microscope
from app.utils.helpers import get_total_ram_gb

class Agent:
    def __init__(self):
        ram_gb = get_total_ram_gb()
        
        # Select model based on RAM
        if ram_gb < 16:
            # Ultra-efficient for <16GB RAM (e.g. 8GB M-series)
            model_id = "Qwen/Qwen2.5-0.5B-Instruct"
            load_in_8bit = True if not torch.backends.mps.is_available() else False
        elif ram_gb > 70:
            model_id = "Qwen/Qwen3-32B-Instruct"
        else:
            # High-performance for 16GB+ RAM
            model_id = "Qwen/Qwen2.5-1.5B-Instruct" 
            load_in_8bit = False

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
