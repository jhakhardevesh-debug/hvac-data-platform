import json
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config.settings import AWSConfig

logger = logging.getLogger(__name__)


class S3Client:

    def __init__(self):
        AWSConfig.validate()

        self._client = boto3.client(
            "s3",
            aws_access_key_id     = AWSConfig.ACCESS_KEY_ID,
            aws_secret_access_key = AWSConfig.SECRET_ACCESS_KEY,
            region_name           = AWSConfig.REGION,
        )

        self.bucket = AWSConfig.S3_BUCKET
        logger.info(f"S3Client initialized for bucket: {self.bucket}")

    def upload_json(self, data: list, s3_key: str, metadata: dict = None) -> bool:
        """Upload a list of records as NDJSON to S3."""
        try:
            ndjson_content = "\n".join(json.dumps(record) for record in data)
            body = ndjson_content.encode("utf-8")

            extra_args = {"ContentType": "application/x-ndjson"}

            if metadata:
                extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

            self._client.put_object(
                Bucket = self.bucket,
                Key    = s3_key,
                Body   = body,
                **extra_args,
            )

            size_kb = len(body) / 1024
            logger.info(
                f"Uploaded {len(data):,} records to "
                f"s3://{self.bucket}/{s3_key} ({size_kb:.1f} KB)"
            )
            return True

        except NoCredentialsError:
            logger.error("AWS credentials not found. Check your .env file.")
            raise

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"S3 upload failed [{error_code}]: {e}")
            raise

    def key_exists(self, s3_key: str) -> bool:
        """Check if a file already exists in S3 — used for idempotent uploads."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=s3_key)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def list_keys(self, prefix: str) -> list:
        """List all S3 keys under a given prefix."""
        keys = []
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        logger.info(f"Found {len(keys)} objects with prefix: {prefix}")
        return keys