"""Akaza Dork Parser — top-level shim.

The real implementation lives in the ``akaza`` package. This file exists so
the legacy ``python akaza.py`` workflow keeps working.

For programmatic / CLI use, prefer:

    python -m akaza scrape -e brave,mojeek,ecosia
    python -m akaza engines
    python -m akaza proxies validate
"""

from __future__ import annotations

import sys


def main() -> int:
    # Delegate to the package CLI when extra args are supplied,
    # otherwise launch the interactive TUI (matches the previous UX).
    if len(sys.argv) > 1:
        from akaza.cli import main as cli_main
        return cli_main()
    from akaza.tui import App
    App().main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
