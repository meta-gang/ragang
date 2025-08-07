import json
import os
from .llm_adapter import BaseLLMAdapter, LocalLLMAdapter, OpenAIAdapter, GeminiAdapter
from .embedding_adapter import BaseEmbeddingAdapter, LocalEmbeddingAdapter, OpenAIEmbeddingAdapter, GeminiEmbeddingAdapter

def create_llm_adapter(llm_config: dict) -> BaseLLMAdapter:
    """
    Creates an appropriate LLM adapter instance based on the LLM configuration (dict).

    Args:
        llm_config (dict): A dictionary containing 'provider' and 'config' keys.

    Returns:
        BaseLLMAdapter: The created LLM adapter instance.
    """
    # 1. Get the provider name to determine which LLM to use.
    provider = llm_config.get("provider")
    # 2. Get the specific configuration parameters required for instantiation.
    config_params = llm_config.get("config", {})

    # 3. Branch based on the provider value to create an instance of the correct class.
    if provider == "openai":
        # Unpack the config_params dictionary as keyword arguments for the OpenAIAdapter class.
        return OpenAIAdapter(**config_params)
    elif provider == "gemini":
        return GeminiAdapter(**config_params)
    elif provider == "local":
        return LocalLLMAdapter(**config_params)
    else:
        # If the provider is not supported, raise an error.
        raise ValueError(f"Unknown LLM provider: {provider}")

def create_embedding_adapter(embedding_config: dict) -> BaseEmbeddingAdapter:
    """
    Creates an appropriate embedding adapter instance based on the embedding configuration (dict).

    Args:
        embedding_config (dict): A dictionary containing 'provider' and 'config' keys.

    Returns:
        BaseEmbeddingAdapter: The created embedding adapter instance.
    """
    # 1. Get the provider name to determine which embedding model to use.
    provider = embedding_config.get("provider")
    # 2. Get the specific configuration parameters required for instantiation.
    config_params = embedding_config.get("config", {})

    # 3. Branch based on the provider value to create an instance of the correct class.
    if provider == "openai":
        return OpenAIEmbeddingAdapter(**config_params)
    elif provider == "gemini":
        return GeminiEmbeddingAdapter(**config_params)
    elif provider == "local":
        return LocalEmbeddingAdapter(**config_params)
    else:
        # If the provider is not supported, raise an error.
        raise ValueError(f"Unknown Embedding provider: {provider}")

def initialize_adapters_from_config(config_path: str = None) -> tuple[BaseLLMAdapter, BaseEmbeddingAdapter]:
    """
    Initializes LLM and embedding adapter instances from a JSON configuration file path.

    Args:
        config_path (str): The path to the JSON configuration file.

    Returns:
        tuple[BaseLLMAdapter, BaseEmbeddingAdapter]: A tuple containing (llm_adapter, embedding_adapter).
    """
    # 1. Read the JSON file and parse it into a Python dictionary.
    if config_path is None:
        jsonfile_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(jsonfile_dir, "..", "uploaded", "api_config.json")
        config_path = os.path.normpath(config_path)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"API Configuration file not found at {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. Extract the LLM and embedding settings separately.
    llm_settings = config.get("llm")
    embedding_settings = config.get("embedding")

    if not llm_settings or not embedding_settings:
        raise ValueError("Configuration file must contain 'llm' and 'embedding' sections.")

    # 3. Call the factory functions defined above to create the instances.
    llm_adapter = create_llm_adapter(llm_settings)
    embedding_adapter = create_embedding_adapter(embedding_settings)

    # 4. Return the two created instances as a tuple.
    return llm_adapter, embedding_adapter
