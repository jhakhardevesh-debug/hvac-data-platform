{{ config(materialized = 'table') }}

select
    reading_id,
    unit_id,
    building_id,
    building_name,
    city,
    zone_id,
    reading_timestamp,
    reading_date,
    anomaly_type,
    quality_flag,
    temperature_celsius,
    energy_consumption_kwh,
    compressor_status,
    error_code,
    temp_deviation_celsius
from {{ ref('silver_sensor_readings') }}
where quality_flag != 'VALID'
order by reading_timestamp desc