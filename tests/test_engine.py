import random
from roast_focus_bot.config import BotConfig
from roast_focus_bot.engine import RuleEngine


class FakeClock:
    def __init__(self, value=0.0):
        self.value = value

    def __call__(self):
        return self.value


def config(**overrides):
    raw = {
        "focus_duration_seconds": 100,
        "distraction_threshold_seconds": 10,
        "inactivity_threshold_seconds": 20,
        "cooldown_seconds": 30,
        "distraction_keywords": ["youtube"],
        "roasts": {"distraction": ["DISTRACTION"], "inactivity": ["IDLE"], "completion": ["COMPLETE"]},
    }
    raw.update(overrides)
    return BotConfig.from_mapping(raw)


def test_distraction_requires_threshold():
    clock = FakeClock(0)
    engine = RuleEngine(config(), clock=clock)
    state = engine.initial_state()

    assert engine.tick(state, "YouTube", last_activity=0) is None
    clock.value = 9
    assert engine.tick(state, "YouTube", last_activity=9) is None
    engine.tick(state, "YouTube", last_activity=0)
    clock.value = 10
    assert engine.tick(state, "YouTube", last_activity=10) == "DISTRACTION"


def test_leaving_distraction_resets_timer():
    clock = FakeClock(0)
    engine = RuleEngine(config(), clock=clock)
    state = engine.initial_state()

    engine.tick(state, "YouTube", last_activity=0)
    clock.value = 5
    engine.tick(state, "VS Code", last_activity=5)
    clock.value = 10
    assert engine.tick(state, "VS Code", last_activity=10) is None


def test_distraction_recovery():
    clock = FakeClock(0)
    engine = RuleEngine(config(), clock=clock)
    state = engine.initial_state()

    # Trigger distraction at 10s
    engine.tick(state, "YouTube", last_activity=0)
    clock.value = 10
    assert engine.tick(state, "YouTube", last_activity=10) == "DISTRACTION"

    # User switches to Work window at 15s
    clock.value = 15
    assert engine.tick(state, "VS Code", last_activity=15) is None
    assert state.distraction_started_at is None

    # User goes back to YouTube at 20s
    clock.value = 20
    assert engine.tick(state, "YouTube", last_activity=20) is None
    # Still needs 10s of distraction from 20s -> 30s
    clock.value = 25
    assert engine.tick(state, "YouTube", last_activity=20) is None
    clock.value = 51  # past both cooldown (from 10s + 30s = 40s) and distraction threshold (from 20s + 10s = 30s)
    assert engine.tick(state, "YouTube", last_activity=20) == "DISTRACTION"


def test_inactivity_triggers_and_recovers():
    clock = FakeClock(0)
    engine = RuleEngine(config(), clock=clock)
    state = engine.initial_state()
    clock.value = 20
    assert engine.tick(state, "VS Code", last_activity=0) == "IDLE"

    # User resumes activity at 22s
    clock.value = 25
    assert engine.tick(state, "VS Code", last_activity=22) is None


def test_cooldown_prevents_spam():
    clock = FakeClock(0)
    engine = RuleEngine(config(), clock=clock)
    state = engine.initial_state()
    engine.tick(state, "YouTube", last_activity=0)
    clock.value = 10
    assert engine.tick(state, "YouTube", last_activity=10) == "DISTRACTION"
    clock.value = 20
    assert engine.tick(state, "YouTube", last_activity=20) is None
    clock.value = 40
    assert engine.tick(state, "YouTube", last_activity=40) == "DISTRACTION"


def test_ignored_window_wins_over_distraction_keyword():
    clock = FakeClock(0)
    cfg = config(ignored_keywords=["youtube - roast & chastise focus bot"])
    engine = RuleEngine(cfg, clock=clock)
    state = engine.initial_state()
    clock.value = 20
    assert engine.tick(state, "YouTube - Roast & Chastise Focus Bot", last_activity=0) == "IDLE"


def test_focus_duration_completes_session():
    clock = FakeClock(0)
    engine = RuleEngine(config(focus_duration_seconds=50), clock=clock)
    state = engine.initial_state()
    clock.value = 50
    assert engine.tick(state, "VS Code", last_activity=50) is None
    assert state.completed is True

    # Subsequent tick when completed returns None
    clock.value = 60
    assert engine.tick(state, "YouTube", last_activity=0) is None


def test_paused_state_suppresses_enforcement_and_completion():
    clock = FakeClock(0)
    engine = RuleEngine(config(focus_duration_seconds=50), clock=clock)
    state = engine.initial_state()
    state.paused = True
    # Even if clock exceeds focus duration, paused state must not complete
    clock.value = 100
    assert engine.tick(state, "YouTube", last_activity=0) is None
    assert state.completed is False


def test_pause_and_resume_preserves_focus_duration():
    clock = FakeClock(0)
    engine = RuleEngine(config(focus_duration_seconds=50), clock=clock)
    state = engine.initial_state()

    # 10s of active focus
    clock.value = 10
    assert engine.tick(state, "VS Code", last_activity=10) is None

    # Pause at 10s for 100s
    state.paused = True
    state.paused_at = 10
    clock.value = 110

    # Resume at 110s
    state.total_paused_duration += clock.value - state.paused_at
    state.paused_at = None
    state.paused = False

    # Effective elapsed time is 110 - 0 - 100 = 10s (40s remaining of 50s total)
    assert engine.tick(state, "VS Code", last_activity=110) is None
    assert state.completed is False

    # Advance to 149s (effective 49s < 50s)
    clock.value = 149
    assert engine.tick(state, "VS Code", last_activity=149) is None
    assert state.completed is False

    # Advance to 150s (effective 50s >= 50s) -> completes!
    clock.value = 150
    assert engine.tick(state, "VS Code", last_activity=150) is None
    assert state.completed is True


def test_roast_selection():
    cfg = config(roasts={"distraction": ["Roast A", "Roast B"]})
    rng = random.Random(42)
    engine = RuleEngine(cfg, rng=rng)
    assert engine.choose_roast("distraction") in ["Roast A", "Roast B"]
    # Fallback for unknown category
    assert engine.choose_roast("non_existent") == "Back to work."
    # Fallback for completion
    assert engine.choose_roast("completion") == "Focus session complete. Well done on staying the course."
