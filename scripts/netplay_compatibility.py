"""
Fetch the Netplay Compatibility List CSV from AdrianCassar's gist
and convert it to JSON.
"""

import csv
import io
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional
import requests

# =========================
# Configuration
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CSV_URL = (
    "https://gist.githubusercontent.com/AdrianCassar/"
    "0de59389724dae24566ed9126ff77e38/raw/"
    "Netplay%20Compatibility%20List%20Database.csv"
)

OUTPUT_FILE = "data/game-compatibility/netplay.json"

TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

# Emoji to status mapping
STATUS_MAP = {
    "\u2705": "ok",  # ✅
    "\u26a0\ufe0f": "partial",  # ⚠️
    "\u274c": "fail",  # ❌
}

# Regex for markdown links: [text](url)
LINK_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
LINK_TEXT_REGEX = re.compile(r"\[([^\]]+)\]\([^)]+\)")
BOLD_REGEX = re.compile(r"\*\*([^*]+)\*\*")
BACKTICK_REGEX = re.compile(r"`([^`]+)`")


def fetch_csv(url: str) -> str:
    """Fetch CSV content from URL with retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Fetching CSV (attempt %d/%d)...", attempt, MAX_RETRIES)
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning("Attempt %d failed: %s", attempt, e)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE**attempt
                logger.info("Retrying in %ds...", wait)
    logger.error("Failed to fetch CSV after %d attempts", MAX_RETRIES)
    sys.exit(1)


def parse_status(value: str) -> Optional[str]:
    """Convert emoji status to a normalized string."""
    value = value.strip()
    if not value:
        return None
    return STATUS_MAP.get(value, value)


def parse_links(value: str) -> List[Dict[str, str]]:
    """Extract markdown links from a string into a list of {text, url} dicts."""
    return [{"text": m.group(1), "url": m.group(2)} for m in LINK_REGEX.finditer(value)]


def clean_comment(value: str) -> str:
    """Strip markdown links, bold, backticks, and flatten whitespace."""
    value = LINK_TEXT_REGEX.sub(r"\1", value)
    value = BOLD_REGEX.sub(r"\1", value)
    value = BACKTICK_REGEX.sub(r"\1", value)
    return " ".join(value.split())


def parse_csv(content: str) -> List[Dict[str, Any]]:
    """Parse CSV content into a list of game entries."""
    reader = csv.reader(io.StringIO(content))
    header = next(reader)

    # Find column indices by name
    columns = {name.strip(): i for i, name in enumerate(header) if name.strip()}
    required = ["Game Name", "Title ID"]
    for col in required:
        if col not in columns:
            logger.error("Missing required column: %s", col)
            sys.exit(1)

    games = []
    for row_num, row in enumerate(reader, start=2):
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))

        title_id = row[columns["Title ID"]].strip().upper()
        if not title_id:
            continue

        game = {
            "id": title_id,
            "title": row[columns["Game Name"]].strip(),
            "status": {
                "working_public": parse_status(
                    row[columns.get("Working Public", -1)]
                    if "Working Public" in columns
                    else ""
                ),
                "tested_locally": parse_status(
                    row[columns.get("Tested Locally", -1)]
                    if "Tested Locally" in columns
                    else ""
                ),
                "only_local": parse_status(
                    row[columns.get("Only Local", -1)]
                    if "Only Local" in columns
                    else ""
                ),
                "systemlink": parse_status(
                    row[columns.get("Systemlink", -1)]
                    if "Systemlink" in columns
                    else ""
                ),
            },
            "comments": (
                clean_comment(row[columns.get("Comments", -1)])
                if "Comments" in columns
                else ""
            ),
            "links": (
                parse_links(row[columns.get("Others", -1)])
                if "Others" in columns
                else []
            ),
        }
        games.append(game)

    return games


def main():
    content = fetch_csv(CSV_URL)
    games = parse_csv(content)
    games.sort(key=lambda g: g["title"].lower())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info("Wrote %d games to %s", len(games), OUTPUT_FILE)


if __name__ == "__main__":
    main()
