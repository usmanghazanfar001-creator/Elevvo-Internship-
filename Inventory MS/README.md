# Inventory Management System

A small, dependency-free, object-oriented inventory manager in Python. It tracks
products by SKU, validates stock and prices, raises low-stock alerts, and
handles perishable goods with expiry tracking.

## Features

- **`Product`**: name, SKU, price, stock quantity and low-stock threshold.
- **`PerishableProduct`** (subclass): expiry date, `is_expired()`,
  `days_until_expiry()`, `is_expiring_soon()` and an expiry alert that is merged
  into the normal status/report.
- **Validation with `@property`** only where it is needed: price and stock
  cannot be negative, the expiry date must be a real date. Errors are clear
  `ValueError` messages.
- **`Inventory`**: add products (duplicate SKUs rejected), add stock, remove stock
  (removing more than available is rejected), low-stock alerts, expiry alerts
  and an aligned table report built with f-strings.
- `__str__` / `__repr__` on the product classes for clean printing and debugging.
- Pytest suite (43 tests) and a demo script.

## Project structure

```
.
├── inventory/
│   ├── __init__.py
│   ├── product.py        # Product, PerishableProduct
│   └── inventory.py      # Inventory
├── tests/
│   ├── test_product.py
│   ├── test_perishable_product.py
│   └── test_inventory.py
├── main.py               # demo script
├── pytest.ini
├── requirements.txt
└── README.md
```

## How to run

Requires Python 3.10+ (the library itself uses only the standard library).

```bash
python main.py
```

The demo uses a fixed "today" (2026-10-20) so its output is reproducible. In your
own code, omit the `today` argument and the current date is used.

### Quick usage

```python
from inventory import Inventory, PerishableProduct, Product

inv = Inventory()
inv.add_product(Product("Notebook", "STAT-001", 3.25, stock=120))
inv.add_product(PerishableProduct("Milk", "DAIRY-001", 1.89, "2026-10-22", stock=40))
inv.remove_stock("DAIRY-001", 5)
print(inv.report())
```

## How to run the tests

```bash
pip install -r requirements.txt
pytest
```

## Sample output

```text

=== Initial report ===
INVENTORY REPORT (as of 2026-10-20)
SKU       | Name            | Type       |  Price | Qty | Min |   Value | Details        | Status
----------+-----------------+------------+--------+-----+-----+---------+----------------+--------------------------
ELEC-001  | Laptop Stand    | Standard   | $34.99 |  25 |   5 | $874.75 |                | OK
ELEC-002  | USB-C Cable     | Standard   |  $9.50 |   4 |  10 |  $38.00 |                | LOW STOCK
STAT-001  | Notebook        | Standard   |  $3.25 | 120 |  20 | $390.00 |                | OK
DAIRY-001 | Whole Milk 1L   | Perishable |  $1.89 |  40 |  10 |  $75.60 | exp 2026-10-22 | EXPIRES in 2d
DAIRY-002 | Greek Yogurt    | Perishable |  $0.99 |   8 |  10 |   $7.92 | exp 2026-10-19 | EXPIRED 1d ago, LOW STOCK
BAKE-001  | Sourdough Bread | Perishable |  $4.50 |  15 |   5 |  $67.50 | exp 2026-10-30 | OK
FISH-001  | Fresh Salmon    | Perishable | $12.99 |   6 |   3 |  $77.94 | exp 2026-10-20 | EXPIRES TODAY
----------+-----------------+------------+--------+-----+-----+---------+----------------+--------------------------
7 products | total stock value $1,531.71 | 4 with alerts

=== Printing products (__str__ and __repr__) ===
Laptop Stand [ELEC-001] $34.99 x 25 in stock
Whole Milk 1L [DAIRY-001] $1.89 x 40 in stock, expires 2026-10-22
PerishableProduct(name='Whole Milk 1L', sku='DAIRY-001', price=1.89, stock=40, low_stock_threshold=10, expiry_date='2026-10-22', expiring_soon_days=7)

=== Add and remove stock ===
Restock ELEC-002 +30 -> 34 units
Sell DAIRY-001 -35    -> 5 units

=== Validation (all of these are rejected) ===
[rejected] remove 99 Sourdough: Cannot remove 99 units of BAKE-001: only 15 in stock.
[rejected] add 0 stock: Quantity must be greater than zero (got 0).
[rejected] negative price: Price cannot be negative (got -1.0).
[rejected] negative stock: Stock cannot be negative (got -3).
[rejected] impossible expiry date: Invalid expiry date '2026-02-30': expected a real date in YYYY-MM-DD format.
[rejected] duplicate SKU: A product with SKU 'ELEC-001' already exists.
[rejected] unknown SKU: No product with SKU 'NOPE-000' in the inventory.

=== Low-stock alerts ===
LOW STOCK: Whole Milk 1L [DAIRY-001] has 5 left (threshold 10)
LOW STOCK: Greek Yogurt [DAIRY-002] has 8 left (threshold 10)

=== Expiry alerts (most urgent first) ===
EXPIRED 1d ago: Greek Yogurt [DAIRY-002] (8 units, exp 2026-10-19)
EXPIRES TODAY: Fresh Salmon [FISH-001] (6 units, exp 2026-10-20)
EXPIRES in 2d: Whole Milk 1L [DAIRY-001] (5 units, exp 2026-10-22)

=== Perishable behaviour ===
Whole Milk 1L: expired=False, days left=2, expiring soon=True

=== Final report ===
INVENTORY REPORT (as of 2026-10-20)
SKU       | Name            | Type       |  Price | Qty | Min |   Value | Details        | Status
----------+-----------------+------------+--------+-----+-----+---------+----------------+--------------------------
ELEC-001  | Laptop Stand    | Standard   | $34.99 |  25 |   5 | $874.75 |                | OK
ELEC-002  | USB-C Cable     | Standard   |  $9.50 |  34 |  10 | $323.00 |                | OK
STAT-001  | Notebook        | Standard   |  $3.25 | 120 |  20 | $390.00 |                | OK
DAIRY-001 | Whole Milk 1L   | Perishable |  $1.89 |   5 |  10 |   $9.45 | exp 2026-10-22 | EXPIRES in 2d, LOW STOCK
DAIRY-002 | Greek Yogurt    | Perishable |  $0.99 |   8 |  10 |   $7.92 | exp 2026-10-19 | EXPIRED 1d ago, LOW STOCK
BAKE-001  | Sourdough Bread | Perishable |  $4.50 |  15 |   5 |  $67.50 | exp 2026-10-30 | OK
FISH-001  | Fresh Salmon    | Perishable | $12.99 |   6 |   3 |  $77.94 | exp 2026-10-20 | EXPIRES TODAY
----------+-----------------+------------+--------+-----+-----+---------+----------------+--------------------------
7 products | total stock value $1,750.56 | 3 with alerts
```

## Design notes

- **Polymorphic alerts.** `Product.alerts()` returns the low-stock alert;
  `PerishableProduct.alerts()` adds expiry alerts on top. `Inventory.report()` just
  calls `status()` and never checks types, so new product types need no changes there.
- **Testable dates.** Every date-dependent method accepts an optional `today`.
- **Low stock is inclusive**: stock `<=` threshold counts as low.
- **Expiry**: an item is good through its expiry date and expired the day after.
