import json
import urllib.request
import os
import sys
import re
from pathlib import Path

GITHUB_API = "https://api.github.com/repos"
GITHUB_COMMIT_URL = "https://github.com/xenia-canary/xenia-canary/commit/"

# Base directory (project root)
BASE_DIR = Path(__file__).parent.parent.parent


def debug(msg):
    print(f"[DEBUG] {msg}", file=sys.stderr)


def gh_get(url):
    debug(f"Requesting {url}")
    headers = {"User-Agent": "github-actions", "Accept": "application/vnd.github+json"}
    token = os.environ.get("AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        debug("Using AUTH_TOKEN for authentication")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        # Check rate limit headers
        remaining = resp.headers.get("X-RateLimit-Remaining")
        limit = resp.headers.get("X-RateLimit-Limit")
        reset_time = resp.headers.get("X-RateLimit-Reset")
        debug(f"Rate limit: {remaining}/{limit} remaining, resets at {reset_time}")
        if remaining is not None and int(remaining) == 0:
            raise RuntimeError("GitHub API rate limit reached, stopping execution.")
        text = resp.read()
        debug(f"Response status: {resp.status}, length: {len(text)} bytes")
        return json.loads(text)


def split_changes(body: str):
    if not body:
        return {"title": "", "changes": ""}

    # If body starts with "### Changes", strip it and use commit message for title
    if body.startswith("### Changes"):
        changes = body.replace("### Changes", "", 1).strip()
        return {"title": "", "changes": changes}

    parts = body.split("\n\n", 1)
    title = parts[0].strip()
    changes = parts[1].strip() if len(parts) > 1 else ""
    return {"title": title, "changes": changes}


async def fetch_full_shas_batch_with_crawlee(short_shas: list[str]) -> dict[str, str]:
    """Fetch multiple full commit SHAs from GitHub using Crawlee in batch."""
    try:
        from crawlee import ConcurrencySettings, Request
        from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

        results = {}

        crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=len(short_shas),
            concurrency_settings=ConcurrencySettings(max_concurrency=10),
        )

        @crawler.router.default_handler
        async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
            short_sha = context.request.user_data.get("short_sha")
            soup = context.soup

            # Method 1: Check og:url meta tag
            og_url = soup.find("meta", property="og:url")
            if og_url and og_url.get("content"):
                match = re.search(r"commit/([a-f0-9]{40})", og_url.get("content"))
                if match:
                    results[short_sha] = match.group(1)
                    debug(f"  ✓ {short_sha} -> {match.group(1)}")
                    return

            # Method 2: Check data-copied attribute
            copied = soup.find(attrs={"data-copied": re.compile(r"^[a-f0-9]{40}$")})
            if copied:
                full_sha = copied.get("data-copied")
                results[short_sha] = full_sha
                debug(f"  ✓ {short_sha} -> {full_sha}")
                return

            # Method 3: Check code element with commit-sha class
            code = soup.find("code", class_=re.compile(r"commit-sha"))
            if code:
                match = re.search(r"([a-f0-9]{40})", code.get_text())
                if match:
                    results[short_sha] = match.group(1)
                    debug(f"  ✓ {short_sha} -> {match.group(1)}")
                    return

            debug(f"  ✗ Failed to extract SHA for {short_sha}")

        requests = [
            Request.from_url(
                f"{GITHUB_COMMIT_URL}{short_sha}", user_data={"short_sha": short_sha}
            )
            for short_sha in short_shas
        ]

        await crawler.run(requests)
        return results
    except Exception as e:
        debug(f"Failed to fetch full SHAs with Crawlee: {e}")
        return {}


def fetch_full_shas_batch(short_shas: list[str]) -> dict[str, str]:
    """Fetch multiple full commit SHAs from GitHub commit pages."""
    import asyncio

    return asyncio.run(fetch_full_shas_batch_with_crawlee(short_shas))


