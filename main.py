"""Launcher: ``python main.py`` (same as ``python -m facemouse``)."""
import sys

from facemouse.app import main

if __name__ == "__main__":
    sys.exit(main())
