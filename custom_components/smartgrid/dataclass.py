from datetime import datetime
from dataclasses import dataclass

#
# @dataclass
# class BatteryScheduleModel:
#     date_on: datetime
#     date_off: datetime
#     rate: float


@dataclass
class RatesModel:
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
    battery_capacity_wh: float
    enable_battery_controller: bool
    inverter_keepalive_per_period_wh: float
    inverter_minimum_energy: float
    loads_energy_profile: str
    maximum_charge_per_period_wh: float
    minimum_battery_level_wh: float
    n_cheapest_rates: int
    solar_energy_profile: str
    rates_limit: int

# @dataclass
# class SmartGridScheduleModel:
#     period_from: datetime
#     period_to: datetime
#     battery_start: float
#     loads: float
#     solar: float
#     battery_end: float
#     soc_start: int
#     soc_end: int
#     rates: float
#     grid: float
#     cost: float
#     force_charge: bool
#     last_updated: datetime


@dataclass
class SmartGridDataSchedule:
    end: list[datetime]
    loads: list[float]
    rates: list[float]
    solar: list[float]
    start: list[datetime]
    force_charge: list[datetime]
    total_cost: float = 0
    battery_end: list[float] | None = None
    battery_start: list[float] | None = None
    cost: list[float] | None = None
    grid: list[float] | None = None
    soc_end: list[float] | None = None
    soc_start: list[float] | None = None
    iteration: int = 0
    subiteration: int = 0