def fetch_commit_details(repo: str, tag: str):
    """Fetch commit from release tag and parse its message into title/body."""
    url = f"{GITHUB_API}/xenia-canary/xenia-canary/commits/{tag}"
    try:
        commit_data = gh_get(url)
        full_msg = commit_data["commit"]["message"]
        lines = full_msg.splitlines()
        title = lines[0]
        body = "\n".join(lines[1:]).strip()
        return {"title": title, "changes": body}
    except Exception as e:
        debug(f"Failed to fetch commit for {repo}@{tag}: {e}")
        return {"title": "", "changes": ""}


def fetch_releases(repo: str, existing_tags=None):
    """Fetch all releases page by page first, then filter if existing_tags is provided."""
    all_releases = []
    page = 1
    per_page = 100

    # Phase 1: Fetch ALL releases from GitHub API first
    while True:
        url = f"{GITHUB_API}/{repo}/releases?per_page={per_page}&page={page}"
        try:
            batch = gh_get(url)
        except Exception as e:
            debug(f"Error fetching page {page} for {repo}: {e}")
            debug(f"Stopping fetch, assuming final page reached.")
            break
        if not batch or len(batch) == 0:
            debug(f"No more releases on {repo}, page {page}, stopping.")
            break
        debug(f"Fetched {len(batch)} releases from {repo}, page {page}")
        all_releases.extend(batch)
        page += 1

    debug(f"Total releases fetched from {repo}: {len(all_releases)}")

    # Phase 2: Filter releases if existing_tags is provided
    if existing_tags:
        filtered_releases = []
        for rel in all_releases:
            if rel.get("tag_name") not in existing_tags:
                filtered_releases.append(rel)
            else:
                # Stop when we hit an existing tag (releases are ordered by date)
                debug(f"Found existing tag {rel.get('tag_name')}, stopping filter.")
                break
        debug(f"New releases after filtering: {len(filtered_releases)}")
        return filtered_releases

    return all_releases


