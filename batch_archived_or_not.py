import json
import os
import random
import re
import requests
import sys
import PySimpleGUI as sg
import pandas as pd
from collections import defaultdict
from datetime import datetime
from requests.packages.urllib3.exceptions import InsecureRequestWarning



VERSION = "1.0.2"
URL_TEMPLATE =r"https://{}/api/archived_or_not?user=constdoc@ucsc.edu&password=1156high"
#ADDRESS = r"localhost:5000" #for testing
ADDRESS = r"ppdo-dev-app-1.ucsc.edu"

class GuiHandler:
    """
        This class is used to create and launch the various GUI windows used by the script.
    """

    def __init__(self, app_version: str):
        self.gui_theme = random.choice(["DarkTeal6", "Green", "LightBrown11", "LightPurple", "SandyBeach", "DarkGreen4",
                                        "BluePurple", "Reddit", "DarkBrown5", "DarkBlue8", "LightGreen6", "LightBlue7",
                                        "DarkGreen2", "Kayak", "LightBrown3", "LightBrown1", "LightTeal", "Tan",
                                        "TealMono", "LightBrown4", "LightBrown3", "LightBrown2", "DarkPurple4",
                                        "DarkPurple", "DarkGreen5", "Dark Brown3", "DarkAmber", "DarkGrey6",
                                        "DarkGrey2", "DarkTeal1", "LightGrey6", "DarkBrown6"])
        self.window_close_button_event = "-WINDOW CLOSE ATTEMPTED-"
        self.app_version = app_version

    def _main_form_layout(self):
        """
        Create the layout for the main form.
        :return: The layout for the main form.
        """
        layout = [
            [sg.Text("Version: " + self.app_version)],
            [sg.Text("Input a valid file path in box below. Manually input the path or select Browse to locate the folder.")],
            [sg.Text("Path to directory of files to check: "), sg.InputText(key='input_files_location'), sg.FolderBrowse(key='input_files_location')],
            [sg.Checkbox("Should file checking be recursive through nested sub-directories?", key='recursive')],
            [sg.Checkbox("Only show files that are not found on the server?", key='only_missing')],
            [sg.Text("Note: If you requested only the missing files, do not select any output other than 'window'.")],
            [sg.Text("Output Type: "), sg.Combo(values=['json', 'excel', 'window'], default_value='window', key='output_type')],
            [sg.Submit(), sg.Cancel(), sg.ProgressBar(100, orientation='h', size=(50, 15), bar_color=('green', 'white'), key='progressbar')]
        ]
        return layout

    def make_window(self, window_name: str, window_layout: list, figure=None):
        """

        :param window_name:
        :param window_layout:
        :param figure: matplotlib figure to be included in layout, requires sg.Canvas(key='-CANVAS-') element in layout
        :return:
        """

        sg.theme(self.gui_theme)

        # launch gui
        window = sg.Window(window_name, layout=window_layout, finalize=True, enable_close_attempted_event=True)
        window.bring_to_front()
        event, values = window.read()
        values["Button Event"] = event
        window.close()
        return defaultdict(None, values)


class TestGuiHandler:


    @staticmethod
    def test_main_form():
        gui_handler = GuiHandler("1.0.0")
        layout = gui_handler._main_form_layout()
        window = sg.Window("Test Window", layout=layout, finalize=True)
        window.bring_to_front()
        event, values = window.read()
        values["Button Event"] = event
        window.close()
        return values
    

def split_path(path):
    """
    Split a path into a list of directories/files/mount points. It is built to accommodate Splitting both Windows and Linux paths
    on linux systems. (It will not necessarily work to process linux paths on Windows systems)
    :param path: The path to split.
    """

    def detect_filepath_type(filepath):
        """
        Detects the corresponding OS of the filepath. (Windows, Linux, or Unknown)
        :param filepath: The filepath to detect.
        :return: The OS of the filepath. (Windows, Linux, or Unknown)
        """
        windows_pattern = r"^[A-Za-z]:\\(.+)$"
        linux_pattern = r"^/([^/]+/)*[^/]+$"

        if re.match(windows_pattern, filepath):
            return "Windows"
        elif re.match(linux_pattern, filepath):
            return "Linux"
        else:
            return "Unknown"
        
    def split_windows_path(filepath):
        """"""
        parts = []
        curr_part = ""
        is_absolute = False

        if filepath.startswith("\\\\"):
            # UNC path
            parts.append(filepath[:2])
            filepath = filepath[2:]
        elif len(filepath) >= 2 and filepath[1] == ":":
            # Absolute path
            parts.append(filepath[:2])
            filepath = filepath[2:]
            is_absolute = True

        for char in filepath:
            if char == "\\":
                if curr_part:
                    parts.append(curr_part)
                    curr_part = ""
            else:
                curr_part += char

        if curr_part:
            parts.append(curr_part)

        if not is_absolute and not parts:
            # Relative path with a single directory or filename
            parts.append(curr_part)

        return parts
    
    def split_other_path(path):

        allparts = []
        while True:
            parts = os.path.split(path)
            if parts[0] == path:  # sentinel for absolute paths
                allparts.insert(0, parts[0]) 
                break
            elif parts[1] == path:  # sentinel for relative paths
                allparts.insert(0, parts[1])
                break
            else:
                path = parts[0]
                allparts.insert(0, parts[1])
        return allparts

    path = str(path)
    path_type = detect_filepath_type(path)
    
    if path_type == "Windows":
        return split_windows_path(path)
    
    return split_other_path(path)

