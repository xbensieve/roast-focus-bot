from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from .config import BotConfig
from .engine import FocusController

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def _default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir_cfg = Path(sys.executable).resolve().parent / "default.json"
        if exe_dir_cfg.exists():
            return exe_dir_cfg
        cwd_cfg = Path.cwd() / "default.json"
        if cwd_cfg.exists():
            return cwd_cfg
        return exe_dir_cfg

    repo_cfg = Path(__file__).resolve().parents[2] / "config" / "default.json"
    if repo_cfg.exists():
        return repo_cfg

    cwd_cfg = Path.cwd() / "config" / "default.json"
    if cwd_cfg.exists():
        return cwd_cfg

    cwd_direct = Path.cwd() / "default.json"
    if cwd_direct.exists():
        return cwd_direct

    return repo_cfg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Roast & Chastise Focus Bot")
    parser.add_argument("--config", default=str(_default_config_path()))
    parser.add_argument("--dry-run", action="store_true", help="Validate config/dependencies without starting listeners")
    parser.add_argument("--self-test", action="store_true", help="Validate runtime imports and config, then exit")
    return parser


def _attach_console_if_frozen() -> None:
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        try:
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _attach_console_if_frozen()
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    try:
        config = BotConfig.load(args.config)
    except (FileNotFoundError, ValueError) as exc:
        logging.error("Configuration error: %s", exc)
        return 1

    logging.info("Loaded configuration: focus_duration=%ss, distraction_threshold=%ss",
                 config.focus_duration_seconds, config.distraction_threshold_seconds)

    if args.dry_run:
        logging.info("Dry-run validation successful")
        return 0

    if sys.platform != "win32":
        logging.error("This application is Windows-only")
        return 2

    from .platform_windows import (
        PynputActivityTracker,
        PynputEmergencyHotkey,
        WindowsActiveWindowProvider,
        WindowsEnforcer,
    )

    if args.self_test:
        provider = WindowsActiveWindowProvider(config.window_title_max_length)
        current_title = provider.title()
        logging.info("Self-test window lookup: current_title=%r", current_title)
        enforcer = WindowsEnforcer(
            enable_tts=config.enable_tts,
            enable_alarm=False,
            tts_rate=config.tts_rate,
            tts_volume=config.tts_volume,
            alarm_frequency_hz=config.alarm_frequency_hz,
            alarm_duration_ms=config.alarm_duration_ms,
            alarm_repetitions=1,
        )
        logging.info("Self-test completed successfully")
        return 0

    stop_event = threading.Event()
    provider = WindowsActiveWindowProvider(config.window_title_max_length)
    tracker = PynputActivityTracker(__import__("time"))
    enforcer = WindowsEnforcer(
        enable_tts=config.enable_tts,
        enable_alarm=config.enable_alarm,
        tts_rate=config.tts_rate,
        tts_volume=config.tts_volume,
        alarm_frequency_hz=config.alarm_frequency_hz,
        alarm_duration_ms=config.alarm_duration_ms,
        alarm_repetitions=config.alarm_repetitions,
    )
    controller = FocusController(config, provider, tracker, enforcer, stop_event)
    hotkey = PynputEmergencyHotkey(config.emergency_hotkey, stop_event.set)

    try:
        hotkey.start()
        controller.run()
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    finally:
        hotkey.stop()
        stop_event.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
