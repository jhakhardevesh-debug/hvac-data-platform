{{ config(
    materialized = 'incremental',
    unique_key    = 'reading_id',
    on_schema_change = 'sync_all_columns'
) }}

with source as (
    select
        raw_data:reading_id::varchar                as reading_id,
        raw_data:building_id::varchar               as building_id,
        raw_data:zone_id::varchar                   as zone_id,
        raw_data:unit_id::varchar                   as unit_id,
        raw_data:timestamp::timestamp_ntz           as reading_timestamp,
        raw_data:temperature_celsius::float         as temperature_celsius,
        raw_data:humidity_pct::float                as humidity_pct,
        raw_data:energy_consumption_kwh::float      as energy_consumption_kwh,
        raw_data:runtime_minutes::int               as runtime_minutes,
        raw_data:setpoint_celsius::float            as setpoint_celsius,
        raw_data:compressor_status::varchar         as compressor_status,
        raw_data:error_code::varchar                as error_code,
        raw_data:anomaly_type::varchar              as anomaly_type,
        raw_data:data_quality_flag::varchar         as data_quality_flag,
        reading_date,
        load_timestamp
    from {{ source('bronze', 'raw_sensor_readings') }}

    {% if is_incremental() %}
        where load_timestamp > (select max(load_timestamp) from {{ this }})
    {% endif %}
),

enriched as (
    select
        s.*,
        b.building_name,
        b.city,
        b.country,
        case
            when s.temperature_celsius is null          then 'SENSOR_NULL_TEMP'
            when s.temperature_celsius > 35             then 'OUT_OF_RANGE_TEMP'
            when s.temperature_celsius < 10             then 'OUT_OF_RANGE_TEMP'
            when s.energy_consumption_kwh is null       then 'SENSOR_NULL_ENERGY'
            when s.anomaly_type != 'NORMAL'             then 'ANOMALY_DETECTED'
            else 'VALID'
        end                                             as quality_flag,
        case
            when extract(hour from s.reading_timestamp) between 8 and 18
                then 'BUSINESS_HOURS'
            when extract(hour from s.reading_timestamp) between 19 and 22
                then 'EVENING'
            else 'OFF_HOURS'
        end                                             as time_bucket,
        s.temperature_celsius - s.setpoint_celsius      as temp_deviation_celsius
    from source s
    left join {{ source('reference', 'dim_buildings') }} b
        on s.building_id = b.building_id
)

select * from enriched