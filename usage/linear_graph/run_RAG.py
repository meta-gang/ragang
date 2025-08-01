from build_RAG import buildRag
from container import RAGContainer

class RunRag:
    def __init__(self, rag: RAGContainer):
        self.rag = rag
    
    def run(self):
        return 0