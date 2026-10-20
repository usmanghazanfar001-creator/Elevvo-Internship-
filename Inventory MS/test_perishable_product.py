"""Tests for PerishableProduct expiry behaviour."""

from datetime import date, datetime

import pytest

from inventory import PerishableProduct

TODAY = date(2026, 10, 20)


def make(expiry: date | str, **kwargs: int) -> PerishableProduct:
    return PerishableProduct("Milk", "M-1", 2.0, expiry, stock=10, **kwargs)


def test_days_until_expiry() -> None:
    assert make("2026-10-25").days_until_expiry(TODAY) == 5
    assert make("2026-10-20").days_until_expiry(TODAY) == 0
    assert make("2026-10-18").days_until_expiry(TODAY) == -2


def test_is_expired_only_after_expiry_date() -> None:
    assert not make("2026-10-20").is_expired(TODAY)  # last good day
    assert make("2026-10-19").is_expired(TODAY)


def test_expiring_soon_window() -> None:
    assert make("2026-10-27").is_expiring_soon(TODAY)  # exactly 7 days
    assert not make("2026-10-28").is_expiring_soon(TODAY)
    assert not make("2026-10-19").is_expiring_soon(TODAY)  # expired, not "soon"
    assert make("2026-10-28", expiring_soon_days=10).is_expiring_soon(TODAY)


@pytest.mark.parametrize(
    ("expiry", "expected"),
    [
        ("2026-10-18", "EXPIRED 2d ago"),
        ("2026-10-20", "EXPIRES TODAY"),
        ("2026-10-23", "EXPIRES in 3d"),
        ("2026-12-01", None),
    ],
)
def test_expiry_alert(expiry: str, expected: str | None) -> None:
    assert make(expiry).expiry_alert(TODAY) == expected


def test_alerts_combine_expiry_and_low_stock() -> None:
    item = PerishableProduct("Milk", "M-1", 2.0, "2026-10-19", stock=2)
    assert item.status(TODAY) == "EXPIRED 1d ago, LOW STOCK"


def test_healthy_item_status_is_ok() -> None:
    assert make("2026-12-01").status(TODAY) == "OK"


def test_expiry_accepts_date_datetime_and_iso_string() -> None:
    expected = date(2026, 11, 1)
    assert make(expected).expiry_date == expected
    assert make(datetime(2026, 11, 1, 8, 30)).expiry_date == expected
    assert make(" 2026-11-01 ").expiry_date == expected


@pytest.mark.parametrize("bad", ["2026-02-30", "tomorrow", "", "01/11/2026"])
def test_invalid_expiry_string_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="Invalid expiry date"):
        make(bad)


def test_non_date_expiry_rejected() -> None:
    with pytest.raises(ValueError, match="must be a date"):
        make(20261101)  # type: ignore[arg-type]


def test_invalid_expiry_via_setter_keeps_old_value() -> None:
    item = make("2026-11-01")
    with pytest.raises(ValueError):
        item.expiry_date = "not-a-date"
    assert item.expiry_date == date(2026, 11, 1)


def test_inherits_stock_validation() -> None:
    with pytest.raises(ValueError, match="Stock cannot be negative"):
        PerishableProduct("Milk", "M-1", 2.0, "2026-11-01", stock=-1)


def test_str_and_repr_include_expiry() -> None:
    item = make("2026-11-01")
    assert str(item).endswith("expires 2026-11-01")
    assert "expiry_date='2026-11-01'" in repr(item)
    assert repr(item).startswith("PerishableProduct(")
