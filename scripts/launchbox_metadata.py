import xml.etree.ElementTree as ET
import json
import os
import sys
import time
from datetime import datetime


def categorize_artwork_type(artwork_type):
    """Categorize artwork types into main groups"""
    if not artwork_type:
        return "Other"

    artwork_type_lower = artwork_type.lower()

    if "arcade" in artwork_type_lower:
        return "Arcade"
    elif "banner" in artwork_type_lower:
        return "Banner"
    elif "background" in artwork_type_lower:
        return "Background"
    elif "box" in artwork_type_lower or "fanart - box" in artwork_type_lower:
        return "Box"
    elif "cart" in artwork_type_lower or "fanart - cart" in artwork_type_lower:
        return "Cart"
    elif "disc" in artwork_type_lower or "fanart - disc" in artwork_type_lower:
        return "Disc"
    elif "icon" in artwork_type_lower:
        return "Icon"
    elif "poster" in artwork_type_lower:
        return "Poster"
    elif "screenshot" in artwork_type_lower:
        return "Screenshots"
    elif "square" in artwork_type_lower:
        return "Square"
    else:
        return "Other"


def subcategorize_artwork(artwork_type, main_category):
    """Create subcategories for Box and Cart"""
    if not artwork_type:
        return None

    artwork_type_lower = artwork_type.lower()

    if main_category == "Box":
        if "front" in artwork_type_lower:
            return "Front"
        elif "back" in artwork_type_lower:
            return "Back"
        elif "spine" in artwork_type_lower:
            return "Spine"
        elif "3d" in artwork_type_lower:
            return "3D"
        else:
            return "Other"
    elif main_category == "Cart":
        if "front" in artwork_type_lower:
            return "Front"
        elif "back" in artwork_type_lower:
            return "Back"
        elif "3d" in artwork_type_lower:
            return "3D"
        else:
            return "Other"

    return None


def safe_print(message, file=None):
    """Safely print messages with proper encoding handling"""
    try:
        print(message, file=file)
    except UnicodeEncodeError:
        # Fallback to ASCII with error replacement if Unicode fails
        safe_message = message.encode("ascii", errors="replace").decode("ascii")
        print(safe_message, file=file)


