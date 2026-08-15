from app.agent.registry import ToolRegistry
from app.tools.business import build_business_registry
from app.tools.knowledge import build_knowledge_tool


def build_default_registry() -> ToolRegistry:
    registry = build_business_registry()
    registry.register(build_knowledge_tool())
    return registry
