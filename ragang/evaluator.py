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
_EXPLICIT_PROVENANCE_FIELDS = {
    "prompt_version", "corpus_version", "dataset_version", "metric_version",
    "model_digest", "model_revision", "model_version", "configuration_version",
    "temperature", "seed", "top_p", "top_k", "max_tokens", "num_predict",
    "repeat_penalty",
}
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
    except Exception:
        source = implementation
    return {
        "implementation": implementation,
        "implementation_fingerprint": _fingerprint(source),
    }


def _component_attributes(component: Any) -> dict:
    try:
        return dict(vars(component))
    except (TypeError, AttributeError):
        return {}


def _adapter_descriptors(component: Any) -> list[dict]:
    adapters = []
    for attribute, adapter in sorted(_component_attributes(component).items()):
        if not attribute.endswith("_adapter") or adapter is None:
            continue
        descriptor = {
            "role": attribute.removesuffix("_adapter"),
            **_implementation_descriptor(adapter),
        }
        try:
            model_name = getattr(adapter, "model_name", None)
        except Exception:
            model_name = None
        if isinstance(model_name, str) and model_name:
            descriptor["model"] = model_name
        descriptor["settings"] = _safe_settings(adapter)
        adapters.append(descriptor)
    return adapters


def _safe_settings(component: Any) -> dict:
    """Keep only bounded, non-content configuration values.

    Provenance is intended to identify an evaluator configuration, not to copy
    user documents, prompts, local paths, or credentials into every result.
    """
    settings = {}
    attributes = _component_attributes(component)
    for name in _EXPLICIT_PROVENANCE_FIELDS:
        if name not in attributes:
            try:
                attributes[name] = getattr(component, name)
            except (AttributeError, TypeError):
                pass
            except Exception:
                # Provenance must not cause an otherwise valid evaluation to fail.
                pass
    for attribute, value in sorted(attributes.items()):
        lowered = attribute.lower()
        explicit = attribute in _EXPLICIT_PROVENANCE_FIELDS
        if (
            attribute.startswith("_")
            or attribute in _STRUCTURAL_FIELDS
            or attribute.endswith("_adapter")
            or (not explicit and any(part in lowered for part in _SENSITIVE_FIELD_PARTS))
            or (not explicit and any(part in lowered for part in _CONTENT_FIELD_PARTS))
        ):
            continue
        if value is None or isinstance(value, (bool, int)):
            settings[attribute] = value
        elif isinstance(value, float) and math.isfinite(value):
            settings[attribute] = value
        elif isinstance(value, str) and len(value) <= 200:
            settings[attribute] = _redact_message(value)
        elif isinstance(value, (list, tuple)) and all(
            item is None
            or isinstance(item, (bool, int))
            or (isinstance(item, float) and math.isfinite(item))
            or (isinstance(item, str) and len(item) <= 200)
            for item in value
        ):
            if len(value) <= 20:
                settings[attribute] = [
                    _redact_message(item) if isinstance(item, str) else item
                    for item in value
                ]
    return settings


def evaluator_provenance(metric: Any, *, parameter_binding_version: str | None = None) -> dict:
    """Return deterministic metric identity without credentials or raw prompts."""
    descriptor = {
        **_implementation_descriptor(metric),
        "parameter_sources": list(getattr(metric, "param_refs", [])),
        "settings": _safe_settings(metric),
        "adapters": _adapter_descriptors(metric),
    }
    if parameter_binding_version is not None:
        descriptor["parameter_binding_version"] = parameter_binding_version
    descriptor["fingerprint"] = _fingerprint(descriptor)
    return descriptor


def safe_failure(error: BaseException | None = None) -> dict:
    if error is None:
        return {
            "type": "not_evaluated",
            "message": "Metric did not produce a valid score.",
        }

    message = _redact_message(str(error).replace("\n", " ")[:500])
    return {"type": type(error).__name__, "message": message}


