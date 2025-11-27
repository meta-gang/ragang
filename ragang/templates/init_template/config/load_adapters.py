import os

from ragang.adapters.milvus_adapter import MilvusAdapter
from ragang.adapters.embedding_adapter import GeminiEmbeddingAdapter, BaseEmbeddingAdapter
from ragang.adapters.llm_adapter import GeminiAdapter, BaseLLMAdapter

__all__ = ['load']

from ragang.core.utils.ansi_styler import ANSIStyler


def __init_milvus(collection_name: str = 'test', dim: int = 768) -> MilvusAdapter:
    adapter = MilvusAdapter(config_path='./config/vector_db.json')
    if adapter.has_collection(collection_name):
        adapter.drop_collection(collection_name)
        adapter.create_collection(collection_name, dim)
    else:
        adapter.create_collection(collection_name, dim)

    return adapter


def __init_embedding(api_key: str) -> BaseEmbeddingAdapter:
    adapter = GeminiEmbeddingAdapter(api_key)
    return adapter


def __init_llm(api_key: str) -> BaseLLMAdapter:
    adapter = GeminiAdapter(api_key=api_key, model_name='gemini-2.5-flash')
    return adapter


def __split_to_chunk(doc: str, size: int) -> list[str]:
    return [doc[i:i + size] for i in range(0, len(doc), size)]


def load(api_key: str) -> dict:
    collection_name = 'test'

    vec_db = __init_milvus(collection_name)
    emb = __init_embedding(api_key)
    llm = __init_llm(api_key)

    doc = ''
    docs_dir = './datas/docs'
    for fname in os.listdir(docs_dir):
        if fname.endswith('.txt'):
            print(f"Adding document {fname} into vector db...")
            with open(os.path.join(docs_dir, fname), 'r', encoding='utf-8') as f:
                doc += f.read() + '\n'
    chunk = __split_to_chunk(doc, 500)

    if len((emb_vectors := emb.create_embeddings(chunk))) > 0:
        vec_db.insert(collection_name, [emb_vectors.tolist(), chunk])
        vec_db.create_index(collection_name)
    else:
        print(ANSIStyler.style("something went wrong", fore_color='light-magenta', font_style='bold'))

    return {
        'vec': vec_db,
        'emb': emb,
        'llm': llm
    }
