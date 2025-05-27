import argparse
import asyncio
from datetime import datetime
from os.path import exists
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
from uploader.ks_uploader.main import ks_setup, KSVideo
from uploader.tencent_uploader.main import weixin_setup, TencentVideo
from uploader.tk_uploader.main_chrome import tiktok_setup, TiktokVideo
from utils.base_social_media import get_supported_social_media, get_cli_action, SOCIAL_MEDIA_DOUYIN, \
    SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU, load_workflow_config
from utils.constant import TencentZoneTypes
from utils.files_times import get_title_and_hashtags


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
    elif args.action == 'upload':
        title, tags = get_title_and_hashtags(args.video_file)
        video_file = args.video_file

        if args.publish_type == 0:
            print("Uploading immediately...")
            publish_date = 0
        else:
            print("Scheduling videos...")
            publish_date = parse_schedule(args.schedule)

        if args.platform == SOCIAL_MEDIA_DOUYIN:
            await douyin_setup(account_file, handle=False)
            app = DouYinVideo(title, video_file, tags, publish_date, account_file)
        elif args.platform == SOCIAL_MEDIA_TIKTOK:
            await tiktok_setup(account_file, handle=True)
            app = TiktokVideo(title, video_file, tags, publish_date, account_file)
        elif args.platform == SOCIAL_MEDIA_TENCENT:
            await weixin_setup(account_file, handle=True)
            category = TencentZoneTypes.LIFESTYLE.value  # 标记原创需要否则不需要传
            app = TencentVideo(title, video_file, tags, publish_date, account_file, category)
        elif args.platform == SOCIAL_MEDIA_KUAISHOU:
            await ks_setup(account_file, handle=True)
            app = KSVideo(title, video_file, tags, publish_date, account_file)
        else:
            print("Wrong platform, please check your input")
            exit()

        await app.main()
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

    # Now, call the main run_workflow function with the selected account config
    try:
        # We need to pass the config dictionary, not the path, if we're filtering accounts
        # We'll need to adjust run_workflow to accept either path or dict, or create a wrapper
        # For simplicity now, let's adjust run_workflow to accept the config dict directly.
        # Note: This requires a small change in utils/base_social_media.py as well.

        # Option 1: Adjust run_workflow to accept dict (requires change in utils)
        from utils.base_social_media import run_workflow # Import here to avoid circular dependency
        await run_workflow(selected_account_config) # Passing dict instead of path

        # Option 2 (Alternative): Create a temporary config file with selected account and pass path
        # import tempfile
        # with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
        #     json.dump(selected_account_config, tmp_file, ensure_ascii=False, indent=4)
        #     tmp_file_path = tmp_file.name
        # try:
        #     from utils.base_social_media import run_workflow
        #     await run_workflow(tmp_file_path) # Pass path to temp file
        # finally:
        #     os.remove(tmp_file_path) # Clean up temp file

    except Exception as e:
         print(f"An error occurred during workflow execution: {e}")


if __name__ == "__main__":
    asyncio.run(main())
