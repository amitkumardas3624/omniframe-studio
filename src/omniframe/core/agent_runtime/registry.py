"""Typed action registry — the contract an AI agent programs against.

Every capability in OmniFrame is exposed as an :class:`ActionSpec`: a name, a
JSON Schema for its input and output, the preconditions it enforces, and the
error codes it may raise.  Agents can introspect the registry (``omniframe
tools``) and call actions without reading the source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from ..errors import ActionError, PreconditionFailed, ToolNotFound, ValidationError
from ..logging import get_logger

LOG = get_logger("core.agent_runtime.registry")

Handler = Callable[..., Any]


# ---------------------------------------------------------------------------
# Minimal JSON Schema validation (subset used by OmniFrame action schemas)
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def validate_against_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str = "$",
    inject_defaults: bool = True,
) -> list[str]:
    """Validate ``value`` against a JSON Schema subset.

    Returns a list of human readable error strings (empty when valid).  When
    ``inject_defaults`` is true, missing properties that declare a ``default``
    are written back into the (mutable) ``value`` when it is a dict.
    """

    errors: list[str] = []
    if not schema:
        return errors

    declared_type = schema.get("type")
    if declared_type:
        types = declared_type if isinstance(declared_type, list) else [declared_type]
        allowed: tuple[type, ...] = ()
        for t in types:
            allowed += _TYPE_MAP.get(t, ())
        if allowed and not isinstance(value, allowed):
            if not (isinstance(value, bool) and "boolean" not in types):
                errors.append(f"{path}: expected type {declared_type}, got {type(value).__name__}")
                return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")

    if isinstance(value, dict):
        properties: dict[str, Any] = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"{path}: missing required property '{required}'")
        for key, sub in properties.items():
            if key in value:
                errors.extend(
                    validate_against_schema(
                        value[key], sub, path=f"{path}.{key}", inject_defaults=inject_defaults
                    )
                )
            elif inject_defaults and isinstance(sub, dict) and "default" in sub:
                value[key] = sub["default"]
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property '{key}'")

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_against_schema(
                        item, item_schema, path=f"{path}[{index}]", inject_defaults=False
                    )
                )
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: expected at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: expected at most {schema['maxItems']} items")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: must be <= {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: must be > {schema['exclusiveMinimum']}")

    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: must be at least {schema['minLength']} characters")

    return errors


# ---------------------------------------------------------------------------
# Action specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionSpec:
    """A single callable capability exposed to agents."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    handler: Handler | None = None
    engine: str = "core"
    preconditions: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    mutating: bool = False
    idempotent: bool = True
    tags: tuple[str, ...] = ()

    def to_tool_schema(self) -> dict[str, Any]:
        """Render the action as an MCP / tool-calling schema."""

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "meta": {
                "engine": self.engine,
                "mutating": self.mutating,
                "idempotent": self.idempotent,
                "preconditions": list(self.preconditions),
                "error_codes": list(self.error_codes),
                "tags": list(self.tags),
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_tool_schema()


class ActionRegistry:
    """A registry of :class:`ActionSpec` objects."""

    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    # -- registration ---------------------------------------------------
    def register(self, spec: ActionSpec, *, overwrite: bool = False) -> ActionSpec:
        if spec.name in self._actions and not overwrite:
            raise ValueError(f"Action '{spec.name}' is already registered")
        if spec.name in self._actions:
            LOG.debug("overwriting action", extra={"action": spec.name})
        self._actions[spec.name] = spec
        return spec

    def action(
        self,
        name: str,
        *,
        description: str,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        engine: str = "core",
        preconditions: tuple[str, ...] = (),
        error_codes: tuple[str, ...] = (),
        mutating: bool = False,
        idempotent: bool = True,
        tags: tuple[str, ...] = (),
        overwrite: bool = False,
    ) -> Callable[[Handler], Handler]:
        """Decorator form of :meth:`register`."""

        def decorator(fn: Handler) -> Handler:
            self.register(
                ActionSpec(
                    name=name,
                    description=description,
                    input_schema=input_schema or {"type": "object"},
                    output_schema=output_schema or {"type": "object"},
                    handler=fn,
                    engine=engine,
                    preconditions=preconditions,
                    error_codes=error_codes,
                    mutating=mutating,
                    idempotent=idempotent,
                    tags=tags,
                ),
                overwrite=overwrite,
            )
            return fn

        return decorator

    # -- lookup ---------------------------------------------------------
    def get(self, name: str) -> ActionSpec:
        try:
            return self._actions[name]
        except KeyError as exc:
            raise ToolNotFound(
                f"Unknown action '{name}'.", available=sorted(self._actions)
            ) from exc

    def has(self, name: str) -> bool:
        return name in self._actions

    def names(self) -> list[str]:
        return sorted(self._actions)

    def list_actions(self) -> list[ActionSpec]:
        return [self._actions[name] for name in sorted(self._actions)]

    def by_engine(self, engine: str) -> list[ActionSpec]:
        return [a for a in self.list_actions() if a.engine == engine]

    # -- execution ------------------------------------------------------
    def execute(self, name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate the input, run the handler and normalise the result."""

        spec = self.get(name)
        payload = dict(params or {})

        errors = validate_against_schema(payload, spec.input_schema)
        if errors:
            raise ValidationError(
                f"Invalid arguments for action '{name}'.",
                action=name,
                errors=errors,
            )

        if spec.handler is None:
            raise PreconditionFailed(
                f"Action '{name}' has no executable handler.", action=name
            )

        try:
            result = spec.handler(**payload)
        except Exception as exc:  # normalise everything into an ActionError
            from ..errors import OmniFrameError

            if isinstance(exc, OmniFrameError):
                raise
            raise ActionError(
                f"Action '{name}' failed: {exc}", action=name, error=type(exc).__name__
            ) from exc

        if isinstance(result, dict):
            return result
        return {"result": result}

    # -- manifests ------------------------------------------------------
    def to_tool_schemas(self) -> list[dict[str, Any]]:
        return [spec.to_tool_schema() for spec in self.list_actions()]

    def to_json_document(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "kind": "omniframe_tool_manifest",
            "tools": self.to_tool_schemas(),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_json_document(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

_REGISTRY = ActionRegistry()


def get_registry() -> ActionRegistry:
    """Return the process-wide registry."""

    return _REGISTRY


def build_tool_manifest(registry: ActionRegistry | None = None) -> dict[str, Any]:
    """Build the JSON tool manifest consumed by agents and MCP clients."""

    return (registry or get_registry()).to_json_document()
