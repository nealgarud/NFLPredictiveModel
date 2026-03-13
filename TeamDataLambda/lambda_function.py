"""
TeamDataLambda

Reads PFF team grade CSVs from S3 (team_data_nfl bucket),
splits each row into offensive / defensive / special teams payloads,
and upserts into three Supabase tables.

S3 layout expected:
    teamdatalambda/
        data/pff_team_grades_2022.csv
        data/pff_team_grades_2023.csv
        data/pff_team_grades_2024.csv

Invoke event formats:

  Single season:
    {"bucket": "teamdatalambda", "season": 2024}

  Multiple seasons:
    {"bucket": "teamdatalambda", "seasons": [2022, 2023, 2024]}

  Custom S3 key (e.g. .txt extension):
    {"bucket": "teamdatalambda", "season": 2024, "s3_key": "data/pff_team_grades_2024.txt"}

  S3 trigger (automatic on file upload):
    {"Records": [{"s3": {"bucket": {"name": "..."}, "object": {"key": "data/pff_team_grades_2024.csv"}}}]}
"""

import json
import logging
import re

from S3FileReader import S3FileReader
from DatabaseUtils import DatabaseUtils
from TeamDataProcessor import TeamDataProcessor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_BUCKET = "teamdatalambda"


# ---------------------------------------------------------------------------
# Event normalisation — handle all three invocation styles
# ---------------------------------------------------------------------------

def _parse_event(event: dict) -> list[dict]:
    """
    Returns a list of {"bucket": str, "season": int, "s3_key": str} dicts,
    one per season to process.
    """
    jobs = []

    # S3 trigger format
    if "Records" in event:
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key    = record["s3"]["object"]["key"]
            season = _season_from_key(key)
            if season:
                jobs.append({"bucket": bucket, "season": season, "s3_key": key})
            else:
                logger.warning(f"Could not infer season from S3 key: {key}")
        return jobs

    bucket = event.get("bucket", DEFAULT_BUCKET)

    # Single season with optional explicit key
    if "season" in event:
        season = int(event["season"])
        s3_key = event.get("s3_key", f"data/pff_team_grades_{season}.csv")
        jobs.append({"bucket": bucket, "season": season, "s3_key": s3_key})
        return jobs

    # Multiple seasons
    if "seasons" in event:
        for season in event["seasons"]:
            season = int(season)
            jobs.append({
                "bucket": bucket,
                "season": season,
                "s3_key": f"data/pff_team_grades_{season}.csv",
            })
        return jobs

    raise ValueError(f"Unrecognised event format: {event}")


def _season_from_key(key: str) -> int | None:
    """Extract 4-digit year from S3 key path. e.g. '2024/team_grades.csv' → 2024."""
    match = re.search(r"(\d{4})", key)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    try:
        jobs = _parse_event(event)
        logger.info(f"Processing {len(jobs)} season(s): {[j['season'] for j in jobs]}")
    except ValueError as e:
        logger.error(str(e))
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    db = DatabaseUtils()
    results = []

    try:
        processor = TeamDataProcessor(db_utils=db, batch_size=32)

        for job in jobs:
            bucket  = job["bucket"]
            season  = job["season"]
            s3_key  = job["s3_key"]

            logger.info(f"--- Season {season} | s3://{bucket}/{s3_key} ---")

            reader = S3FileReader(bucket_name=bucket)
            # Try .csv first; fall back to .txt (PFF sometimes exports with wrong ext)
            try:
                csv_rows = reader.read_csv_from_s3(s3_key)
            except Exception:
                txt_key = s3_key.replace(".csv", ".txt")
                logger.warning(f"CSV not found at {s3_key}, trying {txt_key}")
                csv_rows = reader.read_csv_from_s3(txt_key)

            if not csv_rows:
                logger.warning(f"No rows found for season {season}")
                results.append({"season": season, "status": "empty"})
                continue

            summary = processor.process_and_store(csv_rows, season)
            logger.info(f"Season {season} complete: {summary}")
            results.append({"status": "ok", **summary})

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "partial_results": results}),
        }
    finally:
        db.close()

    logger.info(f"All done. Results: {results}")
    return {
        "statusCode": 200,
        "body": json.dumps({"success": True, "results": results}),
    }
