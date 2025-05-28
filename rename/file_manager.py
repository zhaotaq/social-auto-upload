import os
from pathlib import Path
import json

class FileManager:
    def __init__(self, base_videos_dir="videos"):
        # Assuming videos are in BASE_DIR / videos / account_name / video_type
        # For this specific tool, let's assume we're working within a specific video_type folder
        # The user will need to select the folder using the GUI
        self.current_dir = None # This will be set by the GUI when a folder is selected

    def set_directory(self, directory_path):
        """Sets the current working directory for file operations."""
        if os.path.isdir(directory_path):
            self.current_dir = Path(directory_path)
            print(f"FileManager working directory set to: {self.current_dir}")
            return True
        else:
            print(f"Error: Directory not found: {directory_path}")
            self.current_dir = None
            return False

    def list_video_files(self):
        """Lists all .mp4 files in the current directory."""
        if not self.current_dir:
            print("Error: Working directory not set.")
            return []
        video_files = sorted(list(self.current_dir.glob("*.mp4")))
        return video_files

    def get_video_info(self, video_file_path):
        """Reads title and tags from a companion .txt file, or returns empty if not found."""
        txt_file_path = video_file_path.with_suffix('.txt')
        title = ""
        tags = []
        if txt_file_path.exists():
            try:
                with open(txt_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Assuming the format is: Title\nTag1 Tag2 Tag3...
                    lines = content.splitlines()
                    if lines:
                        title = lines[0].strip()
                    if len(lines) > 1:
                        # Remove potential comments or empty lines after tags
                        tag_line = lines[1].strip()
                        if tag_line:
                             tags = tag_line.split()
            except Exception as e:
                print(f"Error reading {txt_file_path}: {e}")
        return title, tags

    def save_video_info(self, video_file_path, title, tags):
        """Saves title and tags to a companion .txt file."""
        if not self.current_dir:
            print("Error: Working directory not set. Cannot save.")
            return False

        txt_file_path = video_file_path.with_suffix('.txt')
        try:
            with open(txt_file_path, 'w', encoding='utf-8') as f:
                f.write(title.strip() + '\n')
                # Ensure tags are written even if empty, to create the file
                f.write(' '.join(tags).strip() + '\n')
            # print(f"Saved info to {txt_file_path}") # Suppress excessive print
            return True
        except Exception as e:
            print(f"Error saving to {txt_file_path}: {e}")
            return False

    def rename_files(self, file_info_list):
        """Renames video and txt files based on sorted order and adds sequence numbers, then saves info."""
        if not self.current_dir:
            print("Error: Working directory not set. Cannot rename.")
            return False

        # Create a mapping of original path to new path to handle potential conflicts
        rename_map = {}
        for index, file_info in enumerate(file_info_list):
            original_video_path = Path(file_info['original_path'])

            # Generate new name with sequence number (e.g., 01_, 02_)
            # Use 2 digits for numbering, adjust if more than 99 videos expected
            seq_number = f"{index + 1:02d}_"
            # Ensure we get the original file name *without* any existing sequence number if present
            # A simple approach is to take the part after the last underscore if it looks like a sequence number
            # A more robust approach would be to store the original name without prefix when loading
            # For now, let's assume original_path contains the name as it was loaded initially
            original_name_without_prefix = original_video_path.name # Use the name from the path

            new_video_name = seq_number + original_name_without_prefix
            new_video_path = self.current_dir / new_video_name

            # Add to rename map
            rename_map[original_video_path] = new_video_path

        # Check for conflicting target filenames before renaming
        target_paths = set(rename_map.values())
        if len(target_paths) != len(rename_map):
             print("Error: Conflicting target filenames detected after applying sequence numbers. Aborting rename.")
             # You might want to provide more details about which files conflict
             return False

        success = True
        # First pass: Rename files (handle potential overwrites carefully)
        # Using temporary names can be safer but adds complexity. Let's stick to direct rename for now
        # but rely on the target_exists check below.

        renamed_paths_map = {} # Map original path to the path *after* renaming in this pass

        for original_video_path, new_video_path in rename_map.items():
            original_txt_path = original_video_path.with_suffix('.txt')
            new_txt_path = new_video_path.with_suffix('.txt')

            try:
                # Rename video file
                if original_video_path != new_video_path:
                     # Check if target exists and is not the original file (which shouldn't happen in direct rename)
                    if new_video_path.exists():
                        print(f"Warning: Target video file already exists: {new_video_path}. Skipping rename for {original_video_path.name}.")
                        success = False
                        # We still add the original path to renamed_paths_map, pointing to itself if rename skipped
                        renamed_paths_map[original_video_path] = original_video_path
                        if original_txt_path.exists():
                             renamed_paths_map[original_txt_path] = original_txt_path
                        continue # Skip renaming this pair
                    
                    os.rename(original_video_path, new_video_path)
                    print(f"Renamed video: {original_video_path.name} -> {new_video_path.name}")
                    renamed_paths_map[original_video_path] = new_video_path
                else:
                    # File doesn't need renaming, map original path to itself
                    renamed_paths_map[original_video_path] = original_video_path

                # Rename txt file if it exists (after video rename, targeting the new video name's suffix)
                # Check if the original txt exists before attempting to rename it
                if original_txt_path.exists():
                    if original_txt_path != new_txt_path:
                        if new_txt_path.exists():
                            print(f"Warning: Target txt file already exists: {new_txt_path}. Skipping rename for {original_txt_path.name}.")
                            # Keep existing txt path if rename skipped
                            renamed_paths_map[original_txt_path] = original_txt_path
                            # Don't set success to False here, only if video rename failed
                            continue # Skip renaming this txt
                        
                        os.rename(original_txt_path, new_txt_path)
                        print(f"Renamed txt: {original_txt_path.name} -> {new_txt_path.name}")
                        renamed_paths_map[original_txt_path] = new_txt_path
                    else:
                         # Txt file doesn't need renaming, map original txt path to its new location based on video's new name
                         renamed_paths_map[original_txt_path] = new_txt_path
                # If original txt didn't exist, it won't be in renamed_paths_map initially.

            except FileNotFoundError:
                 print(f"Error: File not found during rename for {original_video_path.name}. It might have been moved or deleted.")
                 success = False
                 # Still try to save info later based on the intended new path
                 renamed_paths_map[original_video_path] = new_video_path # Map to intended new path even if rename failed
                 # No need to map original_txt_path here if video not found, it won't be saved later

            except FileExistsError:
                print(f"Error: Target file already exists during rename for {original_video_path.name}. This should have been caught earlier.")
                success = False
                renamed_paths_map[original_video_path] = new_video_path # Map to intended new path
                # No need to map original_txt_path here

            except Exception as e:
                print(f"An unexpected error occurred during rename for {original_video_path.name}: {e}")
                success = False
                renamed_paths_map[original_video_path] = new_video_path # Map to intended new path
                # No need to map original_txt_path here

        # Second pass: Save/update txt file content based on the file_info_list and renamed paths
        for file_info in file_info_list:
             original_video_path = Path(file_info['original_path'])
             
             # Get the final path of the video file after potential renaming
             # Use the renamed_paths_map to get the actual new path, falling back to original if rename failed/skipped
             final_video_path = renamed_paths_map.get(original_video_path, original_video_path) 
             
             # Construct the final txt path based on the final video path
             final_txt_path = final_video_path.with_suffix('.txt')

             # Save the current title and tags from the file_info_list to the final txt file path
             # This will create the txt file if it doesn't exist or overwrite it if it does.
             save_success = self.save_video_info(final_video_path, file_info.get('title', ''), file_info.get('tags', []))
             if not save_success:
                 success = False # If saving fails for any file, the overall operation is not fully successful

        return success

# Helper function to generate initial file info list (used by GUI)
def generate_initial_file_info(directory_path):
    file_manager = FileManager()
    if not file_manager.set_directory(directory_path):
        return []

    video_files = file_manager.list_video_files()
    file_info_list = []
    for video_file in video_files:
        title, tags = file_manager.get_video_info(video_file)
        file_info_list.append({
            'original_path': str(video_file), # Store the path as it was when loaded
            'video_name': video_file.name,
            'title': title,
            'tags': tags,
            'display_order': 0 # Placeholder for GUI sorting
        })

    # Sort initially by video name (natural sort might be better, but simple sort for now)
    # After renaming, the name will include the prefix, so re-loading will sort by prefix.
    file_info_list.sort(key=lambda x: x['video_name'])

    # Assign initial display order based on sorted order
    for i, file_info in enumerate(file_info_list):
        file_info['display_order'] = i

    return file_info_list 