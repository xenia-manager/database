# Xenia Manager Database

This repository serves as a centralized public database for Xbox 360 game compatibility, patches, and related metadata, intended for use with [Xenia Manager](https://github.com/xenia-manager/xenia-manager).

---

## 📁 Repository Structure

The `data` folder contains several JSON files and subfolders, organized as follows:

- `game-compatibility/`  
  - `stable.json` — Xenia Stable Compatibility List  
  - `canary.json` — Xenia Canary Compatibility List

- `metadata` — scraped games metadata
  - `launchbox` - processed Launchbox Database metadata (Daily)
    - `games.json` - full metadata for every game
    - `search.json` - short metadata used to search
    - `titles` - every game metadata split into it's own JSON file

- `wikipedia_games.json` — (Deprecated) Wikipedia-based game list

- `patches/`  
  - `canary.json` — Canary build patches  
  - `netplay.json` — Netplay-specific patches

- `version.json` - cached latest GitHub releases for Xenia Manager

- `gamecontrollerdb.txt` - cached SDL game controller database (credits to [mdqinc](https://github.com/mdqinc/SDL_GameControllerDB))

---

## 🌐 Data Information

### Game Compatibility Information

- **Xenia Stable Compatibility List:**  
  [stable.json](https://raw.githubusercontent.com/xenia-manager/database/main/data/game-compatibility/stable.json)  
  `data/game-compatibility/stable.json`

- **Xenia Canary Compatibility List:**  
  [canary.json](https://raw.githubusercontent.com/xenia-manager/database/main/data/game-compatibility/canary.json)  
  `data/game-compatibility/canary.json`

### Game Information

- **Launchbox Database (Processed):**  
  [games.json](https://raw.githubusercontent.com/xenia-manager/database/main/data/metadata/launchbox/games.json)  
  `data/metadata/launchbox/games.json`

- **Wikipedia List of Xbox360 Games (No longer used):**  
  [wikipedia_games.json](https://raw.githubusercontent.com/xenia-manager/database/main/data/wikipedia_games.json)  
  `data/wikipedia_games.json`

### Patches

- **Canary Patches:**  
  [patches/canary_patches.json](https://raw.githubusercontent.com/xenia-manager/database/main/data/patches/canary.json)  
  `data/patches/canary.json`

- **Netplay Patches:**  
  [patches/netplay_patches.json](https://raw.githubusercontent.com/xenia-manager/database/main/data/patches/netplay.json)  
  `data/patches/netplay.json`

## How It Works

- **Data Format:**  
  All files are in JSON format, making them easy to parse in any programming language.

- **Autoupdate:**  
  The `update_database.yml` GitHub Actions workflow automatically updates `version.json` hourly, while other information is updated once per day.

- **Usage:**  
  Fork the repository.
  You can fetch and use these files in your own tools, scripts, or applications.


## Credits
- [Launchbox (Games Metadata)](https://www.launchbox-app.com/)
- [mdqinc (Comprehensive SDL Game Controller database)](https://github.com/mdqinc/SDL_GameControllerDB)
- [Xenia (Emulator, their compatibility tracker & game patches)](http://xenia.jp/)