def create_paths_from_file_locations(row, file_server_location):
    path_parts_list = split_path(row['file_server_directories'])
    path_parts_list.append(row['filename'])
    path_parts_list = [file_server_location] + path_parts_list
    return os.path.join(*path_parts_list)

def add_terminal_text_color(text, color):
    """
    Add terminal text color to the text.
    :param text: The text to add color to.
    :param color: The color to add to the text.
    """
    color_map = {
        'green': '1;32;40m',
        'cyan': '0;36m',
        'yellow': '1;33;40m',
        'purple': '0;35m'
    }

    if color not in color_map:
        raise ValueError(f"Invalid color: {color}")
    
    if not sys.stdin.isatty():
        return text

    return f"\033[{color_map[color]}{text}\033[0m"


def main():
    # Disable SSL warnings
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Enable ANSI escape sequences for color output
    os.system('')

    gui_handler = GuiHandler("1.0.0")
    layout = gui_handler._main_form_layout()
    window = sg.Window("Test Window", layout=layout, finalize=True)
    progress_bar = window['progressbar']
    window.bring_to_front()

    while True:
        event, values = window.read()
        only_missing_files = False
        recursive = False
        # close window event
        if event == sg.WIN_CLOSED or event == 'Cancel':
            break
        # recursive button event
        if values['recursive']:
            recursive = True
        # only_missing_files button event
        if values['only_missing']:
            only_missing_files = True
        # submit button event, hosts main program
        if event == 'Submit':
            pb_counter = 0
            pb_max = 100
            progress_bar.update_bar(pb_counter, pb_max)
            files_location = values['input_files_location']
            # proceed ONLY if path is provided
            if files_location == "":
                sg.popup_error("Must input filepath")
                break

            results = {}
            # find total number of files (for the progress bar)
            if recursive:
                pb_max = sum(1 for _, _, fi in os.walk(files_location) for f in fi)

            for root, dirs, files in os.walk(files_location):
                if not recursive:
                    pb_max = len(files)
                for file in files:
                    pb_counter += 1
                    progress_bar.update_bar(pb_counter, pb_max)
                    filepath = os.path.join(root, file)
                    request_url = URL_TEMPLATE.format(ADDRESS)
                    with open(filepath, 'rb') as f:
                        files = {'file': f}
                        response = None
                        try:
                            response = requests.post(request_url, files=files, verify=False)
                            file_locations = []
                            if response.status_code == 404:
                                file_locations = "None"
                            else:
                                if only_missing_files:
                                    continue
                                file_locations = json.loads(response.text)
                        except Exception as e:
                            if response and response.status_code and response.status_code in [404, 400, 500, 405]:
                                sg.popup_error(f"Request Error:\n{response.text}")
                                break
                    results[filepath] = file_locations
                if root == files_location and not recursive:
                    break

            # export output based on user options
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # export json
            if values['output_type'] == 'json' and not only_missing_files:
                results_filepath = os.path.join(os.getcwd(), f'archived_or_not_results_{timestamp}.json')
                with open(results_filepath, 'w') as f:
                    json.dump(results, f, indent=4)
                window.close()
                sg.popup_ok(results_filepath, title="Results excel file saved to:")

            # export excel
            elif values['output_type'] == 'excel' and not only_missing_files:
                results_filepath = os.path.join(os.getcwd(), f'archived_or_not_results_{timestamp}.xlsx')
                df = pd.DataFrame(data=results)
                df.to_excel(results_filepath)
                window.close()
                sg.popup_ok(results_filepath, title="Results excel file saved to:")

            window.close()

            # format the output
            out = []
            if only_missing_files:
                count = 0
                for key, vals in results.items():
                    if vals != "None":
                        continue
                    else:
                        count += 1
                        key = key.replace("/", "\\")
                        out.append(f"Locations for {key}")
                        out.append("  \\")
                        out.append("   | None")
                        out.append("  /")
                if count == 0:
                    out.append("All files were located on the server")
            else:
                for key, vals in results.items():
                    key = key.replace("/", "\\")
                    out.append(f"Locations for {key}")
                    out.append("  \\")
                    if vals != "None":
                        for val in vals:
                            val = val.replace("/", "\\")
                            out.append(f"   | R:\\{val}")
                    else:
                        out.append("   | None")
                    out.append("  /")

            # output to window (default)
            layout = [[sg.Multiline(default_text="\n".join(out), size=(130, 30), font=('Courier', 10), key="line",
                                    autoscroll=True)]]
            window = sg.Window("File Locations", layout, finalize=True)
            while True:
                event, values = window.read()
                if event == sg.WIN_CLOSED:
                    break

    window.close()

if __name__ == '__main__':
    #TestGuiHandler.test_main_form()
    main()


# Features to add:
#   - Add ability choose between json, excel, or None output
#   - GUI?