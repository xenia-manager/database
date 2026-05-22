import json, urllib.request, os, sys
from pathlib import Path

GITHUB_API = "https://api.github.com/repos"

# Base directory (project root)
BASE_DIR = Path(__file__).parent.parent


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
        text = resp.read()
        debug(f"Response status: {resp.status}, length: {len(text)} bytes")
        return json.loads(text)


# ----- Xenia Manager tags -----
def fetch_latest_tag_string(repo_url):
    try:
        debug(f"Fetching latest tag from {repo_url}")
        data = gh_get(repo_url)
        tag = data.get("tag_name")
        date = data.get("published_at") or data.get("created_at")
        debug(f"Tag found: {tag}")
        return tag
    except Exception as e:
        print(f"Error fetching {repo_url}: {e}", file=sys.stderr)
        return {"tag_name": None, "date": None}


def fetch_xenia_manager_data():
    stable_tag = fetch_latest_tag_string(
        f"{GITHUB_API}/xenia-manager/xenia-manager/releases/latest"
    )
    experimental_tag = fetch_latest_tag_string(
        f"{GITHUB_API}/xenia-manager/experimental-builds/releases/latest"
    )

    def get_download_url(repo):
        try:
            data = gh_get(f"{GITHUB_API}/{repo}/releases/latest")
            assets = [a for a in data.get("assets", [])]
            return assets[0].get("browser_download_url") if assets else None
        except Exception as e:
            debug(f"Error fetching download URL for {repo}: {e}")
            return None

    return {
        # Old format for backwards compatibility
        "stable": stable_tag,
        "experimental": experimental_tag,
        # New format with tag_name and url
        "xenia_manager": {
            "stable": {
                "tag_name": stable_tag,
                "url": get_download_url("xenia-manager/xenia-manager"),
            },
            "experimental": {
                "tag_name": experimental_tag,
                "url": get_download_url("xenia-manager/experimental-builds"),
            },
        },
    }


# ----- Canary (read from canary.json) -----
def fetch_latest_canary(old_version=None):
    """Read the latest canary release from canary.json (already fetched by canary.py)."""
    canary_path = BASE_DIR / "data" / "xenia-releases" / "canary.json"

    # Try to load canary.json
    if not os.path.exists(canary_path):
        debug("canary.json not found, falling back to API fetch")
        return _fetch_canary_from_api(old_version)

    try:
        with open(canary_path, "r", encoding="utf-8") as f:
            releases = json.load(f)

        if not releases:
            debug("No releases in canary.json, using old version")
            return old_version

        # First release is the newest (already sorted by canary.py)
        latest = releases[0]
        tag_name = latest.get("tag_name")
        target_commitish = latest.get("target_commitish", "")
        published_at = latest.get("published_at")
        assets = latest.get("assets", [])

        # Find Windows asset
        windows_asset = None
        for asset in assets:
            if "windows" in asset.get("name", "").lower():
                windows_asset = asset
                break

        if not windows_asset:
            debug("No Windows asset found in canary.json, using old version")
            return old_version

        return {
            "tag_name": tag_name,
            "date": published_at,
            "url": windows_asset.get("url"),
        }
    except Exception as e:
        debug(f"Error reading canary.json: {e}, falling back to API fetch")
        return _fetch_canary_from_api(old_version)


