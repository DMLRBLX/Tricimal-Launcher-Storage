import os
import time
import shutil
import json
import msvcrt
import re
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
DOWNLOADS_DIR = r"C:\Users\jerem\Downloads"
TARGET_PARENT_DIR = r"C:\Users\jerem\Downloads\GitHub\Tricimal-Launcher-Storage"

# Constants
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
APP_EXTENSIONS = {'.apk', '.apkm'}
IGNORE_EXTENSIONS = {'.crdownload', '.part', '.tmp'}
ONE_HUNDRED_MB_IN_BYTES = 100 * 1024 * 1024

def sanitize_name(name):
    """Replaces invalid file/folder characters with '^'."""
    # Standard invalid Windows characters + ';' as requested
    return re.sub(r'[<>:"/\\|?*;]', '^', name)

def get_safe_input(prompt_text):
    """Helper to ensure we get valid user input."""
    while True:
        response = input(prompt_text).strip()
        if response:
            return response
        print("[-] Input cannot be empty. Please try again.")

def wait_for_file_lock(filepath, timeout=10):
    """Ensures the browser has fully released the file before moving."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            os.rename(filepath, filepath)
            return True
        except OSError:
            time.sleep(0.5)
    return False

def responsive_sleep_and_check_for_o(duration=2.0):
    """
    Sleeps for the specified duration but constantly checks the keyboard buffer.
    Returns True immediately if 'o' is pressed.
    """
    start = time.time()
    while time.time() - start < duration:
        if msvcrt.kbhit():
            try:
                char = msvcrt.getch().decode('utf-8').lower()
                if char == 'o':
                    return True
            except Exception:
                pass # Ignore non-utf-8 keys (like arrows)
        time.sleep(0.1)
    return False

def clear_existing_files(folder_path, extensions):
    """Deletes any files in the target folder that match the given extensions."""
    for f in os.listdir(folder_path):
        if any(f.lower().endswith(ext) for ext in extensions):
            file_to_del = os.path.join(folder_path, f)
            try:
                os.remove(file_to_del)
                print(f"[*] Deleted old file: {f}")
            except Exception as e:
                print(f"[-] Could not delete old file {f}: {e}")

def wait_for_files(need_img=False, need_app=False):
    """
    Dedicated watcher for Overwrite Mode. Concurrently watches for needed files 
    so order of download doesn't cause race conditions.
    """
    seen = set(os.listdir(DOWNLOADS_DIR))
    found_img = None
    found_app = None
    
    while True:
        time.sleep(1)
        try:
            current = set(os.listdir(DOWNLOADS_DIR))
        except Exception: 
            continue
        
        new_files = current - seen
        for f in new_files:
            f_lower = f.lower()
            if any(f_lower.endswith(ext) for ext in IGNORE_EXTENSIONS): 
                continue
            
            f_path = os.path.join(DOWNLOADS_DIR, f)
            if not os.path.isfile(f_path) or not wait_for_file_lock(f_path): 
                continue
            
            if need_img and not found_img and any(f_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
                found_img = f_path
                print(f"[+] Detected new Image: {f}")
            elif need_app and not found_app and any(f_lower.endswith(ext) for ext in APP_EXTENSIONS):
                found_app = f_path
                print(f"[+] Detected new App: {f}")
                
        seen = current
        
        # Check if our requirements are met
        if (not need_img or found_img) and (not need_app or found_app):
            return found_img, found_app

def replace_app_and_update_json(target_folder, new_app_path, raw_name=None):
    """Replaces the app, handles the 100MB logic, and cleanly updates meta.json."""
    meta_path = os.path.join(target_folder, "meta.json")
    meta_data = {}
    
    # 1. Load existing JSON to preserve values like 'unique', 'type', and 'name'
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
        except Exception as e:
            print(f"[-] Failed to read existing meta.json: {e}")

    # 2. Check App File Size BEFORE moving
    app_size = os.path.getsize(new_app_path)
    apk_url = ""
    is_large_file = app_size > ONE_HUNDRED_MB_IN_BYTES
    
    if is_large_file:
        size_mb = app_size / (1024 * 1024)
        print(f"\n[!] The new app file is large ({size_mb:.2f} MB). It will remain in Downloads.")
        apk_url = get_safe_input("Please enter the APK/APKM download URL: ")
    else:
        print("\n[*] File is under 100MB. Setting 'apkUrl' to empty.")

    # 3. Delete old app from target folder
    clear_existing_files(target_folder, APP_EXTENSIONS)

    # 4. Move the new app ONLY if it is not a large file
    if not is_large_file:
        new_app_dest = os.path.join(target_folder, os.path.basename(new_app_path))
        shutil.move(new_app_path, new_app_dest)
        print("[*] App file moved to target directory.")

    # 5. Generate Metadata Updates (using the original path name)
    app_filename_only = os.path.splitext(os.path.basename(new_app_path))[0]
    app_extension = os.path.splitext(os.path.basename(new_app_path))[1].replace(".", "")
    
    meta_data["packageName"] = app_filename_only
    meta_data["apkUrl"] = apk_url
    meta_data["date"] = datetime.today().strftime('%Y-%m-%d')
    meta_data["extension"] = app_extension
    
    # Safety fallback in case the original JSON was corrupted
    if "name" not in meta_data: 
        meta_data["name"] = raw_name if raw_name else os.path.basename(target_folder)
    if "unique" not in meta_data: 
        meta_data["unique"] = "com." + os.path.basename(target_folder).replace(" ", ".").lower()
    if "type" not in meta_data: 
        meta_data["type"] = "game"

    # 6. Save meta.json
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2, ensure_ascii=False)
    print(f"[*] meta.json successfully updated.")

    # 7. Clean up large files directly from Downloads
    if is_large_file:
        try:
            os.remove(new_app_path)
            print(f"[+] Large app file deleted from Downloads to save space: {os.path.basename(new_app_path)}")
        except Exception as e:
            print(f"[-] Failed to delete large app file from Downloads: {e}")

def handle_overwrite_mode():
    print("\n" + "="*60)
    print("=== OVERWRITE MODE ACTIVATED ===")
    
    # 1. Prompt for valid folder and sanitize
    while True:
        folder_name_raw = get_safe_input("Enter the name of the folder to overwrite: ")
        folder_name = sanitize_name(folder_name_raw)
        target_folder = os.path.join(TARGET_PARENT_DIR, folder_name)
        
        if not os.path.exists(target_folder):
            retry = input(f"[-] Cannot find folder '{folder_name}'. Try again? (y/n): ").strip().lower()
            if retry != 'y':
                print("[*] Canceling overwrite. Returning to normal mode.")
                return
        else:
            break
            
    # 2. Prompt for overwrite type
    while True:
        print("\nWhat would you like to overwrite?")
        print("  1. Icon")
        print("  2. APK/APKM")
        print("  3. Both Icon and APK/APKM")
        choice = input("Enter choice (1/2/3) or 'q' to cancel: ").strip()
        
        if choice.lower() == 'q':
            print("[*] Canceling overwrite. Returning to normal mode.")
            return
        if choice in ['1', '2', '3']:
            break
        print("[-] Invalid choice.")
        
    # 3. Execute chosen overwrite flow
    if choice == '1':
        print(f"\n[*] Waiting for a new Image file in Downloads to overwrite {folder_name} icon...")
        new_img, _ = wait_for_files(need_img=True, need_app=False)
        clear_existing_files(target_folder, IMAGE_EXTENSIONS)
        shutil.move(new_img, os.path.join(target_folder, os.path.basename(new_img)))
        print(f"[+] Icon successfully overwritten in {folder_name}.")
        
    elif choice == '2':
        print(f"\n[*] Waiting for a new APK/APKM file in Downloads to overwrite {folder_name} app...")
        _, new_app = wait_for_files(need_img=False, need_app=True)
        # Pass the raw name in case meta.json needs to be rebuilt
        replace_app_and_update_json(target_folder, new_app, raw_name=folder_name_raw)
        print(f"[+] App and JSON successfully overwritten in {folder_name}.")
        
    elif choice == '3':
        print(f"\n[*] Waiting for 1 new Image AND 1 new App file to overwrite {folder_name}...")
        new_img, new_app = wait_for_files(need_img=True, need_app=True)
        
        # Replace Icon
        clear_existing_files(target_folder, IMAGE_EXTENSIONS)
        shutil.move(new_img, os.path.join(target_folder, os.path.basename(new_img)))
        # Replace App and JSON
        replace_app_and_update_json(target_folder, new_app, raw_name=folder_name_raw)
        print(f"[+] Both Icon and App successfully overwritten in {folder_name}.")

    print("="*60 + "\n")

def process_pair(image_path, app_path):
    """Normal Generation Flow with Overwrite Detection"""
    print("\n" + "="*60)
    print("[+] NEW PAIR DETECTED (Normal Mode)")
    print(f"    Image: {os.path.basename(image_path)}")
    print(f"    App:   {os.path.basename(app_path)}")
    print("="*60)

    overwrite_mode = False
    while True:
        app_name_raw = get_safe_input("Enter a name for this app: ")
        # Sanitize the input to prevent Windows file path errors
        app_name = sanitize_name(app_name_raw)
        
        target_folder = os.path.join(TARGET_PARENT_DIR, app_name)
        if os.path.exists(target_folder):
            ans = input(f"[?] The folder '{app_name}' already exists. Overwrite it? (y/n): ").strip().lower()
            if ans == 'y':
                overwrite_mode = True
                break
            else:
                print("[-] Please choose another name.")
        else:
            break

    # If overwriting, try to load existing metadata to preserve custom fields
    existing_meta = {}
    if overwrite_mode:
        meta_path = os.path.join(target_folder, "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    existing_meta = json.load(f)
            except Exception as e:
                print(f"[-] Failed to read existing meta.json: {e}")

    # Default to the existing type if we are overwriting, otherwise default to "game"
    default_type = existing_meta.get("type", "game")
    app_type = input(f'Enter the type (Press Enter to default to "{default_type}"): ').strip()
    if not app_type:
        app_type = default_type

    try:
        os.makedirs(target_folder, exist_ok=True)
    except Exception as e:
        print(f"[-] Failed to create directory: {e}")
        return

    # Clean out the old files if we are overwriting
    if overwrite_mode:
        print("\n[*] Clearing old files before moving new ones...")
        clear_existing_files(target_folder, IMAGE_EXTENSIONS)
        clear_existing_files(target_folder, APP_EXTENSIONS)

    print("\n[*] Processing files...")
    
    # 1. Move the image immediately
    new_image_path = os.path.join(target_folder, os.path.basename(image_path))
    shutil.move(image_path, new_image_path)
    print("[*] Image moved to target directory.")

    # 2. Check App File Size BEFORE moving
    app_size = os.path.getsize(app_path)
    apk_url = ""
    is_large_file = app_size > ONE_HUNDRED_MB_IN_BYTES
    
    if is_large_file:
        size_mb = app_size / (1024 * 1024)
        print(f"\n[!] The app file is large ({size_mb:.2f} MB). It will remain in Downloads.")
        apk_url = get_safe_input("Please enter the APK/APKM download URL: ")
    else:
        print("\n[*] File is under 100MB. Setting 'apkUrl' to empty.")
        # Only move the app if it's under the limit
        new_app_path = os.path.join(target_folder, os.path.basename(app_path))
        shutil.move(app_path, new_app_path)
        print("[*] App file moved to target directory.")

    # Extract metadata using the original app_path base name
    app_filename_only = os.path.splitext(os.path.basename(app_path))[0]
    app_extension = os.path.splitext(os.path.basename(app_path))[1].replace(".", "")
    
    # Maintain database integrity by using the sanitized name for the unique ID, 
    # but the RAW unmodified string for the display name.
    unique_id = existing_meta.get("unique", "com." + app_name.replace(" ", ".").lower())
    final_name = existing_meta.get("name", app_name_raw)

    meta_data = {
        "unique": unique_id,
        "name": final_name,
        "packageName": app_filename_only,
        "apkUrl": apk_url,
        "date": datetime.today().strftime('%Y-%m-%d'),
        "extension": app_extension,
        "type": app_type
    }

    meta_path = os.path.join(target_folder, "meta.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Success! meta.json generated in: {target_folder}")

    # 3. Clean up the large app file from Downloads
    if is_large_file:
        try:
            os.remove(app_path)
            print(f"[+] Large app file deleted from Downloads to save space: {os.path.basename(app_path)}")
        except Exception as e:
            print(f"[-] Failed to delete large app file from Downloads: {e}")

    print("="*60 + "\n")

def main():
    os.makedirs(TARGET_PARENT_DIR, exist_ok=True)

    print("=== Background Organizer Started ===")
    print(" -> Press 'o' at any time to enter Overwrite Mode")
    print(f"Monitoring: {DOWNLOADS_DIR}")
    print("Waiting for 1 Image and 1 App file to be downloaded...")

    try:
        seen_files = set(os.listdir(DOWNLOADS_DIR))
    except Exception as e:
        print(f"Failed to access downloads folder: {e}")
        return

    image_queue = []
    app_queue = []

    while True:
        # Custom responsive sleep checks for 'o' continuously
        if responsive_sleep_and_check_for_o(2.0):
            handle_overwrite_mode()
            
            # Reset baseline after overwrite mode finishes so files handled 
            # during that time aren't accidentally processed as new normal pairs
            try:
                seen_files = set(os.listdir(DOWNLOADS_DIR))
            except Exception:
                pass
                
            print("=== Resuming Normal Background Organizer ===")
            print("Waiting for 1 Image and 1 App file to be downloaded...")
            continue
        
        try:
            current_files = set(os.listdir(DOWNLOADS_DIR))
        except Exception:
            continue

        new_files = current_files - seen_files

        for file in new_files:
            file_lower = file.lower()
            
            if any(file_lower.endswith(ext) for ext in IGNORE_EXTENSIONS):
                continue
                
            file_path = os.path.join(DOWNLOADS_DIR, file)
            
            if not os.path.isfile(file_path):
                continue

            if not wait_for_file_lock(file_path):
                print(f"[-] Could not get read access to {file}. Skipping for now.")
                continue

            if any(file_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
                image_queue.append(file_path)
                print(f"[*] Queued new image: {file}")
            elif any(file_lower.endswith(ext) for ext in APP_EXTENSIONS):
                app_queue.append(file_path)
                print(f"[*] Queued new app: {file}")

        seen_files = current_files

        if image_queue and app_queue:
            image_to_process = image_queue.pop(0)
            app_to_process = app_queue.pop(0)
            
            process_pair(image_to_process, app_to_process)
            
            # Reset baseline after processing
            seen_files = set(os.listdir(DOWNLOADS_DIR))

if __name__ == "__main__":
    main()