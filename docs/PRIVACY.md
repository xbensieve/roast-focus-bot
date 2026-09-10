# Privacy and Data Handling

## Data collected in memory

The process keeps only:

- current active-window title (truncated by configuration);
- a monotonic timestamp of the most recent keyboard/mouse activity;
- session state and timers;
- local diagnostic log messages.

## Data explicitly not collected

The application does not collect or persist:

- key contents;
- key names/identities;
- mouse coordinates;
- clipboard contents;
- screenshots;
- browser URLs beyond what may appear as ordinary active-window title text;
- credentials or form contents;
- network telemetry.

## Local logs

Logs are intended for troubleshooting. Operators should avoid enabling verbose logging that copies sensitive window titles into shared logs. The default logger records only truncated titles when an event is evaluated.

## Ownership model

The tool is intended for personal use on a machine controlled by the operator. It should not be deployed as covert employee monitoring or used to monitor other people's devices without appropriate authorization.

## Safety behavior

The bot is a configurable productivity tool, not a medical intervention. It does not diagnose, treat, or intentionally manipulate a user's medical state.
