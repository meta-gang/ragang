"""Evaluator provenance and safe failure metadata."""

from __future__ import annotations

from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import inspect
import json
import math
from numbers import Real
import re
from typing import Any

from ragang.core.bases.datas.performance import Performance


_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret|authorization)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)([?&](?:key|api_key|token)=)[^&\s]+"),
)
_PATH_PATTERNS = (
    re.compile(r"(?<![:\w])/(?:[^/\s]+/)+[^,\s;:]*"),
    re.compile(r"\b[A-Za-z]:\\(?:[^\\\s]+\\)*[^,\s;:]*"),
)
_SENSITIVE_FIELD_PARTS = (
    "api_key",
    "token",
    "password",
    "secret",
    "authorization",
    "header",
    "url",
    "endpoint",
    "host",
    "path",
)
_CONTENT_FIELD_PARTS = (
    "answer",
    "context",
    "corpus",
    "document",
    "generation",
    "prompt",
    "query",
    "response",
    "text",
)
_STRUCTURAL_FIELDS = {
    "dependency",
    "direction",
    "is_starter",
    "lazy_state",
    "metrics",
    "module_id",
    "param_keys",
    "param_refs",
}


def _redact_message(value: str) -> str:
    value = _SECRET_PATTERNS[0].sub("Bearer [REDACTED]", value)
    for pattern in _SECRET_PATTERNS[1:]:
        value = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", value)
    for pattern in _PATH_PATTERNS:
        value = pattern.sub("[PATH]", value)
    return value


def _fingerprint(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def _implementation_descriptor(component: Any) -> dict:
    component_class = component if inspect.isclass(component) else component.__class__
    implementation = f"{component_class.__module__}.{component_class.__qualname__}"
    try:
        source = inspect.getsource(component_class)
    except (OSError, TypeError):
        source = implementation
    return {
        "implementation": implementation,
        "implementation_fingerprint": _fingerprint(source),
    }


def _adapter_descriptors(component: Any) -> list[dict]:
    adapters = []
    for attribute, adapter in sorted(vars(component).items()):
        if not attribute.endswith("_adapter") or adapter is None:
            continue
        descriptor = {
            "role": attribute.removesuffix("_adapter"),
            **_implementation_descriptor(adapter),
        }
        model_name = getattr(adapter, "model_name", None)
        if isinstance(model_name, str) and model_name:
            descriptor["model"] = model_name
        adapters.append(descriptor)
    return adapters


def _safe_settings(component: Any) -> dict:
    """Keep only bounded, non-content configuration values.

    Provenance is intended to identify an evaluator configuration, not to copy
    user documents, prompts, local paths, or credentials into every result.
    """
    settings = {}
    for attribute, value in sorted(vars(component).items()):
        lowered = attribute.lower()
        if (
            attribute.startswith("_")
            or attribute in _STRUCTURAL_FIELDS
            or attribute.endswith("_adapter")
            or any(part in lowered for part in _SENSITIVE_FIELD_PARTS)
            or any(part in lowered for part in _CONTENT_FIELD_PARTS)
        ):
            continue
        if value is None or isinstance(value, (bool, int, float)):
            settings[attribute] = value
        elif isinstance(value, str) and len(value) <= 200:
            settings[attribute] = _redact_message(value)
        elif isinstance(value, (list, tuple)) and all(
            item is None
            or isinstance(item, (bool, int, float))
            or (isinstance(item, str) and len(item) <= 200)
            for item in value
        ):
            if len(value) <= 20:
                settings[attribute] = [
                    _redact_message(item) if isinstance(item, str) else item
                    for item in value
                ]
    return settings


def evaluator_provenance(metric: Any) -> dict:
    """Return deterministic metric identity without credentials or raw prompts."""
    return {
        **_implementation_descriptor(metric),
        "parameter_sources": list(getattr(metric, "param_refs", [])),
        "settings": _safe_settings(metric),
        "adapters": _adapter_descriptors(metric),
    }


def safe_failure(error: BaseException | None = None) -> dict:
    if error is None:
        return {
            "type": "not_evaluated",
            "message": "Metric did not produce a valid score.",
        }

    message = _redact_message(str(error).replace("\n", " ")[:500])
    return {"type": type(error).__name__, "message": message}


def attach_evaluator_context(performance: Performance, metric: Any, error: BaseException | None = None) -> Performance:
    if not isinstance(performance, Performance):
        raise TypeError(f"Metric '{metric.__class__.__name__}' must return Performance")
    if performance.did_eval and (
        isinstance(performance.score, bool)
        or not isinstance(performance.score, Real)
        or not math.isfinite(float(performance.score))
    ):
        raise ValueError(
            f"Metric '{metric.__class__.__name__}' marked a non-finite or non-numeric score as evaluated"
        )
    failure = None
    if not performance.did_eval:
        failure = performance.failure or safe_failure(error)
    performance.attach_context(evaluator_provenance(metric), failure)
    return performance


def build_run_metadata(container: Any) -> dict:
    modules = []
    for module in container.modules.values():
        modules.append({
            "module_id": module.module_id,
            **_implementation_descriptor(module),
            "settings": _safe_settings(module),
            "adapters": _adapter_descriptors(module),
            "metrics": [evaluator_provenance(metric) for metric in (module.metrics or [])],
        })
    configuration = {
        "flow_id": container.flow_id,
        "flow_graph": [list(edge) for edge in container.storage.flow_graph],
        "execution_policy": {"max_steps": container.max_steps},
        "modules": modules,
        "e2e_metrics": [evaluator_provenance(metric) for metric in (container.metrics or [])],
    }
    try:
        framework_version = version("ragang")
    except PackageNotFoundError:
        framework_version = "unknown"
    return {
        "schema_version": 1,
        "framework_version": framework_version,
        "config_fingerprint": _fingerprint(configuration),
        "configuration": configuration,
    }
