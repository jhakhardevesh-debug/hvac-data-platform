{{ config(materialized = 'table') }}

select
    building_id,
    building_name,
    city,
    country,
    reading_date,
    count(*)                                        as total_readings,
    round(sum(energy_consumption_kwh), 2)           as total_energy_kwh,
    round(avg(energy_consumption_kwh), 3)           as avg_energy_kwh,
    round(avg(temperature_celsius), 2)              as avg_temperature,
    round(avg(humidity_pct), 2)                     as avg_humidity,
    count(case when quality_flag = 'ANOMALY_DETECTED'
               then 1 end)                          as anomaly_count,
    count(case when compressor_status = 'ERROR'
               then 1 end)                          as error_count,
    round(
        count(case when quality_flag = 'ANOMALY_DETECTED'
                   then 1 end) * 100.0 / count(*), 2
    )                                               as anomaly_rate_pct
from {{ ref('silver_sensor_readings') }}
where quality_flag != 'SENSOR_NULL_ENERGY'
group by 1, 2, 3, 4, 5