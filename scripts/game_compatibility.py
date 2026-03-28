import json
import os
import sys
import time
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from datetime import datetime, timedelta

# Configuration defaults (overridden in main)
DEFAULT_OWNER = "xenia-canary"
DEFAULT_REPO = "game-compatibility"
DEFAULT_OUTPUT_FILE = "data/game-compatibility/canary.json"

STATE = "open"
PER_PAGE = 100
BASE_URL = "https://api.github.com"

# Enhanced rate limiting
RATE_LIMIT_DELAY = 1.0
SEARCH_API_DELAY = 2.0  # Separate delay for search API
MAX_RETRIES = 5
RETRY_BASE_DELAY = 10
GITHUB_TOKEN = os.getenv("TOKEN")

# Rate limiting tracking
last_request_time = 0
remaining_requests = 5000  # Default for authenticated users


def get_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "xenia-data-sync/1.0",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def smart_rate_limit():
    """Intelligent rate limiting based on remaining quota and request history"""
    global last_request_time, remaining_requests

    current_time = time.time()
    time_since_last = current_time - last_request_time

    # Dynamic delay based on remaining requests
    if remaining_requests < 100:
        delay = 5.0  # Very conservative when low
    elif remaining_requests < 500:
        delay = 2.0  # Conservative when medium
    else:
        delay = RATE_LIMIT_DELAY  # Normal rate

    # Ensure minimum time between requests
    if time_since_last < delay:
        sleep_time = delay - time_since_last
        print(
            f"⏱️  Rate limiting: sleeping {sleep_time:.1f}s (remaining: {remaining_requests})"
        )
        time.sleep(sleep_time)

    last_request_time = time.time()


def update_rate_limit_info(response_headers: Dict[str, str]):
    """Update rate limit tracking from response headers"""
    global remaining_requests

    if "x-ratelimit-remaining" in response_headers:
        remaining_requests = int(response_headers["x-ratelimit-remaining"])

    if "x-ratelimit-reset" in response_headers:
        reset_time = int(response_headers["x-ratelimit-reset"])
        current_time = int(time.time())
        if reset_time > current_time:
            reset_in = reset_time - current_time
            if remaining_requests < 50:
                print(
                    f"⚠️  Low rate limit: {remaining_requests} remaining, resets in {reset_in}s"
                )


def parse_title(issue_title: str, debug: bool = False) -> Dict[str, Optional[str]]:
    try:
        title = issue_title.strip()
        if debug:
            print(f"🔍 Parsing title: '{title}'")

        if " - " in title:
            parts = title.split(" - ", 1)
            return {"id": parts[0].strip().upper(), "title": parts[1].strip()}

        if "-" in title:
            dash_index = title.find("-")
            if dash_index > 0:
                potential_id = title[:dash_index].strip()
                potential_title = title[dash_index + 1 :].strip()
                if len(potential_id) == 8 and potential_id.isalnum():
                    return {"id": potential_id.upper(), "title": potential_title}

        return {"id": None, "title": title}
    except Exception as e:
        print(f"❌ Error parsing title '{issue_title}': {e}", file=sys.stderr)
        return {"id": None, "title": issue_title}


def parse_labels(labels: List[Dict], debug: bool = False) -> str:
    try:
        state_mappings = {
            "state-nothing": "Unplayable",
            "state-crash": "Unplayable",
            "state-crash-guest": "Unplayable",
            "state-crash-host": "Unplayable",
            "state-crash-xna-WONTFIX": "Unplayable",
            "state-intro": "Loads",
            "state-hang": "Loads",
            "state-load": "Loads",
            "state-title": "Loads",
            "state-menus": "Loads",
            "state-gameplay": "Gameplay",
            "state-playable": "Playable",
        }

        for label in labels:
            label_name = label.get("name", "")
            if label_name in state_mappings:
                return state_mappings[label_name]

        return "Unknown"
    except Exception as e:
        print(f"❌ Error parsing labels: {e}", file=sys.stderr)
        return "Unknown"


def validate_repo_exists(owner: str, repo: str, debug: bool = False) -> bool:
    """Check if the repository exists before trying to fetch issues"""
    url = f"{BASE_URL}/repos/{owner}/{repo}"

    if debug:
        print(f"🔍 Checking if repository {owner}/{repo} exists...")

    try:
        smart_rate_limit()
        request = Request(url, headers=get_headers())
        with urlopen(request, timeout=30) as response:
            update_rate_limit_info(dict(response.headers))
            if response.status == 200:
                if debug:
                    print(f"✅ Repository {owner}/{repo} exists and is accessible")
                return True
    except HTTPError as e:
        if e.code == 404:
            print(f"❌ Repository {owner}/{repo} not found (404)", file=sys.stderr)
        elif e.code == 403:
            print(
                f"❌ Access denied to {owner}/{repo} (403). Check permissions/token.",
                file=sys.stderr,
            )
        else:
            print(
                f"❌ HTTP Error {e.code} when checking repository: {e.reason}",
                file=sys.stderr,
            )
        return False
    except Exception as e:
        print(f"❌ Error checking repository: {e}", file=sys.stderr)
        return False

    return False


