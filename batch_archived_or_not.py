import json
import os
import re
import requests
import sys
from datetime import datetime
from requests.packages.urllib3.exceptions import InsecureRequestWarning



VERSION = "1.0.2"
URL_TEMPLATE =r"https://{}/api/archived_or_not?user=constdoc@ucsc.edu&password=1156high"
#ADDRESS = r"localhost:5000" #for testing
ADDRESS = r"ppdo-dev-app-1.ucsc.edu"

def split_path(path):
    """
    Split a path into a list of directories/files/mount points. It is built to accomodate Splitting both Windows and Linux paths
    on linux systems. (It will not necessarily work to process linux paths on Windows systems)
    :param path: The path to split.
    """

    def detect_filepath_type(filepath):
        """
        Detects the cooresponding OS of the filepath. (Windows, Linux, or Unknown)
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
    
    #retrieve user values
    print(f"Version: {add_terminal_text_color(VERSION, 'yellow')}")
    files_location = input("Enter path to directory of files to check: ")
    recursive = True if input("Should file checking be recursive through nested sub-directories? (y/n): ").lower().startswith('y') else False
    only_missing_files = True if input("Only show files that are not found on the server? (y/n): ").lower().startswith('y') else False
    # if the user is not only interested in missing files, ask if they want to create a json file of the results
    create_json = True if (not only_missing_files and input("Create json file of results? (y/n): ").lower().startswith('y')) else False

    
    results= {} 
    for root, _, files in os.walk(files_location):
        
        for file in files:
            filepath = os.path.join(root, file)
            path_relative_to_files_location = os.path.relpath(filepath, files_location)
            request_url = URL_TEMPLATE.format(ADDRESS)
            file_locations = []
            with open(filepath, 'rb') as f:
                files = {'file': f}
                response = None
                try:
                    response = requests.post(request_url, files=files, verify=False)
                    file_locations = []
                    file_str = f"\nLocations for {path_relative_to_files_location}\n"
                    if response.status_code == 404:
                        print(add_terminal_text_color(text=file_str, color='green'))
                        print('\tNone')
                        
                    else:
                        if only_missing_files:
                            continue

                        file_locations = json.loads(response.text)
                        print(add_terminal_text_color(text=file_str, color='green'))
                        for i, location in enumerate(file_locations):
                            # if the output is being piped to console, alternate the color of the output
                            if (i % 2 != 0):
                                location = add_terminal_text_color(text=location, color='cyan')
                            print(f"\t{location}")

                except Exception as e:
                    if response and response.status_code and response.status_code in [404, 400, 500, 405]:
                        print(f"Request Error:\n{response.text}")
                        break

            results[filepath] = file_locations

        if root == files_location and not recursive:
            break

    if create_json:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        results_filepath = os.path.join(os.getcwd(), f'archived_or_not_results_{timestamp}.json')
        with open(results_filepath, 'w') as f:
            json.dump(results, f, indent=4)
        # print the results filepath in purple if the output is being piped to console
        print(add_terminal_text_color(text=f"\nResults file saved to: {results_filepath}\n", color='purple'))

    # wait for user input to exit
    input("Press Enter to exit...")

if __name__ == '__main__':
    main()