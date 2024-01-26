import json
import os
import random
import re
import requests
import PySimpleGUI as sg
import pandas as pd
from openpyxl.styles.alignment import Alignment
from collections import defaultdict
from datetime import datetime
from requests.packages.urllib3.exceptions import InsecureRequestWarning

VERSION = "1.1.0"
URL_TEMPLATE =r"https://{}/api/archived_or_not?user=constdoc@ucsc.edu&password=1156high"
#ADDRESS = r"localhost:5000" # for testing
ADDRESS = r"ppdo-dev-app-1.ucsc.edu"

class GuiHandler:
    """
        This class is used to create and launch the various GUI windows used by the script.
    """

    def __init__(self, app_version: str):
        self.gui_theme = 'Dark2'
        self.app_version = app_version

    def _main_form_layout(self):
        """
        Create the layout for the main form.
        :return: The layout for the main form.
        """
        sg.theme('Dark2')

        layout = [
            [sg.Text("Version: " + self.app_version)],
            [sg.Text("Input a valid file path in box below. Copy and paste it from Windows File Explorer or use 'Browse' to locate a folder.")],
            [sg.Text("Path to directory of files to check: "), sg.InputText(size=(80, 5), key='input_files_location'),
             sg.FolderBrowse(key='input_files_location')],
            [sg.Checkbox("Should file checking be recursive through nested sub-directories?", key='recursive', default=True)],
            [sg.Checkbox("Only show files that are not found on the server? Useful for reducing the output from this tool (won't effect excel or json output)", key='only_missing')],
            [sg.Text("Saved Output Type: "), sg.Combo(values=['json', 'excel', 'None'], default_value='None',
                                                      key='output_type')],
            [sg.Submit(), sg.Cancel(), sg.ProgressBar(100, orientation='h', size=(70, 15), bar_color=('green', 'white'),
                                                      key='progressbar')],
            [sg.Multiline(size=(110, 20), font=('Courier', 10), key='multiline', write_only=True, autoscroll=True)]
        ]
        return layout

    def make_window(self, window_name: str, window_layout: list):
        """

        :param window_name:
        :param window_layout:
        :return:
        """

        sg.theme(self.gui_theme)

        # launch gui
        window = sg.Window(window_name, layout=window_layout, resizable=True, finalize=True)
        window.bring_to_front()
        return window



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

def json_export(r, time):
    results_filepath = os.path.join(os.getcwd(), f'archived_or_not_results_{time}.json')
    with open(results_filepath, 'w') as f:
        json.dump(r, f, indent=4)
    return results_filepath

def excel_export(r, time):
    results_filepath = os.path.join(os.getcwd(), f'archived_or_not_results_{time}.xlsx')
    df = pd.DataFrame.from_dict(r, orient='index')
    with pd.ExcelWriter(results_filepath, engine="openpyxl") as w:
        sheet_name = "sheet1"
        df.to_excel(w, sheet_name=sheet_name, header=False)
        sheet = w.sheets[sheet_name]
        for cell in sheet["A"]:
            cell.alignment = Alignment(horizontal="left")
    return results_filepath

def main():
    # Disable SSL warnings
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    gui_handler = GuiHandler(app_version=VERSION)
    layout = gui_handler._main_form_layout()
    window = gui_handler.make_window("Batch Archived-or-Not", layout)
    progress_bar = window['progressbar']

    # multiline element
    multiline_output = window['multiline']

    while True:
        event, values = window.read()
        only_missing_files = False
        recursive = False
        # close window event
        if event == sg.WIN_CLOSED or event == 'Cancel':
            break
        # submit button event, hosts main program
        if event == 'Submit':
            # recursive button event
            if values['recursive']:
                recursive = True
            # only_missing_files button event
            if values['only_missing']:
                only_missing_files = True
            pb_counter = 0
            pb_max = 100
            progress_bar.update_bar(pb_counter, pb_max)
            files_location = values['input_files_location']
            # reset mline in case user is using the same window again
            multiline_output.update("")

            # proceed ONLY if path is provided
            if not os.path.isdir(files_location):
                sg.popup_error("Must input valid filepath")

            results = {}
            # find total number of files (for the progress bar)
            if recursive:
                pb_max = sum(1 for _, _, fi in os.walk(files_location) for f in fi)

            for root, dirs, files in os.walk(files_location):
                if not recursive:
                    pb_max = len(files)
                
                # iterate through files in directory
                for file in files:
                    pb_counter += 1
                    progress_bar.update_bar(pb_counter, pb_max)
                    filepath = os.path.join(root, file)
                    path_relative_to_files_location = os.path.relpath(filepath, files_location)
                    request_url = URL_TEMPLATE.format(ADDRESS)
                    
                    # open file and send to server endpoint
                    with open(filepath, 'rb') as f:
                        files = {'file': f}
                        response = None
                        try:
                            response = requests.post(request_url, files=files, verify=False)
                            file_locations = []
                            file_str = f"\nLocations for {path_relative_to_files_location}\n\n"
                            
                            # if file is not found on server, display "None" in red
                            if response.status_code == 404:
                                multiline_output.update(file_str, text_color_for_value='green', append=True)
                                multiline_output.update("\tNone\n", text_color_for_value='red', append=True)
                                file_locations = "None"
                            else:
                                if only_missing_files:
                                    continue
                                file_locations = json.loads(response.text)
                                multiline_output.update(file_str, text_color_for_value='green', append=True)
                                for i, location in enumerate(file_locations):
                                    # if the output is being piped to gui, alternate the color of the output
                                    color = 'black'
                                    if (i % 2) != 0:
                                        color = 'grey'
                                    location = "R:\\" + location.replace("/", "\\")
                                    multiline_output.update(f"\t{location}\n", text_color_for_value=color, append=True)
                        except Exception as e:
                            if response and response.status_code and response.status_code in [404, 400, 500, 405]:
                                sg.popup_error(f"Request Error:\n{response.text}")
                                break
                    results[filepath] = file_locations
                if root == files_location and not recursive:
                    break

            if os.path.isdir(files_location):
                multiline_output.update("\nSearch complete.", text_color_for_value='red', append=True)

            # export output based on user options

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # export json
            if values['output_type'] == 'json':
                path_name = json_export(results, timestamp)
                window.close()
                sg.popup_ok(path_name, title="Results excel file saved to:")

            # export excel
            elif values['output_type'] == 'excel':
                path_name = excel_export(results, timestamp)
                window.close()
                sg.popup_ok(path_name, title="Results excel file saved to:")

    window.close()

if __name__ == '__main__':
    #TestGuiHandler.test_main_form()
    main()


# TODO:
#   - Reformat excel
#   - Replicate 'None' output behavior for all output types
#   - choose and check output path permissions. default to cwd