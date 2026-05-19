"""
Compatibility shim: ``import hmda_analyzer`` is equivalent to ``import hmdaanalyzer``.

Both import paths work after ``pip install hmda-analyzer``:

    from hmda_analyzer import denial_rate_by_race    # pip-install convention
    from hmdaanalyzer import denial_rate_by_race     # canonical form
"""
from hmdaanalyzer import *          # noqa: F401, F403
from hmdaanalyzer import __version__, __all__  # noqa: F401
