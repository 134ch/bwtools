"""The single choke point for every tool call.

Every transport (CLI, MCP, future HTTP) funnels through Runner.call. This is
what gives us uniform metrics, error classification, and argument validation
across every harness.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from pydantic import ValidationError, create_model

from .errors import (
    BwkitError,
    InvalidArgumentsError,
    MissingCredentialError,
    MissingExtraError,
    ToolDisabledError,
    ToolError,
    UnknownToolError,
)
from .metrics import Call, Metrics, sha256_of_canonical_json, utcnow_iso
from .registry import ResolvedTool
from .spec import ToolSpec


def _validate_arguments(spec: ToolSpec, arguments: dict) -> dict:
    """Use the spec's input_schema (generated from run() hints) to validate.

    We rebuild a pydantic model from the signature on the fly — it's cheap
    and lets us reuse pydantic's coercion for CLI-level stringy inputs.
    """
    import inspect
    from typing import get_type_hints

    sig = inspect.signature(spec.run)
    hints = get_type_hints(spec.run)
    fields: dict[str, tuple[Any, Any]] = {}
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = hints.get(name, Any)
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (ann, default)
    Model = create_model(f"{spec.run.__name__}_In", **fields)  # type: ignore[call-overload]

    unknown = set(arguments) - set(fields)
    if unknown:
        raise InvalidArgumentsError(f"unknown arguments: {sorted(unknown)}")

    try:
        return Model(**arguments).model_dump()
    except ValidationError as e:
        raise InvalidArgumentsError(e.errors()) from e


class Runner:
    def __init__(self, registry: dict[str, ResolvedTool], metrics: Metrics) -> None:
        self.registry = registry
        self.metrics = metrics

    def call(
        self,
        tool: str,
        *,
        caller: str,
        transport: str,
        arguments: Optional[dict] = None,
    ) -> Any:
        arguments = arguments or {}

        resolved = self.registry.get(tool)
        if resolved is None:
            self._record_fast(tool, caller, transport, "unknown_tool", UnknownToolError.__name__)
            raise UnknownToolError(tool)
        if not resolved.enabled:
            self._record_fast(tool, caller, transport, "tool_disabled", ToolDisabledError.__name__)
            raise ToolDisabledError(tool)

        # Validation can fail before the timed call starts — but we still want a metrics row.
        try:
            validated = _validate_arguments(resolved.spec, arguments)
        except InvalidArgumentsError as e:
            self._record_fast(tool, caller, transport, e.code, type(e).__name__, arguments=arguments)
            raise

        t0 = time.monotonic()
        status, error_code, error_class = "ok", None, None
        try:
            result = resolved.spec.run(**validated)
            return result
        except MissingExtraError as e:
            status, error_code, error_class = "error", e.code, type(e).__name__; raise
        except MissingCredentialError as e:
            status, error_code, error_class = "error", e.code, type(e).__name__; raise
        except ToolError as e:
            status, error_code, error_class = "error", e.code, type(e).__name__; raise
        except TimeoutError as e:
            status, error_code, error_class = "error", "timeout", type(e).__name__; raise
        except BwkitError as e:
            status, error_code, error_class = "error", e.code, type(e).__name__; raise
        except Exception as e:
            status, error_code, error_class = "error", "unexpected", type(e).__name__; raise
        finally:
            self.metrics.record(Call(
                ts=utcnow_iso(),
                tool=tool,
                caller=caller,
                transport=transport,
                latency_ms=int((time.monotonic() - t0) * 1000),
                status=status,
                error_code=error_code,
                error_class=error_class,
                input_hash=sha256_of_canonical_json(validated),
            ))

    # Helpers for failures that happen before/outside the timed body.

    def _record_fast(
        self,
        tool: str,
        caller: str,
        transport: str,
        error_code: str,
        error_class: str,
        *,
        arguments: Optional[dict] = None,
    ) -> None:
        self.metrics.record(Call(
            ts=utcnow_iso(),
            tool=tool,
            caller=caller,
            transport=transport,
            latency_ms=0,
            status="error",
            error_code=error_code,
            error_class=error_class,
            input_hash=sha256_of_canonical_json(arguments or {}),
        ))
