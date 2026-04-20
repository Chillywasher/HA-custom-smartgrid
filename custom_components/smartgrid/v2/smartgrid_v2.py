import json
import math
import itertools
import logging

from datetime import datetime, timedelta
from typing import Callable

from ..dataclass import Rate, SmartGridDataSchedule
from .const import DATA_SCHEDULE, DATA_REPORT
from .model import Bucket, Schedule
from .print_table import PrintTable


_LOGGER = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d %H:%M"
KWH_DP = 3
N_CHEAPEST_RATES = 15
N_MAX_RATES = 24


class SmartGridV2:

    def __init__(
            self,
            get_battery_capacity: Callable[[], float],
            get_rates: Callable[[], tuple[Rate, ...]],
            get_battery_soc: Callable[[], float],
            get_battery_min_soc: Callable[[], float],
    ):

        self.get_battery_capacity = get_battery_capacity
        self.get_rates = get_rates
        self.get_battery_soc = get_battery_soc
        self.get_battery_min_soc = get_battery_min_soc

        self.battery_capacity = 0.0  # default only
        self.battery_soc = 100.0  # default only
        self.min_soc = 10.0  # default only
        self.max_charge = 4.5  # default only


    @property
    def min_level(self) -> float:
        """
        Converts minimum SoC to kWh
        """
        return self.battery_capacity / 100 * self.min_soc

    @property
    def battery_level(self) -> float:
        """
        Converts battery SoC to kWh
        """
        if self.battery_soc == 0:
            return 0
        return self.battery_capacity / 100 * self.battery_soc

    def start_program(self):

        self.battery_soc = self.get_battery_soc()  # listens to changes from the API
        self.min_soc = self.get_battery_min_soc()  # listens to changes from the API
        self.battery_capacity = self.get_battery_capacity()

        rates = self.get_rates()
        assert len(rates) > 0

        rates = rates[:N_MAX_RATES]

        cheapest_rates = list(rates)
        cheapest_rates.sort(key=lambda rate: rate.value_inc_vat)
        cheapest_periods = cheapest_rates[:N_CHEAPEST_RATES]

        loads = self.get_loads(rates)

        schedules: list[Schedule] = []

        for i in range(len(cheapest_periods)):

            for periods in itertools.combinations(cheapest_periods, i):
                schedule = self.calculate(rates, loads, self.battery_level, periods)
                total_cost = math.fsum([
                    bucket.cost
                    for bucket in schedule
                ])

                schedules.append(
                    Schedule(
                        buckets=schedule,
                        charging_periods=periods,
                        total_cost=total_cost 
                    )
                )

        schedules.sort(key=lambda s: s.total_cost)

        headings = ["From", "Bat Start", "SoC Start", "Load", "Force Charge",
                    "Grid", "Bat End", "SoC End", "Rate", "Cost"]

        sorted_schedules = schedules[:5]

        s_list = []

        new_schedule = []

        for schedule in sorted_schedules:

            buckets = schedule.buckets
            content = [
                [datetime.strftime(b.start_date, DATE_FORMAT) for b in buckets],
                [b.start_level for b in buckets],
                [round(100 / self.battery_capacity * b.start_level) for b in buckets],
                loads,
                [b.force_charge for b in buckets],
                [b.grid for b in buckets],
                [b.end_level for b in buckets],
                [round(100 / self.battery_capacity * b.end_level) for b in buckets],
                [b.rate for b in buckets],
                [b.cost for b in buckets]
            ]

            pt = PrintTable(headings=headings, content=content)
            print(pt.print_table())
            print(f"£{schedule.total_cost}")

            new_schedule.append(
                SmartGridDataSchedule(
                    end=[b.start_date + timedelta(minutes=30) for b in buckets],
                    loads=loads,
                    rates=[b.rate for b in buckets],
                    solar=[0] * 8,
                    start=[b.start_date for b in buckets],
                    charging_periods=schedule.charging_periods,
                    total_cost=0,
                    battery_end=[b.end_level for b in buckets],
                    battery_start=[b.start_level for b in buckets],
                    cost=[b.cost for b in buckets],
                    grid=[b.grid for b in buckets],
                    soc_end=[round(100 / self.battery_capacity * b.end_level) for b in buckets],
                    soc_start=[round(100 / self.battery_capacity * b.start_level) for b in buckets],

            ))

            periods = [
                str(s.start.hour).zfill(2) + ":" +
                str(s.start.minute).zfill(2)
                for s in schedule.charging_periods
            ]
            periods.sort()
            s_list.append({
                "Total cost (£)": round(schedule.total_cost, 2),
                "Charging periods": periods
            })

        return {
            DATA_SCHEDULE: sorted_schedules[0],
            DATA_REPORT: {
                "title": f"Top 5 schedules",
                "data": s_list
            }
        }

    def calculate(
            self,
            rates: tuple[Rate, ...],
            loads: list[float],
            start_level: float,
            force_charge_periods: tuple[Rate, ...]
    ) -> list[Bucket]:

        buckets = []

        for i in range(len(rates)):

            grid = 0
            cost = 0
            rate = rates[i].value_inc_vat
            load = loads[i]

            force_charge = rates[i] in force_charge_periods

            # energy is needed from the grid if the load exceeds the battery min level
            if start_level - load < self.min_level:
                grid += abs(start_level - self.min_level - load)

            # even more energy needed from grid for a force charge
            if force_charge:
                potential_charge = self.battery_capacity - start_level
                if potential_charge >= self.max_charge:
                    grid += self.max_charge
                else:
                    grid += potential_charge

            end_level = start_level - load + grid

            if grid > 0:
                cost = grid * rate

            bucket = Bucket(
                start_date=rates[i].start,
                start_level=round(start_level, KWH_DP),
                rate=rate,
                load=round(load, KWH_DP),
                cost=round(cost, 2),
                force_charge=force_charge,
                grid=round(grid, KWH_DP),
                end_level=round(end_level, KWH_DP)
            )

            buckets.append(bucket)
            start_level = end_level

        return buckets

    @staticmethod
    def get_loads(rates: tuple[Rate, ...]):
        """
        Implement getting loads here
        """
        with open("./loads.json", "r") as file:
            data = json.load(file)
        loads = data["loads"]
        assert len(loads) == 48

        def get_load(dt: datetime) -> float:
            base = datetime(dt.year, dt.month, dt.day, 0, 0, 0).astimezone()
            assert dt >= base
            assert dt.minute == 0 or dt.minute == 30
            index = int((dt - base).total_seconds() / 60 / 30)
            return loads[index]

        return [
            get_load(rate.start)
            for rate in rates
        ]
