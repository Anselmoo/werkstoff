"""Produces OrderEvent records — the data contract consumer/process.py depends on."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    sku: str
    quantity: int
    unit_price_cents: int


def generate_events(count: int) -> list[OrderEvent]:
    return [
        OrderEvent(order_id=f"ord-{i}", sku="SKU-0001", quantity=1, unit_price_cents=1999)
        for i in range(count)
    ]
