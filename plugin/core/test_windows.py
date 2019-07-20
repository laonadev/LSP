from typing import Callable, List, Set, Dict
import tempfile
import unittest

from . import test_sublime as test_sublime
from .diagnostics import WindowDiagnostics
from .events import global_events
from .sessions import create_session, Session
from .test_rpc import MockSettings
from .test_session import MockClient, test_config, test_language
from .test_sublime import MockWindow, MockView
from .types import ClientConfig, LanguageConfig
from .windows import WindowManager, WindowRegistry, ViewLike


class MockHandlerDispatcher(object):
    def __init__(self, can_start: bool = True) -> None:
        self._can_start = can_start
        self._initialized: Set[str] = set()

    def on_start(self, config_name: str, window) -> bool:
        return self._can_start

    def on_initialized(self, config_name: str, window, client):
        self._initialized.add(config_name)


class TestGlobalConfigs(object):
    def for_window(self, window):
        return MockConfigs()


class MockConfigs(object):
    def __init__(self):
        self.all = [test_config]

    def is_supported(self, view):
        return self.scope_config(view) is not None

    def scope_config(self, view, point=None):
        if view.file_name() is None:
            return None
        else:
            return test_config

    def syntax_configs(self, view):
        if view.settings().get("syntax") == "Plain Text":
            return [test_config]
        else:
            return []

    def syntax_supported(self, view: ViewLike) -> bool:
        return view.settings().get("syntax") == "Plain Text"

    def syntax_config_languages(self, view: ViewLike) -> Dict[str, LanguageConfig]:
        if self.syntax_supported(view):
            return {
                "test": test_language
            }
        else:
            return {}

    def update(self, configs: List[ClientConfig]) -> None:
        pass

    def disable(self, config_name: str) -> None:
        pass


class MockDocuments(object):
    def __init__(self):
        self._documents: List[str] = []
        self._sessions: Dict[str, Session] = {}

    def add_session(self, session: Session) -> None:
        self._sessions[session.config.name] = session

    def remove_session(self, config_name: str) -> None:
        del self._sessions[config_name]

    def handle_view_opened(self, view: ViewLike):
        file_name = view.file_name()
        if file_name:
            self._documents.append(file_name)

    def reset(self):
        self._documents = []


class TestDocumentHandlerFactory(object):
    def for_window(self, window, configs):
        return MockDocuments()


def mock_start_session(window, project_path, config, on_created: Callable, on_ended: Callable):
    return create_session(test_config, project_path, dict(), MockSettings(),
                          bootstrap_client=MockClient(),
                          on_created=on_created,
                          on_ended=on_ended)


class WindowRegistryTests(unittest.TestCase):

    def test_can_get_window_state(self):
        windows = WindowRegistry(TestGlobalConfigs(), TestDocumentHandlerFactory(),
                                 mock_start_session,
                                 test_sublime, MockHandlerDispatcher())
        test_window = MockWindow()
        wm = windows.lookup(test_window)
        self.assertIsNotNone(wm)

    def test_removes_window_state(self):
        global_events.reset()
        test_window = MockWindow([[MockView(__file__)]])
        windows = WindowRegistry(TestGlobalConfigs(), TestDocumentHandlerFactory(),
                                 mock_start_session,
                                 test_sublime, MockHandlerDispatcher())
        wm = windows.lookup(test_window)
        wm.start_active_views()

        self.assertIsNotNone(wm)

        # closing views triggers window unload detection
        test_window.close()
        global_events.publish("view.on_close", MockView(__file__))
        test_sublime._run_timeout()

        self.assertEqual(len(windows._windows), 0)


class WindowManagerTests(unittest.TestCase):

    def test_can_start_active_views(self):
        docs = MockDocuments()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))
        self.assertListEqual(docs._documents, [__file__])

    def test_can_open_supported_view(self):
        docs = MockDocuments()
        window = MockWindow([[]])
        wm = WindowManager(window, MockConfigs(), docs, WindowDiagnostics(), mock_start_session, test_sublime,
                           MockHandlerDispatcher())

        wm.start_active_views()
        self.assertIsNone(wm.get_session(test_config.name))
        self.assertListEqual(docs._documents, [])

        # session must be started (todo: verify session is ready)
        view = MockView(__file__)

        wm.activate_view(view)
        self.assertIsNotNone(wm.get_session(test_config.name))
        self.assertEqual(len(docs._sessions), 1)

    def test_can_restart_sessions(self):
        docs = MockDocuments()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm.restart_sessions()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_ends_sessions_when_closed(self):
        global_events.reset()
        docs = MockDocuments()
        test_window = MockWindow([[MockView(__file__)]])
        wm = WindowManager(test_window, MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # closing views triggers window unload detection
        test_window.close()
        global_events.publish("view.on_close", MockView(__file__))
        test_sublime._run_timeout()
        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

    def test_ends_sessions_when_quick_switching(self):
        global_events.reset()
        docs = MockDocuments()
        test_window = MockWindow([[MockView(__file__)]])
        wm = WindowManager(test_window, MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # change project_path
        new_project_path = tempfile.gettempdir()
        test_window.set_folders([new_project_path])
        # global_events.publish("view.on_close", MockView(__file__))
        another_view = MockView(None)
        another_view.settings().set("syntax", "Unsupported Syntax")
        wm.activate_view(another_view)

        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

        # don't forget to check or we'll keep restarting sessions!
        self.assertEqual(wm._project_path, new_project_path)

    def test_offers_restart_on_crash(self):
        docs = MockDocuments()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_session, test_sublime,
                           MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm._handle_server_crash(test_config)

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_invokes_language_handler(self):
        docs = MockDocuments()
        dispatcher = MockHandlerDispatcher()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_session, test_sublime,
                           dispatcher)
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # client_start_listeners, client_initialization_listeners,
        self.assertTrue(test_config.name in dispatcher._initialized)