def main():
    # Set UTF-8 encoding for stdout on Windows
    if sys.platform.startswith("win"):
        try:
            # Try to set UTF-8 encoding for console output
            import io

            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
        except:
            # If that fails, we'll handle encoding issues in safe_print
            pass

    # Check for debug mode
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv

    if debug_mode:
        safe_print("[DEBUG] Debug mode enabled")
        safe_print(f"[INFO] Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start_time = time.time()

    # Check if XML file exists
    xml_file = "Metadata/Metadata.xml"
    if not os.path.exists(xml_file):
        safe_print(f"[ERROR] {xml_file} not found", file=sys.stderr)
        safe_print(
            "        Please ensure you have downloaded and extracted the Metadata.zip file",
            file=sys.stderr,
        )
        sys.exit(1)

    if debug_mode:
        file_size = os.path.getsize(xml_file) / (1024 * 1024)  # Size in MB
        safe_print(f"[INFO] XML file size: {file_size:.1f} MB")

    try:
        # Parse Metadata.xml
        if debug_mode:
            safe_print("[INFO] Parsing XML file...")

        tree = ET.parse(xml_file)
        root = tree.getroot()

        if debug_mode:
            safe_print("[SUCCESS] XML parsed successfully")
            safe_print(f"[INFO] Root element: {root.tag}")

    except Exception as e:
        safe_print(f"[ERROR] Error parsing XML file: {e}", file=sys.stderr)
        sys.exit(1)

    # Collect all unique GameImage types
    if debug_mode:
        safe_print("[INFO] Collecting unique GameImage types...")

    gameimage_types = set()
    total_images = 0

    for img in root.findall("GameImage"):
        total_images += 1
        type_text = img.findtext("Type")
        if type_text:
            gameimage_types.add(type_text)

    if debug_mode:
        safe_print(f"[INFO] Found {total_images} total GameImage elements")
        safe_print(f"[INFO] Found {len(gameimage_types)} unique image types")

    safe_print("All unique <GameImage> types:")
    for img_type in sorted(gameimage_types):
        safe_print(f"- {img_type}")

    # Build a mapping from DatabaseID to list of GameImage elements
    if debug_mode:
        safe_print("[INFO] Building DatabaseID to GameImage mapping...")

    images_by_dbid = {}
    images_without_dbid = 0

    for img in root.findall("GameImage"):
        dbid = img.findtext("DatabaseID")
        if dbid:
            images_by_dbid.setdefault(dbid, []).append(img)
        else:
            images_without_dbid += 1

    if debug_mode:
        safe_print(f"[INFO] Games with images: {len(images_by_dbid)}")
        if images_without_dbid > 0:
            safe_print(f"[WARNING] Images without DatabaseID: {images_without_dbid}")

    # Prepare the output lists
    output_games = []
    simplified_games = []

    # Create directories
    if debug_mode:
        safe_print("[INFO] Creating output directories...")

    try:
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/metadata/launchbox/titles", exist_ok=True)
        if debug_mode:
            safe_print("[SUCCESS] Directories created successfully")
    except Exception as e:
        safe_print(f"[ERROR] Error creating directories: {e}", file=sys.stderr)
        sys.exit(1)

    # Process games
    total_games = 0
    xbox360_games = 0
    games_without_dbid = 0
    games_with_artwork = 0
    processed_games = 0

    excluded_fields = [
        "Name",
        "DatabaseID",
        "MaxPlayers",
        "ReleaseType",
        "Cooperative",
        "Platform",
        "CommunityRatingCount",
    ]

    if debug_mode:
        safe_print("[INFO] Processing games...")
        safe_print(f"[INFO] Excluded fields: {', '.join(excluded_fields)}")

    for game in root.findall("Game"):
        total_games += 1

        platform = game.findtext("Platform")
        if platform != "Microsoft Xbox 360":
            continue

        xbox360_games += 1

        dbid = game.findtext("DatabaseID")
        if not dbid:
            games_without_dbid += 1
            if debug_mode and games_without_dbid <= 3:  # Only show first 3
                name = game.findtext("Name", "Unknown")
                safe_print(f"[WARNING] Game without DatabaseID: '{name}'")
            continue

        # Convert the Game element to a dict with specific ordering
        game_dict = {}

        # Add Name first if it exists
        name = game.findtext("Name")
        if name:
            game_dict["Name"] = name

        # Add DatabaseID second
        game_dict["DatabaseID"] = dbid

        # Count fields
        total_fields = len(list(game))
        included_fields = 0

        # Add all other fields in sorted order for deterministic output
        other_fields = {}
        for child in game:
            if child.tag not in excluded_fields:
                other_fields[child.tag] = child.text
                included_fields += 1

        for key in sorted(other_fields.keys()):
            game_dict[key] = other_fields[key]

        if debug_mode and processed_games < 3:  # Show details for first 3 games
            safe_print(f"[DEBUG] Game {processed_games + 1}: '{name}' (ID: {dbid})")
            safe_print(f"        Fields: {included_fields}/{total_fields} included")

        # Attach grouped Artwork if images exist
        artwork_stats = {"total_images": 0, "categories": {}}

        if dbid in images_by_dbid:
            games_with_artwork += 1

            artwork_groups = {
                "Arcade": [],
                "Banner": [],
                "Background": [],
                "Box": {},
                "Cart": {},
                "Disc": [],
                "Icon": [],
                "Poster": [],
                "Screenshots": [],
                "Square": [],
                "Other": [],
            }

            for img in images_by_dbid[dbid]:
                artwork_stats["total_images"] += 1

                # Create img_dict with sorted keys for deterministic output
                img_fields = {}
                for child in img:
                    if child.tag != "DatabaseID":
                        img_fields[child.tag] = child.text

                # Add URL field based on FileName
                filename = img.findtext("FileName")
                if filename:
                    img_fields["URL"] = f"http://images.launchbox-app.com/{filename}"

                # Build img_dict with sorted keys
                img_dict = {k: img_fields[k] for k in sorted(img_fields.keys())}

                artwork_type = img.findtext("Type")
                main_category = categorize_artwork_type(artwork_type)

                # Track category stats
                artwork_stats["categories"][main_category] = (
                    artwork_stats["categories"].get(main_category, 0) + 1
                )

                if main_category in ["Box", "Cart"]:
                    subcategory = subcategorize_artwork(artwork_type, main_category)
                    if subcategory:
                        if subcategory not in artwork_groups[main_category]:
                            artwork_groups[main_category][subcategory] = []
                        artwork_groups[main_category][subcategory].append(img_dict)
                    else:
                        if "Other" not in artwork_groups[main_category]:
                            artwork_groups[main_category]["Other"] = []
                        artwork_groups[main_category]["Other"].append(img_dict)
                else:
                    artwork_groups[main_category].append(img_dict)

            # Remove empty categories and subcategories, and sort entries by Type then Region
            cleaned_artwork = {}
            # Process categories in sorted order for consistency
            for category in sorted(artwork_groups.keys()):
                content = artwork_groups[category]
                if isinstance(content, list) and content:
                    # Sort the list of artwork dicts by 'Type', then 'Region', then 'FileName' for full determinism
                    sorted_content = sorted(
                        content,
                        key=lambda x: (
                            (x.get("Type") or "").lower(),
                            (x.get("Region") or "").lower(),
                            (x.get("FileName") or "").lower(),
                        ),
                    )
                    cleaned_artwork[category] = sorted_content
                elif isinstance(content, dict) and content:
                    # Remove empty subcategories and sort each subcategory
                    cleaned_subcategories = {}
                    # Process subcategories in sorted order for consistency
                    for subcat in sorted(content.keys()):
                        sublist = content[subcat]
                        if sublist:
                            # Sort by 'Type', then 'Region', then 'FileName' for full determinism
                            sorted_sublist = sorted(
                                sublist,
                                key=lambda x: (
                                    (x.get("Type") or "").lower(),
                                    (x.get("Region") or "").lower(),
                                    (x.get("FileName") or "").lower(),
                                ),
                            )
                            cleaned_subcategories[subcat] = sorted_sublist
                    if cleaned_subcategories:
                        cleaned_artwork[category] = cleaned_subcategories

            if cleaned_artwork:
                game_dict["Artwork"] = cleaned_artwork

            if debug_mode and processed_games < 3:
                safe_print(
                    f"        Artwork: {artwork_stats['total_images']} images in {len(cleaned_artwork)} categories"
                )
                for cat, count in artwork_stats["categories"].items():
                    if count > 0:
                        safe_print(f"          - {cat}: {count}")

        output_games.append(game_dict)

        # Create simplified entry for search.json
        simplified_entry = {"Name": name, "DatabaseID": dbid}
        simplified_games.append(simplified_entry)

        processed_games += 1

        # Progress indicator for large datasets
        if debug_mode and processed_games % 100 == 0:
            safe_print(f"[PROGRESS] Processed {processed_games} Xbox 360 games...")

    # Sort output lists by DatabaseID for deterministic ordering
    output_games.sort(
        key=lambda g: (
            int(g["DatabaseID"]) if g["DatabaseID"].isdigit() else g["DatabaseID"]
        )
    )
    simplified_games.sort(
        key=lambda g: (
            int(g["DatabaseID"]) if g["DatabaseID"].isdigit() else g["DatabaseID"]
        )
    )

    # Create individual game files (after sorting, so this section is independent of order)
    if debug_mode:
        safe_print("[INFO] Creating individual game files...")

    for game_dict in output_games:
        dbid = game_dict["DatabaseID"]
        name = game_dict.get("Name", "Unknown")
        try:
            game_folder = f"data/metadata/launchbox/titles/{dbid}"
            os.makedirs(game_folder, exist_ok=True)

            with open(f"{game_folder}/info.json", "w", encoding="utf-8") as f:
                json.dump(game_dict, f, indent=2, ensure_ascii=False, sort_keys=True)
        except Exception as e:
            safe_print(
                f"[ERROR] Error creating individual file for {name} (ID: {dbid}): {e}",
                file=sys.stderr,
            )

    # Save main files
    if debug_mode:
        safe_print("[INFO] Saving main JSON files...")

    try:
        # Export detailed games to games.json
        with open("data/metadata/launchbox/games.json", "w", encoding="utf-8") as f:
            json.dump(output_games, f, indent=2, ensure_ascii=False, sort_keys=True)

        # Export simplified games to search.json
        with open("data/metadata/launchbox/search.json", "w", encoding="utf-8") as f:
            json.dump(simplified_games, f, indent=2, ensure_ascii=False, sort_keys=True)

        if debug_mode:
            safe_print("[SUCCESS] Main JSON files saved successfully")

    except Exception as e:
        safe_print(f"[ERROR] Error saving main JSON files: {e}", file=sys.stderr)
        sys.exit(1)

    # Calculate processing time
    end_time = time.time()
    processing_time = end_time - start_time

    # Print results
    safe_print(f"[SUCCESS] Exported {len(output_games)} games to games.json")
    safe_print(f"[SUCCESS] Exported {len(simplified_games)} games to search.json")
    safe_print(
        f"[SUCCESS] Created individual game files in data/metadata/launchbox/titles/[DatabaseID]/ folders"
    )

    # Print summary statistics
    safe_print(f"\n[SUMMARY] Processing Summary:")
    safe_print(f"  Total games in database: {total_games}")
    safe_print(f"  Xbox 360 games found: {xbox360_games}")
    safe_print(f"  Games processed successfully: {processed_games}")
    safe_print(f"  Games with artwork: {games_with_artwork}")
    if games_without_dbid > 0:
        safe_print(f"  Xbox 360 games without DatabaseID: {games_without_dbid}")
    safe_print(f"  Processing time: {processing_time:.2f} seconds")

    # Print artwork categorization summary
    safe_print("\n[ARTWORK] Artwork categorization summary:")
    category_counts = {}
    total_artwork_items = 0

    for game in output_games:
        if "Artwork" in game:
            for category in game["Artwork"]:
                category_counts[category] = category_counts.get(category, 0) + 1

                # Count individual artwork items
                if isinstance(game["Artwork"][category], list):
                    total_artwork_items += len(game["Artwork"][category])
                elif isinstance(game["Artwork"][category], dict):
                    for subcategory in game["Artwork"][category]:
                        total_artwork_items += len(
                            game["Artwork"][category][subcategory]
                        )

    for category, count in sorted(category_counts.items()):
        safe_print(f"  - {category}: {count} games have this artwork type")

    safe_print(f"\n[INFO] Total artwork items processed: {total_artwork_items}")

    if debug_mode:
        safe_print(f"\n[DEBUG] Debug Summary:")
        if len(output_games) > 0:
            safe_print("  Sample games:")
            for i, game in enumerate(output_games[:3]):
                artwork_count = 0
                if "Artwork" in game:
                    for category in game["Artwork"]:
                        if isinstance(game["Artwork"][category], list):
                            artwork_count += len(game["Artwork"][category])
                        elif isinstance(game["Artwork"][category], dict):
                            for subcategory in game["Artwork"][category]:
                                artwork_count += len(
                                    game["Artwork"][category][subcategory]
                                )

                safe_print(
                    f"    {i+1}. ID={game.get('DatabaseID', 'N/A')}, Title='{game.get('Name', 'N/A')}', Artwork={artwork_count} items"
                )

            if len(output_games) > 3:
                safe_print(f"    ... and {len(output_games) - 3} more")

        safe_print(f"  Files created:")
        safe_print(f"    - data/metadata/launchbox/games.json")
        safe_print(f"    - data/metadata/launchbox/search.json")
        safe_print(f"    - {len(output_games)} individual info.json files")

        safe_print(f"  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
