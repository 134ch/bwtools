"""Tool specification dataclass + JSON Schema generation from type hints.

Tool modules export a `SPEC: ToolSpec` constant. The registry reads it,
generates input/output schemas from the run() callable's type hints, and
hands the finalized spec to the runner.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field, replace
from typing import Any, Callable, get_type_hints

from pydantic import TypeAdapter, create_model


@dataclass(frozen=True)
class ToolSpec:
    name: str
    summary: str
    upstream: str
    maintained: bool
    default_enabled: bool
    extras: tuple[str, ...]
    env_vars: tuple[str, ...]
    run: Callable[..., Any]
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)


def _param_default(p: inspect.Parameter) -> Any:
    return ... if p.default is inspect.Parameter.empty else p.default


def generate_input_schema(run: Callable[..., Any]) -> dict:
    """Build a JSON Schema for run()'s keyword-compatible parameters.

    Parameters without annotations are typed as `Any`. `*args` / `**kwargs`
    are skipped. The resulting schema is a standard JSON Schema object.
    """
    sig = inspect.signature(run)
    hints = get_type_hints(run)
    fields: dict[str, tuple[Any, Any]] = {}
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = hints.get(name, Any)
        fields[name] = (ann, _param_default(param))
    model = create_model(f"{run.__name__}_Input", **fields)  # type: ignore[call-overload]
    schema = model.model_json_schema()
    # Drop pydantic's generated "title" noise that isn't useful to agents.
    schema.pop("title", None)
    return schema


def generate_output_schema(run: Callable[..., Any]) -> dict:
    hints = get_type_hints(run)
    ret = hints.get("return", Any)
    try:
        schema = TypeAdapter(ret).json_schema()
    except Exception:
        schema = {}
    if isinstance(schema, dict):
        schema.pop("title", None)
    return schema


def finalize_spec(spec: ToolSpec) -> ToolSpec:
    """Return a copy of `spec` with input/output schemas populated from run()."""
    return replace(
        spec,
        input_schema=generate_input_schema(spec.run),
        output_schema=generate_output_schema(spec.run),
    )
