"""Layer 2 colours a Next shows as see-through (Codex review C4).

NR $14 (global transparency) is compared with the TOP 8 BITS of a 9-bit colour, whatever its palette index and its
priority bit: with $14 = $E3 both RGB333 $1C6 and $1C7 vanish (docs/NEXT_REGISTERS.md). An engine checks the opaque
entries its art uses after quantisation; deliberately transparent entries and entries no pixel draws are exempt.
"""


def top8(palette, fmt):
    """The top 8 bits of each entry: fmt 'pairs' = NR $44 byte pairs (RRRGGGBB, B0 + priority), '9bit' = ints
    RRRGGGBBB, '8bit' = NR $41 bytes RRRGGGBB."""
    if fmt == 'pairs':
        return list(palette[0::2])
    if fmt == '9bit':
        return [v >> 1 for v in palette]
    if fmt == '8bit':
        return list(palette)
    raise ValueError(fmt)


def collisions(palette, fmt, keep=(), transparent=0xE3):
    """Indices of entries (other than those in keep) a Next would not show."""
    return [i for i, t in enumerate(top8(palette, fmt)) if t == transparent and i not in keep]


def fix(palette, fmt, keep=(), transparent=0xE3, to=0xE7):
    """The palette with every opaque entry whose top 8 bits equal the transparency moved to `to` (the next shade, 0xE7,
    as #281 and the published nxc fixes of 2026-11-21 did); keep = deliberately transparent or undrawn entries.
    Same type and format as given. A palette with no such entry comes back unchanged."""
    bad = set(collisions(palette, fmt, keep, transparent))
    if not bad:
        return palette
    if fmt == 'pairs':
        out = bytearray(palette)
        for i in bad:
            out[2 * i] = to
        return type(palette)(out) if isinstance(palette, (bytes, bytearray)) else out
    if fmt == '9bit':
        return [(to << 1 | v & 1) if i in bad else v for i, v in enumerate(palette)]
    return [to if i in bad else v for i, v in enumerate(palette)]


def check(palette, fmt, what, keep=(), transparent=0xE3):
    """Refuse a palette with an opaque entry equal to the transparency (it would show as see-through)."""
    bad = collisions(palette, fmt, keep, transparent)
    if bad:
        raise ValueError('%s: Layer 2 entr%s %s equal the transparency 0x%02X in their top 8 bits: a Next shows them '
                         'see-through (pick another colour, e.g. 0xE7)' % (what, 'y' if len(bad) == 1 else 'ies',
                                                                          bad[:8], transparent))


def selfcheck():
    """-> failures"""
    bad = []
    if collisions([0x1C6, 0x1C7, 0x1CF, 0x000], '9bit') != [0, 1]:
        bad.append('9bit: both RGB333 0x1C6 and 0x1C7 vanish, 0x1CF does not')
    if collisions(bytes([0xE3, 0x80, 0xE3, 0x00, 0xE7, 0x01]), 'pairs') != [0, 1]:
        bad.append('pairs: an E3 entry with the priority bit still vanishes, E7 does not')
    if collisions([0xE3, 0xE3, 0x1F], '8bit', keep=(0,)) != [1]:
        bad.append('8bit: a deliberately transparent entry is exempt, another E3 is not')
    if fix(bytes([0xE3, 0x00, 0xE3, 0x81, 0x1F, 0x00]), 'pairs', keep=(0,)) != bytes([0xE3, 0x00, 0xE7, 0x81, 0x1F, 0x00]):
        bad.append('fix pairs: the kept entry stays, the opaque one moves to E7 keeping its low and priority bits')
    if fix([0x1C6, 0x1C7, 0x02], '9bit') != [0x1CE, 0x1CF, 0x02]:
        bad.append('fix 9bit: 0x1C6 / 0x1C7 move to 0x1CE / 0x1CF')
    return bad
