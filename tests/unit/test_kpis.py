"""Unit tests for KPI calculations (documented definitions)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.kpis import (customs_sla_breach_rate, fuel_efficiency,
                                otd_rate, warehouse_utilization)


def test_otd_rate_basic():
    # 4 on-time out of 5 delivered -> 80%
    assert otd_rate(4, 5) == 80.0


def test_otd_rate_zero_delivered():
    assert otd_rate(0, 0) is None


def test_otd_rate_all_on_time():
    assert otd_rate(10, 10) == 100.0


def test_warehouse_utilization():
    assert warehouse_utilization(5000, 10000) == 50.0


def test_warehouse_utilization_zero_capacity():
    assert warehouse_utilization(100, 0) is None


def test_fuel_efficiency():
    assert fuel_efficiency(345, 100) == 3.45


def test_fuel_efficiency_zero_fuel():
    assert fuel_efficiency(100, 0) is None


def test_customs_sla_breach_rate():
    assert customs_sla_breach_rate(10, 100) == 10.0


def test_customs_sla_breach_rate_no_cleared():
    assert customs_sla_breach_rate(5, 0) is None
