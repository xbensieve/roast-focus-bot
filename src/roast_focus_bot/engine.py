from __future__ import annotations

import logging
import random
import threading
from dataclasses import dataclass
from time import monotonic, sleep

from .config import BotConfig
from .interfaces import ActiveWindowProvider, ActivityTracker, Enforcer

LOGGER = logging.getLogger(__name__)


@dataclass
class EngineState:
    started_at: float
    paused: bool = False
    paused_at: float | None = None
    total_paused_duration: float = 0.0
    distraction_started_at: float | None = None
    distraction_title: str | None = None
    last_enforcement_at: float | None = None
    last_enforcement_category: str | None = None
    completed: bool = False


class RuleEngine:
    def __init__(self, config: BotConfig, clock=monotonic, rng: random.Random | None = None) -> None:
        self.config = config
        self.clock = clock
        self.rng = rng or random.Random()

    def initial_state(self) -> EngineState:
        return EngineState(started_at=self.clock())

    def is_distraction(self, title: str) -> bool:
        normalized = title.lower()
        if any(token in normalized for token in self.config.ignored_keywords):
            return False
        return any(token in normalized for token in self.config.distraction_keywords)

    def choose_roast(self, category: str) -> str:
        options = self.config.roasts.get(category, ())
        if options:
            return self.rng.choice(options)
        if category == "completion":
            return "Focus session complete. Well done on staying the course."
        return "Back to work."

    def evaluate(self, state: EngineState, active_title: str, last_activity: float, now: float) -> str | None:
        if state.paused or state.completed:
            return None

        distraction = self.is_distraction(active_title)
        if distraction:
            if state.distraction_started_at is None:
                state.distraction_started_at = now
                state.distraction_title = active_title
        else:
            state.distraction_started_at = None
            state.distraction_title = None

        cooldown_ok = (
            state.last_enforcement_at is None
            or now - state.last_enforcement_at >= self.config.cooldown_seconds
        )
        if not cooldown_ok:
            return None

        if (
            state.distraction_started_at is not None
            and now - state.distraction_started_at >= self.config.distraction_threshold_seconds
        ):
            state.last_enforcement_at = now
            state.last_enforcement_category = "distraction"
            state.distraction_started_at = now
            return self.choose_roast("distraction")

        if now - last_activity >= self.config.inactivity_threshold_seconds:
            state.last_enforcement_at = now
            state.last_enforcement_category = "inactivity"
            return self.choose_roast("inactivity")

        return None

    def tick(self, state: EngineState, active_title: str, last_activity: float) -> str | None:
        if state.paused or state.completed:
            return None
        now = self.clock()
        effective_elapsed = now - state.started_at - state.total_paused_duration
        if effective_elapsed >= self.config.focus_duration_seconds:
            state.completed = True
            return None
        return self.evaluate(state, active_title, last_activity, now)


class FocusController:
    def __init__(
        self,
        config: BotConfig,
        window_provider: ActiveWindowProvider,
        activity_tracker: ActivityTracker,
        enforcer: Enforcer,
        stop_event: threading.Event,
        clock=monotonic,
    ) -> None:
        self.config = config
        self.window_provider = window_provider
        self.activity_tracker = activity_tracker
        self.enforcer = enforcer
        self.stop_event = stop_event
        self.clock = clock
        self.engine = RuleEngine(config, clock=clock)
        self.state = self.engine.initial_state()

    def pause(self) -> None:
        if self.state.paused:
            return
        now = self.clock()
        self.state.paused = True
        self.state.paused_at = now
        self.state.distraction_started_at = None
        LOGGER.info("Focus session paused")

    def resume(self) -> None:
        if not self.state.paused:
            return
        now = self.clock()
        if self.state.paused_at is not None:
            self.state.total_paused_duration += max(0.0, now - self.state.paused_at)
            self.state.paused_at = None
        self.state.paused = False
        if hasattr(self.activity_tracker, "_touch"):
            self.activity_tracker._touch()
        LOGGER.info("Focus session resumed")

    def run(self) -> None:
        LOGGER.info("Focus session started: duration=%ss", self.config.focus_duration_seconds)
        self.activity_tracker.start()
        try:
            while not self.stop_event.is_set() and not self.state.completed:
                try:
                    title = self.window_provider.title()
                    message = self.engine.tick(self.state, title, self.activity_tracker.last_activity)
                    if message:
                        self.enforcer.enforce(self.state.last_enforcement_category or "unknown", message)
                except Exception:
                    LOGGER.exception("Unexpected error during monitoring tick")

                if self.state.completed:
                    break
                self.stop_event.wait(self.config.poll_interval_seconds)

            if self.state.completed:
                completion_message = self.engine.choose_roast("completion")
                LOGGER.info("Focus session completed successfully: %s", completion_message)
                try:
                    self.enforcer.enforce("completion", completion_message)
                except Exception:
                    LOGGER.exception("Failed to announce session completion")
        finally:
            self.activity_tracker.stop()
            LOGGER.info("Focus session stopped")
