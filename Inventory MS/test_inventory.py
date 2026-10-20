"""Tests for the Inventory class."""

from datetime import date

import pytest

from inventory import Inventory, PerishableProduct, Product

TODAY = date(2026, 10, 20)


@pytest.fixture
def inventory() -> Inventory:
    inv = Inventory()
    inv.add_product(Product("Cable", "C-1", 9.5, stock=4, low_stock_threshold=10))
    inv.add_product(Product("Stand", "S-1", 35.0, stock=25, low_stock_threshold=5))
    inv.add_product(PerishableProduct("Yogurt", "Y-1", 1.0, "2026-10-19", stock=20))
    inv.add_product(PerishableProduct("Milk", "M-1", 2.0, "2026-10-22", stock=20))
    inv.add_product(PerishableProduct("Rice", "R-1", 3.0, "2027-10-22", stock=20))
    return inv


def test_add_product_and_lookup(inventory: Inventory) -> None:
    assert len(inventory) == 5
    assert "C-1" in inventory
    assert inventory.get_product("C-1").name == "Cable"


def test_duplicate_sku_rejected(inventory: Inventory) -> None:
    with pytest.raises(ValueError, match="already exists"):
        inventory.add_product(Product("Other", "C-1", 1.0))


def test_unknown_sku_raises_key_error(inventory: Inventory) -> None:
    with pytest.raises(KeyError, match="No product with SKU"):
        inventory.add_stock("NOPE", 1)


def test_add_and_remove_stock(inventory: Inventory) -> None:
    assert inventory.add_stock("S-1", 5) == 30
    assert inventory.remove_stock("S-1", 10) == 20


def test_remove_more_than_available_rejected(inventory: Inventory) -> None:
    with pytest.raises(ValueError, match="only 25 in stock"):
        inventory.remove_stock("S-1", 26)
    assert inventory.get_product("S-1").stock == 25


def test_low_stock_alerts(inventory: Inventory) -> None:
    alerts = inventory.low_stock_alerts()
    assert len(alerts) == 1
    assert "Cable" in alerts[0] and "4 left" in alerts[0]


def test_restocking_clears_low_stock_alert(inventory: Inventory) -> None:
    inventory.add_stock("C-1", 20)
    assert inventory.low_stock_alerts() == []


def test_expiry_alerts_are_ordered_and_skip_healthy_items(
    inventory: Inventory,
) -> None:
    alerts = inventory.expiry_alerts(TODAY)
    assert len(alerts) == 2
    assert alerts[0].startswith("EXPIRED 1d ago: Yogurt")
    assert alerts[1].startswith("EXPIRES in 2d: Milk")


def test_report_is_aligned_and_flags_items(inventory: Inventory) -> None:
    lines = inventory.report(TODAY).splitlines()
    table = [line for line in lines if " | " in line and "products" not in line]
    separators = {tuple(i for i, ch in enumerate(line) if ch == "|") for line in table}
    # Every table line (header + rows) has its column separators in the same place.
    assert len(separators) == 1
    report = "\n".join(lines)
    assert "EXPIRED 1d ago" in report
    assert "LOW STOCK" in report
    assert "5 products" in report


def test_empty_inventory_report() -> None:
    assert "Inventory is empty." in Inventory().report(TODAY)
