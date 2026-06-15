# Smart HVAC Monitoring & Energy Optimization

End-to-end data engineering portfolio project processing 864,000 HVAC sensor readings across 5 commercial buildings in the UAE/Middle East through a Bronze/Silver/Gold medallion architecture on Snowflake.

---

## Tech Stack

Python, Apache Airflow, AWS S3, Snowflake, dbt Core, Git

---

## Architecture

- Python simulator generates 864,000 HVAC sensor readings across 5 buildings
- Raw JSON uploaded to AWS S3 with Hive-style date partitioning (year=/month=/day=)
- Snowflake external stage ingests S3 data into Bronze as raw VARIANT JSON (schema-on-read)
- dbt incremental model transforms Bronze into Silver — typed columns, dimension joins, quality flags
- Three dbt Gold tables aggregate Silver data into business-ready analytical datasets
- Apache Airflow DAG orchestrates the full pipeline end-to-end on a daily schedule

---

## Pipeline Layers

**Bronze**

Raw sensor readings stored as Snowflake VARIANT JSON via external stage linked to S3. Zero transformation — exact source copy with a virtual reading_date column for partition pruning.

**Silver**

dbt incremental model that parses JSON fields into typed columns, joins with DIM_BUILDINGS and DIM_EQUIPMENT reference tables, and applies data quality classification flags: VALID, ANOMALY_DETECTED, OUT_OF_RANGE_TEMP, SENSOR_NULL_TEMP, SENSOR_NULL_ENERGY.

**Gold**

Three dbt table models built for direct analytical consumption:

| Table | Description |
| --- | --- |
| gold_anomaly_alerts | Flagged anomaly events with severity classification |
| gold_building_energy_summary | Energy KPIs aggregated per building |
| gold_equipment_health | Equipment health scoring per unit |

---

## Data Quality

dbt generic tests implemented on silver_sensor_readings:

| Test | Column | Result |
| --- | --- | --- |
| unique | reading_id | PASS |
| not_null | reading_id | PASS |
| not_null | reading_timestamp | PASS |
| not_null | building_id | PASS |
| not_null | quality_flag | PASS |
| accepted_values | building_id | PASS |
| accepted_values | compressor_status | PASS |
| accepted_values | quality_flag | PASS |

PASS=8 WARN=0 ERROR=0 across 864,000 records.

---

## Simulated Buildings

| Building ID | City | Country |
| --- | --- | --- |
| BLDG_001 | Dubai | UAE |
| BLDG_002 | Abu Dhabi | UAE |
| BLDG_003 | Doha | Qatar |
| BLDG_004 | Riyadh | Saudi Arabia |
| BLDG_005 | Sharjah | UAE |

---

## Project Structure

```
hvac-data-platform/
├── dbt_hvac/
│   ├── models/
│   │   ├── staging/
│   │   │   └── sources.yml
│   │   ├── silver/
│   │   │   ├── silver_sensor_readings.sql
│   │   │   └── schema.yml
│   │   └── gold/
│   │       ├── gold_anomaly_alerts.sql
│   │       ├── gold_building_energy_summary.sql
│   │       └── gold_equipment_health.sql
│   └── dbt_project.yml
├── src/
│   ├── simulator/
│   └── ingestion/
├── airflow/
│   └── dags/
│       └── hvac_pipeline_dag.py
├── simulator/
├── ingestion/
└── README.md
```

---

## Airflow Orchestration

The pipeline is fully automated via an Apache Airflow DAG running on a daily schedule. All 5 tasks execute in sequence — each task only starts if the previous one succeeds.

```
generate_hvac_data → upload_to_s3 → load_to_snowflake → dbt_run → dbt_test
```

| Task | What it does |
| --- | --- |
| generate_hvac_data | Runs the Python simulator to generate daily sensor readings |
| upload_to_s3 | Uploads NDJSON files to S3 with Hive-style date partitioning |
| load_to_snowflake | Executes COPY INTO to load new S3 files into Bronze |
| dbt_run | Runs all dbt models — Silver incremental + Gold tables |
| dbt_test | Runs all 8 dbt data quality tests |

DAG configuration: `@daily` schedule, 2 retries per task with 5-minute retry delay, `catchup=False`.

Full DAG run time: ~2 minutes end to end.
