"""
simulator/hvac_simulator.py

Purpose:
    Simulates realistic HVAC IoT sensor data for 5 buildings,
    4 zones per building, 5 units per zone.

Design decisions to explain in interviews:

1. We use a CLASS for HVACUnit because HVAC units have STATE.
   A unit that was malfunctioning at 2pm is still malfunctioning
   at 2:05pm. Classes let us model this persistent state naturally.

2. We INJECT ANOMALIES deliberately because real datasets are never
   clean. Without anomalies, there is nothing interesting to detect
   in the Gold layer.

3. We use a SINUSOIDAL temperature curve because real temperature
   follows a daily pattern — not random noise.

4. We produce NDJSON (one JSON per line) because Snowflake's
   COPY INTO handles it natively and it is streaming-friendly.

5. We use a GENERATOR (yield) in HVACSimulator to avoid loading
   millions of records into RAM at once.
"""

import uuid
import math
import random
import logging
from datetime import datetime, timedelta
from typing import Generator

from config.settings import PipelineConfig
from config.constants import (
    BUILDING_IDS,
    ZONES_PER_BUILDING,
    TEMPERATURE_THRESHOLDS,
    ENERGY_THRESHOLDS,
    COMPRESSOR_STATUSES,
    FAULT_ERROR_CODES,
)

# ── Logging setup ────────────────────────────────────────────────
# Production-style logging — every message shows timestamp,
# module name, level, and the actual message.
# This makes debugging much easier than plain print() statements.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# HVACUnit — represents ONE physical HVAC unit with persistent state
# ════════════════════════════════════════════════════════════════

