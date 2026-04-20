from datetime import datetime
from dataclasses import dataclass


@dataclass
class Rate:
    start: datetime
    end: datetime
    value_inc_vat: float


@dataclass
class SmartGridPeriod:
    hour: int
    minute: int
    energy: float


@dataclass
class SmartGridConfigModel:
    # battery_capacity_kwh: float
    # enable_battery_controller: bool
    inverter_keepalive_per_period_kwh: float
    inverter_minimum_energy: float
    # loads_energy_profile: str
    maximum_charge_per_period_kwh: float
    minimum_battery_level_kwh: float
    n_cheapest_rates: int
    rates_limit: int


@dataclass
class SmartGridDataSchedule:
    end: list[datetime]
    loads: list[float]
    rates: list[float]
    solar: list[float]
    start: list[datetime]
    charging_periods: tuple[Rate, ...]
    total_cost: float = 0
    battery_end: list[float] | None = None
    battery_start: list[float] | None = None
    cost: list[float] | None = None
    grid: list[float] | None = None
    soc_end: list[float] | None = None
    soc_start: list[float] | None = None
