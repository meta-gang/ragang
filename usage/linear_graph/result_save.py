import json
import os

class MetricVisualizer:
    def __init__(self, rag_container):
        self.storage = rag_container.storage
        self.records = self._extract_metrics_records()

    def _extract_metrics_records(self):
        records = []
        for q_id, state in self.storage.history.items():
            tot_x_time: float = 0
            row = {
                "qid": q_id,
                "query": state.query,
                "answer": state.answer,
                "e2e_score": str(state.performance),
                "total_time_ms": 0.0,
                "metrics": {}
            }

            for mid, packets in state.snapshots.items():
                module_metrics = []
                for packet in packets:
                    perf_obj = packet.performance
                    x_time = packet.x_time * 1000
                    tot_x_time += x_time
                    module_metrics.append({
                        "performance": str(perf_obj),
                        "metric": perf_obj.metric,
                        "score": perf_obj.score,
                        "time_ms": round(x_time, 4)
                    })
                row["metrics"][mid] = module_metrics

            row["total_time_ms"] = round(tot_x_time, 4)
            records.append(row)
        return records

    def save_to_json(self, filename=None):
        if filename is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(base_dir, "..", "..", "frontend", "public", "metric_summary.json")
            filename = os.path.normpath(filename)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2, ensure_ascii=False)
        print(f"Metric summary saved to '{filename}'.")
