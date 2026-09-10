try:
    from .cli import main
except ImportError:
    from roast_focus_bot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
