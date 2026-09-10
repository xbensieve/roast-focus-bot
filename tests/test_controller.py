import threading
from roast_focus_bot.config import BotConfig
from roast_focus_bot.engine import FocusController


class FakeClock:
    def __init__(self, value=0.0):
        self.value = value

    def __call__(self):
        return self.value


class FakeWindowProvider:
    def __init__(self, title="VS Code"):
        self._title = title
        self.call_count = 0

    def title(self):
        self.call_count += 1
        return self._title


class FakeTracker:
    def __init__(self, last_activity=0.0):
        self._last_activity = last_activity
        self.started = False
        self.stopped = False

    @property
    def last_activity(self):
        return self._last_activity

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakeEnforcer:
    def __init__(self):
        self.enforcements = []

    def enforce(self, category: str, message: str) -> None:
        self.enforcements.append((category, message))


def test_controller_lifecycle_and_stop_event():
    config = BotConfig.from_mapping({
        "focus_duration_seconds": 100,
        "distraction_threshold_seconds": 10,
        "poll_interval_seconds": 0.001,
    })
    clock = FakeClock(0)
    provider = FakeWindowProvider("VS Code")
    tracker = FakeTracker(0)
    enforcer = FakeEnforcer()
    stop_event = threading.Event()

    controller = FocusController(config, provider, tracker, enforcer, stop_event, clock=clock)

    # Trigger stop immediately after 1 iteration by setting stop_event
    def stop_after_delay():
        stop_event.set()

    timer = threading.Timer(0.01, stop_after_delay)
    timer.start()
    controller.run()
    timer.join()

    assert tracker.started is True
    assert tracker.stopped is True


def test_controller_session_completion_announcement():
    config = BotConfig.from_mapping({
        "focus_duration_seconds": 10,
        "poll_interval_seconds": 0.001,
        "roasts": {"completion": ["You finished!"]},
    })
    clock = FakeClock(0)
    provider = FakeWindowProvider("VS Code")
    tracker = FakeTracker(0)
    enforcer = FakeEnforcer()
    stop_event = threading.Event()

    controller = FocusController(config, provider, tracker, enforcer, stop_event, clock=clock)

    # Advance clock to complete session on first tick
    clock.value = 15
    controller.run()

    assert controller.state.completed is True
    assert tracker.stopped is True
    assert len(enforcer.enforcements) == 1
    assert enforcer.enforcements[0] == ("completion", "You finished!")


def test_controller_pause_resume():
    config = BotConfig.from_mapping({"focus_duration_seconds": 100})
    clock = FakeClock(0)
    controller = FocusController(config, FakeWindowProvider(), FakeTracker(), FakeEnforcer(), threading.Event(), clock=clock)
    assert controller.state.paused is False
    controller.pause()
    assert controller.state.paused is True
    controller.resume()
    assert controller.state.paused is False


def test_controller_loop_resilience_on_provider_exception():
    config = BotConfig.from_mapping({
        "focus_duration_seconds": 5,
        "poll_interval_seconds": 0.001,
    })
    clock = FakeClock(0)

    class FailingProvider:
        def __init__(self):
            self.calls = 0

        def title(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Temporary window lookup error")
            return "VS Code"

    provider = FailingProvider()
    tracker = FakeTracker(0)
    enforcer = FakeEnforcer()
    stop_event = threading.Event()

    controller = FocusController(config, provider, tracker, enforcer, stop_event, clock=clock)

    # Let the first tick fail, then advance clock to complete
    def advance():
        clock.value = 10

    timer = threading.Timer(0.01, advance)
    timer.start()
    controller.run()
    timer.join()

    assert provider.calls >= 2
    assert controller.state.completed is True
