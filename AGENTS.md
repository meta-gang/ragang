# RAGANG maintenance guide

## Project identity

RAGANG is a ground-truth-free RAG evaluation and diagnosis framework. Changes
must improve evaluation correctness, evaluator trust, failure diagnosis,
iteration speed, reproducibility, or the real dashboard workflow. Do not turn
the project into a generic observability platform or add metrics only for
feature count.

Optional reference- or gold-based metrics may coexist with the gold-free core,
but gold data must never become mandatory for running RAGANG, obtaining an
honest evaluation status, or using its diagnosis workflow.

## Architecture

- `ragang/core/bases/abstracts/` contains the flow engine and the module,
  metric, and container contracts.
- `ragang/core/bases/datas/` contains graph links and the serializable runtime
  state (`FlowStorage`, `State`, `Packet`, and `Performance`).
- `ragang/modules/` and `ragang/metrics/` contain the public module and metric
  implementations. Built-in metrics are grouped by retriever, generator, and
  end-to-end scope.
- `ragang/adapters/` contains LLM, embedding, and Milvus integrations.
- `ragang/cli_script/` is the `ragang` CLI. A user project is loaded through
  its `manager.py`, and `containers()` constructs the flows.
- `ragang/core/network/` serves the local WebSocket protocol used by the
  dashboard. CLI history and dashboard payloads share the same serialized
  runtime state.
- `ragang/templates/init_template/` is copied by `ragang init`; changes to the
  runtime contract usually require matching template updates.
- `ragang/web/` is generated frontend output. Its source of truth is the
  separate `RAG-APP-UI` repository.

## Local commands

- Create or activate a Python 3.13+ virtual environment, then install the
  project with `python -m pip install -e .`.
- Inspect the CLI with `ragang --help`; the main workflows are `ragang init`,
  `ragang run`, `ragang query-gen`, and `ragang show`.
- Run the regression suite with
  `python -m unittest discover -s tests -v`.
- Run an import/compile check with `python -m compileall -q ragang`.
- Build a wheel with `python -m pip wheel . --no-deps -w dist` when package
  verification is needed.
- For a byte-reproducible release wheel, set `SOURCE_DATE_EPOCH` to the source
  commit timestamp before building. Keep `MANIFEST.in` synchronized with each
  verified frontend asset set so orphan files in a dirty worktree are never
  packaged.

Tests must not require live paid APIs or a running Milvus instance unless they
are explicitly marked as integration tests. Use deterministic fake adapters
for normal regression coverage.

## Evaluation correctness

- A score is valid only when the metric received the inputs it declares and
  completed successfully.
- Empty or unsupported inputs, adapter errors, malformed judge output, and
  parsing failures must produce an explicit not-evaluated or error state; do
  not fabricate zero, one, or another numeric fallback.
- Keep observed evidence separate from inferred diagnosis in serialized
  results and UI copy.
- Preserve metric scale, units, parameter ordering, and version semantics.
  Any intentional semantic change needs focused tests and user-facing notes.
- Never aggregate heterogeneous metrics into an overall score or best/worst
  module ranking. Direction and units must be interpreted per metric.
- Every evaluated score must be a finite non-boolean real number. A valid zero
  remains evaluated; unsupported inputs and calculation failures do not.
- Graph and retry changes must preserve every module repetition, bounded
  `max_steps`, parent execution IDs, the actually selected next modules,
  latency, and failure state. Trace input/output values only by key name.
- Counterfactual perturbations must be deterministic from recorded parameters,
  keep semantic labels explicitly user-supplied/unverified, and avoid causal
  claims.
- Tests must encode correct behavior. Never weaken or delete a test merely to
  make a change pass.

## Frontend and generated assets

- Never hand-edit minified JavaScript, CSS, source maps, service workers, or
  hashed assets under `ragang/web/`.
- Make UI changes in `RAG-APP-UI`, run its checks and production build, and
  replace the bundled asset set as one reviewed build artifact.
- Record the exact committed `RAG-APP-UI` source SHA in durable backend
  documentation whenever a verified build is installed into `ragang/web/`.
- `index.html` and the service worker must reference only files present in the
  same build. Remove stale hashed assets when installing a verified build.
- Do not expose the dashboard beyond loopback by default. Treat WebSocket file
  names and payloads as untrusted input.

## Contribution rules

- Work on a dedicated branch, not `main` or `validation` directly.
- Keep changes small, reviewable, and tied to a reproduced issue or an
  accepted modernization requirement.
- After each change run focused tests, the regression suite, relevant
  integration checks, and compile/import checks.
- Do not commit API keys, personal paths, generated history, local settings,
  vector database data, or virtual environments.
- Never print, copy, partially reproduce, hash, or otherwise expose discovered
  credential values. Report only redacted metadata and environment-variable
  names needed for remediation.
- Do not push, merge, tag, publish, or rewrite history without explicit user
  approval.
