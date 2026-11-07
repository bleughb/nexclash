"""New-engine verification baseline; adapt the replay loop from chuckie.verify.

Chuckie is a legacy loop example: do not copy its CMP definition. Install the
HLIB_R_IN/_OUT hooks (patch.preserve-r card), and compare R at every boundary.
Keep engine-specific memory, pixel and interrupt checks in the engine.
"""
from nexclash.hooklib import CMP_R

CMP = CMP_R


def register_differences(original, patched):
    """Use in the engine's failure reporting, including an R-off-by-one negative."""
    return {index: (original[index], patched[index])
            for index in CMP if original[index] != patched[index]}
