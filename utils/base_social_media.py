from pathlib import Path
from typing import List
import json
from datetime import datetime

from conf import BASE_DIR

SOCIAL_MEDIA_DOUYIN = "douyin"
SOCIAL_MEDIA_TENCENT = "tencent"
SOCIAL_MEDIA_TIKTOK = "tiktok"
SOCIAL_MEDIA_BILIBILI = "bilibili"
SOCIAL_MEDIA_KUAISHOU = "kuaishou"

# Import uploader modules and utilities
# Moved imports inside functions to break circular dependency
# import os
# import asyncio
# import time
# from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
# from uploader.ks_uploader.main import ks_setup, KSVideo
# from uploader.tencent_uploader.main import weixin_setup, TencentVideo
# from uploader.bilibili_uploader.main import BilibiliUploader, read_cookie_json_file, extract_keys_from_json
# from uploader.tk_uploader.main_chrome import tiktok_setup, TiktokVideo

from utils.files_times import get_title_and_hashtags, generate_schedule_time_next_day
from utils.constant import TencentZoneTypes # Needed for Tencent video category


def get_supported_social_media() -> List[str]:
    return [SOCIAL_MEDIA_DOUYIN, SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU]


def get_cli_action() -> List[str]:
    return ["upload", "login", "watch"]


async def set_init_script(context):
    stealth_js_path = Path(BASE_DIR / "utils/stealth.min.js")
    await context.add_init_script(path=stealth_js_path)
    return context


