from collections.abc import Callable
from uuid import uuid4

from app.agent.contracts import ToolContext, ToolDefinition
from app.agent.registry import ToolRegistry


async def query_inventory(context: ToolContext, args: dict) -> dict:
    quantity = {"MEM-16GB": 42, "LAPTOP-14": 7, "DOCK-USB-C": 0}.get(args["sku"], 0)
    return {
        "sku": args["sku"],
        "location": args.get("location", "MAIN"),
        "quantity": quantity,
        "available": quantity > 0,
    }


async def get_leave_balance(context: ToolContext, args: dict) -> dict:
    balances = {"annual": 12.5, "sick": 8.0}
    return {
        "user_id": str(context.user.id),
        "leave_type": args["leave_type"],
        "remaining_days": balances[args["leave_type"]],
    }


def build_business_registry(
    id_factory: Callable[[], str] = lambda: uuid4().hex[:8],
) -> ToolRegistry:
    async def create_work_ticket(context: ToolContext, args: dict) -> dict:
        return {"ticket_id": f"TKT-{id_factory()}", "status": "open", **args}

    async def submit_expense(context: ToolContext, args: dict) -> dict:
        return {
            "expense_id": f"EXP-{id_factory()}",
            "status": "submitted",
            "submitted_by": str(context.user.id),
            **args,
        }

    registry = ToolRegistry()
    definitions = [
        ToolDefinition(
            "create_work_ticket",
            "Create an IT support ticket.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                    "description": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["title", "description", "priority"],
                "additionalProperties": False,
            },
            "write",
            create_work_ticket,
            lambda a: f"Create a {a['priority']} priority IT ticket titled '{a['title']}'.",
        ),
        ToolDefinition(
            "query_inventory",
            "Query stock for a SKU and optional location.",
            {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "minLength": 1, "maxLength": 64},
                    "location": {"type": "string", "minLength": 1, "maxLength": 64},
                },
                "required": ["sku"],
                "additionalProperties": False,
            },
            "read",
            query_inventory,
            lambda a: f"Read inventory for SKU {a['sku']}.",
        ),
        ToolDefinition(
            "get_leave_balance",
            "Read the current user's leave balance.",
            {
                "type": "object",
                "properties": {"leave_type": {"type": "string", "enum": ["annual", "sick"]}},
                "required": ["leave_type"],
                "additionalProperties": False,
            },
            "read",
            get_leave_balance,
            lambda a: f"Read {a['leave_type']} leave balance.",
        ),
        ToolDefinition(
            "submit_expense",
            "Submit an employee expense report.",
            {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "exclusiveMinimum": 0, "maximum": 1000000},
                    "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                    "category": {
                        "type": "string",
                        "enum": ["travel", "meals", "supplies", "other"],
                    },
                    "description": {"type": "string", "minLength": 1, "maxLength": 1000},
                    "receipt_reference": {"type": "string", "minLength": 1, "maxLength": 256},
                },
                "required": [
                    "amount",
                    "currency",
                    "category",
                    "description",
                    "receipt_reference",
                ],
                "additionalProperties": False,
            },
            "write",
            submit_expense,
            lambda a: f"Submit {a['amount']} {a['currency']} as {a['category']} expense.",
        ),
    ]
    for definition in definitions:
        registry.register(definition)
    return registry
