#!/usr/bin/env python3
"""A command line tool for extracting text and images from PDF and
output it to plain text, html, xml or tags.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import babeldoc.assets.assets

from pdf2zh_next.config import ConfigManager
from pdf2zh_next.high_level import do_translate_file_async

__version__ = "2.5.4"

logger = logging.getLogger(__name__)


def _cli_flag_present(*flag_names: str) -> bool:
    args = sys.argv[1:]
    return any(arg in flag_names for arg in args)


def _cli_option_value(option_name: str) -> str | None:
    args = sys.argv[1:]
    for index, arg in enumerate(args):
        if arg == option_name and index + 1 < len(args):
            return args[index + 1]
        prefix = f"{option_name}="
        if arg.startswith(prefix):
            return arg[len(prefix) :]
    return None


def _load_settings_for_gui_after_config_error(
    config_manager: ConfigManager, error: Exception
):
    from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel

    cli_env = config_manager.config_cli_settings or CLIEnvSettingsModel()
    gui_requested = (
        _cli_flag_present("--gui", "--desktop-gui", "--webview-gui")
        or cli_env.basic.gui
        or cli_env.basic.desktop_gui
        or cli_env.basic.webview_gui
    )
    if not gui_requested:
        raise error

    logger.warning(
        "Configuration validation failed before GUI startup; opening GUI so settings can be repaired: %s",
        error,
    )
    cli_env.basic.gui = True
    if _cli_flag_present("--desktop-gui"):
        cli_env.basic.desktop_gui = True
    if _cli_flag_present("--webview-gui"):
        cli_env.basic.webview_gui = True

    server_port = _cli_option_value("--server-port")
    if server_port:
        try:
            cli_env.gui_settings.server_port = int(server_port)
        except ValueError:
            logger.warning("Invalid --server-port value ignored: %s", server_port)
    auth_file = _cli_option_value("--auth-file")
    if auth_file:
        cli_env.gui_settings.auth_file = auth_file
    welcome_page = _cli_option_value("--welcome-page")
    if welcome_page:
        cli_env.gui_settings.welcome_page = welcome_page
    return cli_env.to_settings_model()


def find_all_files_in_directory(directory_path):
    """
    Recursively search all PDF files in the given directory and return their paths as a list.

    :param directory_path: str, the path to the directory to search
    :return: list of PDF file paths
    """
    directory_path = Path(directory_path)
    # Check if the provided path is a directory
    if not directory_path.is_dir():
        raise ValueError(f"The provided path '{directory_path}' is not a directory.")

    file_paths = []

    # Walk through the directory recursively
    for root, _, files in os.walk(directory_path):
        for file in files:
            # Check if the file is a PDF
            if file.lower().endswith(".pdf"):
                # Append the full file path to the list
                file_paths.append(Path(root) / file)

    return file_paths


async def main() -> int:
    from rich.logging import RichHandler

    logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])

    config_manager = ConfigManager()
    try:
        settings = config_manager.initialize_config()
    except Exception as e:
        settings = _load_settings_for_gui_after_config_error(config_manager, e)
    if settings.basic.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # disable httpx, openai, httpcore, http11 logs
    logging.getLogger("httpx").setLevel("CRITICAL")
    logging.getLogger("httpx").propagate = False
    logging.getLogger("openai").setLevel("CRITICAL")
    logging.getLogger("openai").propagate = False
    logging.getLogger("httpcore").setLevel("CRITICAL")
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("http11").setLevel("CRITICAL")
    logging.getLogger("http11").propagate = False

    for v in logging.Logger.manager.loggerDict.values():
        if getattr(v, "name", None) is None:
            continue
        if (
            v.name.startswith("pdfminer")
            or v.name.startswith("peewee")
            or v.name.startswith("httpx")
            or "http11" in v.name
            or "openai" in v.name
            or "pdfminer" in v.name
        ):
            v.disabled = True
            v.propagate = False

    logger.debug(f"settings: {settings}")

    if settings.basic.version:
        print(f"pdf2zh-next version: {__version__}")
        return 0

    logger.info("Warmup babeldoc assets...")
    babeldoc.assets.assets.warmup()

    if settings.basic.gui:
        # Check if webview desktop GUI is requested
        if hasattr(settings.basic, "webview_gui") and settings.basic.webview_gui:
            from pdf2zh_next.webview_gui import setup_webview_gui

            return setup_webview_gui()
        # Check if desktop GUI is requested
        elif hasattr(settings.basic, "desktop_gui") and settings.basic.desktop_gui:
            from pdf2zh_next.desktop_gui import setup_desktop_gui

            setup_desktop_gui()
        else:
            from pdf2zh_next.gui import setup_gui

            setup_gui(
                auth_file=settings.gui_settings.auth_file,
                welcome_page=settings.gui_settings.welcome_page,
                server_port=settings.gui_settings.server_port,
            )
        return 0

    assert len(settings.basic.input_files) >= 1, "At least one input file is required"
    await do_translate_file_async(settings, ignore_error=True)
    return 0


def cli():
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli()
