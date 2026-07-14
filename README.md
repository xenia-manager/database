# Xenia Manager Database

This repository serves as a centralized public database for Xbox 360 game compatibility, patches, and related metadata, intended for use with [Xenia Manager](https://github.com/xenia-manager/xenia-manager).

All files are in JSON format and can be fetched directly from GitHub raw URLs.

---

## Data Files

### Game Compatibility

| File | Description |
|------|-------------|
| `game-compatibility/canary.json` | Xenia Canary compatibility from GitHub issues |
| `game-compatibility/stable.json` | Xenia Stable compatibility from GitHub issues |
| `game-compatibility/netplay.json` | Netplay/Xbox Live compatibility from [Xenia Netplay](https://github.com/AdrianCassar/xenia-canary) |
| `game-compatibility/mousehook.json` | Mousehook mouse-aim support from [Xenia Mousehook](https://github.com/marinesciencedude/xenia-canary-mousehook) |

### Patches

| File | Description |
|------|-------------|
| `patches/canary.json` | Canary game patches (`.patch.toml` files) |
| `patches/netplay.json` | Netplay-specific patches |

### Metadata

| File | Description |
|------|-------------|
| `metadata/launchbox/games.json` | Full LaunchBox metadata for every game |
| `metadata/launchbox/search.json` | Lightweight name + ID index for search |

### Other

| File | Description |
|------|-------------|
| `version.json` | Cached latest release versions for all products |
| `xenia-releases/canary.json` | Full Xenia Canary release history |
| `gamecontrollerdb.txt` | SDL GameControllerDB mappings |

---

## Schemas

### Game Compatibility (canary.json, stable.json)

```json
{
  "issue": 1162,
  "id": "58410B16",
  "title": "Street Fighter III: Online Edition",
  "updated": "2026-07-14T11:18:37Z",
  "state": "Gameplay",
  "labels": {
    "state": ["state-gameplay"],
    "others": []
  },
  "url": "https://github.com/xenia-canary/game-compatibility/issues/1162"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `issue` | number | GitHub issue number |
| `id` | string | 8-character uppercase hex Xbox Title ID |
| `title` | string | Game title |
| `updated` | string | ISO 8601 timestamp of last update |
| `state` | string | Compatibility state: `"Unplayable"`, `"Loads"`, `"Gameplay"`, `"Playable"` |
| `labels.state` | string[] | GitHub labels indicating state |
| `labels.others` | string[] | Any other GitHub labels |
| `url` | string | Link to the GitHub issue |

### Netplay Compatibility (netplay.json)

```json
{
  "id": "415607FF",
  "title": "007: Quantum of Solace",
  "status": {
    "working_public": "partial",
    "tested_locally": null,
    "only_local": null,
    "systemlink": "partial"
  },
  "comments": "Patch required for systemlink. Systemlink requires a server.",
  "links": [
    {
      "text": "Systemlink Patch",
      "url": "https://github.com/AdrianCassar/Xenia-WebServices/blob/main/patches/415607FF%20-%20Quantum%20of%20Solace.patch.toml"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | 8-character uppercase hex Xbox Title ID |
| `title` | string | Game title |
| `status.working_public` | string \| null | `"ok"`, `"partial"`, `"fail"`, or `null` if untested |
| `status.tested_locally` | string \| null | Same values |
| `status.only_local` | string \| null | Same values |
| `status.systemlink` | string \| null | Same values |
| `comments` | string | Flattened notes (single line, no markdown) |
| `links` | array | Related patches, videos, etc. |

### Mousehook Compatibility (mousehook.json)

```json
{
  "id": "5454082B",
  "title": "Red Dead Redemption",
  "mouse_support": "Good",
  "supported_versions": "Original TU0/TU9, Undead Nightmare (Platinum Hits) TU4 & Game Of The Year Edition Disk 1/2 TU0",
  "notes": "Duel crosshair isn't mousehooked, RS is emulated when in duels"
}
```

Games with multiple Title IDs use an array:

```json
{
  "id": ["545107D1", "545107F8"],
  "title": "Saints Row 1",
  "mouse_support": "Fair",
  "supported_versions": "TU1 US/TU0 JP",
  "notes": "..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string \| string[] | 8-char hex Title ID(s) |
| `title` | string | Game title |
| `mouse_support` | string | `"Good"`, `"Fair"`, or `"Poor"` |
| `supported_versions` | string | Tested build/TU versions |
| `notes` | string | Flattened notes (single line, no HTML/markdown) |

### Patches (patches/canary.json, patches/netplay.json)

GitHub Contents API response for patch `.patch.toml` files:

```json
{
  "name": "415607D1 - Call of Duty 2.patch.toml",
  "path": "patches/415607D1 - Call of Duty 2.patch.toml",
  "sha": "e000a5895607890e9aae4ca96b5175fb92a6b2e5",
  "size": 396,
  "url": "https://api.github.com/repos/AdrianCassar/Xenia-WebServices/contents/patches/...",
  "html_url": "https://github.com/AdrianCassar/Xenia-WebServices/blob/main/patches/...",
  "download_url": "https://raw.githubusercontent.com/AdrianCassar/Xenia-WebServices/main/patches/...",
  "type": "file"
}
```

### Version (version.json)

```json
{
  "stable": "4.2.2",
  "experimental": "2026-07-14-601cf88",
  "xenia_manager": {
    "stable": { "tag_name": "4.2.2", "url": "..." },
    "experimental": { "tag_name": "2026-07-14-601cf88", "url": "..." }
  },
  "xenia": {
    "canary": { "tag_name": "...", "date": "...", "url": "..." },
    "netplay": {
      "stable": { "tag_name": "...", "date": "...", "url": "..." },
      "nightly": { "tag_name": "...", "commit_sha": "...", "date": "...", "url": "..." }
    },
    "mousehook": {
      "standard": { "tag_name": "...", "date": "...", "url": "..." },
      "netplay": { "tag_name": "...", "date": "...", "url": "..." }
    }
  }
}
```

### LaunchBox Metadata (metadata/launchbox/games.json)

```json
{
  "Name": "Halo 3",
  "DatabaseID": "14927",
  "Developer": "Bungie",
  "Publisher": "Microsoft Game Studios",
  "ReleaseDate": "2007-09-25T00:00:00",
  "Genres": ["First-Person Shooter"],
  "Overview": "...",
  "Artwork": {
    "Box 3D": [...],
    "Box Front": [...],
    "Banner": [...],
    "Background": [...]
  }
}
```

Each artwork entry contains `URL`, `FileName`, `Region`, `Type`, and `CRC32`.

---

## Updating the Data

The `update_database.yml` GitHub Actions workflow updates data automatically:

| Schedule | What updates |
|----------|-------------|
| 3x daily (00:00, 08:00, 16:00 UTC) | Game compatibility, version info, canary releases |
| Daily (00:00 UTC) | Patches, netplay compatibility, mousehook compatibility, gamecontrollerdb, LaunchBox metadata |

All jobs can also be triggered manually via `workflow_dispatch` with per-step toggles.

### Running Scripts Locally

```bash
pip install requests

python scripts/game_compatibility.py          # Canary compatibility
python scripts/game_compatibility.py --stable # Stable compatibility
python scripts/netplay_compatibility.py       # Netplay compatibility
python scripts/mousehook_compatibility.py     # Mousehook compatibility
python scripts/update_versions.py             # Version info
python scripts/releases-parser/canary.py      # Canary release history
python scripts/launchbox_metadata.py          # LaunchBox metadata (requires Metadata.xml)
```

---

## Credits

- [Launchbox](https://www.launchbox-app.com/) — Game metadata
- [mdqinc/SDL_GameControllerDB](https://github.com/mdqinc/SDL_GameControllerDB) — SDL controller mappings
- [AdrianCassar/Xenia-WebServices](https://github.com/AdrianCassar/Xenia-WebServices) — Netplay compatibility & patches
- [marinesciencedude/xenia-canary-mousehook](https://github.com/marinesciencedude/xenia-canary-mousehook) — Mousehook compatibility
- [Xenia](http://xenia.jp/) — Emulator, compatibility tracker & game patches
