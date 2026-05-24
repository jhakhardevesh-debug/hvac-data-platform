"""
config/settings.py

Purpose:
    Single place where ALL configuration is loaded from environment variables.
    Every other file in this project imports from here.
    Nobody calls os.getenv() directly anywhere else.

Why this matters:
    If a variable name changes, you update it in ONE place.
    If credentials are wrong, you check ONE file.
    New developers see ALL required config in ONE place.
"""

import os
from dotenv import load_dotenv

# load_dotenv() reads your .env file and loads each line
# into the operating system's environment variables.
# After this runs, os.getenv("AWS_ACCESS_KEY_ID") works.
load_dotenv()


class AWSConfig:
    """All AWS-related configuration."""

    ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    REGION = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET = os.getenv("S3_BUCKET_NAME")

    @classmethod
    def validate(cls):
        """
        Call this before any AWS operation.
        Gives a clear error message if credentials are missing
        instead of a confusing AWS error later.

        This is called defensive programming — check
        preconditions before proceeding.
        """
        missing = []
        if not cls.ACCESS_KEY_ID:
            missing.append("AWS_ACCESS_KEY_ID")
        if not cls.SECRET_ACCESS_KEY:
            missing.append("AWS_SECRET_ACCESS_KEY")
        if not cls.S3_BUCKET:
            missing.append("S3_BUCKET_NAME")

        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: "
                f"{', '.join(missing)}\n"
                f"Check your .env file against .env.example"
            )


class SnowflakeConfig:
    """All Snowflake-related configuration."""

    ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
    USER = os.getenv("SNOWFLAKE_USER")
    PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
    WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "HVAC_WH")
    DATABASE = os.getenv("SNOWFLAKE_DATABASE", "HVAC_DB")
    SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "BRONZE")

    @classmethod
    def as_dict(cls):
        """
        Returns a dictionary in the exact format
        snowflake-connector-python expects.

        Usage:
            conn = snowflake.connector.connect(
                **SnowflakeConfig.as_dict()
            )
        """
        return {
            "account": cls.ACCOUNT,
            "user": cls.USER,
            "password": cls.PASSWORD,
            "warehouse": cls.WAREHOUSE,
            "database": cls.DATABASE,
            "schema": cls.SCHEMA,
        }


class PipelineConfig:
    """Pipeline behavior configuration."""

    # int() converts the string value from .env to an integer
    # The second argument is the default if variable is not set
    SIMULATION_DAYS_BACK = int(
        os.getenv("SIMULATION_DAYS_BACK", "30")
    )
    BUILDINGS_COUNT = int(
        os.getenv("BUILDINGS_COUNT", "5")
    )
    SENSORS_PER_BUILDING = int(
        os.getenv("SENSORS_PER_BUILDING", "20")
    )
    BATCH_SIZE = int(
        os.getenv("BATCH_SIZE", "1000")
    )

    # This never changes — it is a fixed business requirement
    # 5 minute intervals between sensor readings
    READING_INTERVAL_MINUTES = 5