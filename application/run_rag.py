from application.build_rag import buildRag
from container import RAGContainer
from application.result_save import MetricVisualizer
import os
import streamlit as st

class RunRag:
    def __init__(self, rag: RAGContainer):
        self.rag = rag
        self.query = []

    def get_query(self):
        query_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "uploaded", "queries.txt"))
        if not os.path.exists(query_path):
            raise FileNotFoundError(f"Query 파일을 찾을 수 없습니다: {query_path}")

        with open(query_path, "r", encoding="utf-8") as f:
            self.query = [line.strip() for line in f if line.strip()]

        return self.query

    def run(self):
        if not self.query:
            raise ValueError("Query가 비어 있습니다. get_query()를 먼저 호출하세요.")

        self.rag.invoke_batch(self.get_query())

        self.rag.print_eval()

        vis = MetricVisualizer(self.rag)
        vis.save_to_json()

        st.session_state["run_rag"] = True

        return self.rag.storage.history