def _fetch_canary_from_api(old_version=None):
    """Fallback: Fetch latest canary from GitHub API (old behavior)."""
    repo = "xenia-canary/xenia-canary"
    debug(f"Fetching latest release for {repo}")

    # Fetch only the first page of releases
    try:
        releases = gh_get(f"{GITHUB_API}/{repo}/releases?per_page=100&page=1")
        if not releases:
            debug("No releases found, using old version")
            return old_version

        # Sort by release date (newest first)
        releases.sort(
            key=lambda r: r.get("published_at") or r.get("created_at") or "",
            reverse=True,
        )

        # Find the latest release that doesn't contain "experimental" in tag name
        for rel in releases:
            tag = rel.get("tag_name", "").lower()
            # Skip if tag is exactly "experimental" (no SHA prefix)
            if tag == "experimental":
                continue
            assets = [
                a for a in rel.get("assets", []) if "windows" in a["name"].lower()
            ]
            if assets:
                asset = assets[0]
                # Get target_commitish (full commit SHA) from the release
                target_commitish = rel.get("target_commitish", "")
                # Use target_commitish (short 7 chars) as tag_name, fall back to tag if missing
                tag_name = (
                    target_commitish[:7]
                    if target_commitish
                    else (rel.get("tag_name")[:7] if rel.get("tag_name") else None)
                )
                return {
                    "tag_name": tag_name,
                    "date": rel.get("published_at") or rel.get("created_at"),
                    "url": asset.get("browser_download_url"),
                }

        debug("No non-experimental release found, using old version")
        return old_version
    except Exception as e:
        debug(f"Error fetching releases: {e}, using old version")
        return old_version


# ----- Netplay stable -----
def fetch_netplay_stable():
    rel = gh_get(f"{GITHUB_API}/AdrianCassar/xenia-canary/releases/latest")
    assets = [a for a in rel.get("assets", []) if "windows" in a["name"].lower()]
    return {
        "tag_name": rel.get("tag_name")[:7] if rel.get("tag_name") else None,
        "date": rel.get("published_at") or rel.get("created_at"),
        "url": assets[0].get("browser_download_url") if assets else None,
    }


# ----- Netplay nightly -----
def fetch_netplay_nightly():
    branch = "netplay_canary_experimental"
    commit_data = gh_get(f"{GITHUB_API}/AdrianCassar/xenia-canary/commits/{branch}")
    sha_full = commit_data.get("sha", "")
    sha_short = sha_full[:7]
    parents = commit_data.get("parents", [])
    parent_sha = parents[0]["sha"][:7] if parents else None
    date = commit_data.get("commit", {}).get("author", {}).get("date")
    return {
        "tag_name": sha_short or parent_sha or None,
        "commit_sha": sha_full or None,
        "date": date,
        "url": "https://nightly.link/AdrianCassar/xenia-canary/workflows/"
        "Windows_build/netplay_canary_experimental/xenia_canary_netplay_windows.zip",
    }


# ----- Mousehook versions -----
def fetch_mousehook_versions():
    releases = gh_get(f"{GITHUB_API}/marinesciencedude/xenia-canary-mousehook/releases")

    def fmt(rel):
        if not rel:
            return {"tag_name": None, "url": None, "date": None}
        url = (
            rel["assets"][0].get("browser_download_url") if rel.get("assets") else None
        )
        return {
            "tag_name": rel.get("tag_name"),
            "date": rel.get("published_at") or rel.get("created_at"),
            "url": url,
        }

    def is_netplay(rel):
        tag = rel.get("tag_name", "").lower()
        commitish = rel.get("target_commitish", "").lower()
        return "netplay" in tag or "netplay" in commitish

    standard_rel = next((r for r in releases if not is_netplay(r)), None)
    netplay_rel = next((r for r in releases if is_netplay(r)), None)
    return {"standard": fmt(standard_rel), "netplay": fmt(netplay_rel)}


# ----- MAIN -----
debug("=== Starting version fetch process ===")

# Load existing version.json to use as fallback
old_data = {}
if os.path.exists("data/version.json"):
    try:
        with open("data/version.json", "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except Exception as e:
        debug(f"Error loading old version.json: {e}")

old_canary = old_data.get("xenia", {}).get("canary")

fetched_data = {
    **fetch_xenia_manager_data(),
    "xenia": {
        "canary": fetch_latest_canary(old_canary),
        "netplay": {
            "stable": fetch_netplay_stable(),
            "nightly": fetch_netplay_nightly(),
        },
        "mousehook": fetch_mousehook_versions(),
    },
}

os.makedirs("data", exist_ok=True)
with open("data/version.json", "w", encoding="utf-8") as f:
    json.dump(fetched_data, f, indent=2)

print(json.dumps(fetched_data, indent=2))
print("✅ version.json updated with latest releases")