def make_request(
    url: str,
    params: Optional[Dict] = None,
    debug: bool = False,
    is_search: bool = False,
) -> Optional[Dict]:
    # Apply appropriate rate limiting
    if is_search:
        time.sleep(SEARCH_API_DELAY)
    else:
        smart_rate_limit()

    # Validate parameters
    if params:
        clean_params = {}
        for k, v in params.items():
            if isinstance(v, (str, int)):
                clean_params[k] = str(v)
            else:
                print(f"⚠️ Skipping invalid parameter {k}={v}", file=sys.stderr)
        params = clean_params

        if params:
            url = f"{url}?{urlencode(params)}"

    if debug:
        print(f"🌐 Making request to: {url}")

    for attempt in range(MAX_RETRIES):
        try:
            request = Request(url, headers=get_headers())
            with urlopen(request, timeout=30) as response:
                update_rate_limit_info(dict(response.headers))

                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if debug:
                        print(
                            f"✅ Request successful, got {len(data) if isinstance(data, list) else 1} item(s)"
                        )
                    return data
                else:
                    print(
                        f"❌ Unexpected status code: {response.status}", file=sys.stderr
                    )
        except HTTPError as e:
            if e.code == 403:
                # Exponential backoff for rate limiting
                wait_time = RETRY_BASE_DELAY * (2**attempt)
                print(
                    f"⏱️  Rate limited (403). Waiting {wait_time} seconds... (attempt {attempt + 1}/{MAX_RETRIES})",
                    file=sys.stderr,
                )
                time.sleep(wait_time)
            elif e.code == 422:
                print(
                    f"❌ Unprocessable Entity (422). Likely reached end of available pages.",
                    file=sys.stderr,
                )
                if debug:
                    print(f"   URL: {url}", file=sys.stderr)
                return []
            else:
                print(f"❌ HTTP Error {e.code}: {e.reason}", file=sys.stderr)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BASE_DELAY * (attempt + 1))
        except URLError as e:
            print(f"❌ URL Error: {e.reason}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BASE_DELAY * (attempt + 1))
        except Exception as e:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BASE_DELAY * (attempt + 1))

    return None


def process_issues(
    issues_data: List[Dict], debug: bool = False, owner: str = "", repo: str = ""
) -> List[Dict]:
    processed = []
    for issue in issues_data:
        try:
            issue_number = issue.get("number", 0)
            issue_url = issue.get("html_url", "")

            # Skip pull requests
            if "pull_request" in issue:
                if debug:
                    print(f"⏭️ Skipping pull request #{issue_number}")
                continue

            # Skip specific issues depending on repo
            if owner == "xenia-canary" and issue_number == 1:
                if debug:
                    print(f"⏭️ Skipping Canary repo issue #{issue_number}")
                continue
            elif owner == "xenia-project" and issue_number == 2247:
                if debug:
                    print(f"⏭️ Skipping Stable repo issue #{issue_number}")
                continue

            title_data = parse_title(issue.get("title", ""), debug)
            state = parse_labels(issue.get("labels", []), debug)

            # Get all labels
            labels = [label.get("name", "") for label in issue.get("labels", [])]

            # Get updated date
            updated_at = issue.get("updated_at", "")

            game_data = {
                "issue": issue_number,
                "id": title_data["id"],
                "title": title_data["title"],
                "updated": updated_at,
                "state": state,
                "labels": labels,
                "url": issue_url,
            }

            processed.append(game_data)
        except Exception as e:
            print(
                f"❌ Error processing issue {issue.get('number', 'unknown')}: {e}",
                file=sys.stderr,
            )
            continue
    return processed


def get_repo_stats(owner: str, repo: str, debug: bool = False) -> Dict[str, int]:
    """Get repository statistics to understand total issue counts"""
    url = f"{BASE_URL}/repos/{owner}/{repo}"
    data = make_request(url, debug=debug)

    if data and isinstance(data, dict):
        return {
            "open_issues": data.get("open_issues_count", 0),
            "total_issues": data.get("open_issues_count", 0),
        }
    return {"open_issues": 0, "total_issues": 0}


