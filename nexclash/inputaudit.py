"""Declared inputs only (selftest's rebuild / verify runs set NEXCLASH_INPUT_AUDIT=FILE, NEXCLASH_INPUT_ROOT=the staged
folder): every file a build opens for reading outside the repository, the staged folder, Python's own files, the
temporary folder and the system folders is appended to FILE. selftest fails the run when FILE is not empty: a build
that reads an undeclared file (Lunar Jetman's palette once came from a Downloads folder) is not reproducible from
its record. Files named by environment variables the toolkit documents (NEXCLASH_NEXT_ROM, NEXCLASH_CONFIG,
NEXCLASH_COLOURS) are allowed and reported by the run itself."""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILES = ('NEXCLASH_NEXT_ROM', 'NEXCLASH_CONFIG', 'NEXCLASH_COLOURS')


def _roots():
    r = [_HERE, os.environ.get('NEXCLASH_INPUT_ROOT'), sys.prefix, sys.base_prefix, sys.exec_prefix,
         tempfile.gettempdir(), '/dev', '/proc', '/sys', '/usr', '/etc', '/lib', '/lib64', '/opt']
    r += [p for p in sys.path if p and os.path.isdir(p)]
    return tuple(sorted({os.path.realpath(p) + os.sep for p in r if p}))


def install(log):
    roots = _roots()
    files = {os.path.realpath(os.environ[k]) for k in ENV_FILES if os.environ.get(k)} | {os.path.realpath(log)}
    busy = [False]

    def hook(event, args):
        if event != 'open' or busy[0]:
            return
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        if isinstance(mode, str) and any(c in mode for c in 'wax+'):
            return
        if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            return
        busy[0] = True
        try:
            p = os.path.realpath(os.fsdecode(path))
            if p in files or (p + os.sep).startswith(roots) or not os.path.isfile(p):
                return
            with open(log, 'a') as f:
                f.write(p + '\n')
        finally:
            busy[0] = False
    sys.addaudithook(hook)


def read(log):
    """-> sorted undeclared files a run read (empty: only declared inputs)."""
    return sorted(set(open(log).read().split('\n')) - {''}) if os.path.exists(log) else []
