import PySimpleGUI as sg

def create_layout():
    layout = [
        [sg.Text('选择视频文件夹:'), sg.Input(key='-FOLDER-', enable_events=True, readonly=True), sg.FolderBrowse('浏览')],
        [sg.Text('-'*50)],
        [sg.Text('视频文件列表 (拖拽调整顺序):')],
        [sg.Table(
            values=[[]],  # Initial empty data
            headings=['序号', '视频文件名', '标题', '标签'],
            max_col_width=250,
            auto_size_columns=True,
            display_row_numbers=False,
            justification='left',
            num_rows=15,
            key='-VIDEOSTABLE-',
            enable_events=True,
            enable_click_events=True, # Enable click events for row selection
            right_click_menu=['', ['上移', '下移']], # Right click menu for reordering
            row_height=35, # Increase row height for better readability
            tooltip='双击行编辑标题和标签，右键上移/下移调整顺序',
            expand_x=True, # Add this to expand horizontally
            expand_y=True  # Add this to expand vertically
        )],
        [sg.Text('当前编辑视频: '), sg.Text('', size=(50, 1), key='-CURRENTVIDEO-')],
        [sg.Text('标题:'), sg.Input(size=(80, 1), key='-TITLEINPUT-')],
        [sg.Text('标签:'), sg.Input(size=(80, 1), key='-TAGSINPUT-', tooltip='多个标签用空格分隔')],
        [sg.Button('更新标题/标签', key='-UPDATETAGS-'), sg.Button('应用新顺序和命名', key='-APPLYRENAME-')],
        [sg.Text('-'*50)],
        [sg.Output(size=(100, 10), key='-OUTPUT-', font='Courier 10')]
    ]
    return layout 