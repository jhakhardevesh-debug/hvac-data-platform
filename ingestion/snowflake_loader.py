import logging
from datetime import datetime, timedelta
import snowflake.connector
from config.settings import SnowflakeConfig

logger = logging.getLogger(__name__)


def get_connection():
    return snowflake.connector.connect(**SnowflakeConfig.as_dict())


def load_date_partition(date):
    year  = date.year
    month = date.month
    day   = date.day

    pattern = f".*year={year}/month={month:02d}/day={day:02d}/.*\\.json"

    copy_sql = f"""
        COPY INTO HVAC_DB.BRONZE.RAW_SENSOR_READINGS (
            SOURCE_FILE_NAME,
            SOURCE_FILE_ROW_NUM,
            RAW_DATA
        )
        FROM (
            SELECT
                METADATA$FILENAME,
                METADATA$FILE_ROW_NUMBER,
                $1
            FROM @HVAC_DB.BRONZE.s3_raw_stage
        )
        PATTERN     = '{pattern}'
        FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = FALSE)
        ON_ERROR    = 'CONTINUE'
        FORCE       = FALSE;
    """

    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("USE WAREHOUSE HVAC_WH;")
        cursor.execute(copy_sql)
        results     = cursor.fetchall()
        rows_loaded = sum(row[3] for row in results if row[3])
        logger.info(f"Loaded {rows_loaded:,} rows for {year}-{month:02d}-{day:02d}")
        return rows_loaded
    finally:
        cursor.close()
        conn.close()


def load_all_partitions(days_back=30):
    end_date   = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days_back)
    current    = start_date
    total      = 0

    while current < end_date:
        rows    = load_date_partition(current)
        total  += rows
        current += timedelta(days=1)

    logger.info(f"Full load complete: {total:,} total rows")
    return total