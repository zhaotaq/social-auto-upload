import argparse
import asyncio
from datetime import datetime, timedelta
from os.path import exists
from pathlib import Path
import json
import tempfile
import os

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
from uploader.ks_uploader.main import ks_setup, KSVideo
from uploader.tencent_uploader.main import weixin_setup, TencentVideo
from uploader.tk_uploader.main_chrome import tiktok_setup, TiktokVideo
from utils.base_social_media import get_supported_social_media, get_cli_action, SOCIAL_MEDIA_DOUYIN, \
    SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU, load_workflow_config
from utils.constant import TencentZoneTypes
from utils.files_times import get_title_and_hashtags, generate_schedule_time_next_day


def parse_schedule(schedule_raw):
    if schedule_raw:
        schedule = datetime.strptime(schedule_raw, '%Y-%m-%d %H:%M')
    else:
        schedule = None
    return schedule


async def main():
    # 主解析器
    parser = argparse.ArgumentParser(description="Upload video to multiple social-media.")
    parser.add_argument("platform", metavar='platform', nargs='?', choices=get_supported_social_media(), help="Choose social-media platform: douyin tencent tiktok kuaishou")

    parser.add_argument("account_name", type=str, nargs='?', help="Account name for the platform: xiaoA")
    subparsers = parser.add_subparsers(dest="action", metavar='action', help="Choose action", required=True)

    # Add workflow subcommand
    workflow_parser = subparsers.add_parser('workflow', help='Run the multi-account workflow')
    workflow_parser.add_argument('-c', '--config', help='Path to the workflow configuration file', required=True)

    actions = get_cli_action()
    # Add navigate action to supported actions
    actions.append('navigate')

    for action in actions:
        action_parser = subparsers.add_parser(action, help=f'{action} operation')
        if action == 'login':
            # Login 不需要额外参数
            continue
        elif action == 'upload':
            action_parser.add_argument("video_file", help="Path to the Video file")
            action_parser.add_argument("-pt", "--publish_type", type=int, choices=[0, 1],
                                       help="0 for immediate, 1 for scheduled", default=0)
            action_parser.add_argument('-t', '--schedule', help='Schedule UTC time in %Y-%m-%d %H:%M format')

    # 解析命令行参数
    args = parser.parse_args()
    # 参数校验
    if args.action == 'upload':
        if not exists(args.video_file):
            raise FileNotFoundError(f'Could not find the video file at {args["video_file"]}')
        if args.publish_type == 1 and not args.schedule:
            parser.error("The schedule must must be specified for scheduled publishing.")

    account_file = Path(BASE_DIR / "cookies" / f"{args.platform}_{args.account_name}.json")
    account_file.parent.mkdir(exist_ok=True)

    # 根据 action 处理不同的逻辑
    if args.action == 'login':
        print(f"Logging in with account {args.account_name} on platform {args.platform}")
        if args.platform == SOCIAL_MEDIA_DOUYIN:
            await douyin_setup(str(account_file), handle=True)
        elif args.platform == SOCIAL_MEDIA_TIKTOK:
            await tiktok_setup(str(account_file), handle=True)
        elif args.platform == SOCIAL_MEDIA_TENCENT:
            await weixin_setup(str(account_file), handle=True)
        elif args.platform == SOCIAL_MEDIA_KUAISHOU:
            await ks_setup(str(account_file), handle=True)
    elif args.action == 'workflow':
        print(f"Running workflow with config file: {args.config}")
        # Call a function to handle the workflow
        await run_workflow(args.config)
    elif args.action == 'navigate':
        await show_navigation_menu()


async def show_navigation_menu():
    """Displays the terminal navigation menu and handles user input."""
    print("\n===== Social Auto Upload Navigation Menu =====")
    print("1. Manage Cookies")
    print("2. Run Upload Workflow")
    print("3. Exit")
    print("==========================================")

    while True:
        choice = input("Enter your choice: ")
        
        if choice == '1':
            print("\nManage Cookies selected.")
            # Call function to handle cookie management
            await manage_cookies_menu()
        elif choice == '2':
            print("\nRun Upload Workflow selected.")
            # Call function to run workflow
            await run_workflow_interactively()
        elif choice == '3':
            print("Exiting navigation menu.")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


