import json
import socket
import time
from typing import Any


def _add_argument_to_list(arg_list: list, key: str, value: Any):
    if value is None:
        return
    if isinstance(value, bool):
        if value:
            arg_list.append(f"--{key}")
    elif isinstance(value, list):
        if value:
            arg_list.append(f"--{key}")
            for item in value:
                arg_list.append(str(item))
    elif isinstance(value, dict):
        arg_list.append(f"--{key}")
        arg_list.append(json.dumps(value))
    else:
        arg_list.append(f"--{key}")
        arg_list.append(str(value))


def convert_args_dict_to_list(args_dict: dict) -> list:
    arg_list = []
    for key, value in args_dict.items():
        formatted_key = key.replace('_', '-')
        _add_argument_to_list(arg_list, formatted_key, value)
    return arg_list


def resolve_with_retry(hostname, max_attempts=5, delay=1):
    for i in range(max_attempts):
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            if i < max_attempts - 1:
                time.sleep(delay)
    return None
