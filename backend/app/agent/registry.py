from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from app.agent.contracts import ToolDefinition


class DuplicateToolError(ValueError):
    pass


class UnknownToolError(LookupError):
    pass


class ToolArgumentsError(ValueError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)
        try:
            Draft202012Validator.check_schema(tool.parameters)
        except SchemaError as exc:
            raise ToolArgumentsError(f"Invalid schema for {tool.name}") from exc
        self._tools[tool.name] = tool

    @property
    def names(self) -> set[str]:
        return set(self._tools)

    def get(self, name: str, allowed: set[str]) -> ToolDefinition:
        if name not in allowed or name not in self._tools:
            raise UnknownToolError(name)
        return self._tools[name]

    def validate(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(name)
        try:
            Draft202012Validator(tool.parameters).validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentsError(exc.message) from exc
        return arguments

    def openai_tools(self, allowed: set[str]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": dict(tool.parameters),
                },
            }
            for name, tool in self._tools.items()
            if name in allowed
        ]
