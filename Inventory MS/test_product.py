"""Tests for the base Product class."""

import pytest

from inventory import Product


@pytest.fixture
def product() -> Product:
    return Product("Widget", "W-1", 10.0, stock=10, low_stock_threshold=3)


def test_valid_product_is_created(product: Product) -> None:
    assert (product.name, product.sku, product.price, product.stock) == (
        "Widget", "W-1", 10.0, 10,
    )
    assert product.total_value == 100.0


def test_negative_stock_rejected_in_constructor() -> None:
    with pytest.raises(ValueError, match="Stock cannot be negative"):
        Product("Widget", "W-1", 10.0, stock=-1)


def test_negative_stock_rejected_via_setter(product: Product) -> None:
    with pytest.raises(ValueError, match="Stock cannot be negative"):
        product.stock = -5
    assert product.stock == 10  # unchanged after a failed assignment


def test_negative_price_rejected(product: Product) -> None:
    with pytest.raises(ValueError, match="Price cannot be negative"):
        product.price = -0.01
    with pytest.raises(ValueError, match="Price cannot be negative"):
        Product("Widget", "W-1", -1)


@pytest.mark.parametrize("bad", [2.5, "3", True])
def test_stock_must_be_a_whole_number(bad: object) -> None:
    with pytest.raises(ValueError, match="whole number"):
        Product("Widget", "W-1", 1.0, stock=bad)  # type: ignore[arg-type]


def test_add_stock(product: Product) -> None:
    assert product.add_stock(5) == 15


@pytest.mark.parametrize("bad", [0, -2])
def test_add_stock_requires_positive_quantity(product: Product, bad: int) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        product.add_stock(bad)


def test_remove_stock(product: Product) -> None:
    assert product.remove_stock(4) == 6


def test_remove_exact_stock_is_allowed(product: Product) -> None:
    assert product.remove_stock(10) == 0


def test_remove_too_much_stock_rejected(product: Product) -> None:
    with pytest.raises(ValueError, match="only 10 in stock"):
        product.remove_stock(11)
    assert product.stock == 10


def test_low_stock_threshold_is_inclusive(product: Product) -> None:
    assert not product.is_low_stock()
    product.remove_stock(7)  # 3 left == threshold
    assert product.is_low_stock()
    assert product.status() == "LOW STOCK"


def test_str_and_repr(product: Product) -> None:
    assert str(product) == "Widget [W-1] $10.00 x 10 in stock"
    assert repr(product) == (
        "Product(name='Widget', sku='W-1', price=10.0, stock=10, "
        "low_stock_threshold=3)"
    )
