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
    ('rainbow_z80n_sky', 'is_rainbow_sky', None),                          # Rainbow Islands sky fix: opt-in rework of rainbow_z80n (NEXCLASH_REWORK)
    ('rainbow_z80n', 'is_rainbow', lambda a: getattr(a, 'engine', None) != 'rainbow'),  # Rainbow Islands (128K), Z80N
    ('rainbow', 'is_rainbow', None),                                      # Rainbow Islands: deprecated (--engine rainbow)
    ('wally2', 'is_wally2', lambda a: getattr(a, 'engine', None) != 'wally'),  # Everyone's a Wally, updated
    ('wally', 'is_wally', None),                                          # Everyone's a Wally (frozen: --engine wally)
    ('chuckie', 'is_chuckie', None),                                      # Chuckie Egg (48K)
    ('rambo', 'is_rambo', None),                                          # Rambo (48K)
    ('ikari_warriors', 'is_ikari_warriors', None),                        # Ikari Warriors (48K)
    ('nemesis', 'is_nemesis', None),                                      # Nemesis the Warlock (48K)
    ('jetpac_v11', 'is_jetpac', lambda a: getattr(a, 'altrom_fill', None) == 'whole'),  # Jet Pac v1.1: opt-in rework of jetpac
    ('jetpac', 'is_jetpac', None),                                        # Jetpac (16K)
    ('loderunner', 'is_loderunner', None),                                # Lode Runner (48K)
    ('commando', 'is_commando', None),                                    # Commando (128K)
    ('midres', 'is_midres', None),                                        # Midnight Resistance (128K)
    ('smashtv', 'is_smashtv', None),                                      # Smash TV (48K, BASIC loader)
    ('renegade', 'is_renegade', None),                                    # Target Renegade (128K, BASIC loader)
    ('matchday_v2', 'is_matchday', lambda a: getattr(a, 'altrom_fill', None) == 'whole'),  # Match Day: opt-in rework of matchday
    ('matchday', 'is_matchday', None),                                    # Match Day (48K)
    ('cyclone', 'is_cyclone', None),                                      # Cyclone (48K)
    ('incredible_shrinking_fireman_add_GPT6_ASTRA', 'is_fireman', lambda a: getattr(a, 'z80', '').endswith('-add-GPT6_ASTRA.z80')),
    ('incredible_shrinking_fireman_add_opus', 'is_incredible_shrinking_fireman_add_opus', None),  # The Incredible Shrinking Fireman (48K)
    ('atic_atac_v13', 'is_atic_atac_v13', None),                          # Atic Atac v1.3: opt-in rework of atic_atac (NEXCLASH_REWORK)
    ('atic_atac', 'is_atic_atac', None),                                  # Atic Atac (48K)
    ('renegade128', 'is_renegade128', None),                              # Renegade (128K release)
    ('cauldron', 'is_cauldron', None),                                    # Cauldron (48K)
    ('nightshade', 'is_nightshade', None),                                # Nightshade (48K)
    ('knight_tyme', 'is_knight_tyme', None),                              # Knight Tyme (128K)
    ('spellbound_magic_knight', 'is_spellbound_magic_knight', None),      # Spellbound (128K, Magic Knight 2)
    ('three_weeks', 'is_three_weeks', None),                              # Three Weeks in Paradise (128K)
    ('starquake', 'is_starquake', None),                                  # Starquake (48K)
    ('lunar_jetman', 'is_lunar_jetman', None),                            # Lunar Jetman (48K)
    ('robin_of_the_wood', 'is_robin_of_the_wood', None),                  # Robin of the Wood (128K)
]


def find(snapshot, args=None):
    """-> the engine module that builds this snapshot, or None (generic path)."""
    for name, detector, cond in ENGINES:
        mod = importlib.import_module('nexclash.' + name)
        if getattr(mod, detector)(snapshot) and (cond is None or cond(args)):
            return mod
    return None
