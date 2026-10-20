"""Engine registry: which dedicated engine builds a snapshot (`nexclash.py auto`, cmd_auto).

A new engine adds ONE line here (and nothing in nexclash.py). Order matters: the first engine
whose detector accepts the snapshot builds it; snapshots no detector accepts go to the generic
TID / Dizzy path in nexclash.py.

Why a separate file (2026-10-20): every game's evidence depends on nexclash.py, so the dispatch
line a new game used to add there was a shared-code change, and `selftest.py --affected --verify`
then re-verified one game of EVERY engine (hours) for a one-line table entry. This file runs no
verification code - it only picks the module - so records.plan() treats it as rebuild-only: a
wrong or missing entry changes which engine builds a game, and the rebuild's MD5s catch that.
Keep it that way: a table and a loop, nothing else.
"""
import importlib

# (module, detector, extra condition on the auto arguments or None)
ENGINES = [
    ('rainbow', 'is_rainbow', None),                                      # Rainbow Islands (128K)
    ('wally2', 'is_wally2', lambda a: getattr(a, 'engine', None) != 'wally'),  # Everyone's a Wally, updated
    ('wally', 'is_wally', None),                                          # Everyone's a Wally (frozen: --engine wally)
    ('chuckie', 'is_chuckie', None),                                      # Chuckie Egg (48K)
    ('jetpac', 'is_jetpac', None),                                        # Jetpac (16K)
    ('loderunner', 'is_loderunner', None),                                # Lode Runner (48K)
    ('commando', 'is_commando', None),                                    # Commando (128K)
    ('midres', 'is_midres', None),                                        # Midnight Resistance (128K)
    ('smashtv', 'is_smashtv', None),                                      # Smash TV (48K, BASIC loader)
    ('renegade', 'is_renegade', None),                                    # Target Renegade (128K, BASIC loader)
    ('matchday', 'is_matchday', None),                                    # Match Day (48K)
]


def find(snapshot, args=None):
    """-> the engine module that builds this snapshot, or None (generic path)."""
    for name, detector, cond in ENGINES:
        mod = importlib.import_module('nexclash.' + name)
        if getattr(mod, detector)(snapshot) and (cond is None or cond(args)):
            return mod
    return None
