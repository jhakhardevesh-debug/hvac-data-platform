from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

P = "/mnt/c/Users/tanvi/Documents/hvac-data-platform"
DBT = "/home/tanvi/dbt-env/bin/dbt"
D = P + "/dbt_hvac"
PROFILES = "/mnt/c/Users/tanvi/.dbt"

default_args = {
    "owner": "devesh",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="hvac_pipeline",
    default_args=default_args,
    description="HVAC pipeline S3 to Snowflake Gold",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["hvac", "snowflake", "dbt"],
) as dag:

    t1 = BashOperator(
        task_id="generate_hvac_data",
        bash_command="cd " + P + " && PYTHONPATH=" + P + " python simulator/hvac_simulator.py",
    )

    t2 = BashOperator(
        task_id="upload_to_s3",
        bash_command="cd " + P + " && PYTHONPATH=" + P + " python simulator/upload_to_s3.py",
    )

    t3 = BashOperator(
        task_id="load_to_snowflake",
        bash_command="cd " + P + " && PYTHONPATH=" + P + " python ingestion/snowflake_loader.py",
    )

    t4 = BashOperator(
        task_id="dbt_run",
        bash_command="cd " + D + " && " + DBT + " deps --profiles-dir " + PROFILES + " && " + DBT + " run --profiles-dir " + PROFILES,
    )

    t5 = BashOperator(
        task_id="dbt_test",
        bash_command="cd " + D + " && " + DBT + " test --profiles-dir " + PROFILES,
    )

    t1 >> t2 >> t3 >> t4 >> t5