def generate_smart_date_ranges(
    owner: str, repo: str, debug: bool = False
) -> List[tuple]:
    """Generate optimal date ranges based on repository activity"""
    current_date = datetime.now()
    ranges = []

    # For older repositories, use larger chunks for older dates
    # and smaller chunks for recent dates where activity is higher

    # 2013-2018: Yearly chunks (likely low activity)
    for year in range(2013, 2019):
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        ranges.append((start_date, end_date, f"{year}"))

    # 2019-2021: 6-month chunks (medium activity)
    for year in range(2019, 2022):
        ranges.append((f"{year}-01-01", f"{year}-06-30", f"{year} H1"))
        ranges.append((f"{year}-07-01", f"{year}-12-31", f"{year} H2"))

    # 2022-current: Quarterly chunks (high activity)
    for year in range(2022, current_date.year + 1):
        quarters = [
            ("01-01", "03-31", "Q1"),
            ("04-01", "06-30", "Q2"),
            ("07-01", "09-30", "Q3"),
            ("10-01", "12-31", "Q4"),
        ]

        for start_month_day, end_month_day, quarter in quarters:
            start_date = f"{year}-{start_month_day}"
            end_date = f"{year}-{end_month_day}"

            # Don't process future dates
            if datetime.strptime(start_date, "%Y-%m-%d") > current_date:
                break

            ranges.append((start_date, end_date, f"{year} {quarter}"))

    return ranges


def fetch_issues_optimized_chunks(
    owner: str, repo: str, debug: bool = False
) -> List[Dict]:
    """Optimized chunking strategy with better rate limiting"""
    all_issues = []
    date_ranges = generate_smart_date_ranges(owner, repo, debug)

    print(f"🗓️  Using optimized chunking: {len(date_ranges)} date ranges")

    for i, (start_date, end_date, label) in enumerate(date_ranges):
        print(f"📅 Fetching issues from {label} ({i+1}/{len(date_ranges)})...")

        page = 1
        range_issues = []

        while True:
            params = {
                "q": f"repo:{owner}/{repo} is:issue is:open created:{start_date}..{end_date}",
                "sort": "created",
                "order": "desc",
                "per_page": PER_PAGE,
                "page": page,
            }

            url = f"{BASE_URL}/search/issues"
            data = make_request(url, params, debug, is_search=True)

            if not data or not isinstance(data, dict):
                break

            items = data.get("items", [])
            total_count = data.get("total_count", 0)

            if not items:
                break

            if debug:
                print(
                    f"  📄 {label} Page {page}: {len(items)} issues (total in range: {total_count})"
                )

            processed_issues = process_issues(items, debug, owner, repo)
            range_issues.extend(processed_issues)

            if len(items) < PER_PAGE:
                break

            page += 1

            # Safety valve - search API has a 1000 result limit anyway
            if page > 10:
                print(f"  ⚠️  Reached pagination limit for {label}")
                break

        print(f"✅ {label}: Found {len(range_issues)} issues")
        all_issues.extend(range_issues)

        # Extra pause between date ranges to be respectful
        if i < len(date_ranges) - 1:  # Don't sleep after the last range
            time.sleep(1)

    # Remove duplicates
    seen_urls = set()
    unique_issues = []
    for issue in all_issues:
        if issue["url"] not in seen_urls:
            seen_urls.add(issue["url"])
            unique_issues.append(issue)

    if len(all_issues) != len(unique_issues):
        print(f"🔄 Removed {len(all_issues) - len(unique_issues)} duplicate issues")

    return unique_issues


def fetch_all_issues(owner: str, repo: str, debug: bool = False) -> List[Dict]:
    """Standard API fetch with improved rate limiting"""
    if not validate_repo_exists(owner, repo, debug):
        return []

    repo_stats = get_repo_stats(owner, repo, debug)
    if debug:
        print(
            f"📊 Repository stats: {repo_stats['open_issues']} open issues (includes PRs)"
        )

    all_issues = []
    page = 1
    max_pages = 100

    while page <= max_pages:
        params = {
            "state": STATE,
            "per_page": PER_PAGE,
            "page": page,
            "sort": "created",
            "direction": "desc",
        }

        url = f"{BASE_URL}/repos/{owner}/{repo}/issues"
        data = make_request(url, params, debug)

        if data is None:
            print("❌ Failed to fetch data (connection error)")
            break
        elif isinstance(data, list) and len(data) == 0:
            if page == 1:
                print("✅ No issues found in repository")
            else:
                if debug:
                    print(f"✅ No more issues (reached end at page {page})")
                else:
                    print("✅ Reached end of available data")
            break

        if not isinstance(data, list):
            print(f"❌ Expected list, got {type(data)}", file=sys.stderr)
            if isinstance(data, dict) and "message" in data:
                print(f"   API message: {data['message']}", file=sys.stderr)
            break

        if debug:
            print(
                f"📄 Processing page {page} with {len(data)} issues (total: {len(all_issues)})"
            )

        processed_issues = process_issues(data, debug, owner, repo)
        all_issues.extend(processed_issues)

        if len(data) < PER_PAGE:
            if debug:
                print(f"📄 Last page reached (got {len(data)} < {PER_PAGE})")
            break

        page += 1

    if len(all_issues) >= 999 and page > 10:
        print(
            "⚠️  Note: Hit GitHub's pagination limit (~1000 results).", file=sys.stderr
        )
        print(
            "   Use --complete flag to fetch all issues via search API.",
            file=sys.stderr,
        )

    return all_issues


