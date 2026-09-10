import json
from pathlib import Path
import pytest
from roast_focus_bot.config import BotConfig


def test_defaults_are_reasonable():
    cfg = BotConfig.from_mapping({})
    assert cfg.focus_duration_seconds == 2700
    assert cfg.distraction_threshold_seconds == 60
    assert cfg.inactivity_threshold_seconds == 180
    assert cfg.cooldown_seconds == 120
    assert cfg.poll_interval_seconds == 1.0
    assert cfg.enable_tts is True
    assert cfg.enable_alarm is True
    assert cfg.tts_rate == 185
    assert cfg.tts_volume == 1.0


def test_mapping_converts_lists_to_immutable_tuples():
    cfg = BotConfig.from_mapping({"distraction_keywords": ["YouTube", "FACEBOOK"]})
    assert cfg.distraction_keywords == ("youtube", "facebook")


def test_load_default_json():
    default_path = Path(__file__).resolve().parents[1] / "config" / "default.json"
    cfg = BotConfig.load(default_path)
    assert cfg.focus_duration_seconds == 2700
    assert "distraction" in cfg.roasts
    assert "inactivity" in cfg.roasts
    assert "completion" in cfg.roasts
    assert len(cfg.roasts["completion"]) > 0


def test_load_nonexistent_file_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        BotConfig.load("non_existent_config_file_12345.json")


def test_load_malformed_json_raises_valueerror(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json: 123}", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON"):
        BotConfig.load(bad_json)


def test_load_non_dict_root_raises_valueerror(tmp_path):
    list_json = tmp_path / "list.json"
    list_json.write_text("['not', 'a', 'dict']", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON"):
        BotConfig.load(list_json)

    valid_array_json = tmp_path / "array.json"
    valid_array_json.write_text("[\"item1\", \"item2\"]", encoding="utf-8")
    with pytest.raises(ValueError, match="Configuration root must be a JSON object"):
        BotConfig.load(valid_array_json)


def test_load_directory_path_raises_valueerror(tmp_path):
    with pytest.raises(ValueError, match="is a directory, not a file"):
        BotConfig.load(tmp_path)


def test_from_mapping_not_dict():
    with pytest.raises(ValueError, match="Configuration mapping must be a dict"):
        BotConfig.from_mapping("string")  # type: ignore


@pytest.mark.parametrize(
    "key,val,err",
    [
        ("focus_duration_seconds", 0, "focus_duration_seconds must be positive"),
        ("focus_duration_seconds", -10, "focus_duration_seconds must be positive"),
        ("distraction_threshold_seconds", 0, "distraction_threshold_seconds must be positive"),
        ("distraction_threshold_seconds", -5, "distraction_threshold_seconds must be positive"),
        ("inactivity_threshold_seconds", 0, "inactivity_threshold_seconds must be positive"),
        ("cooldown_seconds", -1, "cooldown_seconds must be non-negative"),
        ("poll_interval_seconds", 0, "poll_interval_seconds must be positive"),
        ("window_title_max_length", 0, "window_title_max_length must be positive"),
        ("tts_rate", 0, "tts_rate must be positive"),
        ("tts_volume", -0.1, "tts_volume must be between 0.0 and 1.0"),
        ("tts_volume", 1.5, "tts_volume must be between 0.0 and 1.0"),
        ("alarm_frequency_hz", 30, "alarm_frequency_hz must be between 37 and 32767"),
        ("alarm_frequency_hz", 35000, "alarm_frequency_hz must be between 37 and 32767"),
        ("alarm_duration_ms", 0, "alarm_duration_ms must be positive"),
        ("alarm_repetitions", 0, "alarm_repetitions must be positive"),
        ("emergency_hotkey", [], "emergency_hotkey must not be empty"),
    ],
)
def test_validation_errors(key, val, err):
    with pytest.raises(ValueError, match=err):
        BotConfig.from_mapping({key: val})


def test_empty_and_whitespace_keywords_are_filtered():
    cfg = BotConfig.from_mapping({
        "distraction_keywords": ["  ", "", "YouTube", "   reddit   "],
        "ignored_keywords": ["", "  ", "focus bot"],
    })
    assert cfg.distraction_keywords == ("youtube", "reddit")
    assert cfg.ignored_keywords == ("focus bot",)


def test_unknown_configuration_keys_warn_and_load(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        cfg = BotConfig.from_mapping({"extra_field": 123, "focus_duration_seconds": 1200})
        assert cfg.focus_duration_seconds == 1200
        assert "Unknown configuration fields ignored" in caplog.text


def test_invalid_type_raises_valueerror():
    with pytest.raises(ValueError, match="Invalid configuration parameter type"):
        BotConfig.from_mapping({"focus_duration_seconds": "not-a-number"})


def test_malformed_roasts_mapping():
    with pytest.raises(ValueError, match="roasts must be a mapping"):
        BotConfig.from_mapping({"roasts": "not-a-dict"})

    with pytest.raises(ValueError, match="must be a list of strings"):
        BotConfig.from_mapping({"roasts": {"distraction": "just-a-string"}})
