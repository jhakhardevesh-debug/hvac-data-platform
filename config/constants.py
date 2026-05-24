"""
config/constants.py

Purpose:
    Business-domain constants that never change between environments.

Critical distinction:
    settings.py  = environment-specific (different in dev vs prod)
    Example: Snowflake password is different everywhere
                   
    constants.py = business rules 
    Example: "critically hot" is 30 degrees Celsius
    everywhere — dev, staging, and production


"""
# ================================================================
# BUILDING CONFIGURATION
# ================================================================

BUILDING_IDS = [f"BLDG_{str(i).zfill(3)}" for i in range(1, 6)]
# Result: ['BLDG_001', 'BLDG_002', 'BLDG_003', 'BLDG_004', 'BLDG_005']

# Each building is divided into zones
ZONES_PER_BUILDING = ["ZONE_A", "ZONE_B", "ZONE_C", "ZONE_D"]

# ================================================================
# TEMPERATURE THRESHOLDS (in Celsius)
# Based on ASHRAE 55 — the international standard for
# thermal comfort in occupied buildings
# ================================================================
TEMPERATURE_THRESHOLDS = {
    "critically_cold": 15.0,  # Below this: equipment may freeze
    "cold": 18.0,             # Below this: occupant discomfort
    "optimal_min": 20.0,      # ASHRAE comfort zone starts here
    "optimal_max": 24.0,      # ASHRAE comfort zone ends here
    "warm": 27.0,             # Above this: occupant discomfort
    "critically_hot": 30.0,   # Above this: potential equipment damage
}


# ================================================================
# ENERGY CONSUMPTION THRESHOLDS
# Unit: kWh per 5-minute reading interval per HVAC unit
# ================================================================
ENERGY_THRESHOLDS = {
    "low_kwh": 1.0,      # Unit is barely running
    "normal_kwh": 3.5,   # Expected normal operation range
    "high_kwh": 6.0,     # Investigate if sustained at this level
    "critical_kwh": 9.0, # Immediate alert — possible malfunction
}


# ================================================================
# EQUIPMENT STATES
# Valid compressor states — anything outside this list
# is a data quality error in the Silver layer
# ================================================================
COMPRESSOR_STATUSES = [
    "RUNNING",      # Actively cooling
    "IDLE",         # Powered on but not actively cooling
    "STANDBY",      # Low power mode
    "ERROR",        # Fault detected
    "MAINTENANCE",  # Manually taken offline
]


# ================================================================
# FAULT CODES
# Error codes indicating real hardware problems
# In production these come from manufacturer documentation
# ================================================================
FAULT_ERROR_CODES = ["E001", "E002", "E003", "E004", "E005"]


# ================================================================
# S3 PATH STRUCTURE
# Hive-style partitioning: year=2024/month=01/day=15
# ================================================================
S3_PREFIX_TEMPLATE = (
    "raw/sensors/"
    "year={year}/"
    "month={month:02d}/"
    "day={day:02d}/"
)