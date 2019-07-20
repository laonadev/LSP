from .types import ClientConfig, LanguageConfig, ClientStates, Settings
from .sessions import create_session, Session
from .protocol import Request, Notification
from .logging import debug

import unittest
import unittest.mock
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional and Session
except ImportError:
    pass


completion_provider = {
    'triggerCharacters': ['.'],
    'resolveProvider': False
}


class MockClient():
    def __init__(self, async_response=None) -> None:
        self.responses = {
            'initialize': {"capabilities": dict(testing=True, hoverProvider=True,
                                                completionProvider=completion_provider, textDocumentSync=True)},
        }  # type: dict
        self._notifications = []  # type: List[Notification]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._async_response_callback = async_response

    def send_request(self, request: Request, on_success: 'Callable', on_error: 'Callable' = None) -> None:
        response = self.responses.get(request.method)
        debug("TEST: responding to", request.method, "with", response)
        if self._async_response_callback:
            self._async_response_callback(lambda: on_success(response))
        else:
            on_success(response)

    def send_notification(self, notification: Notification) -> None:
        self._notifications.append(notification)

    def on_notification(self, name, handler: 'Callable') -> None:
        self._notification_handlers[name] = handler

    def on_request(self, name, handler: 'Callable') -> None:
        self._request_handlers[name] = handler

    def set_error_display_handler(self, handler: 'Callable') -> None:
        pass

    def set_crash_handler(self, handler: 'Callable') -> None:
        pass

    def exit(self) -> None:
        pass


test_language = LanguageConfig("test", ["source.test"], ["Plain Text"])
test_config = ClientConfig("test", [], None, languages=[test_language])


class SessionTest(unittest.TestCase):

    def assert_if_none(self, session) -> 'Session':
        self.assertIsNotNone(session)
        return session

    def setUp(self) -> None:
        self.project_path = "/"
        self.created_callback = unittest.mock.Mock()
        self.ended_callback = unittest.mock.Mock()
        self.session = self.assert_if_none(
            create_session(test_config, self.project_path, dict(), Settings(),
                           bootstrap_client=MockClient(),
                           on_created=self.created_callback,
                           on_ended=self.ended_callback))
        self.assertEqual(self.session.state, ClientStates.READY)
        self.assertIsNotNone(self.session.client)
        self.assertEqual(self.session.project_path, self.project_path)
        self.assertTrue(self.session.has_capability("testing"))

    def test_can_get_started_session(self):
        self.created_callback.assert_called_once()

    def test_can_shutdown_session(self):
        self.created_callback.assert_called_once()
        self.session.end()
        self.assertEqual(self.session.state, ClientStates.STOPPING)
        self.assertEqual(self.session.project_path, self.project_path)
        self.assertIsNone(self.session.client)
        self.assertFalse(self.session.has_capability("testing"))
        self.assertIsNone(self.session.get_capability("testing"))
        self.ended_callback.assert_called_once()

    def test_has_active_handlers_for_simple_messages(self):
        self.created_callback.assert_called_once()
        self.assertIn('window/logMessage', self.session.client._notification_handlers)
        self.assertIn('window/showMessage', self.session.client._notification_handlers)
        self.assertIn('window/showMessageRequest', self.session.client._request_handlers)