def process_releases(raw_releases, repo: str):
    results = []
    # Collect entries that need full SHA fetching
    entries_needing_sha = []

    for rel in raw_releases:
        tag = rel.get("tag_name", "")
        # Extract SHA from tag (first 7 characters if it's a valid hex SHA)
        # Handles formats: "8911a3b", "8911a3b_canary_experimental", etc.
        sha = tag[:7] if len(tag) >= 7 else tag
        if len(sha) != 7 or not all(c in "0123456789abcdef" for c in sha.lower()):
            debug(f"Skipping invalid release tag: {tag}")
            continue
        assets = [
            {"name": a["name"], "url": a["browser_download_url"]}
            for a in rel.get("assets", [])
            if "xenia" in a["name"].lower()
        ]
        if not assets:
            debug(f"Skipping release {tag} because it has no matching assets")
            continue

        body_split = split_changes(rel.get("body") or "")
        title, changes = body_split["title"], body_split["changes"]

        # --- Fallback to commit if body missing ---
        if not title and not changes:
            debug(f"No changelog for {tag}, fetching commit info from repo")
            commit_info = fetch_commit_details(repo, tag)
            title, changes = commit_info["title"], commit_info["changes"]

        # --- Fallback to release name if title still empty ---
        if not title:
            release_name = rel.get("name", "")
            if release_name:
                debug(f"Using release name as title for {tag}: {release_name}")
                title = release_name

        # Use target_commitish (short 7 chars) as tag_name, fall back to tag if missing
        target_commitish = rel.get("target_commitish", "")

        # Validate target_commitish is a commit SHA, not a branch name
        if target_commitish and (
            len(target_commitish) < 7
            or not all(c in "0123456789abcdef" for c in target_commitish[:7].lower())
        ):
            # target_commitish is invalid (e.g., "canary_experimental"), use tag instead
            tag_name = tag[:7] if tag else None
            # Store the tag's SHA for later full SHA fetching
            short_sha = tag[:7] if tag else None
            entries_needing_sha.append(
                {
                    "result_index": len(results),
                    "short_sha": short_sha,
                }
            )
        else:
            tag_name = (
                target_commitish[:7] if target_commitish else (tag[:7] if tag else None)
            )
            short_sha = target_commitish if target_commitish else tag
            # Check if it's a short SHA (7 chars) that needs to be expanded
            if len(short_sha) == 7:
                entries_needing_sha.append(
                    {
                        "result_index": len(results),
                        "short_sha": short_sha,
                    }
                )

        results.append(
            {
                "tag_name": tag_name,
                "target_commitish": short_sha if short_sha else None,
                "published_at": rel.get("published_at"),
                "url": rel.get("html_url"),
                "commit_url": (
                    f"https://github.com/xenia-canary/xenia-canary/commit/{short_sha}"
                    if short_sha
                    else (
                        f"https://github.com/xenia-canary/xenia-canary/commit/{tag}"
                        if tag
                        else None
                    )
                ),
                "changelog": {"title": title, "changes": changes},
                "assets": assets,
            }
        )
        debug(f"Prepared release {tag_name} with {len(assets)} assets")

    # Fetch full SHAs for entries that need them (batch processing)
    if entries_needing_sha:
        unique_shas = list(
            set(
                entry["short_sha"]
                for entry in entries_needing_sha
                if entry["short_sha"]
            )
        )
        debug(f"Fetching full SHAs for {len(unique_shas)} unique entries...")
        full_shas = fetch_full_shas_batch(unique_shas)

        # Update results with fetched full SHAs
        for entry in entries_needing_sha:
            short_sha = entry["short_sha"]
            if short_sha and short_sha in full_shas:
                result_index = entry["result_index"]
                full_sha = full_shas[short_sha]
                results[result_index]["target_commitish"] = full_sha
                results[result_index]["commit_url"] = f"{GITHUB_COMMIT_URL}{full_sha}"
            elif short_sha:
                debug(
                    f"  ✗ Failed to fetch full SHA for {short_sha}, keeping short SHA"
                )

    return results


# ----- MAIN -----
os.makedirs("data/xenia-releases/", exist_ok=True)
output_path = "data/xenia-releases/canary.json"

if not os.path.exists(output_path):
    debug("No existing JSON, fetching all releases from xenia-canary...")
    all_releases = []
    repo = "xenia-canary/xenia-canary"
    raw = fetch_releases(repo)
    processed = process_releases(raw, repo)
    debug(f"Adding {len(processed)} releases from {repo}")
    all_releases.extend(processed)
else:
    debug("Existing JSON found, fetching new releases from xenia-canary...")
    with open(output_path, "r", encoding="utf-8") as f:
        existing = json.load(f)

    existing_dict = {r["tag_name"]: r for r in existing}
    # Filter out experimental tags from existing_tags to avoid stopping early
    # Skip only exact "experimental" and "canary_experimental" tags, keep SHA+experimental (e.g., 8911a3b_experimental)
    existing_tags = {
        tag
        for tag in existing_dict.keys()
        if tag.lower() != "experimental" and "canary_experimental" not in tag.lower()
    }

    raw_releases = fetch_releases("xenia-canary/xenia-canary", existing_tags)
    processed_releases = process_releases(raw_releases, "xenia-canary/xenia-canary")
    new_count = 0
    for release in processed_releases:
        if release["tag_name"] not in existing_dict:
            existing_dict[release["tag_name"]] = release
            new_count += 1
            debug(f"Added new release {release['tag_name']} (total new: {new_count})")
    all_releases = list(existing_dict.values())
    debug(f"Total new releases added: {new_count}")

debug(f"Total releases after update: {len(all_releases)}")

# sort newest first
all_releases.sort(key=lambda r: r.get("published_at") or "", reverse=True)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(all_releases, f, indent=2)

debug(f"Saved {len(all_releases)} releases to {output_path}")
