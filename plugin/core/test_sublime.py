# NOTE: This module is used entirely for tests, so there is no need to do the "try catch ImportError" workaround.
from typing import Dict, List, Optional, Tuple, Any
from .types import ViewLike, WindowLike
import os


DIALOG_CANCEL = 0
DIALOG_YES = 1
DIALOG_NO = 2


class MockSublimeSettings:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class MockView(ViewLike):
    def __init__(self, file_name):
        self._file_name = file_name
        self._window = None
        self._settings = MockSublimeSettings({"syntax": "Plain Text"})
        self._status = dict()  # type: Dict[str, str]
        self._text = "asdf"

    def file_name(self):
        return self._file_name

    def set_window(self, window):
        self._window = window

    def set_status(self, key, status):
        self._status[key] = status

    def window(self):
        return self._window

    def settings(self):
        return self._settings

    def substr(self, region):
        return self._text

    def size(self):
        return len(self._text)

    def sel(self):
        return [Region(1, 1)]

    def score_selector(self, region, scope: str) -> int:
        return 1

    def buffer_id(self):
        return 1


class MockWindow(WindowLike):
    def __init__(self, files_in_groups: 'List[List[ViewLike]]' = []) -> None:
        self._files_in_groups = files_in_groups
        self._is_valid = True
        self._folders = [os.path.dirname(__file__)]
        self._default_view = MockView(None)
        self._project_data: Optional[Dict[str, Any]] = None
        self.commands: List[Tuple[str, Dict[str, Any]]] = []

    def id(self):
        return 0

    def folders(self):
        return self._folders

    def set_folders(self, folders):
        self._folders = folders

    def num_groups(self):
        return len(self._files_in_groups)

    def active_group(self):
        return 0

    def project_data(self) -> Optional[dict]:
        return self._project_data

    def set_project_data(self, data: Optional[dict]):
        self._project_data = data

    def active_view(self) -> Optional[ViewLike]:
        return self.active_view_in_group(0)

    def close(self):
        self._is_valid = False

    def is_valid(self):
        return self._is_valid

    def extract_variables(self):
        return {
            "project_path": os.path.dirname(__file__)
        }

    def active_view_in_group(self, group):
        if group < len(self._files_in_groups):
            files = self._files_in_groups[group]
            if len(files) > 0:
                return files[0]
            else:
                return self._default_view

    def add_view_in_group(self, group, view):
        self._files_in_groups[group].append(view)

    def status_message(self, msg: str) -> None:
        pass

    def views(self):
        views = []
        for views_in_group in self._files_in_groups:
            if len(views_in_group) < 1:
                views.append(self._default_view)
            else:
                for view in views_in_group:
                    views.append(view)
        return views

    def run_command(self, command_name: str, command_args: 'Dict[str, Any]') -> None:
        self.commands.append((command_name, command_args))


def active_window():
    view = MockView(__file__)
    return MockWindow([[view]])


def message_dialog(msg: str) -> None:
    pass


def ok_cancel_dialog(msg: str, ok_title: str) -> bool:
    return True


def yes_no_cancel_dialog(msg, yes_title: str, no_title: str) -> int:
    return DIALOG_YES


_callback = None


def set_timeout_async(callback, duration):
    global _callback
    _callback = callback


def _run_timeout():
    global _callback
    if _callback:
        callback = _callback
        _callback = None
        callback()


class Region:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def begin(self):
        return self.a
