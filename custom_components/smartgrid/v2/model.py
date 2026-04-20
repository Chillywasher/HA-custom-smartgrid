from dataclasses import dataclass
from datetime import datetime

from ..dataclass import Rate

@dataclass
class Bucket:
    start_date: datetime
    start_level: float
    load: float
    rate: float
    cost: float
    force_charge: bool
    grid: float
    end_level: float


@dataclass
class Schedule:
    buckets: list[Bucket]
    charging_periods: tuple[Rate, ...]
    total_cost: float