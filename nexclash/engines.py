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
    ('bubbler', 'is_bubbler', None),                                    # Bubbler (48K), optional Enhanced
    ('underwurlde', 'is_underwurlde', None),                              # Underwurlde (48K)
    ('martianoids', 'is_martianoids', None),                            # Martianoids (48K)
    ('gng', 'is_gng', None),                                            # Ghosts 'n Goblins (48K)
    ('quazatron', 'is_quazatron', None),                                  # Quazatron colour (48K): opt-in, unproven (NEXCLASH_REWORK=quazatron)
    ('rainbow_z80n_sky', 'is_rainbow_sky', None),                          # Rainbow Islands sky fix: opt-in rework of rainbow_z80n (NEXCLASH_REWORK)
    ('nodes_of_yesod', 'is_nodes_of_yesod', None),
    ('pyjamarama', 'is_pyjamarama', None),
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
    ('tid128_v11', 'is_tid128_v11', None),                                # opt-in shared-library rework
    ('tid128', 'is_tid128', None),                                        # Treasure Island Dizzy 128K: opt-in rework of dizzy_patch
    ('loderunner_v3', 'is_loderunner_v3', None),                          # Lode Runner 128K v1.1: opt-in rework of loderunner_v2 (NEXCLASH_REWORK)
    ('loderunner_v2', 'is_loderunner_v2', None),                          # Lode Runner 128K: opt-in rework of loderunner
    ('fwd128', 'is_fwd128', None),                                        # Fantasy World Dizzy 128K: opt-in rework of the generic TID build
    ('magicland128', 'is_magicland128', None),                            # Magicland Dizzy 128K: opt-in rework of the generic TID build
    ('yolk128', 'is_yolk128', None),                                      # Prince of the Yolkfolk 128K: opt-in rework of tid_mirror
    ('loderunner', 'is_loderunner', None),                                # Lode Runner (48K)
    ('commando', 'is_commando', None),                                    # Commando (128K)
    ('midres', 'is_midres', None),                                        # Midnight Resistance (128K)
    ('smashtv', 'is_smashtv', None),                                      # Smash TV (48K, BASIC loader)
    ('renegade_v12', 'is_renegade_v12', None),                            # Target Renegade v1.2: opt-in rework of renegade (NEXCLASH_REWORK)
    ('renegade', 'is_renegade', None),                                    # Target Renegade (128K, BASIC loader)
    ('matchday_v21', 'is_matchday_v21', lambda a: getattr(a, 'altrom_fill', None) == 'whole'),  # Match Day v2.1: speed pass of matchday_v2 (NEXCLASH_REWORK)
    ('matchday_v2', 'is_matchday', lambda a: getattr(a, 'altrom_fill', None) == 'whole'),  # Match Day: opt-in rework of matchday
    ('matchday', 'is_matchday', None),                                    # Match Day (48K)
    ('cyclone', 'is_cyclone', None),                                      # Cyclone (48K)
    ('incredible_shrinking_fireman_add_GPT6_ASTRA', 'is_fireman', lambda a: getattr(a, 'z80', '').endswith('-add-GPT6_ASTRA.z80')),
    ('incredible_shrinking_fireman_add_opus', 'is_incredible_shrinking_fireman_add_opus', None),  # The Incredible Shrinking Fireman (48K)
    ('atic_atac_v14', 'is_atic_atac_v14', None),                          # Atic Atac v1.4: opt-in rework (v1.3 + pace limiter; NEXCLASH_REWORK)
    ('atic_atac_v13', 'is_atic_atac_v13', None),                          # Atic Atac v1.3: opt-in rework of atic_atac (NEXCLASH_REWORK)
    ('atic_atac', 'is_atic_atac', None),                                  # Atic Atac (48K)
    ('renegade128', 'is_renegade128', None),                              # Renegade (128K release)
    ('cauldron_v11', 'is_cauldron', lambda a: getattr(a, 'altrom_fill', None) == 'whole'),  # Cauldron v1.1: opt-in rework of cauldron
    ('cauldron', 'is_cauldron', None),                                    # Cauldron (48K)
    ('nightshade', 'is_nightshade', None),                                # Nightshade (48K)
    ('knight_tyme', 'is_knight_tyme', None),                              # Knight Tyme (128K)
    ('spellbound_magic_knight', 'is_spellbound_magic_knight', None),      # Spellbound (128K, Magic Knight 2)
    ('three_weeks', 'is_three_weeks', None),                              # Three Weeks in Paradise (128K)
    ('starquake', 'is_starquake', None),                                  # Starquake (48K)
    ('lunar_jetman', 'is_lunar_jetman', None),                            # Lunar Jetman (48K)
    ('dynamite_dan', 'is_dynamite_dan', None),                            # Dynamite Dan (48K)
    ('sabre_wulf', 'is_sabre_wulf', None),                                # Sabre Wulf (48K)
    ('solomons_key', 'is_solomons_key', None),                            # Solomon's Key (48K)
    ('robin_of_the_wood', 'is_robin_of_the_wood', None),                  # Robin of the Wood (128K)
    ('cobra', 'is_cobra', None),                                          # Cobra (48K)
    ('gryzor', 'is_gryzor', None),                                        # Gryzor (48K)
    ('green_beret', 'is_green_beret', None),                              # Green Beret (48K)
    ('new_zealand_story', 'is_new_zealand_story', None),                  # The New Zealand Story (128K, tape set: --tape)
    ('ice_palace', 'is_ice_palace', None),                                # Beyond the Ice Palace (128K)
    ('pacmania', 'is_pacmania', None),                                    # Pac-Mania (128K)
    ('abu_simbel', 'is_abu_simbel', None),                                # Abu Simbel Profanation (48K)
    ('knight_lore', 'is_knight_lore', None),                              # Knight Lore (48K): default build; Enhanced needs private assets
    ('alien_8', 'is_alien_8', None),                                      # Alien 8 (48K): default and Enhanced
    ('gunfright', 'is_gunfright', None),                                  # Gunfright (48K): default and Enhanced
    ('army_moves', 'is_army_moves', None),                                # Army Moves (128K, both parts)
    ('game_over', 'is_game_over', None),                                  # Game Over (128K, both worlds)
    ('chase_hq', 'is_chase_hq', None),                                    # Chase H.Q. (128K): Speed, Enhanced in two sets (local art)
    ('atom_ant', 'is_atom_ant', None),                                    # Atom Ant (128K tape form): default and Enhanced
    ('silkworm', 'is_silkworm', None),                                    # Silkworm (128K): default and Enhanced
    ('ruff_and_reddy', 'is_ruff_and_reddy', None),                        # Ruff and Reddy (128K): default and Enhanced
    ('into_the_eagles_nest', 'is_into_the_eagles_nest', None),            # Into the Eagle's Nest (128K): default and Enhanced
    ('phantis', 'is_phantis', None),                                      # Phantis / Game Over 2 (48K, both parts): part 1 Enhanced (local table)
    ('gunrunner', 'is_gunrunner', None),                                  # Gunrunner (48K): default and Enhanced
    ('scooby_doo', 'is_scooby_doo', None),                                # Scooby Doo in the Castle Mystery (48K): default, Enhanced (local set)
    ('booty', 'is_booty', None),                                          # Booty (48K): default and Enhanced
    ('page_pharaoh', 'is_page', None),                                    # Page and the Curse of the Pharaoh (48K): default and Enhanced
    ('mad_mix_2', 'is_mad_mix_2', None),                                  # Mad Mix 2 (128K): default, Enhanced stages 1-3 (local table)
    ('flying_shark', 'is_flying_shark', None),                            # Flying Shark (48K): Layer 2 outline
    ('jillys_farm', 'is_jillys', None),                                   # Jilly's Farm Volume 1 - SokoBAArn! (48K): default and Enhanced
    ('that_sinking_feeling', 'is_tsf', None),                             # That Sinking Feeling (128K tape form): default and Enhanced
]


def find(snapshot, args=None):
    """-> the engine module that builds this snapshot, or None (generic path)."""
    for name, detector, cond in ENGINES:
        mod = importlib.import_module('nexclash.' + name)
        if getattr(mod, detector)(snapshot) and (cond is None or cond(args)):
            return mod
    return None