class HVACUnit:
    """
    Represents a single HVAC unit with persistent state.

    Why a class and not a function?
    Because HVAC units have STATE that persists across readings:
    - is_faulty stays the same across all readings for this unit
    - fault_code stays the same across all readings
    - base_setpoint stays the same across all readings

    If we used a function, we would randomly re-assign faults on
    every reading. A unit would randomly break and fix itself every
    5 minutes — unrealistic and useless for anomaly detection.
    """

    def __init__(
        self,
        building_id: str,
        zone_id: str,
        unit_number: int
    ):
        """
        Initialize one HVAC unit.

        Parameters:
            building_id  : e.g. 'BLDG_001'
            zone_id      : e.g. 'ZONE_A'
            unit_number  : integer, e.g. 1, 2, 3...
        """
        self.building_id = building_id
        self.zone_id = zone_id
        self.unit_number = unit_number

        # Unique unit identifier — combines all three for uniqueness
        # zfill(3) pads: 1 → "001", 10 → "010"
        self.unit_id = (
            f"AC_{building_id}_{zone_id}_{str(unit_number).zfill(3)}"
        )

        # 5% of units have a persistent hardware fault.
        # random.random() gives a float between 0.0 and 1.0.
        # If that float is less than 0.05, this unit is faulty.
        # This decision is made ONCE when the unit is created
        # and stays the same for all future readings.
        self.is_faulty = random.random() < 0.05

        # Assign a specific fault code to faulty units
        # random.choice() picks one item randomly from a list
        self.fault_code = (
            random.choice(FAULT_ERROR_CODES) if self.is_faulty else None
        )

        # Each unit has its own temperature setpoint
        # (the target temperature it tries to maintain)
        # Real buildings have different setpoints per zone
        self.base_setpoint = round(random.uniform(20.0, 23.0), 1)

        if self.is_faulty:
            logger.debug(
                f"Faulty unit created: {self.unit_id} "
                f"with fault code {self.fault_code}"
            )

    def generate_reading(self, timestamp: datetime) -> dict:
        """
        Generate one complete sensor reading for this unit
        at the given timestamp.

        This is the core method — it produces one JSON record
        that represents 5 minutes of sensor data.

        Parameters:
            timestamp : the datetime this reading represents

        Returns:
            dict : complete sensor reading ready for JSON serialization
        """
        hour = timestamp.hour

        # Business hour classification
        is_business_hours = 8 <= hour <= 18
        is_peak_hours = 10 <= hour <= 14  # Hottest part of day

        # Step 1: Calculate base temperature for this hour
        base_temp = self._get_base_temperature(hour)

        # Step 2: Determine if this reading has an anomaly
        anomaly_type = self._determine_anomaly(is_business_hours)

        # Step 3: Build the complete reading dictionary
        reading = {
            # Unique ID for this specific reading
            "reading_id": str(uuid.uuid4()),

            # Unit location identifiers
            "building_id": self.building_id,
            "zone_id": self.zone_id,
            "unit_id": self.unit_id,

            # Timestamps
            # timestamp = when the sensor reading was taken
            # ingestion_timestamp = when we processed it
            "timestamp": timestamp.isoformat() + "Z",
            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z",

            # Sensor readings — may be None if sensor malfunctions
            "temperature_celsius": self._get_temperature(
                base_temp, anomaly_type
            ),
            "humidity_pct": self._get_humidity(is_business_hours),
            "energy_consumption_kwh": self._get_energy(
                is_peak_hours, anomaly_type
            ),
            "runtime_minutes": self._get_runtime(is_business_hours),

            # Unit configuration
            "setpoint_celsius": self.base_setpoint,

            # Equipment state
            "compressor_status": self._get_compressor_status(anomaly_type),
            "error_code": self._get_error_code(anomaly_type),

            # Anomaly label — Silver layer uses this for detection
            "anomaly_type": anomaly_type,

            # Data quality flag — Silver layer will update this
            "data_quality_flag": "RAW",
        }

        return reading

    # ── Private helper methods ────────────────────────────────────
    # Methods starting with _ are "private" by convention.
    # They are internal helpers not meant to be called from outside.

    def _get_base_temperature(self, hour: int) -> float:
        """
        Calculate realistic base temperature for the given hour.

        Uses a sine wave to model the natural daily temperature curve:
        - Coolest at 6am (before sunrise warms the building)
        - Hottest around 2pm (afternoon sun load)
        - Gradually cools through the evening

        math.sin() produces a wave between -1 and 1.
        Multiplying by 4 gives a +/- 4 degree variation.
        Adding 22.0 centers it around 22 degrees Celsius.
        """
        # Shift so hour 6 = start of the curve (value 0)
        hour_offset = (hour - 6) % 24

        # Sine wave: peaks at hour 12 (noon), troughs at hour 0/24
        temp_variation = 4 * math.sin(math.pi * hour_offset / 12)

        # Add small random noise (realistic sensor variation)
        # gauss(mean, std_dev): most readings within 0.5 of base
        noise = random.gauss(0, 0.5)

        return 22.0 + temp_variation + noise

    def _determine_anomaly(self, is_business_hours: bool) -> str:
        """
        Determine what type of anomaly (if any) this reading has.

        This is the most important method for making the project
        interesting. A dataset with no anomalies teaches you nothing
        about real-world data engineering challenges.

        Anomaly rates are realistic:
        - Faulty units always produce problematic readings
        - 0.1% of normal units have complete sensor failure
        - 0.4% have temperature spikes
        - 0.5% have energy anomalies
        - etc.

        random.random() gives 0.0 to 1.0.
        Checking < 0.001 means this triggers 0.1% of the time.
        """
        # Faulty units always produce anomalous readings
        if self.is_faulty:
            return random.choice([
                "UNIT_MALFUNCTION",
                "SENSOR_ERROR",
                "EXCESSIVE_ENERGY",
            ])

        rand = random.random()

        if rand < 0.001:
            return "SENSOR_ERROR"          # 0.1% — sensor fails completely
        elif rand < 0.005:
            return "TEMPERATURE_SPIKE"     # 0.4% — sudden temp spike
        elif rand < 0.010:
            return "EXCESSIVE_ENERGY"      # 0.5% — energy overconsumption
        elif rand < 0.015:
            return "LOW_EFFICIENCY"        # 0.5% — running but not cooling
        elif not is_business_hours and rand < 0.020:
            return "AFTER_HOURS_RUNNING"   # Running when building empty
        else:
            return "NORMAL"                # 97%+ of readings are normal

    def _get_temperature(
        self, base: float, anomaly: str
    ) -> float | None:
        """Return temperature value based on anomaly type."""
        if anomaly == "SENSOR_ERROR":
            return None                    # Null = sensor failure
        elif anomaly == "TEMPERATURE_SPIKE":
            return round(base + random.uniform(8, 15), 2)
        elif anomaly == "LOW_EFFICIENCY":
            return round(base + random.uniform(3, 6), 2)
        else:
            return round(base + random.gauss(0, 0.3), 2)

    def _get_humidity(self, is_business_hours: bool) -> float:
        """
        Return humidity percentage.
        Higher during business hours because people exhale moisture.
        """
        base = 55.0 if is_business_hours else 45.0
        # Clamp between 20% and 95% — physical limits
        return round(min(95, max(20, base + random.gauss(0, 5))), 1)

    def _get_energy(
        self, is_peak: bool, anomaly: str
    ) -> float | None:
        """Return energy consumption in kWh for this 5-minute interval."""
        if anomaly == "SENSOR_ERROR":
            return None
        elif anomaly == "EXCESSIVE_ENERGY":
            return round(random.uniform(8.0, 12.0), 3)

        # Peak hours use more energy — units work harder to cool
        base = 4.5 if is_peak else 2.0
        # max(0, ...) prevents negative energy values
        return round(max(0, base + random.gauss(0, 0.5)), 3)

    def _get_runtime(self, is_business_hours: bool) -> int:
        """Return minutes the unit ran in this 5-minute interval."""
        # During business hours, units run almost constantly
        base = 4 if is_business_hours else 1
        # Clamp between 0 and 5 minutes
        return min(5, max(0, int(base + random.gauss(0, 1))))

    def _get_compressor_status(self, anomaly: str) -> str:
        """Return compressor state string."""
        if anomaly in ["UNIT_MALFUNCTION", "SENSOR_ERROR"]:
            return "ERROR"
        elif anomaly == "AFTER_HOURS_RUNNING":
            return "RUNNING"

        # Normal operation — weighted random selection
        # 60% running, 30% idle, 10% standby
        return random.choices(
            ["RUNNING", "IDLE", "STANDBY"],
            weights=[0.6, 0.3, 0.1]
        )[0]

    def _get_error_code(self, anomaly: str) -> str | None:
        """Return hardware error code or None if no fault."""
        if self.is_faulty and anomaly != "NORMAL":
            return self.fault_code
        if anomaly == "UNIT_MALFUNCTION":
            return random.choice(FAULT_ERROR_CODES)
        return None
    
