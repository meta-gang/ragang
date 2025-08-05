from application.build_rag import buildRag
from container import RAGContainer
from application.result_save import MetricVisualizer
import os
import streamlit as st

class RunRag:
    def __init__(self, rag: RAGContainer):
        self.rag = rag
        self.query = []

    def get_query(self, query_path=None):
        if query_path is None:
            query_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploaded", "queries.txt"))
        if not os.path.exists(query_path):
            raise FileNotFoundError(f"Query 파일을 찾을 수 없습니다: {query_path}")

        with open(query_path, "r", encoding="utf-8") as f:
            self.query = [line.strip() for line in f if line.strip()]

        return self.query

    def run(self, save_path=None, query: list[str] = None, check_test = False):
        if query:
            self.query = query
        else:
            self.query = self.get_query()

        if check_test:
            if "test_num" not in st.session_state:
                st.session_state["test_num"] = 0
            self.rag.invoke(self.query[0], st.session_state["test_num"])
            st.session_state["test_num"] += 1
        else:
            self.rag.invoke_batch(self.query)

        self.rag.print_eval()

        vis = MetricVisualizer(self.rag)
        vis.save_to_json(save_path)

        if check_test:
            st.session_state["run_test_rag"] = True
        else:
            st.session_state["run_rag"] = True

        return self.rag.storage.history