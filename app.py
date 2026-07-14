"""Healthcare Lab process entrypoint and legacy import compatibility."""

from __future__ import annotations

import sys

from backend import app_factory as _application


if __name__ == "__main__":
    _application.main()
else:
    # Existing tests and integrations patch ``app.<symbol>``. Alias the module
    # object so those patches continue to affect the implementation globals
    # while new code imports from responsibility-specific backend modules.
    sys.modules[__name__] = _application
