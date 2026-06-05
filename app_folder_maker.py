import os
import time
import shutil
import json
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
# Replace these paths with your actual system paths.
# Using 'r' before the string ensures Windows backslashes are read correctly.
DOWNLOADS_DIR = r"C:\Users\jerem\Downloads"
TARGET_PARENT_DIR = r"C:\Users\jerem\Downloads\GitHub\Tricimal-Launcher-Storage"

# Constants
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
APP_EXTENSIONS = {'.apk', '.apkm'}
IGNORE_EXTENSIONS = {'.crdownload', '.part', '.tmp'}
ONE_HUNDRED_MB_IN_BYTES = 100 * 1024 * 1024

def get_safe_input(prompt_text):
    """Helper to ensure we get valid user input."""
    while True:
        response = input(prompt_text).strip()
        if response:
            return response
        print("[-] Input cannot be empty. Please try again.")

def wait_for_file_lock(filepath, timeout=10):
    """
    Even after a browser renames a file, it might keep it locked for a fraction
    of a second. This ensures the file is fully released before we try to move it.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to rename the file to itself. If it works, it's not locked.
            os.rename(filepath, filepath)
            return True
        except OSError:
            time.sleep(0.5)
    return False

def process_pair(image_path, app_path):
    """Handles the user prompts, file moving, and JSON generation for a matched pair."""
    print("\n" + "="*50)
    print("[+] NEW PAIR DETECTED!")
    print(f"    Image: {os.path.basename(image_path)}")
    print(f"    App:   {os.path.basename(app_path)}")
    print("="*50)

    # 1. Prompt for App Name and ensure the folder doesn't already exist
    while True:
        app_name = get_safe_input("Enter a name for this app: ")
        target_folder = os.path.join(TARGET_PARENT_DIR, app_name)
        
        if os.path.exists(target_folder):
            print(f"[-] The folder '{app_name}' already exists in the target directory. Please choose another name.")
        else:
            break

    # 2. Prompt for Type
    app_type = input('Enter the type (Press Enter to default to "game"): ').strip()
    if not app_type:
        app_type = "game"

    # 3. Create the folder hierarchy immediately
    try:
        os.makedirs(target_folder, exist_ok=True)
    except Exception as e:
        print(f"[-] Failed to create directory: {e}")
        return

    # 4. Move the files FIRST so they are out of the Downloads folder
    print("\n[*] Moving files to target directory...")
    new_image_path = os.path.join(target_folder, os.path.basename(image_path))
    new_app_path = os.path.join(target_folder, os.path.basename(app_path))
    
    shutil.move(image_path, new_image_path)
    shutil.move(app_path, new_app_path)

    # 5. Check App File Size (now checking the newly moved file)
    app_size = os.path.getsize(new_app_path)
    apk_url = ""
    is_large_file = app_size > ONE_HUNDRED_MB_IN_BYTES
    
    if is_large_file:
        size_mb = app_size / (1024 * 1024)
        print(f"\n[!] The app file is large ({size_mb:.2f} MB).")
        apk_url = get_safe_input("Please enter the APK/APKM download URL: ")
    else:
        print("\n[*] File is under 100MB. Setting 'apkUrl' to empty.")

    # 6. Generate the Meta Data
    app_filename_only = os.path.splitext(os.path.basename(new_app_path))[0]
    app_extension = os.path.splitext(os.path.basename(new_app_path))[1].replace(".", "")
    
    # Create the unique ID (e.g., "My Cool Game" -> "com.my.cool.game")
    unique_id = "com." + app_name.replace(" ", ".").lower()

    meta_data = {
        "unique": unique_id,
        "name": app_name,
        "packageName": app_filename_only,
        "apkUrl": apk_url,
        "date": datetime.today().strftime('%Y-%m-%d'),
        "extension": app_extension,
        "type": app_type
    }

    # 7. Save meta.json
    meta_path = os.path.join(target_folder, "meta.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Success! meta.json generated in: {target_folder}")

    # 8. Delete the app file if it exceeded the size limit
    if is_large_file:
        try:
            os.remove(new_app_path)
            print(f"[+] Large app file deleted successfully to save space: {os.path.basename(new_app_path)}")
        except Exception as e:
            print(f"[-] Failed to delete large app file: {e}")

    print("="*50 + "\n")

def main():
    # Ensure our target parent directory exists
    os.makedirs(TARGET_PARENT_DIR, exist_ok=True)

    print("=== Background Organizer Started ===")
    print(f"Monitoring: {DOWNLOADS_DIR}")
    print("Waiting for 1 Image and 1 App file to be downloaded...")

    # Initial snapshot of the directory to establish a baseline
    try:
        seen_files = set(os.listdir(DOWNLOADS_DIR))
    except Exception as e:
        print(f"Failed to access downloads folder: {e}")
        return

    image_queue = []
    app_queue = []

    while True:
        time.sleep(2) # Polling interval
        
        try:
            current_files = set(os.listdir(DOWNLOADS_DIR))
        except Exception:
            continue # If folder is temporarily locked, skip to next loop

        # Identify files that weren't in our previous snapshot
        new_files = current_files - seen_files

        for file in new_files:
            file_lower = file.lower()
            
            # Skip temp browser files entirely
            if any(file_lower.endswith(ext) for ext in IGNORE_EXTENSIONS):
                continue
                
            file_path = os.path.join(DOWNLOADS_DIR, file)
            
            # Make sure it's actually a file and not a folder created in Downloads
            if not os.path.isfile(file_path):
                continue

            # Wait for browser to release the file lock
            if not wait_for_file_lock(file_path):
                print(f"[-] Could not get read access to {file}. Skipping for now.")
                continue

            # Sort into our queues
            if any(file_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
                image_queue.append(file_path)
                print(f"[*] Queued new image: {file}")
            elif any(file_lower.endswith(ext) for ext in APP_EXTENSIONS):
                app_queue.append(file_path)
                print(f"[*] Queued new app: {file}")

        # Update our baseline snapshot
        seen_files = current_files

        # Check if we have at least one of both needed files
        if image_queue and app_queue:
            # Pop the oldest image and oldest app from the queues
            image_to_process = image_queue.pop(0)
            app_to_process = app_queue.pop(0)
            
            process_pair(image_to_process, app_to_process)
            
            # Because we moved files out of the directory, our 'seen_files' baseline
            # is technically outdated, but the logic (current - seen) handles
            # disappearances flawlessly without throwing errors. We just need to 
            # resync it so it doesn't trigger false positives later.
            seen_files = set(os.listdir(DOWNLOADS_DIR))

if __name__ == "__main__":
    main()