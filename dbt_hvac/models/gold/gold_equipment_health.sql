{{ config(materialized = 'table') }}

select
    unit_id,
    building_id,
    building_name,
    zone_id,
    count(*)                                        as total_readings,
    round(avg(temperature_celsius), 2)              as avg_temperature,
    round(avg(energy_consumption_kwh), 3)           as avg_energy_kwh,
    sum(runtime_minutes)                            as total_runtime_minutes,
    count(case when error_code is not null
               then 1 end)                          as error_count,
    count(case when compressor_status = 'ERROR'
               then 1 end)                          as compressor_error_count,
    count(case when anomaly_type != 'NORMAL'
               then 1 end)                          as anomaly_count,
    max(reading_date)                               as last_reading_date,
    case
        when count(case when error_code is not null
                        then 1 end) > 10            then 'CRITICAL'
        when count(case when error_code is not null
                        then 1 end) > 3             then 'WARNING'
        else 'HEALTHY'
    end                                             as health_status
from {{ ref('silver_sensor_readings') }}
group by 1, 2, 3, 4