# ════════════════════════════════════════════════════════════════
# HVACSimulator — manages ALL units, generates batches of data
# ════════════════════════════════════════════════════════════════

class HVACSimulator:
    """
    Orchestrates data generation across all buildings and units.

    Why separate HVACUnit from HVACSimulator?
    Single Responsibility Principle:
    - HVACUnit  = knows how to generate ITS OWN readings
    - HVACSimulator = knows how to COORDINATE multiple units

    This makes each class independently testable and modifiable.
    If the unit reading logic changes, HVACSimulator is unaffected.
    If the coordination logic changes, HVACUnit is unaffected.
    """

    def __init__(self):
        self.config = PipelineConfig()
        self.units = self._initialize_units()

        logger.info(
            f"Simulator initialized: "
            f"{len(self.units)} total units across "
            f"{len(BUILDING_IDS)} buildings"
        )

    def _initialize_units(self) -> list:
        """
        Create all HVACUnit instances for all buildings and zones.

        Math:
        5 buildings x 4 zones x 5 units = 100 total units
        Each unit generates 1 reading every 5 minutes
        = 100 readings per interval
        = 100 x 288 intervals/day = 28,800 readings/day
        = 28,800 x 30 days = 864,000 readings total
        """
        units = []

        # How many units per zone?
        # SENSORS_PER_BUILDING = 20, divided across 4 zones = 5 each
        units_per_zone = (
            self.config.SENSORS_PER_BUILDING // len(ZONES_PER_BUILDING)
        )

        for building_id in BUILDING_IDS:
            for zone_id in ZONES_PER_BUILDING:
                for unit_num in range(1, units_per_zone + 1):
                    units.append(
                        HVACUnit(building_id, zone_id, unit_num)
                    )

        return units

    def generate_batch(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Generator:
        """
        Generate all sensor readings for a time window.

        Uses a GENERATOR (yield) instead of returning a list.

        Why generator and not a list?
        For 30 days of data:
        864,000 records x ~500 bytes each = ~432 MB in RAM

        A generator produces ONE record at a time and immediately
        discards it after processing. RAM usage stays constant
        regardless of how much data you generate.

        This is a critical interview concept:
        Generator = memory efficient, processes one item at a time
        List      = loads everything into RAM at once
        """
        current_time = start_time
        interval = timedelta(
            minutes=self.config.READING_INTERVAL_MINUTES
        )
        total_records = 0

        while current_time <= end_time:
            for unit in self.units:
                reading = unit.generate_reading(current_time)
                yield reading          # ← produces one record, pauses
                total_records += 1

            current_time += interval   # advance by 5 minutes

        logger.info(
            f"Batch complete: {total_records:,} records "
            f"from {start_time.date()} to {end_time.date()}"
        )

    def generate_daily_batches(
        self,
        days_back: int = None
    ) -> Generator:
        """
        Yields (date, records_list) tuples — one per day.

        Why yield tuples?
        We want to write ONE S3 file per day.
        This method groups records by day and hands them to
        the S3 uploader one day at a time.

        Usage:
            for date, records in simulator.generate_daily_batches(30):
                s3.upload(records, build_key(date))
        """
        days_back = days_back or self.config.SIMULATION_DAYS_BACK

        # Generate from 30 days ago up to yesterday
        # We don't generate today — the day isn't complete yet
        end_date = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_date = end_date - timedelta(days=days_back)

        current_date = start_date

        while current_date < end_date:
            next_date = current_date + timedelta(days=1)

            # Generate all readings for this one day
            # list() forces the generator to produce all records
            daily_records = list(
                self.generate_batch(
                    current_date,
                    next_date - timedelta(minutes=5)
                )
            )

            logger.info(
                f"Date {current_date.date()}: "
                f"{len(daily_records):,} records generated"
            )

            yield current_date, daily_records
            current_date = next_date