def save_compatibility_data(issues: List[Dict], output_file: str) -> bool:
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        def extract_issue_number(game: Dict) -> int:
            return game.get("issue", 0)

        issues.sort(key=extract_issue_number, reverse=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)

        print(f"✅ Saved {len(issues)} games to {output_file}")
        return True
    except Exception as e:
        print(f"❌ Error saving to {output_file}: {e}", file=sys.stderr)
        return False


def check_rate_limit_status():
    """Check current rate limit status"""
    url = f"{BASE_URL}/rate_limit"
    try:
        request = Request(url, headers=get_headers())
        with urlopen(request, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                core_limit = data["resources"]["core"]
                search_limit = data["resources"]["search"]

                print(f"📊 Rate Limit Status:")
                print(
                    f"   Core API: {core_limit['remaining']}/{core_limit['limit']} remaining"
                )
                print(
                    f"   Search API: {search_limit['remaining']}/{search_limit['limit']} remaining"
                )

                if core_limit["remaining"] < 100:
                    reset_time = datetime.fromtimestamp(core_limit["reset"])
                    print(f"   ⚠️  Core API resets at: {reset_time}")

                return core_limit["remaining"], search_limit["remaining"]
    except Exception as e:
        print(f"⚠️  Could not check rate limit: {e}")
        return None, None


def main():
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv
    complete_fetch = "--complete" in sys.argv or "-c" in sys.argv
    check_limits = "--check-limits" in sys.argv

    if check_limits:
        check_rate_limit_status()
        return

    if "--stable" in sys.argv:
        owner = "xenia-project"
        repo = "game-compatibility"
        output_file = "data/game-compatibility/stable.json"
    else:
        owner = DEFAULT_OWNER
        repo = DEFAULT_REPO
        output_file = DEFAULT_OUTPUT_FILE

    if debug_mode:
        print("🐛 Debug mode enabled")

    if complete_fetch:
        print("🔄 Complete fetch mode enabled - using optimized chunking")

    if not GITHUB_TOKEN:
        print(
            "⚠️  Warning: GITHUB_TOKEN not set. API requests will be severely rate-limited.",
            file=sys.stderr,
        )
        print(
            "   Please set the TOKEN environment variable with your GitHub token.",
            file=sys.stderr,
        )

    # Check initial rate limit status
    core_remaining, search_remaining = check_rate_limit_status()

    if core_remaining is not None and core_remaining < 100:
        print(
            "⚠️  Warning: Low API quota remaining. Consider waiting or using a token.",
            file=sys.stderr,
        )

    print(f"Fetching compatibility data from {owner}/{repo}")

    if complete_fetch:
        print("🔍 Using optimized search API with smart chunking...")
        issues = fetch_issues_optimized_chunks(owner, repo, debug_mode)
    else:
        print("📡 Using standard issues API (limited to ~1000 results)...")
        issues = fetch_all_issues(owner, repo, debug_mode)

        if len(issues) >= 999:
            print("💡 Tip: Use --complete flag to fetch all issues via search API.")

    if not issues:
        print("❌ No issues fetched or error occurred", file=sys.stderr)
        sys.exit(1)

    if not save_compatibility_data(issues, output_file):
        sys.exit(1)

    # Summary statistics
    states = {}
    for issue in issues:
        state = issue["state"]
        states[state] = states.get(state, 0) + 1

    print("\n📊 Compatibility Summary:")
    for state, count in sorted(states.items()):
        print(f"  {state}: {count}")

    print(f"\n🎮 Total games: {len(issues)}")

    if debug_mode:
        print(f"\n🔍 Debug Summary:")
        for i, game in enumerate(issues[:3]):
            print(
                f"  {i+1}. ID={game['id']}, Title='{game['title']}', State={game['state']}"
            )
        if len(issues) > 3:
            print(f"  ... and {len(issues) - 3} more")


if __name__ == "__main__":
    main()
