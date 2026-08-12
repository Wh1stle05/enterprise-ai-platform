from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent.contracts import ToolContext
from app.agent.registry import ToolArgumentsError
from app.tools.business import build_business_registry, get_leave_balance, query_inventory


def test_business_registry_exposes_exact_tools_and_contracts() -> None:
    registry = build_business_registry(id_factory=lambda: "fixed")

    assert registry.names == {
        "create_work_ticket",
        "query_inventory",
        "get_leave_balance",
        "submit_expense",
    }

    assert {
        name: (
            registry.get(name, registry.names).side_effect,
            registry.get(name, registry.names).parameters,
        )
        for name in registry.names
    } == {
        "create_work_ticket": (
            "write",
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
        ),
        "query_inventory": (
            "read",
            {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "minLength": 1, "maxLength": 64},
                    "location": {"type": "string", "minLength": 1, "maxLength": 64},
                },
                "required": ["sku"],
                "additionalProperties": False,
            },
        ),
        "get_leave_balance": (
            "read",
            {
                "type": "object",
                "properties": {"leave_type": {"type": "string", "enum": ["annual", "sick"]}},
                "required": ["leave_type"],
                "additionalProperties": False,
            },
        ),
        "submit_expense": (
            "write",
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
        ),
    }


@pytest.mark.asyncio
async def test_read_tools_return_deterministic_results() -> None:
    context = ToolContext(db=AsyncMock(), user=SimpleNamespace(id="user-1"))

    assert await query_inventory(context, {"sku": "MEM-16GB", "location": "SH-A"}) == {
        "sku": "MEM-16GB",
        "location": "SH-A",
        "quantity": 42,
        "available": True,
    }
    assert await query_inventory(context, {"sku": "UNKNOWN"}) == {
        "sku": "UNKNOWN",
        "location": "MAIN",
        "quantity": 0,
        "available": False,
    }
    assert await get_leave_balance(context, {"leave_type": "annual"}) == {
        "user_id": "user-1",
        "leave_type": "annual",
        "remaining_days": 12.5,
    }


@pytest.mark.asyncio
async def test_write_tools_use_injected_ids_and_preserve_arguments() -> None:
    registry = build_business_registry(id_factory=lambda: "fixed")
    context = ToolContext(db=AsyncMock(), user=SimpleNamespace(id="user-1"))
    ticket_args = {"title": "Blue screen", "description": "Stops at boot", "priority": "high"}
    expense_args = {
        "amount": 12.5,
        "currency": "USD",
        "category": "meals",
        "description": "Lunch",
        "receipt_reference": "receipt-1",
    }

    ticket = await registry.get("create_work_ticket", registry.names).handler(context, ticket_args)
    expense = await registry.get("submit_expense", registry.names).handler(context, expense_args)

    assert ticket == {"ticket_id": "TKT-fixed", "status": "open", **ticket_args}
    assert expense == {
        "expense_id": "EXP-fixed",
        "status": "submitted",
        "submitted_by": "user-1",
        **expense_args,
    }


def test_impact_text_is_deterministic_and_writes_are_explicit() -> None:
    registry = build_business_registry(id_factory=lambda: "fixed")

    assert registry.get("query_inventory", registry.names).impact({"sku": "MEM-16GB"}) == (
        "Read inventory for SKU MEM-16GB."
    )
    assert registry.get("get_leave_balance", registry.names).impact({"leave_type": "annual"}) == (
        "Read annual leave balance."
    )
    assert (
        registry.get("create_work_ticket", registry.names).impact(
            {"priority": "high", "title": "Blue screen"}
        )
        == "Create a high priority IT ticket titled 'Blue screen'."
    )
    assert (
        registry.get("submit_expense", registry.names).impact(
            {"amount": 12.5, "currency": "USD", "category": "meals"}
        )
        == "Submit 12.5 USD as meals expense."
    )


def test_business_registry_rejects_invalid_arguments() -> None:
    registry = build_business_registry()

    with pytest.raises(ToolArgumentsError):
        registry.validate(
            "submit_expense",
            {
                "amount": -1,
                "currency": "USD",
                "category": "meals",
                "description": "Lunch",
                "receipt_reference": "receipt-1",
            },
        )
    with pytest.raises(ToolArgumentsError):
        registry.validate(
            "submit_expense",
            {
                "amount": 1,
                "currency": "usd",
                "category": "meals",
                "description": "Lunch",
                "receipt_reference": "receipt-1",
            },
        )
    with pytest.raises(ToolArgumentsError):
        registry.validate("query_inventory", {"sku": "MEM-16GB", "hidden": True})
