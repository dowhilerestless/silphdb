import os
import time
from PIL import Image
import pillow_heif

# --- CONFIGURATION ---
# UPDATE THIS to your actual Google Drive sync folder path
WATCH_DIR = r"G:\My Drive\cards-for-grading"
DEST_DIR = r"C:\Users\david\Documents\repos\silphdb\card-grader\jpegs"

# Ensure the destination folder exists
if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR)

# Register HEIF opener with Pillow so it can read iPhone photos
pillow_heif.register_heif_opener()


def get_image_files(directory):
    """Returns a list of full paths for all image files in the directory."""
    valid_exts = ('.heic', '.jpg', '.jpeg', '.png')
    files = []
    for f in os.listdir(directory):
        if f.lower().endswith(valid_exts):
            files.append(os.path.join(directory, f))
    return files


def get_file_sizes(file_paths):
    """Returns a list of file sizes to check if downloads are complete."""
    try:
        return [os.path.getsize(f) for f in file_paths]
    except FileNotFoundError:
        return []


def process_batch(files):
    """Sorts, converts, renames, and moves a batch of 4 photos."""
    # 1. Sort alphabetically (IMG_4001, IMG_4002, etc. preserves iPhone shoot order)
    files.sort()

    print("\n" + "="*50)
    print(f"📸 4 Photos Detected and Downloaded!")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    # 2. Prompt the user for the card name
    card_name = input(
        "\nWhat card is this? (or type 'skip' to abort): ").strip().lower()

    if card_name == 'skip':
        print("Skipping batch. Please remove files manually if needed.")
        return

    # Our agreed-upon sequence
    suffixes = ["front", "front-rev", "back", "back-rev"]

    print("\nProcessing...")
    for idx, file_path in enumerate(files):
        new_filename = f"{card_name}-{suffixes[idx]}.jpg"
        dest_path = os.path.join(DEST_DIR, new_filename)

        try:
            # 3. Open the image (Pillow + pillow_heif handles HEIC automatically now)
            img = Image.open(file_path)

            # 4. Save as standard JPEG to the destination folder
            # We convert to RGB just in case the HEIC has an alpha/transparency channel
            img.convert('RGB').save(dest_path, "JPEG", quality=95)
            print(f"  ✅ Saved: {new_filename}")

            # Close the file handle so the OS lets us delete it
            img.close()

            # 5. Delete the original file from Google Drive to prep for the next batch
            os.remove(file_path)

        except Exception as e:
            print(f"  ❌ Error processing {os.path.basename(file_path)}: {e}")

    print("\nReady for the next card! Waiting for 4 new photos...")
    print("="*50)


def main():
    print(f"📡 Watching Google Drive: {WATCH_DIR}")
    print(f"💾 Destination: {DEST_DIR}")
    print("Waiting for exactly 4 photos to arrive...")

    while True:
        current_files = get_image_files(WATCH_DIR)

        # We only trigger when EXACTLY 4 files are in the folder
        if len(current_files) == 4:
            # Wait 2 seconds and check file sizes to ensure Google Drive finished downloading them
            sizes_initial = get_file_sizes(current_files)
            time.sleep(2)
            sizes_final = get_file_sizes(current_files)

            # If sizes match and are > 0, the files are completely downloaded and stable
            if sizes_initial == sizes_final and all(size > 0 for size in sizes_initial):
                process_batch(current_files)
            else:
                # Still downloading, loop will catch them on the next pass
                pass

        # If there are more than 4 files, warn the user
        elif len(current_files) > 4:
            print(
                f"⚠️ Warning: Found {len(current_files)} files. Please clear out the extra files so there are exactly 4.")
            time.sleep(5)

        # Sleep for 2 seconds before checking the folder again
        time.sleep(2)


if __name__ == "__main__":
    main()
