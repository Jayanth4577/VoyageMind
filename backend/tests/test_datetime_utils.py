"""Datetime + currency util edge cases (spec §4.4/§4.6)."""
import pytest

from app.utils.currency_utils import allocate_budget, convert_amount
from app.utils.datetime_utils import add_minutes, gap_minutes, minutes_to_hhmm, parse_hhmm


def test_parse_hhmm_valid():
    assert parse_hhmm("00:00") == 0
    assert parse_hhmm("10:30") == 630
    assert parse_hhmm("23:59") == 1439


@pytest.mark.parametrize("bad", ["", "24:00", "12:60", "abc", "10", "10:3x", "-1:00"])
def test_parse_hhmm_invalid(bad):
    assert parse_hhmm(bad) is None


def test_roundtrip():
    assert minutes_to_hhmm(parse_hhmm("09:05")) == "09:05"
    assert minutes_to_hhmm(0) == "00:00"


def test_add_minutes():
    assert add_minutes("10:00", 90) == "11:30"
    assert add_minutes("23:30", 60) == "24:30"  # crosses midnight; caller decides policy
    assert add_minutes("bad", 10) is None


def test_gap_minutes():
    assert gap_minutes("12:00", "12:45") == 45
    assert gap_minutes("12:00", "11:00") == -60  # overlap detection uses this
    assert gap_minutes("", "11:00") is None


def test_convert_amount():
    assert convert_amount(100, 0.5) == 50.0
    assert convert_amount(100, 0.856) == 85.6
    assert convert_amount(3, 1 / 3) == 1.0


def test_allocate_budget_exact_sum():
    weights = {"transport": 3, "accommodation": 4, "food": 2, "buffer": 1}
    allocation = allocate_budget(50000, weights)
    assert sum(allocation.values()) == 50000
    assert allocation["accommodation"] == 20000
    assert allocation["buffer"] == 5000


def test_allocate_budget_rejects_bad_input():
    with pytest.raises(ValueError):
        allocate_budget(-1, {"a": 1})
    with pytest.raises(ValueError):
        allocate_budget(100, {"a": 0})
