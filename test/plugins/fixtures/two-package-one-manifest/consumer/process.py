"""Consumes OrderEvent records produced by producer/generate.py — the real wire this fixture tests."""

from producer.generate import OrderEvent, generate_events


def total_revenue_cents(events: list[OrderEvent]) -> int:
    return sum(e.quantity * e.unit_price_cents for e in events)


if __name__ == "__main__":
    print(total_revenue_cents(generate_events(10)))