def valid_score_value(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def _json_metadata_value(value: Any, depth: int = 0) -> bool:
    """Accept bounded-depth JSON-native metadata; reject cycles and objects."""
    if depth > 32:
        return False
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_json_metadata_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _json_metadata_value(item, depth + 1)
                   for key, item in value.items())
    return False


def performance_metadata_error(performance: dict) -> str | None:
    """Validate public/legacy serialized metric metadata without echoing values.

    Imported histories use the same checks as new evaluator output. Empty units
    remain valid for legacy unitless metrics; identity names must be present.
    """
    def field(name, default=None):
        return performance.get(name, performance.get(f"_Performance__{name}", default))
    name = field("metric")
    if not isinstance(name, str) or not name.strip():
        return "metric must be a non-empty string"
    if not isinstance(field("unit", ""), str):
        return "unit must be a string"
    for name in ("direction", "metric_version"):
        value = field(name)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            return f"{name} must be a non-empty string or None"
    evidence = field("evidence", [])
    if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
        return "evidence must be a list of objects"
    for name, value in (("evidence", evidence), ("scope", field("scope", {})),
                        ("evaluator", field("evaluator", {}))):
        if name != "evidence" and not isinstance(value, dict):
            return f"{name} must be an object"
        if not _json_metadata_value(value):
            return f"{name} must contain finite JSON-native metadata"
    failure = field("failure")
    if failure is not None:
        if not isinstance(failure, dict) or not _json_metadata_value(failure):
            return "failure must be a JSON object or None"
        for name in ("type", "message"):
            if name in failure and not isinstance(failure[name], str):
                return f"failure.{name} must be a string"
    return None


def attach_evaluator_context(performance: Performance, metric: Any, error: BaseException | None = None,
                             *, parameter_binding_version: str | None = None) -> Performance:
    if not isinstance(performance, Performance):
        raise TypeError(f"Metric '{metric.__class__.__name__}' must return Performance")
    metadata = {name: getattr(performance, name) for name in (
        "metric", "unit", "direction", "metric_version", "evidence", "scope", "evaluator", "failure")}
    metadata_error = performance_metadata_error(metadata)
    if metadata_error:
        raise ValueError(f"Metric '{metric.__class__.__name__}' returned invalid metadata: {metadata_error}")
    if type(performance.did_eval) is not bool:
        raise ValueError(f"Metric '{metric.__class__.__name__}' must use a boolean evaluation flag")
    if performance.did_eval and not valid_score_value(performance.score):
        raise ValueError(
            f"Metric '{metric.__class__.__name__}' marked a non-finite or non-numeric score as evaluated"
        )
    failure = None
    if not performance.did_eval:
        failure = performance.failure or safe_failure(error)
    performance.attach_context(evaluator_provenance(metric, parameter_binding_version=parameter_binding_version), failure)
    return performance


def build_run_metadata(container: Any) -> dict:
    modules = []
    for module in container.modules.values():
        modules.append({
            "module_id": module.module_id,
            **_implementation_descriptor(module),
            "settings": _safe_settings(module),
            "adapters": _adapter_descriptors(module),
            "metrics": [evaluator_provenance(metric, parameter_binding_version="ancestry-first-v1")
                        for metric in (module.metrics or [])],
        })
    configuration = {
        "flow_id": container.flow_id,
        "flow_graph": [list(edge) for edge in container.storage.flow_graph],
        "execution_policy": {
            "metric_binding_version": "ancestry-first-v1",
            "max_steps": container.max_steps,
            "module_timeout_seconds": getattr(container, "module_timeout_seconds", None),
            "max_concurrency": getattr(container, "max_concurrency", None),
        },
        "versions": {
            key: value for key, value in _safe_settings(container).items()
            if key in _EXPLICIT_PROVENANCE_FIELDS
        },
        "modules": modules,
        "e2e_metrics": [evaluator_provenance(metric) for metric in (container.metrics or [])],
    }
    try:
        framework_version = version("ragang")
    except PackageNotFoundError:
        framework_version = "unknown"
    return {
        "schema_version": 2,
        "framework_version": framework_version,
        "config_fingerprint": _fingerprint(configuration),
        "configuration": configuration,
    }
