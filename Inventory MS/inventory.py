"""The :class:`Inventory` that manages a collection of products by SKU."""

from __future__ import annotations

from datetime import date
from typing import Iterator, Sequence

from inventory.product import PerishableProduct, Product

_HEADERS = ("SKU", "Name", "Type", "Price", "Qty", "Min", "Value", "Details", "Status")
_RIGHT_ALIGNED = {"Price", "Qty", "Min", "Value"}


class Inventory:
    """A collection of products keyed by their unique SKU."""

    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    # ------------------------------------------------------------------
    # Container helpers
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._products)

    def __iter__(self) -> Iterator[Product]:
        return iter(self._products.values())

    def __contains__(self, sku: object) -> bool:
        return sku in self._products

    def __repr__(self) -> str:
        return f"Inventory(products={len(self)})"

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    def add_product(self, product: Product) -> None:
        """Register a new product.

        Raises:
            ValueError: If a product with the same SKU already exists.
        """
        if product.sku in self._products:
            raise ValueError(f"A product with SKU {product.sku!r} already exists.")
        self._products[product.sku] = product

    def get_product(self, sku: str) -> Product:
        """Return the product with ``sku``.

        Raises:
            KeyError: If no such product exists.
        """
        try:
            return self._products[sku]
        except KeyError:
            raise KeyError(f"No product with SKU {sku!r} in the inventory.") from None

    def add_stock(self, sku: str, quantity: int) -> int:
        """Add stock to a product and return its new stock level."""
        return self.get_product(sku).add_stock(quantity)

    def remove_stock(self, sku: str, quantity: int) -> int:
        """Remove stock from a product and return its new stock level.

        Raises:
            ValueError: If more than the available stock is requested.
        """
        return self.get_product(sku).remove_stock(quantity)

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------
    def low_stock_products(self) -> list[Product]:
        """Return every product at or below its low-stock threshold."""
        return [product for product in self if product.is_low_stock()]

    def low_stock_alerts(self) -> list[str]:
        """Return a readable alert line per low-stock product."""
        return [
            f"LOW STOCK: {p.name} [{p.sku}] has {p.stock} left "
            f"(threshold {p.low_stock_threshold})"
            for p in self.low_stock_products()
        ]

    def expiry_alerts(self, today: date | None = None) -> list[str]:
        """Return alert lines for expired or soon-to-expire perishables.

        The most urgent (earliest expiry) items come first.
        """
        flagged = sorted(
            (
                p
                for p in self
                if isinstance(p, PerishableProduct) and p.expiry_alert(today)
            ),
            key=lambda p: p.expiry_date,
        )
        return [
            f"{p.expiry_alert(today)}: {p.name} [{p.sku}] "
            f"({p.stock} units, exp {p.expiry_date.isoformat()})"
            for p in flagged
        ]

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def report(self, today: date | None = None) -> str:
        """Return an aligned, human-readable table of the whole inventory."""
        today = today or date.today()
        title = f"INVENTORY REPORT (as of {today.isoformat()})"
        if not self._products:
            return f"{title}\nInventory is empty."

        rows = [
            (
                p.sku,
                p.name,
                p.kind,
                f"${p.price:,.2f}",
                str(p.stock),
                str(p.low_stock_threshold),
                f"${p.total_value:,.2f}",
                p.detail(),
                p.status(today),
            )
            for p in self
        ]
        widths = [
            max(len(cell) for cell in column) for column in zip(_HEADERS, *rows)
        ]
        aligns = ["<" if h not in _RIGHT_ALIGNED else ">" for h in _HEADERS]

        header = self._format_row(_HEADERS, widths, aligns)
        divider = "-+-".join("-" * width for width in widths)
        body = [self._format_row(row, widths, aligns) for row in rows]

        total_value = sum(p.total_value for p in self)
        alert_count = sum(1 for p in self if p.alerts(today))
        summary = (
            f"{len(self)} products | total stock value ${total_value:,.2f} "
            f"| {alert_count} with alerts"
        )
        return "\n".join([title, header, divider, *body, divider, summary])

    @staticmethod
    def _format_row(
        cells: Sequence[str], widths: Sequence[int], aligns: Sequence[str]
    ) -> str:
        """Pad each cell to its column width and join them into one line."""
        padded = (
            f"{cell:{align}{width}}"
            for cell, width, align in zip(cells, widths, aligns)
        )
        return " | ".join(padded).rstrip()
