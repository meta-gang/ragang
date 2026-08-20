# Dependency Risk & Security Audit

기준일: 2026-08-20

## Overview & Policy

RAGANG implements strict security and dependency hygiene across both Python backend and TypeScript/React frontend environments:
- Zero live paid APIs required for testing and local execution.
- Deterministic fake adapters for regression suites.
- No plaintext credentials, tokens, or personal paths recorded in logs, errors, or serialized traces.
- Frontend dependency vulnerability tracking and classification.

---

## Python Backend Dependencies

| Package | Minimum Version | Purpose | Security Notes |
| --- | --- | --- | --- |
| `httpx` / `httpcore` | `>=0.28.1` / `>=1.0.0` | Async HTTP client for adapters | Safe timeouts, sanitized exception messages |
| `numpy` | `>=2.3.2` | Numerical computing | Finite float validation, NaN/Inf rejection |
| `scikit-learn` / `scipy` | `>=1.7.1` / `>=1.16.0` | Statistical & vector metrics | Standard metric calculations |
| `pymilvus` | `>=2.6.0` | Milvus vector DB integration | Verified readiness retry logic |
| `pymupdf` | `>=1.26.6` | Document ingestion parsing | Sandboxed parsing |
| `websockets` | `>=15.0.1` | Local dashboard IPC | Loopback-only binding (`127.0.0.1`) |

Backend test suite runs offline without external network dependencies.

---

## Frontend Dependency Risk Assessment (`RAG-APP-UI`)

### Audit Summary
- `npm audit`: 13 package nodes (7 High, 6 Moderate, 0 Critical)
- Underlying Unique Advisories: 8
- P0/P1 Critical Exploits: **0**
- P2 Accepted Operational Risks: **8**
- Security Status: **ACCEPTED RISK (Build-Time / Development-Only Isolation)**

### Detailed Advisory Classification

| Package / Advisory | Severity | Dependency Path | Context & Exposure | Risk Level | Mitigation & Recommendation |
| --- | --- | --- | --- | --- | --- |
| `minimatch` [GHSA-3ppc-4f35-3m26](https://github.com/advisories/GHSA-3ppc-4f35-3m26) | High | `@typescript-eslint/parser` → `minimatch` | Development / Linting only; not bundled into browser runtime | P2 (Accepted) | Upgrade to ESLint 8 / TypeScript-ESLint 8 in dedicated maintenance branch. |
| `minimatch` [GHSA-7r86-cg39-jmmj](https://github.com/advisories/GHSA-7r86-cg39-jmmj) | High | `@typescript-eslint/parser` → `minimatch` | Development / Linting only; not bundled | P2 (Accepted) | Same as above. |
| `minimatch` [GHSA-23c5-xmqv-rm74](https://github.com/advisories/GHSA-23c5-xmqv-rm74) | High | `@typescript-eslint/parser` → `minimatch` | Development / Linting only; not bundled | P2 (Accepted) | Same as above. |
| `react-router` [GHSA-wrjc-x8rr-h8h6](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6) | Moderate | `react-router-dom@6.30.6` | Runtime static client hash routing (`#/dashboard`, `#/test`, `#/run-queries`). No untrusted dynamic URL targets. | P2 (Accepted) | Keep HashRouter; plan React Router 7 migration with browser verification. |
| `react-router` [GHSA-337j-9hxr-rhxg](https://github.com/advisories/GHSA-337j-9hxr-rhxg) | Moderate | `react-router-dom@6.30.6` | SSR hydration error deserialization. RAGANG uses client-only static SPA (no SSR). Unreachable. | P2 (Accepted) | Safe in client-side SPA bundle. |
| `serialize-javascript` [GHSA-5c6j-r48x-rmvq](https://github.com/advisories/GHSA-5c6j-r48x-rmvq) | High | `css-minimizer-webpack-plugin@5.0.1` | Build-time CSS minimization only; processes trusted source files. | P2 (Accepted) | Major plugin upgrade scheduled for compatibility track. |
| `serialize-javascript` [GHSA-qj8w-gfj5-8c6v](https://github.com/advisories/GHSA-qj8w-gfj5-8c6v) | Moderate | `css-minimizer-webpack-plugin@5.0.1` | Build-time CSS minimization only | P2 (Accepted) | Same as above. |
| `uuid` [GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq) | Moderate | `webpack-dev-server@5.2.6` → `sockjs` | Dev-server only; not packaged in production web bundle. | P2 (Accepted) | Isolated from production bundle. |

---

## Security Practices for Contributors

1. **Never commit secrets**: API keys, tokens, personal paths, or vector store dumps must never be staged.
2. **Deterministic provenance**: Metric and run metadata record only public config names and module implementations.
3. **Local Loopback Protocol**: Dashboard and WebSocket servers bind to `127.0.0.1` by default and treat all incoming filenames as untrusted.
