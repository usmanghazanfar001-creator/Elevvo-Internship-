"""Product models: a general :class:`Product` and a :class:`PerishableProduct`.

Validation lives in the property setters (price, stock, expiry date) and in a
single helper for quantities, so every code path enforces the same rules.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _require_whole_number(value: Any, label: str) -> int:
    """Return ``value`` if it is a whole number, otherwise raise ``ValueError``.

    ``bool`` is rejected explicitly because it is a subclass of ``int``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number (got {value!r}).")
    return value


def _require_positive_quantity(quantity: Any) -> int:
    """Validate a quantity used when adding or removing stock."""
    _require_whole_number(quantity, "Quantity")
    if quantity <= 0:
        raise ValueError(f"Quantity must be greater than zero (got {quantity}).")
    return quantity


class Product:
    """A product that is tracked by SKU with a stock level.

    Args:
        name: Human-readable product name.
        sku: Unique stock keeping unit identifier.
        price: Unit price; must not be negative.
        stock: Initial units in stock; must not be negative.
        low_stock_threshold: Stock at or below this level counts as "low".
    """

    kind = "Standard"

    def __init__(
        self,
        name: str,
        sku: str,
        price: float,
        stock: int = 0,
        low_stock_threshold: int = 5,
    ) -> None:
        self.name = name
        self.sku = sku
        self.price = price
        self.stock = stock
        self.low_stock_threshold = low_stock_threshold

    # ------------------------------------------------------------------
    # Validated properties
    # ------------------------------------------------------------------
    @property
    def price(self) -> float:
        """Unit price (never negative)."""
        return self._price

    @price.setter
    def price(self, value: float) -> None:
        if value < 0:
            raise ValueError(f"Price cannot be negative (got {value}).")
        self._price = float(value)

    @property
    def stock(self) -> int:
        """Units currently in stock (never negative)."""
        return self._stock

    @stock.setter
    def stock(self, value: int) -> None:
        _require_whole_number(value, "Stock")
        if value < 0:
            raise ValueError(f"Stock cannot be negative (got {value}).")
        self._stock = value

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------
    @property
    def total_value(self) -> float:
        """Value of the stock on hand (price x stock)."""
        return self._price * self._stock

    def add_stock(self, quantity: int) -> int:
        """Increase stock by ``quantity`` and return the new stock level."""
        self.stock += _require_positive_quantity(quantity)
        return self.stock

    def remove_stock(self, quantity: int) -> int:
        """Decrease stock by ``quantity`` and return the new stock level.

        Raises:
            ValueError: If ``quantity`` is invalid or exceeds the stock on hand.
        """
        _require_positive_quantity(quantity)
        if quantity > self.stock:
            raise ValueError(
                f"Cannot remove {quantity} units of {self.sku}: "
                f"only {self.stock} in stock."
            )
        self.stock -= quantity
        return self.stock

    def is_low_stock(self) -> bool:
        """Return True when stock is at or below the low-stock threshold."""
        return self.stock <= self.low_stock_threshold

    def alerts(self, today: date | None = None) -> list[str]:
        """Return short alert labels that currently apply to this product.

        ``today`` is accepted so subclasses with date-based alerts share the
        same signature; the base class does not use it.
        """
        return ["LOW STOCK"] if self.is_low_stock() else []

    def status(self, today: date | None = None) -> str:
        """Return a one-line status: the alerts joined together, or ``OK``."""
        return ", ".join(self.alerts(today)) or "OK"

    def detail(self) -> str:
        """Extra information for reports; empty for a standard product."""
        return ""

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _repr_fields(self) -> dict[str, Any]:
        """Constructor arguments shown by ``__repr__`` (extended by subclasses)."""
        return {
            "name": self.name,
            "sku": self.sku,
            "price": self.price,
            "stock": self.stock,
            "low_stock_threshold": self.low_stock_threshold,
        }

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self._repr_fields().items())
        return f"{type(self).__name__}({fields})"

    def __str__(self) -> str:
        return f"{self.name} [{self.sku}] ${self.price:,.2f} x {self.stock} in stock"


class PerishableProduct(Product):
    """A product that expires.

    On top of everything :class:`Product` does, it knows *when* it expires and
    reports that through :meth:`is_expired`, :meth:`days_until_expiry`,
    :meth:`is_expiring_soon` and :meth:`expiry_alert`. Those expiry alerts are
    merged into :meth:`alerts`, so reports flag expired items automatically.

    Args:
        expiry_date: A ``date``/``datetime`` or an ISO ``"YYYY-MM-DD"`` string.
        expiring_soon_days: Items expiring within this many days are flagged.
    """

    kind = "Perishable"

    def __init__(
        self,
        name: str,
        sku: str,
        price: float,
        expiry_date: date | str,
        stock: int = 0,
        low_stock_threshold: int = 5,
        expiring_soon_days: int = 7,
    ) -> None:
        super().__init__(name, sku, price, stock, low_stock_threshold)
        self.expiry_date = expiry_date
        self.expiring_soon_days = expiring_soon_days

    @property
    def expiry_date(self) -> date:
        """The last day the product is good to sell."""
        return self._expiry_date

    @expiry_date.setter
    def expiry_date(self, value: date | str) -> None:
        if isinstance(value, datetime):
            value = value.date()
        elif isinstance(value, str):
            try:
                value = date.fromisoformat(value.strip())
            except ValueError:
                raise ValueError(
                    f"Invalid expiry date {value!r}: expected a real date "
                    "in YYYY-MM-DD format."
                ) from None
        elif not isinstance(value, date):
            raise ValueError(
                "Expiry date must be a date or a 'YYYY-MM-DD' string "
                f"(got {type(value).__name__})."
            )
        self._expiry_date = value

    def days_until_expiry(self, today: date | None = None) -> int:
        """Whole days until expiry; negative if already expired."""
        return (self.expiry_date - (today or date.today())).days

    def is_expired(self, today: date | None = None) -> bool:
        """Return True once the expiry date has passed."""
        return self.days_until_expiry(today) < 0

    def is_expiring_soon(self, today: date | None = None) -> bool:
        """Return True if not yet expired but within ``expiring_soon_days``."""
        return 0 <= self.days_until_expiry(today) <= self.expiring_soon_days

    def expiry_alert(self, today: date | None = None) -> str | None:
        """Describe the expiry problem, or return ``None`` if there is none."""
        days = self.days_until_expiry(today)
        if days < 0:
            return f"EXPIRED {-days}d ago"
        if days == 0:
            return "EXPIRES TODAY"
        if days <= self.expiring_soon_days:
            return f"EXPIRES in {days}d"
        return None

    def alerts(self, today: date | None = None) -> list[str]:
        """Expiry alert (if any) followed by the standard low-stock alert."""
        expiry = self.expiry_alert(today)
        return ([expiry] if expiry else []) + super().alerts(today)

    def detail(self) -> str:
        """Show the expiry date in reports."""
        return f"exp {self.expiry_date.isoformat()}"

    def _repr_fields(self) -> dict[str, Any]:
        fields = super()._repr_fields()
        fields["expiry_date"] = self.expiry_date.isoformat()
        fields["expiring_soon_days"] = self.expiring_soon_days
        return fields

    def __str__(self) -> str:
        return f"{super().__str__()}, expires {self.expiry_date.isoformat()}"
