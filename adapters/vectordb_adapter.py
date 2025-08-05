from abc import ABC, abstractmethod
from typing import List, Dict, Any
import chromadb
from adapters.embedding_adapter import BaseEmbeddingAdapter
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

class BaseVectorDBAdapter(ABC):
    """Abstract base class for vector database adapters."""

    @abstractmethod
    def get_or_create_collection(self, name: str, embedding_dim: int):
        """Gets or creates a collection in the vector database."""
        pass

    @abstractmethod
    def add(self, collection_name: str, documents: List[str], metadatas: List[Dict[str, Any]] = None, ids: List[str] = None):
        """Adds documents to a collection."""
        pass

    @abstractmethod
    def query(self, collection_name: str, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        """Queries a collection for similar documents."""
        pass

class ChromaVectorDBAdapter(BaseVectorDBAdapter):
    """Adapter for ChromaDB."""

    def __init__(self, embedding_adapter: BaseEmbeddingAdapter, path: str = None):
        """
        Initializes the ChromaDB adapter.

        Args:
            embedding_adapter: An instance of a class that inherits from BaseEmbeddingAdapter.
            path: The path to the ChromaDB database directory. If None, an in-memory database is used.
        """
        if path:
            self.client = chromadb.PersistentClient(path=path)
        else:
            self.client = chromadb.Client()
        self.embedding_adapter = embedding_adapter

    def get_or_create_collection(self, name: str, embedding_dim: int = None):
        """Gets or creates a collection in ChromaDB."""
        return self.client.get_or_create_collection(name=name)

    def add(self, collection_name: str, documents: List[str], metadatas: List[Dict[str, Any]] = None, ids: List[str] = None):
        """
        Adds documents to a ChromaDB collection.

        Args:
            collection_name: The name of the collection.
            documents: A list of documents to add.
            metadatas: A list of metadata dictionaries corresponding to the documents.
            ids: A list of unique IDs for the documents.
        """
        collection = self.client.get_collection(name=collection_name)
        embeddings = self.embedding_adapter.create_embeddings(documents)
        collection.add(
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def query(self, collection_name: str, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        """
        Queries a ChromaDB collection for similar documents.

        Args:
            collection_name: The name of the collection.
            query_texts: A list of query texts.
            n_results: The number of results to return.

        Returns:
            A dictionary containing the query results.
        """
        collection = self.client.get_collection(name=collection_name)
        query_embeddings = self.embedding_adapter.create_embeddings(query_texts)
        return collection.query(
            query_embeddings=query_embeddings.tolist(),
            n_results=n_results
        )

class MilvusVectorDBAdapter(BaseVectorDBAdapter):
    """Adapter for Milvus DB."""

    def __init__(self, embedding_adapter: BaseEmbeddingAdapter, host: str = "localhost", port: str = "19530", alias: str = "default"):
        """
        Initializes the Milvus adapter.

        Args:
            embedding_adapter: An instance of a class that inherits from BaseEmbeddingAdapter.
            host: The host address of the Milvus server.
            port: The port of the Milvus server.
            alias: The connection alias to use.
        """
        self.embedding_adapter = embedding_adapter
        self.alias = alias
        connections.connect(alias=self.alias, host=host, port=port)

    def get_or_create_collection(self, name: str, embedding_dim: int):
        """
        Gets or creates a collection in Milvus.

        Args:
            name: The name of the collection.
            embedding_dim: The dimension of the embeddings.
        """
        if utility.has_collection(name, using=self.alias):
            return Collection(name, using=self.alias)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="document", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim)
        ]
        schema = CollectionSchema(fields, description=f"{name} collection")
        collection = Collection(name, schema, using=self.alias)
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        return collection

    def add(self, collection_name: str, documents: List[str], metadatas: List[Dict[str, Any]] = None, ids: List[str] = None):
        """
        Adds documents to a Milvus collection.

        Args:
            collection_name: The name of the collection.
            documents: A list of documents to add.
            metadatas: (Not used in this implementation)
            ids: (Not used in this implementation)
        """
        collection = Collection(collection_name, using=self.alias)
        embeddings = self.embedding_adapter.create_embeddings(documents)
        data = [documents, embeddings.tolist()]
        collection.insert(data)

    def query(self, collection_name: str, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        """
        Queries a Milvus collection for similar documents.

        Args:
            collection_name: The name of the collection.
            query_texts: A list of query texts.
            n_results: The number of results to return.

        Returns:
            A dictionary containing the query results.
        """
        collection = Collection(collection_name, using=self.alias)
        collection.load()
        query_embeddings = self.embedding_adapter.create_embeddings(query_texts)
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        results = collection.search(
            data=query_embeddings.tolist(),
            anns_field="embedding",
            param=search_params,
            limit=n_results,
            output_fields=["document"]
        )
        return results