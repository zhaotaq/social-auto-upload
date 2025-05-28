import PySimpleGUI as sg
from .gui_layout import create_layout
from .file_manager import FileManager, generate_initial_file_info

def main():
    # Use ChangeLookAndFeel for compatibility with potentially older PySimpleGUI versions
    sg.ChangeLookAndFeel('LightBlue3')  # Set a theme

    layout = create_layout()
    window = sg.Window('视频上传文件管理器', layout, finalize=True)

    file_manager = FileManager()
    file_info_list = [] # List to hold file info dictionaries
    selected_row_index = -1 # Track the currently selected row index

    def update_table_display(current_selected_index=None):
        """Helper function to regenerate and update the table display."""
        table_data = []
        for i, file_info in enumerate(file_info_list):
             table_data.append([
                 i + 1, # 序号
                 file_info.get('video_name', ''),
                 file_info.get('title', ''),
                 ' '.join(file_info.get('tags', []))
             ])
        window['-VIDEOSTABLE-'].update(values=table_data)

        # Reselect the row after updating the table if a row was selected
        if current_selected_index is not None and 0 <= current_selected_index < len(file_info_list):
            window['-VIDEOSTABLE-'].update(select_rows=[current_selected_index])


    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED or event == 'Exit':
            break

        if event == '-FOLDER-':
            folder_path = values['-FOLDER-']
            if folder_path:
                print(f"Selected folder: {folder_path}")
                # Set the working directory for the file_manager instance
                if file_manager.set_directory(folder_path):
                    # Generate initial list of file info
                    file_info_list = generate_initial_file_info(folder_path)
                    selected_row_index = -1 # Reset selection
                    window['-CURRENTVIDEO-'].update('')
                    window['-TITLEINPUT-'].update('')
                    window['-TAGSINPUT-'].update('')

                    if file_info_list:
                        update_table_display() # Update table
                        print(f"Loaded {len(file_info_list)} video files.")
                    else:
                        window['-VIDEOSTABLE-'].update(values=[[]]) # Clear table
                        print("No video files (.mp4) found in the selected folder.")
                else:
                    # Handle case where directory is not valid (error message already printed in set_directory)
                    file_info_list = [] # Clear list
                    selected_row_index = -1 # Reset selection
                    window['-VIDEOSTABLE-'].update(values=[[]]) # Clear table
                    window['-FOLDER-'].update('') # Clear the input path
                    window['-CURRENTVIDEO-'].update('')
                    window['-TITLEINPUT-'].update('')
                    window['-TAGSINPUT-'].update('')
                    sg.popup_error('无效的文件夹路径', title='错误')

        elif event == '-VIDEOSTABLE-':
            if values['-VIDEOSTABLE-']:
                # Get the index from the event tuple if it's a click event
                if isinstance(event, tuple):
                     if event[0] == '-VIDEOSTABLE-' and event[1] == '+CLICKED+':
                         selected_row_index = event[2][0] # (element_key, '+CLICKED+', (row, col))
                     elif event[0] == '-VIDEOSTABLE-' and event[1] in ('上移', '下移'):
                          # For right-click menu, the selected row is still in values['-VIDEOSTABLE-'][0]
                          # But it's safer to rely on the stored selected_row_index from the last click
                          # if the table allows multiple selections, values could be a list.
                          # Let's assume single selection for simplicity based on the tooltip.
                          # We'll use the stored selected_row_index.
                          pass # selected_row_index is already set from the click event
                     else:
                          # Handle other potential table events if needed
                          # print(f"Unhandled table event tuple: {event}")
                          pass
                elif isinstance(values['-VIDEOSTABLE-'], list) and values['-VIDEOSTABLE-']:
                     selected_row_index = values['-VIDEOSTABLE-'][0] # For standard selection event
                else:
                     selected_row_index = -1 # Should not happen with enable_events=True, but for safety

                # Ensure valid index after getting it from values/event
                if 0 <= selected_row_index < len(file_info_list):
                    # Load selected file info into input fields
                    file_info = file_info_list[selected_row_index]
                    window['-CURRENTVIDEO-'].update(file_info.get('video_name', ''))
                    window['-TITLEINPUT-'].update(file_info.get('title', ''))
                    window['-TAGSINPUT-'].update(' '.join(file_info.get('tags', [])))
                else:
                    selected_row_index = -1 # Invalid index
                    window['-CURRENTVIDEO-'].update('')
                    window['-TITLEINPUT-'].update('')
                    window['-TAGSINPUT-'].update('')
                    # print("Debug: Invalid row selected index.") # Keep quiet unless needed
            else:
                 selected_row_index = -1 # No row selected
                 window['-CURRENTVIDEO-'].update('')
                 window['-TITLEINPUT-'].update('')
                 window['-TAGSINPUT-'].update('')

        elif event == '-UPDATETAGS-':
            if selected_row_index != -1 and 0 <= selected_row_index < len(file_info_list):
                # Update title and tags in the file_info_list
                new_title = values['-TITLEINPUT-']
                new_tags = values['-TAGSINPUT-'].split()
                
                file_info_list[selected_row_index]['title'] = new_title
                file_info_list[selected_row_index]['tags'] = new_tags

                update_table_display(selected_row_index) # Regenerate and update the table display

                print(f"Updated info for {file_info_list[selected_row_index].get('video_name', '')}")
            else:
                print("Please select a video file from the list to update.")

        elif event == '上移':
            if selected_row_index > 0:
                # Swap the selected item with the one above it in file_info_list
                file_info_list[selected_row_index], file_info_list[selected_row_index - 1] = \
                    file_info_list[selected_row_index - 1], file_info_list[selected_row_index]
                selected_row_index -= 1 # Update selected index
                update_table_display(selected_row_index) # Update table display and reselect
                print(f"Moved up: {file_info_list[selected_row_index].get('video_name', '')}")
            elif selected_row_index == 0:
                 print("Already at the top.")
            else:
                print("Please select a video file to move.")

        elif event == '下移':
            if selected_row_index != -1 and selected_row_index < len(file_info_list) - 1:
                # Swap the selected item with the one below it in file_info_list
                file_info_list[selected_row_index], file_info_list[selected_row_index + 1] = \
                    file_info_list[selected_row_index + 1], file_info_list[selected_row_index]
                selected_row_index += 1 # Update selected index
                update_table_display(selected_row_index) # Update table display and reselect
                print(f"Moved down: {file_info_list[selected_row_index].get('video_name', '')}")
            elif selected_row_index == len(file_info_list) - 1:
                 print("Already at the bottom.")
            else:
                print("Please select a video file to move.")

        elif event == '-APPLYRENAME-':
            if file_manager.current_dir and file_info_list:
                print("Applying new order and renaming files...")
                success = file_manager.rename_files(file_info_list)
                if success:
                    print("Renaming and saving completed successfully.")
                    # Reload files after renaming to update the table with new names
                    file_info_list = generate_initial_file_info(file_manager.current_dir)
                    selected_row_index = -1 # Reset selection
                    window['-CURRENTVIDEO-'].update('')
                    window['-TITLEINPUT-'].update('')
                    window['-TAGSINPUT-'].update('')
                    update_table_display() # Update table with new names
                else:
                    print("Renaming and saving encountered errors. Check output above for details.")
                    sg.popup_error('重命名和保存过程中发生错误', title='错误')
            elif not file_manager.current_dir:
                print("Please select a folder first.")
            else:
                print("No video files to rename.")

        # print(f"Event: {event}, Values: {values}") # for debugging

    window.close()

if __name__ == '__main__':
    main() 