"""
simulator/upload_to_s3.py

Purpose:
    Orchestrates simulation and S3 upload.
    Runs the simulator and sends output to S3.

This is the script you run to populate S3 with data.
In production, the simulator would be replaced by real
IoT sensors pushing data via MQTT or Kinesis.

Run with: python -m simulator.upload_to_s3
"""

import logging
from datetime import datetime

from simulator.hvac_simulator import HVACSimulator
from ingestion.s3_client import S3Client
from config.constants import S3_PREFIX_TEMPLATE
from config.settings import PipelineConfig

logger = logging.getLogger(__name__)


def build_s3_key(date: datetime, batch_num: int = 0) -> str:
    """
    Build the S3 file path for a given date.

    Result example:
        raw/sensors/year=2024/month=01/day=15/sensors_000.json

    Why this partition structure?
        year=2024/month=01/day=15 is called Hive-style partitioning.
        AWS Athena, Snowflake, and Apache Spark all recognize it.
        Querying one day never scans other days' files.
        This saves both time and money.

    Parameters:
        date      : the date for this file
        batch_num : if you split one day into multiple files,
                    use 0, 1, 2... to distinguish them.
                    We use one file per day so batch_num is always 0.
    """
    # Build the folder path using the template from constants.py
    prefix = S3_PREFIX_TEMPLATE.format(
        year  = date.year,
        month = date.month,
        day   = date.day,
    )

    # Add the filename inside that folder
    # zfill(3) pads: 0 → "000", 1 → "001"
    filename = f"sensors_{str(batch_num).zfill(3)}.json"

    return prefix + filename
    # Result: raw/sensors/year=2024/month=01/day=15/sensors_000.json


def upload_historical_data(days_back: int = None):
    """
    Generate and upload historical HVAC data to S3.

    IDEMPOTENCY:
        Before uploading each day, we check if the file
        already exists in S3. If it does, we skip it.
        This means you can safely re-run this script
        without creating duplicate files.

        Re-running = same result = idempotent.

    Parameters:
        days_back : how many days of history to generate.
                    None = use value from .env (default 30)
    """
    config    = PipelineConfig()
    simulator = HVACSimulator()
    s3        = S3Client()

    days_back = days_back or config.SIMULATION_DAYS_BACK
    logger.info(
        f"Starting historical upload: {days_back} days"
    )

    total_uploaded = 0
    total_skipped  = 0

    # Loop through each day — simulator yields (date, records) tuples
    for date, records in simulator.generate_daily_batches(days_back):

        # Build the S3 path for this day
        s3_key = build_s3_key(date, batch_num=0)

        # IDEMPOTENCY CHECK
        # If this file already exists in S3, skip it
        if s3.key_exists(s3_key):
            logger.info(f"Skipping {s3_key} — already exists")
            total_skipped += 1
            continue  # jump to next day immediately

        # Attach metadata to the S3 file
        # Metadata is extra information stored WITH the file
        # but not INSIDE the file content
        metadata = {
            "record_count":   len(records),
            "date":           date.strftime("%Y-%m-%d"),
            "generated_at":   datetime.utcnow().isoformat(),
            "pipeline_version": "1.0.0",
        }

        # Upload this day's records to S3
        s3.upload_json(records, s3_key, metadata=metadata)
        total_uploaded += 1

    # Final summary log
    logger.info(
        f"Upload complete. "
        f"Uploaded: {total_uploaded} files, "
        f"Skipped: {total_skipped} files (already existed)"
    )


# This block only runs when you execute this file directly
# It does NOT run when this file is imported by another file
if __name__ == "__main__":
    upload_historical_data()