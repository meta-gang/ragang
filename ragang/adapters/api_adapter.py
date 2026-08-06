import json
import os
from .llm_adapter import BaseLLMAdapter, OllamaLocalLLMAdapter, OpenAIAdapter, GeminiAdapter
from .embedding_adapter import BaseEmbeddingAdapter, LocalEmbeddingAdapter, OpenAIEmbeddingAdapter, \
    GeminiEmbeddingAdapter


class api_adapter:
    def __init__(self, config_path: str = None):
        self.llm_adapter = None
        self.embedding_adapter = None
        self.config_path = config_path

    def create_adapters(self) -> tuple[BaseLLMAdapter, BaseEmbeddingAdapter]:
        if self.config_path is None:
            jsonfile_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(jsonfile_dir, "..", "uploaded", "api_config.json")
            self.config_path = os.path.normpath(self.config_path)
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"API Configuration file not found at {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        llm_settings = config.get("llm")
        embedding_settings = config.get("embedding")

        if not llm_settings or not embedding_settings:
            raise ValueError("Configuration file must contain 'llm' and 'embedding' sections.")

        llm_adapter = self.create_llm_adapter(llm_settings)
        embedding_adapter = self.create_embedding_adapter(embedding_settings)

        return llm_adapter, embedding_adapter

    def create_llm_adapter(self, llm_config: dict) -> BaseLLMAdapter:
        # 1. Get the provider name to determine which LLM to use.
        provider = llm_config.get("provider")
        # 2. Get the specific configuration parameters required for instantiation.
        config_params = llm_config.get("config", {})

        # 3. Branch based on the provider value to create an instance of the correct class.
        if provider == "OpenAI":
            return OpenAIAdapter(**config_params)
        elif provider == "Gemini":
            return GeminiAdapter(**config_params)
        elif provider == "Local":
            return OllamaLocalLLMAdapter(**config_params)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def create_embedding_adapter(self, embedding_config: dict) -> BaseEmbeddingAdapter:
        # 1. Get the provider name to determine which embedding model to use.
        provider = embedding_config.get("provider")
        # 2. Get the specific configuration parameters required for instantiation.
        config_params = embedding_config.get("config", {})

        # 3. Branch based on the provider value to create an instance of the correct class.
        if provider == "OpenAI":
            return OpenAIEmbeddingAdapter(**config_params)
        elif provider == "Gemini":
            return GeminiEmbeddingAdapter(**config_params)
        elif provider == "Local":
            return LocalEmbeddingAdapter(**config_params)
        else:
            raise ValueError(f"Unknown Embedding provider: {provider}")
