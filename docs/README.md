# RAGANG Documentation Index

Welcome to the comprehensive documentation repository for **RAGANG** (*Ground-Truth-Free RAG Evaluation and Diagnosis Framework*).

---

## 🏛️ Architecture & System Design
- [Architecture Overview](architecture/overview.md) — Core engine design, FlowEngine, module contracts, container topologies, and execution lifecycle.
- [Graph & Cycle Execution Tracing](graph-rag/execution-trace.md) — Lineage recording, parent execution tracking, revisit counters, and bounded loop execution.

---

## 📊 Evaluation Contracts & Methodologies
- [Evaluation Contract](evaluation/EVALUATION.md) — Formal definitions of `Evaluated`, `Not Evaluated`, and `Invalid` states; safe evaluator provenance.
- [Metric Catalog](evaluation/metrics.md) — Built-in retriever, generator, and end-to-end metrics, parameters, and interpretation constraints.
- [Counterfactual Evaluation Guide](evaluation/counterfactual.md) — Deterministic context perturbation probes (distractor, conflict, noise, dropout, shuffle).
- [Research Alignment](evaluation/research-alignment.md) — Gold-free evaluation paradigms, academic citations, and grounding principles.

---

## 🔬 Research & Benchmarking
- [Benchmark Protocol](research/benchmark_protocol.md) — Standards for ground-truth-free benchmarking, configuration fingerprints, and reporting rules.
- [Experiment Design Guide](research/experiment_design.md) — Controlled experiment methodologies for linear, branching, retry, and cyclic pipelines.
- [Limitations & Scope Definition](research/limitations.md) — Explicit boundaries: no KG quality scoring, no causal guarantees, no fake overall scores.
- [Research Roadmap](research/roadmap.md) — Active milestones and future research directions for 2026–2027.

---

## ✅ Validation & Acceptance Reports
- [표시 단순화·복합 그래프·첫 사용 안내 검증 (2026-10-26)](validation/USABILITY_GRAPH_ONBOARDING_2026.md) — 최신 사용자 흐름·그래프 결함 수정·오프라인 검증 범위.
- [페르소나 기반 신뢰성 개선 (2026-10-25)](validation/PERSONA_HARDENING_2026.md) — 다섯 사용자 시나리오와 재현 문제·해결·한계.

아래는 각 문서의 작성 시점에 해당하는 과거 기록입니다. 현재 환경의 실제 모델·DB 연동 검증 여부는 최신 보고서를 기준으로 확인하세요.

- [Final Validation Report](validation/FINAL_VALIDATION_REPORT.md) — Comprehensive acceptance matrix, live/offline test evidence, and release readiness.
- [Browser Acceptance Validation](validation/BROWSER_ACCEPTANCE.md) — Full 17-item browser acceptance checklist verified in real Chrome/Chromium.
- [Live Acceptance Report](validation/LIVE_ACCEPTANCE.md) — Integration testing with live Ollama LLM and Milvus vector database.
- [Validation Audit](validation/VALIDATION_AUDIT.md) — Regression harness audit comparing `origin/main` vs `origin/validation`.

---

## 🔒 Security & Provenance
- [Credential Exposure Audit](security/CREDENTIAL_EXPOSURE.md) — Sanitization audit, pattern masking, and local credential triage.
- [Dependency Risk Assessment](security/DEPENDENCY_RISK.md) — Python and npm package vulnerability assessment and operational triage.

---

## 🛠️ Development & Operations
- [Development Guide](development/DEVELOPMENT.md) — Local environment setup, testing procedures, metric checklists, and coding conventions.
- [Release Policy](development/RELEASE.md) — Reproducible wheel packaging, frontend bundle synchronization, and release criteria.
- [2026 Modernization Summary](development/MODERNIZATION_2026.md) — Key modernization improvements and engineering changes.
- [Frontend Provenance](development/FRONTEND_PROVENANCE.md) — Source tracking, exact commit SHA, and deterministic asset build verification.
- [Generated Asset Inventory](development/GENERATED_ASSET_INVENTORY.md) — Inventory of tracked production bundles and orphan artifacts.
- [Interactive Demo Guide](demo/DEMO.md) — Live Ollama/Milvus and offline local demo workflows.
- [Issue Tracker Archive](development/ISSUE.md) & [Code Review Log](development/REVIEW.md) — Historical resolution logs.
