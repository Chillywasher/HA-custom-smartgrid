import itertools
import logging
import math
import operator

from datetime import datetime

from homeassistant.core import HomeAssistant

from .dataclass import Rate, SmartGridConfigModel, SmartGridPeriod, SmartGridDataSchedule
from .const import HOUR, MINUTE, START, END, VALUE_INC_VAT, ENERGY, DATA_SCHEDULE, DATA_REPORT, TOTAL_COST

_LOGGER = logging.getLogger(__name__)


class SmartGrid:

    def __init__(
            self,
            hass: HomeAssistant,
            battery_soc_sensor: str,
            battery_capacity_sensor: str,
            current_rates_sensor: str,
            next_day_rates_sensor: str
    ):
        self.hass = hass
        self.battery_soc_sensor = battery_soc_sensor
        self.battery_capacity_sensor = battery_capacity_sensor
        self.current_rates_sensor = current_rates_sensor
        self.next_day_rates_sensor = next_day_rates_sensor
        self.battery_capacity: float = 0
        self.battery_level: float = 0
        self.config = SmartGridConfigModel(
            n_cheapest_rates=12,
            inverter_minimum_energy=0,
            inverter_keepalive_per_period_kwh=0.1,
            maximum_charge_per_period_kwh=4.5,
            minimum_battery_level_kwh=1.5,
            rates_limit=36,
        )
        self.sensor_timestamp = None
        self.initial_offset_set = False
        self.rates: list[Rate] = []

    def start_program(self) -> dict:

        self.set_rates() # needs calling each time to get latest rates

        self.set_battery_level()

        template = self.get_schedule_template()

        schedules = self.calculate_schedules(
            start_battery_level=self.battery_level,
            template=template
        )

        sort_cost = operator.attrgetter(TOTAL_COST)
        sorted_schedules = sorted(schedules, key=sort_cost)


        trim = 5
        s_list = []
        for schedule in sorted_schedules[:trim]:
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
        if sorted_schedules:
            return {
                DATA_SCHEDULE: sorted_schedules[0],
                DATA_REPORT: {
                    "title": f"Top {trim} schedules",
                    "data": s_list
                }
            }
        return {}

    def get_schedule_template(self) -> SmartGridDataSchedule:
        """
        Provides a base template DataFrame for cost analysis
        Creates half-hourly time periods based on available rates from Octopus
        Adds rates values as column
        Adds loads profile
        Adds solar profile
        """

        rates_values = [float(rate.value_inc_vat) for rate in self.rates]
        start_values = [rate.start for rate in self.rates]
        end_values = [rate.end for rate in self.rates]

        loads = [
            {
                HOUR: 0,
                MINUTE: 0,
                ENERGY: 9600,
            },
            {
                HOUR: 8,
                MINUTE: 0,
                ENERGY: 12000,
            },
            {
                HOUR: 16,
                MINUTE: 0,
                ENERGY: 8000,
            },
            {
                HOUR: 20,
                MINUTE: 0,
                ENERGY: 7000,
            }
        ]

        solar = [
                {
                    HOUR: 0,
                    MINUTE: 0,
                    ENERGY: 0,
                }
            ]

        sorted_loads = self.validate_periods(loads)
        sorted_solar = self.validate_periods(solar)

        loads_values = self.profile_as_list(
            date_range=start_values,
            periods=sorted_loads
        )

        solar_values = self.profile_as_list(
            date_range=start_values,
            periods=sorted_solar
        )

        return SmartGridDataSchedule(
            start=start_values,
            end=end_values,
            loads=loads_values,
            solar=solar_values,
            rates=rates_values,
            charging_periods=()
        )

    def calculate_schedules(
            self,
            start_battery_level: float,
            template: SmartGridDataSchedule
    ) -> list[SmartGridDataSchedule]:

        # need to find the datetimes of the cheapest rates
        # create a tuple pair of datetime & rate
        cheapest: list[tuple[datetime, float]] = [
            (template.start[i], template.rates[i])
            for i in range(0, len(template.start))
        ]
        cheapest.sort(key=lambda tup: tup[1])
        cheapest = cheapest[:self.config.n_cheapest_rates]
        # sorted tuples by rate value, now grab the dates
        cheapest_periods: list[datetime] = [tup[0] for tup in cheapest]

        # compile results
        results: list[SmartGridDataSchedule] = []
        iterations = 0
        calculation_start_time = datetime.now()

        _LOGGER.info("Starting main calculation loop")

        for i in range(len(cheapest_periods)):

            subiterations = 0
            _LOGGER.info(f"Calculating schedule {i + 1}/{len(cheapest_periods)}")

            iteration_start_time = datetime.now()

            for periods in itertools.combinations(cheapest_periods, i):

                # sch = [str(s.hour).zfill(2) + ":" + str(s.minute).zfill(2) for s in periods]
                # sch.sort()
                # print(sch)

                schedule = self.calculate_schedule(
                    config=self.config,
                    charging_periods=periods,
                    start_battery_level=start_battery_level,
                    template=template
                )
                assert schedule not in results
                results.append(schedule)

                subiterations += 1

            seconds = (datetime.now() - iteration_start_time).total_seconds()
            _LOGGER.info(f"completed {subiterations} iterations in "
                         f"{seconds}s "
                         f"avg time: {subiterations / seconds}s")
            iterations += subiterations

        calculation_end_time = datetime.now()
        secs = (calculation_end_time - calculation_start_time).total_seconds()

        _LOGGER.info(
            f"Main calculation loop took {secs:0.0f}s for {iterations} iterations"
        )

        return results

    def calculate_schedule(
            self,
            config: SmartGridConfigModel,
            charging_periods: tuple,
            start_battery_level: float,
            template: SmartGridDataSchedule,
    ) -> SmartGridDataSchedule:

        # values pre-populated in template
        start_values = template.start
        end_values = template.end
        loads_values = template.loads
        solar_values = template.solar
        rates_values = template.rates

        # values that need calculating
        force_charge_values: list[Rate] = []
        battery_start_values: list[float] = []
        battery_end_values: list[float] = []
        soc_start_values: list[float] = []
        soc_end_values: list[float] = []
        grid_values: list[float] = []
        cost_values: list[float] = []

        index = 0
        for start in start_values:

            grid = 0
            loads = template.loads[index]
            solar = template.solar[index]

            if start in charging_periods:
                force_charge = True
            else:
                force_charge = False

            soc_start = 100 / self.battery_capacity * start_battery_level

            if force_charge:
                grid = self.force_charge_result(
                    battery_level=start_battery_level + solar - loads,
                    max_force_charge=config.maximum_charge_per_period_kwh,
                    max_battery_level=self.battery_capacity
                )
                force_charge_values.append(
                    Rate(
                        start=start_values[index],
                        end=end_values[index],
                        value_inc_vat=rates_values[index]
                    )
                )

            end_battery_level = self.charge_battery_result(
                battery_level=start_battery_level,
                add_level=solar + grid - loads,
                max_battery_level=self.battery_capacity,
                min_battery_level=config.minimum_battery_level_kwh
            )

            if not force_charge:
                # energy needs to be pulled from grid when battery is empty (e.g. < 10%)
                # grid value will be zero when force charging has not been predefined
                grid = self.pull_grid_result(
                    battery_level=end_battery_level,
                    loads=loads,
                    min_battery_level=config.minimum_battery_level_kwh,
                    inverter_keepalive_per_period_kwh=config.inverter_keepalive_per_period_kwh
                )

            soc_end = 100 / self.battery_capacity * end_battery_level

            grid_values.append(grid)
            battery_end_values.append(end_battery_level)
            soc_start_values.append(soc_start)
            soc_end_values.append(soc_end)
            cost = grid * template.rates[index]
            cost_values.append(cost)
            battery_start_values.append(start_battery_level)

            start_battery_level = end_battery_level
            index += 1

        # fatal errors:
        test = len(self.rates)
        assert len(battery_end_values) == test
        assert len(battery_start_values) == test
        assert len(cost_values) == test
        assert len(end_values) == test
        # force_charge is variable
        assert len(grid_values) == test
        assert len(loads_values) == test
        assert len(rates_values) == test
        assert len(soc_end_values) == test
        assert len(soc_start_values) == test
        assert len(solar_values) == test
        assert len(start_values) == test

        return SmartGridDataSchedule(
            battery_end=battery_end_values,
            battery_start=battery_start_values,
            cost=cost_values,
            end=end_values,
            charging_periods=tuple(force_charge_values),
            grid=grid_values,
            loads=loads_values,
            rates=rates_values,
            soc_end=soc_end_values,
            soc_start=soc_start_values,
            solar=solar_values,
            start=start_values,
            total_cost=math.fsum(cost_values)
        )


    @staticmethod
    def validate_periods(periods_dict: list[dict]) -> list[SmartGridPeriod]:

        periods = [
            SmartGridPeriod(
                hour=p[HOUR],
                minute=p[MINUTE],
                energy=p[ENERGY],
            )
            for p in periods_dict
        ]

        # must be at least one period
        if len(periods) == 0:
            raise Exception("Profile must contain at least one period")
        # first period must be midnight
        if periods[0].hour != 0 or periods[0].minute != 0:
            raise Exception("First period in profile must start at midnight")

        enforce_unique = []

        for p in periods:
            if p.hour < 0 or p.minute < 0 or p.hour > 23 or p.minute > 59:
                raise Exception(f"Invalid period time: {p.hour}:{p.minute}")
            enforce = str(p.hour + p.minute)
            if enforce in enforce_unique:
                raise Exception(f"Duplicate periods detected: {p.hour}:{p.minute}")
            else:
                enforce_unique.append(enforce)

        # After validation return sorted periods
        sorted_periods = sorted(periods, key=operator.attrgetter(HOUR, MINUTE))
        return sorted_periods

    @staticmethod
    def profile_as_list(
            periods: list[SmartGridPeriod],
            date_range: list[datetime]
    ):

        def calculate_energy_per_charging_period(
                hour: int,
                minute: int
        ):

            for i in range(0, len(periods)):

                # NB year month and day are irrelevant here

                start = datetime(2024, 1, 1, periods[i].hour, periods[i].minute, 0, 0)

                if i + 1 < len(periods):
                    end = datetime(2024, 1, 1, periods[i + 1].hour, periods[i + 1].minute, 0, 0)
                else:
                    end = datetime(2024, 1, 2, 0, 0, 0, 0)

                test_time = datetime(2024, 1, 1, hour, minute, 0, 0)

                if start <= test_time < end:
                    duration_mins = int((end - start).total_seconds() / 60)
                    energy = periods[i].energy
                    energy /= 1000
                    return (energy / duration_mins) * 30 # mins

            raise Exception("An unexpected error ocurred")

        result = [
            calculate_energy_per_charging_period(time.hour, time.minute)
            for time in date_range
        ]

        return result

    @staticmethod
    def force_charge_result(
            battery_level: float,
            max_force_charge: float,
            max_battery_level: float
    ) -> float:
        """
        returns how much energy will need to be provided by the grid to charge the battery
        when force charging
        :param battery_level: the current battery level in kWh
        :param max_force_charge: the maximum amount of battery charge energy in kWh
        :param max_battery_level: the capacity of the battery in kWh
        :return: the actual amount the battery charged by in kWh
        """

        # TODO: If this is the current charging period then the max_force_charge has to be a
        # proprotion of the time remaining in the period

        if battery_level + max_force_charge <= max_battery_level:
            return max_force_charge
        else:
            return max_battery_level - battery_level

    @staticmethod
    def pull_grid_result(
            battery_level: float,
            loads: float,
            min_battery_level: float,
            inverter_keepalive_per_period_kwh: float
    ) -> float:
        """
        returns how much energy will need to be pulled from grid based on current battery level
        when NOT force charging
        :param inverter_keepalive_per_period_kwh: think this has to do with the inverter always pulling a
        trivial amount of energy from the grid (i.e. keep-alive so it knows it is connected to grid)
        :param battery_level:
        :param loads:
        :param min_battery_level:
        :return:
        """
        actual_level: float = battery_level - min_battery_level
        new_level: float = actual_level - loads
        if new_level < 0:
            return abs(new_level)

        return inverter_keepalive_per_period_kwh

    @staticmethod
    def charge_battery_result(
            battery_level: float,
            add_level: float,
            max_battery_level: float,
            min_battery_level: float
    ) -> float:
        """
        returns new battery level given current level and amount of positive/negative charge/discharge
        :param battery_level:
        :param add_level:
        :param max_battery_level:
        :param min_battery_level:
        :return:
        """
        proposed_level = battery_level + add_level

        if proposed_level > max_battery_level:
            return float(max_battery_level)

        elif proposed_level < min_battery_level:
            return float(min_battery_level)

        else:
            return float(proposed_level)

    def set_rates(self):
        try:
            rates1 = self.hass.states.get(self.current_rates_sensor).attributes.get("rates")
            current_rates = [
                Rate(
                    start=r[START],
                    end=r[END],
                    value_inc_vat=r[VALUE_INC_VAT],
                )
                for r in rates1 if r[END] > datetime.now().astimezone()
            ]
        except:
            raise Exception(f"Cannot obtain current rates from '{self.current_rates_sensor}'")
        try:
            rates2 = self.hass.states.get(self.next_day_rates_sensor).attributes.get("rates")
            next_day_rates = [
                Rate(
                    start=r[START],
                    end=r[END],
                    value_inc_vat=r[VALUE_INC_VAT],
                )
                for r in rates2
            ]
        except:
            raise Exception(f"Cannot obtain next day rates from '{self.next_day_rates_sensor}'")

        if next_day_rates:
            rates = current_rates + next_day_rates
        else:
            rates = current_rates

        self.rates = rates[:self.config.rates_limit]

        _LOGGER.info(f"Using {len(self.rates)} rates of {len(rates)}")


    def set_battery_level(self):
        """
        Battery level is calculated by getting the current SoC reading
        and converting it to kWh based on the maximum battery capacity
        """
        #--------------------------------------------------------------------------------
        # GET BATTERY CAPACITY
        #--------------------------------------------------------------------------------
        _LOGGER.info(f"Querying {self.battery_capacity_sensor} for battery capacity kWh")
        try:
            battery_capacity = float(self.hass.states.get(self.battery_capacity_sensor).state)
        except BatteryCapacityUnobtainableException as err:
            _LOGGER.error(err)
            raise Exception(err)
        _LOGGER.info(f"Obtained battery capacity reading of {battery_capacity} kWh")

        #--------------------------------------------------------------------------------
        # GET BATTERY SOC
        #--------------------------------------------------------------------------------
        _LOGGER.info(f"Querying {self.battery_soc_sensor} for battery soc %")
        try:
            soc = float(self.hass.states.get(self.battery_soc_sensor).state)
        except BatterySoCUnobtainableException as err:
            _LOGGER.error(err)
            raise Exception(err)
        _LOGGER.info(f"Obtained SoC reading of {str(soc)}%")

        #--------------------------------------------------------------------------------
        # CALCULATE CURRENT BATTERY LEVEL
        #--------------------------------------------------------------------------------
        battery_level = battery_capacity * soc/100
        _LOGGER.info(f"Calculated battery level is {battery_level} kWh")
        self.battery_level = battery_level
        self.battery_capacity = battery_capacity

class BatterySoCUnobtainableException(Exception):
    """ Occurs when FoxCloud has been offline for some time """
    pass


class BatteryCapacityUnobtainableException(Exception):
    """ Occurs when FoxCloud has been offline for some time """
    pass


