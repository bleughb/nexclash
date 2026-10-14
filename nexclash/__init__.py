"""nexclash package. SkoolKit is found the same way for every entry point (nexclash.py, selftest.py,
`python -m nexclash.<engine>`): installed, or an unpacked copy in C:\\skoolkit-10.1 or ~/skoolkit.
Dependencies: requirements.txt."""
import os as _os
import sys as _sys

try:
    import skoolkit  # noqa: F401
except ImportError:
    for _p in (r'C:\skoolkit-10.1', _os.path.expanduser('~/skoolkit')):
        if _os.path.isdir(_p) and _p not in _sys.path:
            _sys.path.insert(0, _p)
    # still missing: modules that need it say so (build.rom48); records/views work without it
