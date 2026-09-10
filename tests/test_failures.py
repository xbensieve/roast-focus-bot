import sys
from unittest.mock import MagicMock, patch
import pytest

from roast_focus_bot.cli import main
from roast_focus_bot.platform_windows import (
    PynputActivityTracker,
    PynputEmergencyHotkey,
    WindowsActiveWindowProvider,
    WindowsEnforcer,
)


def test_window_provider_exception_returns_unknown():
    provider = WindowsActiveWindowProvider()
    with patch("pygetwindow.getActiveWindow", side_effect=Exception("API failure")):
        assert provider.title() == "UNKNOWN"


def test_window_provider_none_returns_unknown():
    provider = WindowsActiveWindowProvider()
    with patch("pygetwindow.getActiveWindow", return_value=None):
        assert provider.title() == "UNKNOWN"


def test_window_provider_empty_or_whitespace_returns_untitled():
    provider = WindowsActiveWindowProvider()
    fake_window = MagicMock()
    fake_window.title = "   "
    with patch("pygetwindow.getActiveWindow", return_value=fake_window):
        assert provider.title() == "UNTITLED"


def test_window_provider_truncates_long_title():
    provider = WindowsActiveWindowProvider(max_title_length=10)
    fake_window = MagicMock()
    fake_window.title = "0123456789ABCDEF"
    with patch("pygetwindow.getActiveWindow", return_value=fake_window):
        assert provider.title() == "0123456789"


def test_enforcer_tts_failure_does_not_raise():
    with patch("pyttsx3.init", side_effect=Exception("SAPI init failure")):
        enforcer = WindowsEnforcer(
            enable_tts=True,
            enable_alarm=False,
            tts_rate=180,
            tts_volume=1.0,
            alarm_frequency_hz=1000,
            alarm_duration_ms=200,
            alarm_repetitions=1,
        )
        assert enforcer._tts is None
        # Enforce should run without raising
        enforcer.enforce("distraction", "Test message")


def test_enforcer_alarm_failure_does_not_raise():
    with patch("winsound.Beep", side_effect=Exception("Audio hardware error")):
        enforcer = WindowsEnforcer(
            enable_tts=False,
            enable_alarm=True,
            tts_rate=180,
            tts_volume=1.0,
            alarm_frequency_hz=1000,
            alarm_duration_ms=200,
            alarm_repetitions=2,
        )
        enforcer.enforce("distraction", "Test message")


def test_enforcer_completion_suppresses_alarm():
    beep_mock = MagicMock()
    with patch("winsound.Beep", beep_mock):
        enforcer = WindowsEnforcer(
            enable_tts=False,
            enable_alarm=True,
            tts_rate=180,
            tts_volume=1.0,
            alarm_frequency_hz=1000,
            alarm_duration_ms=200,
            alarm_repetitions=1,
        )
        # Category "completion" should not trigger alarm beep
        enforcer.enforce("completion", "Session complete!")
        beep_mock.assert_not_called()

        # Category "distraction" should trigger alarm beep
        enforcer.enforce("distraction", "Back to work!")
        beep_mock.assert_called_once()


def test_hotkey_rejects_invalid_key_combination():
    with pytest.raises(ValueError, match="Ctrl\\+Shift\\+F12"):
        PynputEmergencyHotkey(["ctrl", "alt", "del"], lambda: None)


def test_activity_tracker_clock_compatibility():
    # Test with clock object having .monotonic()
    class ObjClock:
        def __init__(self):
            self._val = 100.0
        def monotonic(self):
            return self._val

    clock_obj = ObjClock()
    tracker_obj = PynputActivityTracker(clock_obj)
    assert tracker_obj.last_activity == 100.0

    # Test with callable clock
    tracker_call = PynputActivityTracker(lambda: 200.0)
    assert tracker_call.last_activity == 200.0


def test_cli_missing_config_returns_1():
    code = main(["--config", "non_existent_file_xyz.json"])
    assert code == 1


def test_cli_dry_run_returns_0():
    code = main(["--dry-run"])
    assert code == 0


def test_cli_non_windows_returns_2():
    with patch("sys.platform", "linux"):
        code = main([])
        assert code == 2


def test_activity_tracker_debounce():
    current_time = 100.0
    def clock():
        return current_time

    tracker = PynputActivityTracker(clock)
    assert tracker.last_activity == 100.0

    # Touch within 0.25s debounce window
    current_time = 100.1
    tracker._touch()
    assert tracker.last_activity == 100.0  # debounced!

    # Touch after debounce window
    current_time = 100.3
    tracker._touch()
    assert tracker.last_activity == 100.3


def test_activity_tracker_stop_does_not_join_current_thread():
    import threading
    tracker = PynputActivityTracker(lambda: 0.0)
    current = threading.current_thread()
    tracker._keyboard_listener = current  # mock current thread as listener
    tracker.stop()  # must not raise RuntimeError: cannot join current thread
    assert tracker._keyboard_listener is None


def test_enforcer_speak_calls_stop_on_playback_failure():
    mock_tts = MagicMock()
    mock_tts.runAndWait.side_effect = Exception("COM playback failure")
    with patch("pyttsx3.init", return_value=mock_tts):
        enforcer = WindowsEnforcer(
            enable_tts=True,
            enable_alarm=False,
            tts_rate=180,
            tts_volume=1.0,
            alarm_frequency_hz=1000,
            alarm_duration_ms=200,
            alarm_repetitions=1,
        )
        enforcer._speak("Hello error")
        mock_tts.stop.assert_called_once()
