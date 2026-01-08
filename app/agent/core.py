from smolagents import CodeAgent, WebSearchTool, TransformersModel
from transformers import BitsAndBytesConfig

class Agent:
    def __init__(self):
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype="bfloat16"
        )

        self.model = model = TransformersModel(
            model_id="Qwen/Qwen2.5-7B-Instruct",
            max_new_tokens=4096,
            device_map="auto",
            model_kwargs={"quantization_config": quant_config}
        )
        self.agent = CodeAgent(tools=[WebSearchTool()], model=model, stream_outputs=True)

    def chat(self, query: str) -> str:
        """
        Process user input and return a response.
        """
        self.agent.run(query)
        return "This is a dummy agent response."
