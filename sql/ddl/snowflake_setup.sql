-- HVAC Data Platform — Snowflake Infrastructure Setup
-- Run once as ACCOUNTADMIN

USE ROLE ACCOUNTADMIN;


-- ── Warehouse ─────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS HVAC_WH
    WAREHOUSE_SIZE      = 'X-SMALL'
    AUTO_SUSPEND        = 60
    AUTO_RESUME         = TRUE
    INITIALLY_SUSPENDED = TRUE;


-- ── Database and Schemas ──────────────────────────────────────
CREATE DATABASE IF NOT EXISTS HVAC_DB;

CREATE SCHEMA IF NOT EXISTS HVAC_DB.BRONZE;
CREATE SCHEMA IF NOT EXISTS HVAC_DB.SILVER;
CREATE SCHEMA IF NOT EXISTS HVAC_DB.GOLD;
CREATE SCHEMA IF NOT EXISTS HVAC_DB.REFERENCE;

GRANT USAGE ON WAREHOUSE HVAC_WH TO ROLE SYSADMIN;
GRANT ALL ON DATABASE HVAC_DB TO ROLE SYSADMIN;
GRANT ALL ON ALL SCHEMAS IN DATABASE HVAC_DB TO ROLE SYSADMIN;


-- ── Reference Tables ──────────────────────────────────────────
USE WAREHOUSE HVAC_WH;
USE DATABASE HVAC_DB;
USE SCHEMA REFERENCE;

CREATE TABLE IF NOT EXISTS DIM_BUILDINGS (
    BUILDING_ID        VARCHAR(20)   NOT NULL PRIMARY KEY,
    BUILDING_NAME      VARCHAR(100),
    CITY               VARCHAR(100),
    COUNTRY            VARCHAR(50),
    TOTAL_FLOORS       NUMBER,
    TOTAL_SQFT         NUMBER,
    HVAC_UNITS_COUNT   NUMBER,
    COMMISSIONED_DATE  DATE,
    CREATED_AT         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO DIM_BUILDINGS VALUES
    ('BLDG_001', 'Emirates Tower Complex',  'Dubai',   'UAE',          54, 320000, 120, '2008-06-15', CURRENT_TIMESTAMP()),
    ('BLDG_002', 'Al Maryah Plaza',         'Abu Dhabi','UAE',          38, 210000,  95, '2012-03-22', CURRENT_TIMESTAMP()),
    ('BLDG_003', 'Doha Business Gate',      'Doha',    'Qatar',        32, 180000,  80, '2014-11-08', CURRENT_TIMESTAMP()),
    ('BLDG_004', 'Riyadh Financial Centre', 'Riyadh',  'Saudi Arabia', 28, 150000,  65, '2016-04-01', CURRENT_TIMESTAMP()),
    ('BLDG_005', 'Sharjah Innovation Hub',  'Sharjah', 'UAE',          18,  95000,  45, '2018-09-30', CURRENT_TIMESTAMP());

CREATE TABLE IF NOT EXISTS DIM_EQUIPMENT (
    UNIT_ID                 VARCHAR(50)   NOT NULL PRIMARY KEY,
    BUILDING_ID             VARCHAR(20)   NOT NULL,
    ZONE_ID                 VARCHAR(20),
    EQUIPMENT_TYPE          VARCHAR(50),
    MANUFACTURER            VARCHAR(100),
    MODEL_NUMBER            VARCHAR(100),
    INSTALL_DATE            DATE,
    EXPECTED_LIFESPAN_YEARS NUMBER,
    RATED_CAPACITY_KW       FLOAT,
    IS_ACTIVE               BOOLEAN       DEFAULT TRUE,
    CREATED_AT              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- ── Bronze Layer ──────────────────────────────────────────────
USE SCHEMA BRONZE;

CREATE TABLE IF NOT EXISTS RAW_SENSOR_READINGS (
    LOAD_ID             VARCHAR(36)   NOT NULL DEFAULT UUID_STRING(),
    LOAD_TIMESTAMP      TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    SOURCE_FILE_NAME    VARCHAR(500),
    SOURCE_FILE_ROW_NUM NUMBER,
    RAW_DATA            VARIANT       NOT NULL,
    READING_DATE        DATE AS (TRY_TO_DATE(RAW_DATA:timestamp::VARCHAR))
)
CLUSTER BY (READING_DATE);


-- ── S3 Storage Integration ────────────────────────────────────
-- After running DESC below, update the IAM trust policy in AWS
-- with STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID

USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION IF NOT EXISTS s3_hvac_integration
    TYPE                      = EXTERNAL_STAGE
    STORAGE_PROVIDER          = 'S3'
    ENABLED                   = TRUE
    STORAGE_AWS_ROLE_ARN      = 'arn:aws:iam::420435662739:role/snowflake-hvac-role'
    STORAGE_ALLOWED_LOCATIONS = ('s3://hvac-raw-data-devesh/');


-- ── External Stage ────────────────────────────────────────────
USE DATABASE HVAC_DB;
USE SCHEMA BRONZE;

CREATE STAGE IF NOT EXISTS s3_raw_stage
    STORAGE_INTEGRATION = s3_hvac_integration
    URL                 = 's3://hvac-raw-data-devesh/raw/'
    FILE_FORMAT         = (
        TYPE              = 'JSON'
        STRIP_OUTER_ARRAY = FALSE
        IGNORE_UTF8_ERRORS = TRUE
    );