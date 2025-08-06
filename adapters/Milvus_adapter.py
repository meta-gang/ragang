from abc import ABC, abstractmethod
from pymilvus import connections, utility, Collection, CollectionSchema, FieldSchema, DataType

class BaseMilvusAdapter(ABC):
    """Abstract base class for Milvus adapters."""
    def __init__(self, host: str = "localhost", port: str = "19530", alias: str = "default"):
        self.host = host
        self.port = port
        self.alias = alias

    @abstractmethod
    def connect(self):
        """Connects to the Milvus server."""
        pass

    @abstractmethod
    def create_collection(self, collection_name: str, dim: int):
        """Creates a new collection in Milvus."""
        pass

    @abstractmethod
    def insert(self, collection_name: str, data: list):
        """Inserts data into a collection."""
        pass

    @abstractmethod
    def retrieve(self, collection_name: str, query_vectors: list, top_k: int):
        """Retrieves similar vectors from a collection."""
        pass

class MilvusAdapter(BaseMilvusAdapter):
    """Adapter for interacting with a Milvus vector database."""

    def __init__(self, host: str = "localhost", port: str = "19530", alias: str = "default"):
        super().__init__(host, port, alias)
        self.connect()

    def connect(self):
        """Connects to the Milvus server."""
        try:
            connections.connect(alias=self.alias, host=self.host, port=self.port)
            print(f"Successfully connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to connect to Milvus: {e}")

    def has_collection(self, collection_name: str):
        """Checks if a collection exists in Milvus."""
        try:
            return utility.has_collection(collection_name, using=self.alias)
        except Exception as e:
            print(f"Failed to check for collection {collection_name}: {e}")
            return False

    def create_collection(self, collection_name: str, dim: int):
        """Creates a new collection in Milvus if it doesn't exist."""
        if self.has_collection(collection_name):
            print(f"Collection {collection_name} already exists.")
            return Collection(collection_name, using=self.alias)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535)
        ]
        schema = CollectionSchema(fields, description="Collection for text embeddings")
        try:
            collection = Collection(collection_name, schema, using=self.alias)
            print(f"Successfully created collection: {collection_name}")
            return collection
        except Exception as e:
            print(f"Failed to create collection {collection_name}: {e}")
            return None
        
    def drop_collection(self, collection_name: str):
        """Drops the specified collection from Milvus."""
        try:
            if self.has_collection(collection_name):
                utility.drop_collection(collection_name, using=self.alias)
                print(f"Successfully dropped collection: {collection_name}")
            else:
                print(f"Collection {collection_name} does not exist.")
        except Exception as e:
            print(f"Failed to drop collection {collection_name}: {e}")

    def insert(self, collection_name: str, data: list):
        """
        Inserts data into a collection.
        The 'data' parameter should be a list of lists, where each inner list corresponds to a field.
        For this schema, it should be [list_of_embeddings, list_of_texts].
        """
        try:
            collection = Collection(collection_name, using=self.alias)
            mr = collection.insert(data)
            print(f"Successfully inserted {len(mr.primary_keys)} entities into {collection_name}.")
            return mr
        except Exception as e:
            print(f"Failed to insert data into {collection_name}: {e}")
            return None
        
    def create_index(self, collection_name: str):
        try:
            collection = Collection(collection_name, using=self.alias)
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            print(f"Index created for collection {collection_name}")
        except Exception as e:
            print(f"Failed to create index for {collection_name}: {e}")


    def retrieve(self, collection_name: str, query_vectors: list, top_k: int):
        """
        Retrieve similar texts from a collection based on query vectors.
        Returns a list of lists of retrieved texts, where each inner list corresponds to a query vector.
        """
        try:
            collection = Collection(collection_name, using=self.alias)
            collection.load()
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            results = collection.search(
                data=query_vectors,
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=None,
                output_fields=["text"]
            )
            
            retrieved_texts_per_query = []
            for hits in results:
                texts = [hit.entity.get('text') for hit in hits]
                retrieved_texts_per_query.append(texts)
            return retrieved_texts_per_query
        except Exception as e:
            print(f"Failed to retrieve data from {collection_name}: {e}")
            return None

if __name__ == '__main__':
    # Example usage
    milvus_adapter = MilvusAdapter()

    collection_name = "my_collection"
    
    # Drop collection if it exists for a clean run
    if milvus_adapter.has_collection(collection_name):
        milvus_adapter.drop_collection(collection_name)

    # Create a collection
    dimension = 8
    milvus_adapter.create_collection(collection_name, dimension)

    # Insert data
    import numpy as np
    vectors = np.random.rand(10, dimension).tolist()
    texts = [f"This is text for vector {i}" for i in range(10)]
    milvus_adapter.insert(collection_name, [vectors, texts])
    milvus_adapter.create_index(collection_name)


    # Retrieve data
    query_vectors = np.random.rand(1, dimension).tolist()
    results = milvus_adapter.retrieve(collection_name, query_vectors, top_k=3)
    print("Query results:")
    print(results)