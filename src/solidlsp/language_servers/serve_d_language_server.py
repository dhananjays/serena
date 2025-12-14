"""
Provides D specific instantiation of the LanguageServer class using serve-d.
"""

import logging
import os
import pathlib
import subprocess
import threading
from typing import cast

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)


class ServeD(SolidLanguageServer):
    """
    Provides D specific instantiation of the LanguageServer class using serve-d.
    """

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        # For D projects, we should ignore:
        # - .dub: DUB package manager cache
        # - node_modules: if the project has JavaScript components
        # - dist/build: common output directories
        return super().is_ignored_dirname(dirname) or dirname in [".dub", "node_modules", "dist", "build"]

    @staticmethod
    def _determine_log_level(line: str) -> int:
        """Classify serve-d stderr output to avoid false-positive errors."""
        line_lower = line.lower()

        # Known informational/warning messages from serve-d that aren't critical errors
        if any(
            [
                "workspace-d setup" in line_lower,
                "dub upgrade" in line_lower,
                "scanning workspace" in line_lower,
            ]
        ):
            return logging.DEBUG

        return SolidLanguageServer._determine_log_level(line)

    @staticmethod
    def _get_dmd_version() -> str | None:
        """Get the installed DMD version or None if not found."""
        try:
            result = subprocess.run(["dmd", "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def _get_serve_d_version() -> str | None:
        """Get the installed serve-d version or None if not found."""
        try:
            result = subprocess.run(["serve-d", "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                # serve-d outputs version to stderr
                output = result.stderr.strip() if result.stderr else result.stdout.strip()
                return output
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def _get_dub_version() -> str | None:
        """Get the installed DUB version or None if not found."""
        try:
            result = subprocess.run(["dub", "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def _setup_runtime_dependency() -> bool:
        """
        Check if required D runtime dependencies are available.
        Raises RuntimeError if critical dependencies (D compiler, serve-d) are missing.
        Logs warnings for optional dependencies (DUB, dfmt, dscanner).
        """
        # Check for D compiler (DMD, LDC, or GDC)
        dmd_version = ServeD._get_dmd_version()
        if not dmd_version:
            # Try ldc2 as alternative
            try:
                result = subprocess.run(["ldc2", "--version"], capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    raise RuntimeError(
                        "No D compiler found. Please install DMD, LDC, or GDC.\n"
                        "Visit https://dlang.org/download.html for installation instructions."
                    )
            except FileNotFoundError:
                raise RuntimeError(
                    "No D compiler found. Please install DMD, LDC, or GDC.\n"
                    "Visit https://dlang.org/download.html for installation instructions."
                )

        # Check for serve-d
        serve_d_version = ServeD._get_serve_d_version()
        if not serve_d_version:
            raise RuntimeError(
                "serve-d is not installed or not in PATH.\n"
                "Please install serve-d from https://github.com/Pure-D/serve-d/releases\n"
                "or via your package manager and ensure it is added to your PATH."
            )

        # Check for DUB (optional but recommended for package management)
        dub_version = ServeD._get_dub_version()

        log.info(f"Found D compiler: {dmd_version or 'LDC/GDC'}")
        log.info(f"Found serve-d: {serve_d_version}")

        if dub_version:
            log.info(f"Found DUB: {dub_version}")
        else:
            log.warning(
                "DUB not found. serve-d will work with reduced functionality:\n"
                "  - External dependency resolution unavailable\n"
                "  - Build configuration switching disabled\n"
                "  - Multi-package workspace support limited\n"
                "Core features (completion, diagnostics, formatting, linting) will still work.\n"
                "For full functionality, install DUB from https://dub.pm/"
            )

        # Check for optional tools
        try:
            result = subprocess.run(["dfmt", "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                log.info(f"Found dfmt: {result.stdout.strip()}")
            else:
                log.warning("dfmt not found. Code formatting will not be available.")
        except FileNotFoundError:
            log.warning("dfmt not found. Code formatting will not be available.")

        try:
            result = subprocess.run(["dscanner", "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                log.info(f"Found dscanner: {result.stdout.strip()}")
            else:
                log.warning("dscanner not found. Enhanced linting will not be available.")
        except FileNotFoundError:
            log.warning("dscanner not found. Enhanced linting will not be available.")

        return True

    def __init__(self, config: LanguageServerConfig, repository_root_path: str, solidlsp_settings: SolidLSPSettings):
        self._setup_runtime_dependency()

        super().__init__(config, repository_root_path, ProcessLaunchInfo(cmd="serve-d", cwd=repository_root_path), "d", solidlsp_settings)
        self.server_ready = threading.Event()

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the serve-d Language Server.
        """
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "clientInfo": {"name": "Serena", "version": "1.0.0"},
            "locale": "en",
            "capabilities": {
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {
                        "documentChanges": True,
                        "resourceOperations": ["create", "rename", "delete"],
                        "failureHandling": "textOnlyTransactional",
                    },
                    "configuration": True,
                    "didChangeWatchedFiles": {"dynamicRegistration": True},
                    "symbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "executeCommand": {"dynamicRegistration": True},
                    "workspaceFolders": True,
                },
                "textDocument": {
                    "publishDiagnostics": {
                        "relatedInformation": True,
                        "tagSupport": {"valueSet": [1, 2]},
                        "versionSupport": False,
                    },
                    "synchronization": {
                        "dynamicRegistration": True,
                        "willSave": True,
                        "willSaveWaitUntil": True,
                        "didSave": True,
                    },
                    "completion": {
                        "dynamicRegistration": True,
                        "contextSupport": True,
                        "completionItem": {
                            "snippetSupport": True,
                            "commitCharactersSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "deprecatedSupport": True,
                            "preselectSupport": True,
                        },
                        "completionItemKind": {"valueSet": list(range(1, 26))},
                    },
                    "hover": {
                        "dynamicRegistration": True,
                        "contentFormat": ["markdown", "plaintext"],
                    },
                    "signatureHelp": {
                        "dynamicRegistration": True,
                        "signatureInformation": {
                            "documentationFormat": ["markdown", "plaintext"],
                            "parameterInformation": {"labelOffsetSupport": True},
                        },
                    },
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "references": {"dynamicRegistration": True},
                    "documentHighlight": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                        "hierarchicalDocumentSymbolSupport": True,
                    },
                    "codeAction": {
                        "dynamicRegistration": True,
                        "codeActionLiteralSupport": {
                            "codeActionKind": {
                                "valueSet": [
                                    "",
                                    "quickfix",
                                    "refactor",
                                    "refactor.extract",
                                    "refactor.inline",
                                    "refactor.rewrite",
                                    "source",
                                    "source.organizeImports",
                                ]
                            }
                        },
                    },
                    "formatting": {"dynamicRegistration": True},
                    "rangeFormatting": {"dynamicRegistration": True},
                    "rename": {"dynamicRegistration": True, "prepareSupport": True},
                    "documentLink": {"dynamicRegistration": True},
                    "typeDefinition": {"dynamicRegistration": True, "linkSupport": True},
                    "implementation": {"dynamicRegistration": True, "linkSupport": True},
                },
                "window": {
                    "showMessage": {"messageActionItem": {"additionalPropertiesSupport": True}},
                    "showDocument": {"support": True},
                    "workDoneProgress": True,
                },
            },
            "initializationOptions": {
                # serve-d specific initialization options
                "d": {
                    "enableFormatting": True,
                    "enableLinting": True,
                    "enableAutoComplete": True,
                }
            },
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
        }
        return cast(InitializeParams, initialize_params)

    def _start_server(self) -> None:
        """Start serve-d server process"""

        def register_capability_handler(params: dict) -> None:
            return

        def window_log_message(msg: dict) -> None:
            log.info(f"LSP: window/logMessage: {msg}")

        def do_nothing(params: dict) -> None:
            return

        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        log.info("Starting serve-d server process")
        self.server.start()
        initialize_params = self._get_initialize_params(self.repository_root_path)

        log.info("Sending initialize request from LSP client to LSP server and awaiting response")
        init_response = self.server.send.initialize(initialize_params)

        # Verify server capabilities
        assert "textDocumentSync" in init_response["capabilities"]
        assert "completionProvider" in init_response["capabilities"]

        self.server.notify.initialized({})
        self.completions_available.set()

        # serve-d is typically ready after initialization
        self.server_ready.set()
        self.server_ready.wait()
