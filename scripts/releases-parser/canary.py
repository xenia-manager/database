import json, urllib.request, os, sys

GITHUB_API = "https://api.github.com/repos"


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
    parts = body.split("\n\n", 1)
    title = parts[0].strip()
    changes = parts[1].strip() if len(parts) > 1 else ""
    return {"title": title, "changes": changes}


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
    """Fetch releases page by page. If existing_tags is provided, stop when reaching a known tag."""
    releases = []
    page = 1
    per_page = 100
    while True:
        url = f"{GITHUB_API}/{repo}/releases?per_page={per_page}&page={page}"
        batch = gh_get(url)
        if not batch or len(batch) == 0:
            debug(f"No more releases on page {page} for {repo}, stopping.")
            break
        debug(f"Fetched {len(batch)} releases from {repo}, page {page}")

        # If we have existing tags, check if we've reached a known release
        if existing_tags:
            found_existing = False
            for rel in batch:
                if rel.get("tag_name") in existing_tags:
                    debug(
                        f"Found existing tag {rel.get('tag_name')} on page {page}, stopping."
                    )
                    found_existing = True
                    break
            # Add all new releases from this page (before the existing tag)
            if found_existing:
                for rel in batch:
                    if rel.get("tag_name") not in existing_tags:
                        releases.append(rel)
                return releases
            debug(f"No existing tags found on page {page}, continuing.")

        releases.extend(batch)
        page += 1
    return releases


def process_releases(raw_releases, repo: str):
    results = []
    for rel in raw_releases:
        tag = rel.get("tag_name", "")
        # Skip tags that are ONLY "experimental" but keep ones with commit SHA (e.g., 8911a3b_experimental)
        if tag.lower() == "experimental" or tag.lower() == "canary_experimental":
            debug(f"Skipping experimental release: {tag}")
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

        # Use target_commitish (short 7 chars) as tag_name, fall back to tag if missing
        target_commitish = rel.get("target_commitish", "")
        tag_name = (
            target_commitish[:7] if target_commitish else (tag[:7] if tag else None)
        )

        results.append(
            {
                "tag_name": tag_name,
                "target_commitish": target_commitish if target_commitish else None,
                "published_at": rel.get("published_at"),
                "url": rel.get("html_url"),
                "commit_url": (
                    f"https://github.com/xenia-canary/xenia-canary/commit/{target_commitish}"
                    if target_commitish
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
