"""Demo of the inventory management system with sample data.

A fixed "today" is used so the output is reproducible; in real use, omit the
``today`` arguments and the current date is used.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from inventory import Inventory, PerishableProduct, Product

TODAY = date(2026, 10, 20)


def section(title: str) -> None:
    """Print a section heading."""
    print(f"\n=== {title} ===")


def attempt(description: str, action: Callable[[], object]) -> None:
    """Run ``action`` and print the validation error it is expected to raise."""
    try:
        action()
    except (ValueError, KeyError) as error:
        print(f"[rejected] {description}: {error.args[0]}")
    else:  # pragma: no cover - demo safety net
        print(f"[unexpectedly accepted] {description}")


def build_inventory() -> Inventory:
    """Create an inventory filled with sample products."""
    inventory = Inventory()
    inventory.add_product(Product("Laptop Stand", "ELEC-001", 34.99, 25, 5))
    inventory.add_product(Product("USB-C Cable", "ELEC-002", 9.50, 4, 10))
    inventory.add_product(Product("Notebook", "STAT-001", 3.25, 120, 20))
    inventory.add_product(
        PerishableProduct("Whole Milk 1L", "DAIRY-001", 1.89, "2026-10-22", 40, 10)
    )
    inventory.add_product(
        PerishableProduct("Greek Yogurt", "DAIRY-002", 0.99, "2026-10-19", 8, 10)
    )
    inventory.add_product(
        PerishableProduct("Sourdough Bread", "BAKE-001", 4.50, "2026-10-30", 15, 5)
    )
    inventory.add_product(
        PerishableProduct("Fresh Salmon", "FISH-001", 12.99, "2026-10-20", 6, 3)
    )
    return inventory


def main() -> None:
    """Walk through every inventory operation."""
    inventory = build_inventory()

    section("Initial report")
    print(inventory.report(TODAY))

    section("Printing products (__str__ and __repr__)")
    print(inventory.get_product("ELEC-001"))
    print(inventory.get_product("DAIRY-001"))
    print(repr(inventory.get_product("DAIRY-001")))

    section("Add and remove stock")
    print(f"Restock ELEC-002 +30 -> {inventory.add_stock('ELEC-002', 30)} units")
    print(f"Sell DAIRY-001 -35    -> {inventory.remove_stock('DAIRY-001', 35)} units")

    section("Validation (all of these are rejected)")
    attempt("remove 99 Sourdough", lambda: inventory.remove_stock("BAKE-001", 99))
    attempt("add 0 stock", lambda: inventory.add_stock("BAKE-001", 0))
    attempt("negative price", lambda: Product("Bad", "BAD-1", -1.0))
    attempt("negative stock", lambda: Product("Bad", "BAD-2", 1.0, stock=-3))
    attempt(
        "impossible expiry date",
        lambda: PerishableProduct("Bad", "BAD-3", 1.0, "2026-02-30"),
    )
    attempt(
        "duplicate SKU",
        lambda: inventory.add_product(Product("Dup", "ELEC-001", 1)),
    )
    attempt("unknown SKU", lambda: inventory.add_stock("NOPE-000", 1))

    section("Low-stock alerts")
    for alert in inventory.low_stock_alerts():
        print(alert)

    section("Expiry alerts (most urgent first)")
    for alert in inventory.expiry_alerts(TODAY):
        print(alert)

    section("Perishable behaviour")
    milk = inventory.get_product("DAIRY-001")
    assert isinstance(milk, PerishableProduct)
    print(
        f"{milk.name}: expired={milk.is_expired(TODAY)}, "
        f"days left={milk.days_until_expiry(TODAY)}, "
        f"expiring soon={milk.is_expiring_soon(TODAY)}"
    )

    section("Final report")
    print(inventory.report(TODAY))


if __name__ == "__main__":
    main()
