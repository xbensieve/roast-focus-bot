# Roast & Chastise Focus Bot

A lightweight, privacy-first Windows desktop daemon that monitors your active window and keyboard/mouse activity during timed focus sessions. When it catches you doomscrolling or going idle, it roasts you — out loud — using local text-to-speech and an audible alarm.

No network calls. No browser extensions. No cloud accounts. Just a small process that watches window titles and speaks uncomfortable truths when you drift off task.

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Building a Standalone Executable](#building-a-standalone-executable)
- [Testing](#testing)
- [Privacy & Data Handling](#privacy--data-handling)
- [License](#license)

## How It Works

1. You start a focus session (default: 45 minutes).
2. The bot polls the foreground window title once per second.
3. If the title matches a configurable distraction keyword (e.g. `youtube`, `reddit`, `tiktok`) and you stay there beyond a threshold, the bot fires an audible alarm and speaks a randomly selected roast through your speakers.
4. If you go completely idle (no keyboard or mouse input) for too long, it calls you out for that too.
5. A cooldown prevents enforcement from repeating too rapidly.
6. When the session timer expires, you receive a congratulatory completion message.
7. Press **Ctrl+Shift+F12** at any time to immediately stop the bot.

## Architecture

The application follows a clean separation of concerns with protocol-based dependency injection, making the core rule engine fully testable without any Windows dependencies.

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Entry Point                       │
│                      (cli.py)                           │
│  Parses args · loads config · wires components · runs   │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│                   FocusController                        │
│                    (engine.py)                           │
│  Main polling loop · owns session lifecycle              │
│  Delegates to RuleEngine for decisions                   │
│  Delegates to Enforcer for punishment                    │
└──────┬──────────────┬───────────────┬────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌─────────────┐ ┌───────────┐ ┌──────────────┐
│ RuleEngine  │ │ Activity  │ │   Windows    │
│ (engine.py) │ │ Tracker   │ │  Enforcer    │
│             │ │ (pynput)  │ │ (pyttsx3 +   │
│ Stateless   │ │           │ │  winsound)   │
│ evaluation  │ │ Keyboard  │ │              │
│ + cooldown  │ │ + mouse   │ │ Alarm beep   │
│ + roast     │ │ timestamp │ │ + TTS speech │
│   selection │ │ only      │ │              │
└─────────────┘ └───────────┘ └──────────────┘
       │
       ▼
┌──────────────────┐
│ ActiveWindow     │
│ Provider         │
│ (PyGetWindow)    │
│                  │
│ Reads foreground │
│ window title     │
└──────────────────┘
```

### Key Design Decisions

- **Protocol-based interfaces** — `ActiveWindowProvider`, `ActivityTracker`, `Enforcer`, and `Clock` are defined as Python `Protocol` types in [`interfaces.py`](src/roast_focus_bot/interfaces.py). The rule engine depends only on these abstractions, never on Windows APIs directly.
- **Monotonic clock** — All timing uses `time.monotonic()` so system clock adjustments cannot affect session duration or distraction thresholds.
- **Failure isolation** — TTS and alarm channels fail independently. If speech synthesis crashes, the alarm still fires and vice versa. Window lookup errors degrade gracefully to `"UNKNOWN"`.
- **No event content logging** — The activity tracker registers keyboard and mouse listeners but immediately discards event payloads. Only a monotonic timestamp is retained.

### Threading Model

| Thread | Purpose |
|--------|---------|
| Main | Controller polling loop (1 Hz by default) |
| pynput keyboard listener | Updates `last_activity` timestamp |
| pynput mouse listener | Updates `last_activity` timestamp |
| pynput hotkey listener | Fires emergency stop on Ctrl+Shift+F12 |

TTS runs synchronously on the main thread during enforcement to prevent overlapping speech.

## Project Structure

```
Roast Focus Bot/
├── src/roast_focus_bot/       # Application source
│   ├── __init__.py
│   ├── __main__.py            # python -m entry point
│   ├── cli.py                 # Argument parsing, component wiring, main()
│   ├── config.py              # BotConfig dataclass, JSON loader, validation
│   ├── engine.py              # RuleEngine (stateless logic) + FocusController
│   ├── interfaces.py          # Protocol definitions (no implementation)
│   └── platform_windows.py   # Windows-specific implementations
├── config/
│   └── default.json           # Default configuration with roast messages
├── tests/                     # pytest suite (no Windows dependency)
│   ├── test_config.py
│   ├── test_controller.py
│   ├── test_engine.py
│   └── test_failures.py
├── scripts/
│   ├── setup-dev.ps1          # Create venv + install dependencies
│   ├── run.ps1                # Launch the bot from source
│   ├── build-exe.ps1          # PyInstaller build + code signing
│   └── test.ps1               # Run pytest
├── docs/                      # Extended documentation
├── .github/workflows/ci.yml   # GitHub Actions CI (Windows runner)
├── RoastFocusBot.spec         # PyInstaller spec for single-file EXE
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Requirements

- **OS:** Windows 10 or later
- **Python:** 3.12+
- **Runtime dependencies:** PyGetWindow, pyttsx3, pynput (pinned in `requirements.txt`)

The bot relies on Windows-native APIs (`winsound.Beep`, SAPI5 via pyttsx3) and cannot run on macOS or Linux.

## Getting Started

### 1. Clone and set up the development environment

```powershell
git clone https://github.com/xbensieve/roast-focus-bot.git
cd roast-focus-bot
.\scripts\setup-dev.ps1
```

This creates a `.venv`, upgrades pip, and installs all pinned dependencies (including dev tools).

### 2. Run from source

```powershell
.\scripts\run.ps1
```

Or manually:

```powershell
.\.venv\Scripts\python.exe -m roast_focus_bot --config config/default.json
```

### 3. Validate without starting a session

```powershell
# Dry run — validates config and dependencies, then exits
.\.venv\Scripts\python.exe -m roast_focus_bot --dry-run

# Self-test — validates runtime imports, tests window lookup and TTS init
.\.venv\Scripts\python.exe -m roast_focus_bot --self-test
```

### 4. Stop the bot

Press **Ctrl+Shift+F12** (global hotkey) or **Ctrl+C** in the terminal.

## Configuration

All behavior is controlled by a single JSON file. The default ships at [`config/default.json`](config/default.json).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `focus_duration_seconds` | `2700` | Session length (45 min) |
| `distraction_threshold_seconds` | `60` | Seconds on a distracting window before enforcement |
| `inactivity_threshold_seconds` | `180` | Seconds of idle input before enforcement |
| `cooldown_seconds` | `120` | Minimum gap between consecutive enforcements |
| `poll_interval_seconds` | `1.0` | How often the active window is checked |
| `enable_tts` | `true` | Enable spoken roast messages |
| `enable_alarm` | `true` | Enable audible alarm beep |
| `tts_rate` | `185` | Speech rate (words per minute) |
| `tts_volume` | `1.0` | Speech volume (0.0–1.0) |
| `alarm_frequency_hz` | `1100` | Beep frequency |
| `alarm_duration_ms` | `550` | Beep duration per repetition |
| `alarm_repetitions` | `3` | Number of beep repetitions |
| `emergency_hotkey` | `["ctrl","shift","f12"]` | Global hotkey to stop the bot |
| `distraction_keywords` | *(see file)* | Window title substrings flagged as distractions |
| `ignored_keywords` | *(see file)* | Window title substrings that override distraction matching |
| `roasts` | *(see file)* | Categorized roast messages (`distraction`, `inactivity`, `completion`) |

Pass a custom config with:

```powershell
.\.venv\Scripts\python.exe -m roast_focus_bot --config path/to/custom.json
```

Unknown keys in the JSON are logged as warnings and ignored. Missing keys fall back to built-in defaults.

## Building a Standalone Executable

The build script produces a single-file `.exe` using PyInstaller, runs the test suite first, and optionally applies a local Authenticode signature:

```powershell
.\scripts\build-exe.ps1
```

Output:
- `dist/roast-focus-bot.exe` — the standalone executable (console-less)
- `dist/default.json` — configuration file, copied alongside the EXE

The EXE looks for `default.json` next to itself, then in the current working directory.

## Testing

Tests run on any platform (they mock all Windows APIs):

```powershell
.\scripts\test.ps1
```

Or directly:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite covers:
- **Configuration loading and validation** — schema enforcement, edge cases, unknown key handling
- **Rule engine logic** — distraction detection, inactivity detection, cooldown behavior, session completion
- **Controller lifecycle** — polling loop, pause/resume, stop event handling
- **Failure resilience** — graceful degradation when TTS, alarm, or window lookup fails

CI runs on every push and pull request via GitHub Actions on a `windows-latest` runner.

## Privacy & Data Handling

The bot is designed to be privacy-respecting by default:

- **No keylogging** — keyboard/mouse listeners record only a timestamp; event payloads (key identity, mouse coordinates, etc.) are discarded immediately.
- **No screenshots, OCR, or clipboard access.**
- **No network connections** — everything runs locally using OS-native speech synthesis.
- **No persistent storage** — no database, no files written during a session. Logs go to stderr only.
- **Window titles are truncated** by a configurable maximum length and held only in memory for the duration of the current evaluation cycle.

See [`docs/PRIVACY.md`](docs/PRIVACY.md) for the full data handling policy.

## License

[MIT](LICENSE) © 2026
