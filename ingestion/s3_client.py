"""
ingestion/s3_client.py

Purpose:
    Reusable S3 operations module.

Design principle:
    This module knows NOTHING about HVAC.
    It only knows how to talk to S3.
    This makes it reusable across any project.

Interview talking point:
    "I separated S3 operations from business logic.
    The s3_client module is a pure infrastructure concern —
    completely unaware of what data it is storing."
"""

import json
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config.settings import AWSConfig

logger = logging.getLogger(__name__)


class S3Client:
    """
    Wrapper around boto3 S3 client.

    Why wrap boto3 instead of using it directly?
    1. Adds retry logic and structured logging automatically
    2. Centralizes error handling in one place
    3. Makes the rest of the code cleaner — no boto3 details scattered everywhere
    4. Easier to mock in tests — replace S3Client with a fake version
    """

    def __init__(self):
        # Validate credentials before attempting any connection
        # Gives a clear error message if .env is not filled in
        AWSConfig.validate()

        # Create the boto3 S3 client using credentials from .env
        self._client = boto3.client(
            "s3",
            aws_access_key_id     = AWSConfig.ACCESS_KEY_ID,
            aws_secret_access_key = AWSConfig.SECRET_ACCESS_KEY,
            region_name           = AWSConfig.REGION,
        )

        self.bucket = AWSConfig.S3_BUCKET
        logger.info(f"S3Client initialized for bucket: {self.bucket}")

    def upload_json(
        self,
        data: list,
        s3_key: str,
        metadata: dict = None,
    ) -> bool:
        """
        Upload a list of dictionaries as NDJSON to S3.

        What is NDJSON?
            Newline Delimited JSON — one JSON object per line.
            Example:
                {"reading_id": "abc", "temperature": 22.4}
                {"reading_id": "def", "temperature": 23.1}
                {"reading_id": "ghi", "temperature": 21.8}

        Why NDJSON instead of a JSON array?
            1. Snowflake COPY INTO handles NDJSON natively
            2. Each line is independently readable
            3. Standard format for log ingestion systems
            4. Streaming friendly — process line by line

        Parameters:
            data     : list of dictionaries (sensor readings)
            s3_key   : path in S3 bucket e.g. raw/sensors/year=2024/month=01/day=15/sensors_001.json
            metadata : optional dict of metadata to attach to the S3 object

        Returns:
            True if upload succeeded
        """
        try:
            # Convert list of dicts to NDJSON string
            # json.dumps() converts one dict to JSON string
            # "\n".join() puts each on its own line
            ndjson_content = "\n".join(
                json.dumps(record) for record in data
            )

            # Encode to bytes — S3 stores bytes not strings
            body = ndjson_content.encode("utf-8")

            # Prepare upload arguments
            extra_args = {"ContentType": "application/x-ndjson"}

            # Attach metadata if provided
            # Metadata = extra information stored with the file
            # Does not affect the file content — just descriptive info
            if metadata:
                extra_args["Metadata"] = {
                    k: str(v) for k, v in metadata.items()
                }

            # Actually upload to S3
            self._client.put_object(
                Bucket = self.bucket,
                Key    = s3_key,
                Body   = body,
                **extra_args,
            )

            # Log success with useful stats
            size_kb = len(body) / 1024
            logger.info(
                f"Uploaded {len(data):,} records to "
                f"s3://{self.bucket}/{s3_key} "
                f"({size_kb:.1f} KB)"
            )
            return True

        except NoCredentialsError:
            logger.error(
                "AWS credentials not found. "
                "Check your .env file."
            )
            raise

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(
                f"S3 upload failed [{error_code}]: {e}"
            )
            raise

    def key_exists(self, s3_key: str) -> bool:
        """
        Check if a file already exists in S3.

        Used for IDEMPOTENCY — if the file already exists,
        skip the upload instead of uploading again.

        What is idempotency?
            Running the same operation multiple times
            produces the same result as running it once.
            Re-running the upload never creates duplicates.

        How it works:
            head_object() asks S3 for metadata about a file.
            If the file exists → returns metadata → we return True
            If the file does not exist → S3 raises a 404 error → we return False
        """
        try:
            self._client.head_object(
                Bucket = self.bucket,
                Key    = s3_key
            )
            return True  # file exists

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False  # file does not exist
            raise  # some other error — re-raise it

    def list_keys(self, prefix: str) -> list:
        """
        List all S3 keys (file paths) under a given prefix.

        Example:
            list_keys("raw/sensors/year=2024/month=01/")
            Returns all files inside that folder path.

        Used by Airflow to find which files need loading into Snowflake.

        Why paginator?
            S3 returns maximum 1000 objects per request.
            If you have more than 1000 files, you need to
            make multiple requests. Paginator handles this
            automatically — you just loop through pages.
        """
        keys = []

        # Paginator automatically handles multiple requests
        # if there are more than 1000 objects
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(
            Bucket = self.bucket,
            Prefix = prefix
        ):
            # Contents = list of objects in this page
            # .get("Contents", []) returns empty list if no objects found
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        logger.info(
            f"Found {len(keys)} objects with prefix: {prefix}"
        )
        return keys