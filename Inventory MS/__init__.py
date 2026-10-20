"""A small object-oriented inventory management library."""

from inventory.inventory import Inventory
from inventory.product import PerishableProduct, Product

__all__ = ["Inventory", "PerishableProduct", "Product"]
