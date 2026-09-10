from __future__ import annotations

import logging
import threading
import winsound
from typing import Iterable

import pygetwindow as gw
import pyttsx3
from pynput import keyboard, mouse

LOGGER = logging.getLogger(__name__)


class WindowsActiveWindowProvider:
    def __init__(self, max_title_length: int = 160) -> None:
        self._max_title_length = max_title_length

    def title(self) -> str:
        try:
            window = gw.getActiveWindow()
            if window is None:
                return "UNKNOWN"
            title = (window.title or "").strip()
            return title[: self._max_title_length] or "UNTITLED"
        except Exception:
            LOGGER.exception("Active-window lookup failed")
            return "UNKNOWN"


class PynputActivityTracker:
    """Track activity timestamps only; never inspect or persist event contents."""

    def __init__(self, clock) -> None:
        self._clock = clock
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._lock = threading.Lock()
        self._last_activity = self._now()

    def _now(self) -> float:
        if hasattr(self._clock, "monotonic"):
            return float(self._clock.monotonic())
        return float(self._clock())

    @property
    def last_activity(self) -> float:
        with self._lock:
            return self._last_activity

    def _touch(self, *_args, **_kwargs) -> None:
        now = self._now()
        if now - self._last_activity < 0.25:
            return
        with self._lock:
            self._last_activity = now

    def start(self) -> None:
        if self._keyboard_listener or self._mouse_listener:
            return
        try:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._touch,
                on_release=self._touch,
            )
            self._keyboard_listener.start()
        except Exception:
            LOGGER.exception("Failed to start keyboard listener")
            self._keyboard_listener = None

        try:
            self._mouse_listener = mouse.Listener(
                on_move=self._touch,
                on_click=self._touch,
                on_scroll=self._touch,
            )
            self._mouse_listener.start()
        except Exception:
            LOGGER.exception("Failed to start mouse listener")
            self._mouse_listener = None

    def stop(self) -> None:
        for listener in (self._keyboard_listener, self._mouse_listener):
            if listener:
                try:
                    listener.stop()
                    if threading.current_thread() != listener:
                        listener.join(timeout=1.0)
                except Exception:
                    LOGGER.exception("Error stopping input listener")
        self._keyboard_listener = None
        self._mouse_listener = None


class PynputEmergencyHotkey:
    def __init__(self, keys: Iterable[str], on_trigger) -> None:
        normalized = {key.lower() for key in keys}
        if normalized != {"ctrl", "shift", "f12"}:
            raise ValueError("This implementation intentionally exposes only Ctrl+Shift+F12")
        self._on_trigger = on_trigger
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        if self._listener:
            return
        try:
            self._listener = keyboard.GlobalHotKeys(
                {"<ctrl>+<shift>+<f12>": self._on_trigger}
            )
            self._listener.start()
        except Exception:
            LOGGER.exception("Failed to register emergency hotkey listener")
            self._listener = None

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
                if threading.current_thread() != self._listener:
                    self._listener.join(timeout=1.0)
            except Exception:
                LOGGER.exception("Error stopping emergency hotkey listener")
            self._listener = None


class WindowsEnforcer:
    def __init__(
        self,
        enable_tts: bool,
        enable_alarm: bool,
        tts_rate: int,
        tts_volume: float,
        alarm_frequency_hz: int,
        alarm_duration_ms: int,
        alarm_repetitions: int,
    ) -> None:
        self._enable_tts = enable_tts
        self._enable_alarm = enable_alarm
        self._tts_rate = tts_rate
        self._tts_volume = max(0.0, min(1.0, tts_volume))
        self._alarm_frequency_hz = alarm_frequency_hz
        self._alarm_duration_ms = alarm_duration_ms
        self._alarm_repetitions = alarm_repetitions
        self._tts = None
        if self._enable_tts:
            try:
                self._tts = pyttsx3.init()
                self._tts.setProperty("rate", self._tts_rate)
                self._tts.setProperty("volume", self._tts_volume)
            except Exception:
                LOGGER.exception("TTS initialization failed; continuing without TTS")
                self._tts = None

    def enforce(self, category: str, message: str) -> None:
        LOGGER.warning("ENFORCEMENT category=%s message=%r", category, message)
        if self._enable_alarm and category != "completion":
            self._alarm()
        if self._tts:
            self._speak(message)

    def _speak(self, message: str) -> None:
        if not self._tts:
            return
        try:
            self._tts.say(message)
            self._tts.runAndWait()
        except Exception:
            LOGGER.exception("TTS playback failed")
            try:
                self._tts.stop()
            except Exception:
                pass

    def _alarm(self) -> None:
        try:
            for _ in range(max(1, self._alarm_repetitions)):
                winsound.Beep(self._alarm_frequency_hz, self._alarm_duration_ms)
        except Exception:
            LOGGER.exception("Alarm playback failed")