def load_workflow_config(config_path: str):
    """Loads the workflow configuration from a JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Workflow config file not found at {config_path}")
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


async def run_workflow(config: dict | str):
    """Runs the multi-account and multi-video-type workflow."""
    
    generated_schedule_times = None
    
    if isinstance(config, str):
        print(f"Loading workflow config from {config}")
        config = load_workflow_config(config)
    else:
        print("Using provided workflow config dictionary.")
        # Assuming config is already a dictionary, validate it if necessary
        # Check if the config dictionary contains the generated schedule
        if 'generated_schedule' in config:
            generated_schedule_times = config.pop('generated_schedule') # Get and remove to avoid passing it down further if not needed
            print(f"Found generated schedule with {len(generated_schedule_times)} entries.")

    print("Workflow config loaded successfully." if isinstance(config, str) else "Using provided workflow config.") # Adjust message
    print("Starting workflow execution...")

    base_videos_path = Path(BASE_DIR) / "videos"
    base_cookies_path = Path(BASE_DIR) / "cookies"

    # Import uploader modules here to avoid circular dependency
    import os
    import asyncio
    import time
    from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
    from uploader.ks_uploader.main import ks_setup, KSVideo
    from uploader.tencent_uploader.main import weixin_setup, TencentVideo
    from uploader.bilibili_uploader.main import BilibiliUploader, read_cookie_json_file, extract_keys_from_json
    # from uploader.tk_uploader.main_chrome import tiktok_setup, TiktokVideo # Add this import if TikTok is needed

    from utils.files_times import get_title_and_hashtags, generate_schedule_time_next_day
    from utils.constant import TencentZoneTypes # Needed for Tencent video category

    for account in config.get('accounts', []):
        account_name = account.get('name')
        video_types = account.get('video_types', [])
        platforms = account.get('platforms', [])
        
        if not account_name:
            print("Warning: Skipping account with no name defined in config.")
            continue

        print(f"\nProcessing account: {account_name}")
        print(f"Video types: {video_types}")
        print(f"Platforms: {platforms}")

        for video_type in video_types:
            # Modify video path to include account name
            video_type_path = base_videos_path / account_name / video_type
            if not video_type_path.exists() or not video_type_path.is_dir():
                print(f"Warning: Video type directory not found: {video_type_path}. Skipping.")
                continue
            
            # Find video files in the video type directory
            video_files = sorted(list(video_type_path.glob("*.mp4"))) # Sort to process in a consistent order
            
            if not video_files:
                print(f"No MP4 videos found for video type '{video_type}' in {video_type_path}. Skipping.")
                continue

            print(f"Found {len(video_files)} videos for type '{video_type}': {[f.name for f in video_files]}")
            
            # Generate schedule times for all videos of this type for this account
            # We assume the schedule time logic applies to all platforms for these videos
            # You might need to adjust this based on your specific scheduling needs
            # Using 16:00 as a default time based on examples
            try:
                publish_datetimes = generate_schedule_time_next_day(len(video_files), 1, daily_times=[16])
            except Exception as e:
                print(f"Error generating schedule times for {video_type}: {e}. Skipping videos for this type.")
                continue

            for index, video_file in enumerate(video_files):
                video_path_str = str(video_file)
                title, tags = get_title_and_hashtags(video_path_str)
                
                # Use generated schedule time if available, otherwise use the default logic
                if generated_schedule_times and index < len(generated_schedule_times):
                    # Convert timestamp back to datetime object
                    publish_date = datetime.fromtimestamp(generated_schedule_times[index])
                    print(f"Using generated schedule time: {publish_date}")
                else:
                    publish_date = publish_datetimes[index] if publish_datetimes else 0 # Use generated schedule or immediate
                
                if not title:
                    print(f"Warning: Skipping video {video_file.name} due to missing title (.txt file).")
                    continue
                
                print(f"\n  Processing video: {video_file.name}")
                print(f"    Title: {title}")
                print(f"    Tags: {tags}")
                print(f"    Scheduled for: {publish_date}")
                
                # List to hold upload tasks for different platforms for this video
                upload_tasks = []
                
                for platform in platforms:
                    print(f"    Attempting to upload to platform: {platform}")
                    
                    # Construct cookie file path for the specific account and platform
                    cookie_file = base_cookies_path / f"{platform}_uploader" / f"{account_name}.json"
                    
                    if not cookie_file.exists():
                        print(f"      Error: Cookie file not found for account '{account_name}' on platform '{platform}' at {cookie_file}. Skipping upload to this platform for this video.")
                        continue
                        
                    # Call the appropriate uploader based on platform and create a task
                    try:
                        if platform == SOCIAL_MEDIA_DOUYIN:
                            # Assuming douyin_setup with handle=False uses existing cookie
                            # We need to run setup before creating the upload task if it initializes state
                            await douyin_setup(cookie_file, handle=False)
                            app = DouYinVideo(title, video_path_str, tags, publish_date, cookie_file)
                            task = asyncio.create_task(app.main(), name=f"{platform}_{account_name}_{video_file.name}")
                            upload_tasks.append(task)
                            
                        elif platform == SOCIAL_MEDIA_KUAISHOU:
                            # Assuming ks_setup with handle=False uses existing cookie
                            await ks_setup(cookie_file, handle=False)
                            app = KSVideo(title, video_path_str, tags, publish_date, cookie_file)
                            task = asyncio.create_task(app.main(), name=f"{platform}_{account_name}_{video_file.name}")
                            upload_tasks.append(task)
                            
                        elif platform == SOCIAL_MEDIA_TENCENT:
                             # Assuming weixin_setup with handle=True is for initial setup, use handle=False for upload
                            await weixin_setup(cookie_file, handle=False) # Use handle=False if setup already done
                            category = TencentZoneTypes.LIFESTYLE.value # Default category, modify if needed based on video type
                            app = TencentVideo(title, video_path_str, tags, publish_date, cookie_file, category)
                            task = asyncio.create_task(app.main(), name=f"{platform}_{account_name}_{video_file.name}")
                            upload_tasks.append(task)
                            
                        elif platform == SOCIAL_MEDIA_BILIBILI:
                            # Bilibili example used a different approach (reading cookie json directly)
                            bili_cookie_data = read_cookie_json_file(cookie_file)
                            bili_cookie_data = extract_keys_from_json(bili_cookie_data)
                            # tid (partition id) is hardcoded to SPORTS_FOOTBALL in example. Needs to be dynamic?
                            # For now, hardcode or use a default. You might need to add this to your config.
                            tid = 255 # Example tid for lifestyle/daily, adjust as needed
                            # Bilibili uploader does not seem to be an async class based on previous read
                            # If it's synchronous, we cannot easily run it with asyncio.create_task
                            # For now, we'll keep it synchronous if it is, or adapt if possible.
                            # Assuming it's async based on context needing await - will create task
                            app = BilibiliUploader(bili_cookie_data, video_path_str, title, title, tid, tags, publish_date)
                            # If Bilibili upload is truly synchronous, this would block. Need confirmation.
                            # For now, assuming it's async or can be run in executor if needed.
                            task = asyncio.create_task(app.upload(), name=f"{platform}_{account_name}_{video_file.name}") # Assuming upload is async now
                            upload_tasks.append(task)
                            # Note: The original code had a time.sleep(10) after Bilibili upload. 
                            # If it's now an async task, this sleep is not needed here.
                            
                        # Add other platforms like tiktok here if needed
                        # elif platform == SOCIAL_MEDIA_TIKTOK:
                        #     await tiktok_setup(cookie_file, handle=True) # Use handle=False if setup already done
                        #     app = TiktokVideo(title, video_path_str, tags, publish_date, cookie_file)
                        #     task = asyncio.create_task(app.main(), name=f"{platform}_{account_name}_{video_file.name}")
                        #     upload_tasks.append(task)
                            
                        else:
                            print(f"      Warning: Unsupported platform '{platform}'. Skipping.")
                            
                    except FileNotFoundError as e:
                        print(f"      Error processing {video_file.name} for {platform} (Account: {account_name}): {e}")
                    except Exception as e:
                         print(f"      An unexpected error occurred during task creation for {video_file.name} to {platform} (Account: {account_name}): {e}")
                         # Optionally, add more specific error handling based on uploader exceptions

                # Wait for all upload tasks for this video to complete
                if upload_tasks:
                    print(f"\n    Waiting for uploads to {len(upload_tasks)} platforms to complete for {video_file.name}...")
                    # Use return_exceptions=True to prevent cancellation of other tasks if one fails
                    results = await asyncio.gather(*upload_tasks, return_exceptions=True)
                    
                    # Process results/exceptions
                    for i, result in enumerate(results):
                        task = upload_tasks[i]
                        platform_name = task.get_name().split('_')[0] # Extract platform name from task name
                        if isinstance(result, Exception):
                            # Check if the exception is a Playwright TargetClosedError
                            if isinstance(result, playwright._impl._errors.TargetClosedError):
                                # Log as a warning or info if it's a known non-critical error after successful upload
                                # This assumes the upload itself completed successfully before this error
                                tencent_logger.warning(f"      Upload task for {platform_name} for {video_file.name} encountered TargetClosedError after completion: {result}")
                            else:
                                # Log other exceptions as errors
                                tencent_logger.error(f"      Upload to {platform_name} for {video_file.name} failed: {result}")
                        # else:
                            # print(f"      Upload to {platform_name} for {video_file.name} completed successfully.") # Optional success message

                # Add a small delay between processing different videos
                await asyncio.sleep(5) # Reduced delay as uploads are now parallel
                
                # After all platforms attempted for this video, save cookies if necessary
                # This assumes cookie saving is part of the uploader's cleanup or state management
                # If cookie saving happens within app.main() or app.upload(), and that task failed,
                # the state might not be saved. Need to ensure state is saved reliably.
                # If a platform task failed with TargetClosedError, saving state afterwards might also fail.
                # A more robust solution might involve saving state immediately after a successful login,
                # and relying on uploaders to handle their own session state during upload.
                # For now, the original code seemed to rely on the uploader saving state.
                # If the error is indeed due to browser context closing on error, we might need to
                # revisit how resources are managed in the uploader classes themselves.

            # Add a delay between processing video types for the same account
            await asyncio.sleep(10)

        # Add a delay between processing different accounts
        await asyncio.sleep(30)

    print("Workflow execution finished.")


async def manage_cookies_menu():
    """Handles the cookie management interactive menu."""
    # Import uploader modules here to avoid circular dependency
    import os
    import asyncio
    import time
    from uploader.douyin_uploader.main import douyin_setup
    from uploader.ks_uploader.main import ks_setup
    from uploader.tencent_uploader.main import weixin_setup
    # from uploader.tk_uploader.main_chrome import tiktok_setup # Add this import if TikTok is needed

    print("\n===== Manage Cookies =====")

    # Load config to get accounts and platforms
    config_path = 'workflow_config.json' # Assuming config file is in the root directory
    try:
        config = load_workflow_config(config_path)
    except FileNotFoundError:
        print(f"Error: Workflow config file not found at {config_path}. Cannot manage cookies.")
        return

    accounts = config.get('accounts', [])
    if not accounts:
        print("No accounts found in the workflow config. Cannot manage cookies.")
        return

    # Display accounts
    print("Select an account:")
    for i, account in enumerate(accounts):
        print(f"{i + 1}. {account.get('name')}")

    while True:
        try:
            account_choice = int(input(f"Enter account number (1-{len(accounts)}): ")) - 1
            if 0 <= account_choice < len(accounts):
                selected_account = accounts[account_choice]
                break
            else:
                print("Invalid account number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Display platforms for the selected account
    platforms = selected_account.get('platforms', [])
    if not platforms:
        print(f"No platforms defined for account {selected_account.get('name')}. Cannot manage cookies.")
        return

    print("\nSelect a platform to get/update cookie:")
    for i, platform in enumerate(platforms):
        print(f"{i + 1}. {platform}")

    while True:
        try:
            platform_choice = int(input(f"Enter platform number (1-{len(platforms)}): ")) - 1
            if 0 <= platform_choice < len(platforms):
                selected_platform = platforms[platform_choice]
                break
            else:
                print("Invalid platform number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    print(f"\nGetting/updating cookie for account '{selected_account.get('name')}' on platform '{selected_platform}'...")
    
    # Construct cookie file path
    account_name = selected_account.get('name')
    base_cookies_path = Path(BASE_DIR) / "cookies"
    cookie_file = base_cookies_path / f"{selected_platform}_uploader" / f"{account_name}.json"
    cookie_file.parent.mkdir(exist_ok=True)
    
    # Call the appropriate setup function based on platform
    try:
        if selected_platform == SOCIAL_MEDIA_DOUYIN:
            await douyin_setup(str(cookie_file), handle=True)
        elif selected_platform == SOCIAL_MEDIA_KUAISHOU:
            await ks_setup(str(cookie_file), handle=True)
        elif selected_platform == SOCIAL_MEDIA_TENCENT:
            await weixin_setup(str(cookie_file), handle=True)
        # elif selected_platform == SOCIAL_MEDIA_TIKTOK:
        #     await tiktok_setup(str(cookie_file), handle=True)
        # Add other platforms as needed
        else:
            print(f"Cookie management for platform '{selected_platform}' is not yet supported in this menu.")
            
        print("Cookie management process completed (check output above for details).")

    except Exception as e:
        print(f"An error occurred during cookie management: {e}")


async def run_workflow_interactively():
    """Handles running the upload workflow interactively."""
    print("\n===== Run Upload Workflow =====")

    # You could add options here to select specific accounts or video types
    # For now, we will directly use the workflow_config.json

    config_path = 'workflow_config.json' # Assuming config file is in the root directory
    try:
        # Call the main run_workflow function
        from utils.base_social_media import run_workflow # Import here to avoid circular dependency if both are in cli_main
        await run_workflow(config_path)
    except FileNotFoundError:
        print(f"Error: Workflow config file not found at {config_path}. Cannot run workflow.")
    except Exception as e:
         print(f"An error occurred during workflow execution: {e}")
