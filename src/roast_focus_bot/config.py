from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

KNOWN_CONFIG_KEYS = {
    "focus_duration_seconds",
    "distraction_threshold_seconds",
    "inactivity_threshold_seconds",
    "cooldown_seconds",
    "poll_interval_seconds",
    "window_title_max_length",
    "enable_tts",
    "enable_alarm",
    "tts_rate",
    "tts_volume",
    "alarm_frequency_hz",
    "alarm_duration_ms",
    "alarm_repetitions",
    "emergency_hotkey",
    "distraction_keywords",
    "ignored_keywords",
    "roasts",
}


@dataclass(frozen=True)
class BotConfig:
    focus_duration_seconds: float = 2700
    distraction_threshold_seconds: float = 60
    inactivity_threshold_seconds: float = 180
    cooldown_seconds: float = 120
    poll_interval_seconds: float = 1.0
    window_title_max_length: int = 160
    enable_tts: bool = True
    enable_alarm: bool = True
    tts_rate: int = 185
    tts_volume: float = 1.0
    alarm_frequency_hz: int = 1100
    alarm_duration_ms: int = 550
    alarm_repetitions: int = 3
    emergency_hotkey: tuple[str, ...] = ("ctrl", "shift", "f12")
    distraction_keywords: tuple[str, ...] = field(default_factory=tuple)
    ignored_keywords: tuple[str, ...] = field(default_factory=tuple)
    roasts: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def validate(self) -> None:
        if self.focus_duration_seconds <= 0:
            raise ValueError("focus_duration_seconds must be positive")
        if self.distraction_threshold_seconds <= 0:
            raise ValueError("distraction_threshold_seconds must be positive")
        if self.inactivity_threshold_seconds <= 0:
            raise ValueError("inactivity_threshold_seconds must be positive")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if self.window_title_max_length <= 0:
            raise ValueError("window_title_max_length must be positive")
        if self.tts_rate <= 0:
            raise ValueError("tts_rate must be positive")
        if not (0.0 <= self.tts_volume <= 1.0):
            raise ValueError("tts_volume must be between 0.0 and 1.0")
        if not (37 <= self.alarm_frequency_hz <= 32767):
            raise ValueError("alarm_frequency_hz must be between 37 and 32767")
        if self.alarm_duration_ms <= 0:
            raise ValueError("alarm_duration_ms must be positive")
        if self.alarm_repetitions <= 0:
            raise ValueError("alarm_repetitions must be positive")
        if not self.emergency_hotkey:
            raise ValueError("emergency_hotkey must not be empty")

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "BotConfig":
        if not isinstance(raw, dict):
            raise ValueError("Configuration mapping must be a dict")

        unknown_keys = set(raw.keys()) - KNOWN_CONFIG_KEYS
        if unknown_keys:
            LOGGER.warning("Unknown configuration fields ignored: %s", sorted(unknown_keys))

        raw_roasts = raw.get("roasts", {})
        if not isinstance(raw_roasts, dict):
            raise ValueError("roasts must be a mapping of category to list of strings")

        roasts: dict[str, tuple[str, ...]] = {}
        for key, value in raw_roasts.items():
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"roasts[{key!r}] must be a list of strings")
            roasts[str(key)] = tuple(str(x) for x in value)

        distraction_keywords = tuple(
            s for x in raw.get("distraction_keywords", [])
            if (s := str(x).strip().lower())
        )
        ignored_keywords = tuple(
            s for x in raw.get("ignored_keywords", [])
            if (s := str(x).strip().lower())
        )

        try:
            config = cls(
                focus_duration_seconds=float(raw.get("focus_duration_seconds", 2700)),
                distraction_threshold_seconds=float(raw.get("distraction_threshold_seconds", 60)),
                inactivity_threshold_seconds=float(raw.get("inactivity_threshold_seconds", 180)),
                cooldown_seconds=float(raw.get("cooldown_seconds", 120)),
                poll_interval_seconds=float(raw.get("poll_interval_seconds", 1.0)),
                window_title_max_length=int(raw.get("window_title_max_length", 160)),
                enable_tts=bool(raw.get("enable_tts", True)),
                enable_alarm=bool(raw.get("enable_alarm", True)),
                tts_rate=int(raw.get("tts_rate", 185)),
                tts_volume=float(raw.get("tts_volume", 1.0)),
                alarm_frequency_hz=int(raw.get("alarm_frequency_hz", 1100)),
                alarm_duration_ms=int(raw.get("alarm_duration_ms", 550)),
                alarm_repetitions=int(raw.get("alarm_repetitions", 3)),
                emergency_hotkey=tuple(str(x) for x in raw.get("emergency_hotkey", ["ctrl", "shift", "f12"])),
                distraction_keywords=distraction_keywords,
                ignored_keywords=ignored_keywords,
                roasts=roasts,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid configuration parameter type: {exc}") from exc

        config.validate()
        return config

    @classmethod
    def load(cls, path: str | Path) -> "BotConfig":
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        if file_path.is_dir():
            raise ValueError(f"Configuration path is a directory, not a file: '{file_path}'")
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON in configuration file '{file_path}': {exc}") from exc
        except OSError as exc:
            raise ValueError(f"Cannot read configuration file '{file_path}': {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Configuration root must be a JSON object")
        return cls.from_mapping(payload)