async def manage_cookies_menu():
    """Handles the cookie management interactive menu."""
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

    config_path = 'workflow_config.json' # Assuming config file is in the root directory
    try:
        # Load the full config first to allow account selection
        config = load_workflow_config(config_path)
    except FileNotFoundError:
        print(f"Error: Workflow config file not found at {config_path}. Cannot run workflow.")
        return
    except Exception as e:
        print(f"Error loading workflow config: {e}. Cannot run workflow.")
        return

    accounts = config.get('accounts', [])
    if not accounts:
        print("No accounts found in the workflow config. Cannot run workflow.")
        return

    # Display accounts for selection
    print("Select an account to run the workflow for:")
    for i, account in enumerate(accounts):
        print(f"{i + 1}. {account.get('name')}")
    print(f"{len(accounts) + 1}. All Accounts") # Option to run for all

    selected_account_config = None
    while True:
        try:
            account_choice = int(input(f"Enter account number (1-{len(accounts) + 1}): ")) - 1
            if 0 <= account_choice < len(accounts):
                selected_account_config = {"accounts": [accounts[account_choice]]}
                print(f"Running workflow for account: {accounts[account_choice].get('name')}")
                break
            elif account_choice == len(accounts):
                 # User selected All Accounts
                selected_account_config = config
                print("Running workflow for all accounts.")
                break
            else:
                print("Invalid account number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Now, prompt user to select video types for the selected account(s)
    if selected_account_config and "accounts" in selected_account_config and selected_account_config["accounts"]:
        # Assuming all selected accounts have the same video types for simplicity in this menu
        # If not, this part would need to be more complex.
        available_video_types = selected_account_config["accounts"][0].get('video_types', [])

        if not available_video_types:
            print(f"No video types defined for the selected account(s). Cannot run workflow.")
            return

        print("\nSelect video type(s) to upload:")
        for i, video_type in enumerate(available_video_types):
            print(f"{i + 1}. {video_type}")
        print(f"{len(available_video_types) + 1}. All Video Types")

        selected_types = []
        while True:
            try:
                type_choice_input = input(f"Enter video type number(s) (e.g., 1,3 or {len(available_video_types) + 1} for all): ")
                choices = [int(c.strip()) - 1 for c in type_choice_input.split(',')]

                invalid_choice = False
                selected_types = [] # Reset selected_types for retry
                for choice in choices:
                    if choice == len(available_video_types):
                        selected_types = available_video_types
                        break # Selected all, exit inner loop
                    elif 0 <= choice < len(available_video_types):
                        selected_types.append(available_video_types[choice])
                    else:
                        print(f"Invalid video type number: {choice + 1}")
                        invalid_choice = True
                        break # Exit inner loop on invalid choice

                if not invalid_choice and selected_types:
                    # Update the config to include only selected video types
                    for account in selected_account_config["accounts"]:
                         account['video_types'] = selected_types
                    print(f"Running workflow for video type(s): {selected_types}")

                    # --- New Schedule Date Selection Logic ---
                    print("\n===== Schedule Start Date =====")
                    print("1. Default (Start Tomorrow)")
                    print("2. Custom Start Date")
                    print("===============================")

                    start_date = None
                    while True:
                        start_choice_input = input("Enter your choice (1 or 2): ")
                        if start_choice_input == '1':
                            start_date = datetime.now() + timedelta(days=1)
                            print(f"Workflow will start scheduling from tomorrow: {start_date.strftime('%Y-%m-%d')}")
                            break
                        elif start_choice_input == '2':
                            while True:
                                date_str = input("Enter custom start date in YYYY-MM-DD format (e.g., 2024-12-31): ")
                                try:
                                    start_date = datetime.strptime(date_str, '%Y-%m-%d')
                                    print(f"Workflow will start scheduling from: {start_date.strftime('%Y-%m-%d')}")
                                    break
                                except ValueError:
                                    print("Invalid date format. Please use YYYY-MM-DD.")
                            break
                        else:
                            print("Invalid choice. Please enter 1 or 2.")
                    # --- End New Schedule Date Selection Logic ---

                    # Now, ask for videos per day
                    while True:
                        try:
                            total_videos_in_selection = 0
                            # Need to calculate total videos based on selected types and account path
                            base_videos_path = Path(BASE_DIR) / "videos"
                            for video_type in selected_types:
                                for account in selected_account_config["accounts"]:
                                    account_name = account.get('name')
                                    if account_name:
                                        video_type_path = base_videos_path / account_name / video_type
                                        if video_type_path.exists() and video_type_path.is_dir():
                                            # Count .mp4 files recursively
                                            for _ in video_type_path.glob("**/*.mp4"):
                                                total_videos_in_selection += 1


                            if total_videos_in_selection == 0:
                                print("No videos found in the selected types. Exiting workflow.")
                                return # Exit function if no videos found

                            print(f"Found {total_videos_in_selection} videos in the selected categories.")

                            videos_per_day = int(input(f"Enter the number of videos to upload per day: "))

                            if videos_per_day <= 0:
                                print("Videos per day must be a positive integer.")
                                continue # Ask again

                            # Calculate the number of days required
                            import math
                            days_to_schedule = math.ceil(total_videos_in_selection / videos_per_day)
                            end_date = start_date + timedelta(days=days_to_schedule - 1)
                            print(f"This will schedule videos over approximately {days_to_schedule} days, ending around {end_date.strftime('%Y-%m-%d')}.")


                            # Generate schedule times based on the selected start date and videos per day
                            # We need to modify generate_schedule_time_next_day or create a new function
                            # that takes a start_date and generates times.
                            # For now, let's adapt the existing function call assuming it can handle a start day offset.
                            # The generate_schedule_time_next_day seems to start from the *next* day (start_days=0 means tomorrow).
                            # We need a function that can start from a specific date.
                            # Let's manually generate the dates and times for now based on the start_date.

                            schedule_times = []
                            current_date = start_date
                            videos_scheduled_count = 0

                            # Assuming a default time like 10:00 AM for each day
                            default_time = "10:00" # You could make this configurable later

                            while videos_scheduled_count < total_videos_in_selection:
                                for i in range(videos_per_day):
                                    if videos_scheduled_count < total_videos_in_selection:
                                        schedule_time_str = f"{current_date.strftime('%Y-%m-%d')} {default_time}"
                                        schedule_times.append(schedule_time_str)
                                        videos_scheduled_count += 1
                                    else:
                                        break # Stop if all videos are scheduled
                                current_date += timedelta(days=1) # Move to the next day

                            print(f"Generated {len(schedule_times)} schedule times starting from {start_date.strftime('%Y-%m-%d')}.")
                            # print("Schedule times:", schedule_times) # Optional: print schedule for verification

                            # Attach the generated schedule times to the config for run_workflow to use
                            # We need a way to pass this schedule to the video processing loop in run_workflow
                            # One way is to add it to the selected_account_config, perhaps under a new key
                            # This requires run_workflow to be updated to look for this schedule.
                            # For now, the schedule is added to selected_account_config and we pass that via temp file.
                            # Assuming run_workflow is updated to read 'generated_schedule' from the config.
                            selected_account_config['generated_schedule'] = schedule_times

                            break # Exit scheduling loop

                        except ValueError:
                            print("Invalid input. Please enter a valid integer.")

                    break # Exit video type selection loop
                elif not invalid_choice:
                     print("No video types selected.")
                     return # Exit function if no types selected

            except ValueError:
                print("Invalid input. Please enter number(s) separated by commas.")
            except Exception as e:
                 print(f"An unexpected error occurred during video type selection: {e}")
                 return # Exit function on unexpected error

    else:
        print("Error: Could not retrieve account configuration.")
        return

    # Now, call the main run_workflow function with the selected account config
    try:
        # Option 2: Create a temporary config file with selected account and pass path
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False, encoding='utf-8') as tmp_file:
            json.dump(selected_account_config, tmp_file, ensure_ascii=False, indent=4)
            tmp_file_path = tmp_file.name
        try:
            from utils.base_social_media import run_workflow
            # Need to pass the schedule times to run_workflow
            # This requires modifying run_workflow to accept a schedule_times list or key in config
            # For now, the schedule is added to selected_account_config and we pass that via temp file.
            # Assuming run_workflow is updated to read 'generated_schedule' from the config.
            await run_workflow(tmp_file_path) # Pass path to temp file
        finally:
            os.remove(tmp_file_path) # Clean up temp file

    except Exception as e:
         print(f"An error occurred during workflow execution: {e}")


if __name__ == "__main__":
    asyncio.run(main())
