"""
Fetch the Mousehook compatibility table from the xenia-canary-mousehook
README.md and convert it to JSON.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List
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

README_URL = (
    "https://raw.githubusercontent.com/marinesciencedude/"
    "xenia-canary-mousehook/refs/heads/mousehook/README.md"
)

OUTPUT_FILE = "data/game-compatibility/mousehook.json"

TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

# Regex patterns for cleaning notes
LINK_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_REGEX = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_REGEX = re.compile(r"\*([^*]+)\*")
BACKTICK_REGEX = re.compile(r"`([^`]+)`")
SUB_OPEN_REGEX = re.compile(r"<sub>\s*", re.IGNORECASE)
SUB_CLOSE_REGEX = re.compile(r"\s*</sub>", re.IGNORECASE)
BR_REGEX = re.compile(r"\s*<br\s*/?>\s*", re.IGNORECASE)
FOOTNOTE_REGEX = re.compile(r"\[\^\d+\]")


def fetch_readme(url: str) -> str:
    """Fetch README content from URL with retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Fetching README (attempt %d/%d)...", attempt, MAX_RETRIES)
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning("Attempt %d failed: %s", attempt, e)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE**attempt
                logger.info("Retrying in %ds...", wait)
    logger.error("Failed to fetch README after %d attempts", MAX_RETRIES)
    sys.exit(1)


def clean_notes(value: str) -> str:
    """Strip HTML tags, markdown formatting, and flatten whitespace."""
    value = SUB_OPEN_REGEX.sub("", value)
    value = SUB_CLOSE_REGEX.sub("", value)
    value = BR_REGEX.sub(" ", value)
    value = LINK_REGEX.sub(r"\1", value)
    value = BOLD_REGEX.sub(r"\1", value)
    value = ITALIC_REGEX.sub(r"\1", value)
    value = BACKTICK_REGEX.sub(r"\1", value)
    value = FOOTNOTE_REGEX.sub("", value)
    return " ".join(value.split())


def clean_supported_versions(value: str) -> str:
    """Strip HTML tags and flatten whitespace from supported versions."""
    value = BR_REGEX.sub(" ", value)
    return " ".join(value.split())


def parse_table(content: str) -> List[Dict[str, Any]]:
    """Parse the markdown table into a list of game entries."""
    lines = content.splitlines()

    # Find the table - look for the header row with Game | Supported versions
    table_start = None
    for i, line in enumerate(lines):
        if re.match(r"\|\s*Game\s*\|", line):
            table_start = i
            break

    if table_start is None:
        logger.error("Could not find mousehook compatibility table")
        return []

    # Skip header and separator rows
    rows = []
    for line in lines[table_start + 2 :]:
        line = line.strip()
        if not line.startswith("|"):
            break
        rows.append(line)

    games = []
    for row in rows:
        # Split by | and strip
        cells = [c.strip() for c in row.split("|")]
        # First and last cells are empty (leading/trailing |)
        cells = cells[1:-1] if len(cells) > 2 else cells

        if len(cells) < 4:
            continue

        title = cells[0].strip()
        if not title:
            continue

        supported_versions = clean_supported_versions(cells[1].strip())
        title_ids_raw = cells[2].strip()
        mouse_support = cells[3].strip()
        notes_raw = cells[4].strip() if len(cells) > 4 else ""

        # Clean footnotes from mouse support (e.g., "Fair[^1]" -> "Fair")
        mouse_support = FOOTNOTE_REGEX.sub("", mouse_support).strip()

        # Handle multiple Title IDs (separated by /)
        title_ids = [tid.strip() for tid in title_ids_raw.split("/") if tid.strip()]

        # Clean notes
        notes = clean_notes(notes_raw)

        game = {
            "id": (
                title_ids if len(title_ids) > 1 else title_ids[0] if title_ids else ""
            ),
            "title": title,
            "mouse_support": mouse_support,
            "supported_versions": supported_versions,
            "notes": notes,
        }
        games.append(game)

    return games


def main():
    content = fetch_readme(README_URL)
    games = parse_table(content)

    if not games:
        logger.warning("No games found in table — skipping output")
        return

    games.sort(key=lambda g: g["title"].lower())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info("Wrote %d games to %s", len(games), OUTPUT_FILE)


if __name__ == "__main__":
    main()
