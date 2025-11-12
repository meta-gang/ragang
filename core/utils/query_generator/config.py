import os

# Data IO
DATA_PATH = "./core/utils/query_generator/my_pdfs"
OUTPUT_PATH = "./datas/queries"


# LLM call
LLM_MODEL = "gpt-5-mini"
API_KEY = os.environ.get("OPENAI_API_KEY", "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")
MAX_WORKERS = 10
