import os

# Query Generation
MAX_NUM_QUERIES = 400
CHUNK_SIZE = 5
CHUNK_OVERLAP = 1
NUM_QUERIES_PER_PAGE = 1


# LLM call
LLM_PROVIDER = "ollama"
OLLAMA_HOST = os.environ.get("RAGANG_OLLAMA_HOST", "127.0.0.1:11434")
LLM_MODEL = os.environ.get("RAGANG_LLM_MODEL", "qwen2.5:3b")
# prefer the environment variable so the key never has to be written into this file
API_KEY = os.environ.get("RAGANG_API_KEY", "")
MAX_WORKERS = 20
MAX_CONTEXT_LENGTH = 8000
