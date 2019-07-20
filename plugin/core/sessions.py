from .logging import debug, server_log
from .process import start_server
from .protocol import Request, Response, completion_item_kinds, symbol_kinds
from .rpc import Client, attach_stdio_client
from .transports import start_tcp_transport
from .types import ClientConfig, ClientStates, Settings
from .url import filename_to_uri

import os

try:
    from typing import Callable, Dict, Any, Optional
    assert Callable and Dict and Any and Optional
except ImportError:
    pass

try:
    import sublime
except ImportError:
    from . import test_sublime as sublime  # type: ignore


def create_session(config: ClientConfig, project_path: str, env: dict, settings: Settings,
                   on_created=None, on_ended: 'Optional[Callable[[str], None]]' = None,
                   bootstrap_client=None) -> 'Optional[Session]':
    session = None
    if config.binary_args:

        process = start_server(config.binary_args, project_path, env, settings.log_stderr)
        if process:
            if config.tcp_port:
                transport = start_tcp_transport(config.tcp_port, config.tcp_host)
                if transport:
                    session = Session(config, project_path, Client(transport, settings), on_created, on_ended)
                else:
                    # try to terminate the process
                    try:
                        process.terminate()
                    except Exception:
                        pass
            else:
                client = attach_stdio_client(process, settings)
                session = Session(config, project_path, client, on_created, on_ended)
    else:
        if config.tcp_port:
            transport = start_tcp_transport(config.tcp_port)

            session = Session(config, project_path, Client(transport, settings),
                              on_created, on_ended)
        elif bootstrap_client:
            session = Session(config, project_path, bootstrap_client,
                              on_created, on_ended)
        else:
            debug("No way to start session")

    return session


def get_initialize_params(project_path: str, config: ClientConfig):
    initializeParams = {
        "processId": os.getpid(),
        "rootUri": filename_to_uri(project_path),
        "rootPath": project_path,
        "capabilities": {
            "textDocument": {
                "synchronization": {
                    "didSave": True
                },
                "hover": {
                    "contentFormat": ["markdown", "plaintext"]
                },
                "completion": {
                    "completionItem": {
                        "snippetSupport": True
                    },
                    "completionItemKind": {
                        "valueSet": completion_item_kinds
                    }
                },
                "signatureHelp": {
                    "signatureInformation": {
                        "documentationFormat": ["markdown", "plaintext"],
                        "parameterInformation": {
                            "labelOffsetSupport": True
                        }
                    }
                },
                "references": {},
                "documentHighlight": {},
                "documentSymbol": {
                    "symbolKind": {
                        "valueSet": symbol_kinds
                    }
                },
                "formatting": {},
                "rangeFormatting": {},
                "definition": {},
                "codeAction": {
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": []
                        }
                    }
                },
                "rename": {}
            },
            "workspace": {
                "applyEdit": True,
                "didChangeConfiguration": {},
                "executeCommand": {},
                "symbol": {
                    "symbolKind": {
                        "valueSet": symbol_kinds
                    }
                }
            }
        }
    }
    if config.init_options:
        initializeParams['initializationOptions'] = config.init_options

    return initializeParams


def extract_message(response: 'Optional[Dict[str, Any]]') -> str:
    return response.get('message', '???') if response else '???'


class Session(object):
    def __init__(self, config: ClientConfig, project_path, client: Client,
                 on_created=None, on_ended: 'Optional[Callable[[str], None]]' = None) -> None:
        self.config = config
        self.project_path = project_path
        self.state = ClientStates.STARTING
        self._on_created = on_created
        self._on_ended = on_ended
        self.capabilities = dict()  # type: Dict[str, Any]
        self.client = client
        self.__setup_special_notification_and_request_handlers()
        self.__initialize()

    def has_capability(self, capability) -> bool:
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability) -> 'Optional[Dict[str, Any]]':
        return self.capabilities.get(capability)

    def end(self):
        self.state = ClientStates.STOPPING
        self.client.send_request(
            Request.shutdown(),
            lambda result: self.__handle_shutdown_result(),
            lambda: self.__handle_shutdown_result())

    def __initialize(self) -> None:
        params = get_initialize_params(self.project_path, self.config)
        self.client.send_request(Request.initialize(params), self.__handle_initialize_result)

    def __setup_special_notification_and_request_handlers(self) -> None:
        self.client.on_notification('window/logMessage', self.__handle_log_message)
        self.client.on_notification('window/showMessage', self.__handle_show_message)
        self.client.on_request('window/showMessageRequest', self.__handle_show_message_request)

    def __handle_log_message(self, response: 'Optional[Dict[str, Any]]') -> None:
        server_log(self.config.name, extract_message(response))

    def __handle_show_message(self, response: 'Optional[Dict[str, Any]]') -> None:
        sublime.message_dialog(extract_message(response))

    def __handle_show_message_request(self, response: 'Dict[str, Any]', request_id: int) -> None:
        actions = response.get("actions", [])
        if not actions:
            return
        titles = list(action.get("title") for action in actions)

        def send_user_choice(index: int) -> None:
            if index == -1:
                return
            result = {"title": titles[index]}
            response = Response(request_id, result)
            self.client.send_response(response)

        sublime.active_window().show_quick_panel(titles, send_user_choice)

    def __handle_initialize_result(self, result):
        self.state = ClientStates.READY
        self.capabilities = result.get('capabilities', dict())
        if self._on_created:
            self._on_created(self)

    def __handle_shutdown_result(self):
        self.client.exit()
        self.client = None
        self.capabilities = dict()
        if self._on_ended:
            self._on_ended(self.config.name)
