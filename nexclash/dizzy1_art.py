"""Dizzy's optional wide colour set: source intake and pixel-key painting sheets.

Colour sources and derived game artwork stay outside the repository. No game code
is imported: each graphics byte is checked against the user's target release.
"""
import hashlib
import json
from pathlib import Path
from . import dizzy1 as G, coloursheet as C, jnext as J


def intake(z80, planes, palette):
    raw = Path(planes).read_bytes()
    vals = list(map(int, Path(palette).read_text().split()))
    if len(vals) != 768:
        raise ValueError('expected 256 RGB triples in the source palette')
    rgb = [tuple(255 * (v >> 2) // 63 for v in vals[i:i + 3]) for i in range(0, 768, 3)]
    rgb9 = [sum(((v * 7 + 127) // 255) << shift for v, shift in zip(c, (6, 3, 0))) for c in rgb]
    mem = G._mem(z80)

    def colour(a, bit):
        off = (5, 2, 0)[(a >> 14) - 1] * 16384 * 9 + (a & 16383) * 9
        if off + 8 >= len(raw) or raw[off + 8] != mem[a]:
            raise ValueError('source graphics do not match the target at %04X' % a)
        return sum(((raw[off + p] >> (7 - bit)) & 1) << p for p in range(8))

    # Check every frame, including the four-pixel-shifted player variants.
    for dizzy, frames in ((False, 256), (True, 78)):
        for f in range(frames):
            q = G.frame_info(mem.__getitem__, f, dizzy)
            if q:
                for a in range(q[0], q[0] + q[1] * q[2]):
                    colour(a, 0)
    l2 = [(v << 1) | bool(v & 3) for v in G.PALETTE]
    l2[0] = 0xE3 << 1
    lookup = {v: i for i, v in reversed(list(enumerate(l2))) if i}
    used = set()
    for f in range(39):
        a, w, h = G.frame_info(mem.__getitem__, f, True)
        for ga in range(a, a + w * h):
            used.update(rgb9[colour(ga, b)] for b in range(8) if mem[ga] & (128 >> b))
    sp = list(l2)
    sp_lookup = {0: 8, 511: 15}
    slots = iter(i for i in range(1, 15) if i != 8)
    for v in sorted(used):
        if v not in sp_lookup:
            index = next(slots, None)
            if index is None:
                raise ValueError('player needs more than 15 opaque sprite colours')
            sp[index] = v
            sp_lookup[v] = index
    entries = {}
    for dizzy, frames in ((False, 256), (True, 39)):
        for f in range(frames):
            q = G.frame_info(mem.__getitem__, f, dizzy)
            if q is None:
                continue
            a, w, h = q
            for ga in range(a, a + w * h):
                colours = []
                for b in range(8):
                    if not mem[ga] & (128 >> b):
                        colours.append(0)
                        continue
                    value = rgb9[colour(ga, b)]
                    if dizzy:
                        index = sp_lookup[value]
                    else:
                        if value not in lookup:
                            if len(l2) == 256 or value >> 1 == 0xE3:
                                raise ValueError('colour cannot be represented by the Layer 2 palette')
                            lookup[value] = len(l2)
                            l2.append(value)
                        index = lookup[value]
                    colours.append(index)
                entries[('D' if dizzy else 'G') + '%04X' % ga] = [mem[ga], 1, colours]
    return dict(credit='Enhanced colours: Jao Paulo (Spec256)',
                source_md5=hashlib.md5(Path(z80).read_bytes()).hexdigest(),
                l2_palette=l2 + [0] * (256 - len(l2)), sprite_palette=sp,
                colour_count=len(l2), entries=entries)


def sheets(z80, art, prefix):
    mem = G._mem(z80)
    values = art['l2_palette'][:art['colour_count']]
    lookup = {v: i for i, v in reversed(list(enumerate(values))) if i}
    for value in art['sprite_palette'][1:]:
        if value not in lookup:
            lookup[value] = len(values)
            values.append(value)
    colours = {k: [e[0], e[1], list(e[2])] + list(e[3:]) for k, e in art['entries'].items()}
    for k, e in colours.items():
        if k[0] == 'D':
            e[2] = [lookup[art['sprite_palette'][v]] if v else 0 for v in e[2]]
    comps = []
    for dizzy, frames in ((True, 39), (False, 256)):
        for f in range(frames):
            p = G.static_part(mem.__getitem__, dizzy, f, 'Dizzy' if dizzy else 'Objects and scenery')
            if p:
                p.update(dx=0, dy=0, dmir=0)
                comps.append(dict(group=p['group'], count=1, parts=[p]))
    results = []
    for suffix, unique in (('_PAINTING_SPRITES', True), ('_REFERENCE_ALL_SPRITES', False)):
        path = str(prefix) + suffix
        if Path(path + '.png').exists() or Path(path + '_layout.json').exists():
            raise ValueError('artwork already exists; choose a new prefix to preserve owner edits')
        count = C.write(comps, path + '.png', path + '_layout.json', [J.rgb333(v) for v in values], colours,
                        width=512, unique=unique, paint_clear=True, identity=G.colour_identity(mem.__getitem__))
        results.append((path + '.png', count))
    return results


def painted(art, png, layout):
    """Read edits; keep existing palette indices where possible (unchanged sheet is byte-identical)."""
    data = json.loads(Path(layout).read_text())
    cmap, report = C.read(png, layout, clear=True)
    palette = [sum(((v * 7 + 127) // 255) << shift for v, shift in zip(rgb, (6, 3, 0)))
               for rgb in data['palette']]
    result = json.loads(json.dumps(art))
    l2 = result['l2_palette'][:result['colour_count']]
    sprite = result['sprite_palette']
    gl = {v: i for i, v in reversed(list(enumerate(l2))) if i}
    sl = {v: i for i, v in reversed(list(enumerate(sprite))) if i}
    used = {palette[v] for k, e in cmap.items() if k[0] == 'D' for v in e[2] if v} | {0, 511}
    # Keep black and white at the engine's default indices, and every still-used existing colour.
    sl.update({0: 8, 511: 15})
    free = iter(i for i in range(1, 15) if i != 8 and sprite[i] not in used)
    for value in sorted(used):
        if value not in sl:
            index = next(free, None)
            if index is None:
                raise ValueError('edited player needs more than 15 opaque colours')
            sprite[index] = value
            sl[value] = index
    entries = {}
    for k, e in cmap.items():
        e = [e[0], e[1], list(e[2])] + list(e[3:])
        for b, index in enumerate(e[2]):
            if not index:
                continue
            value = palette[index]
            if k[0] == 'D':
                e[2][b] = sl[value]
            else:
                if value not in gl:
                    if len(l2) == 256 or value >> 1 == 0xE3:
                        raise ValueError('edited colour cannot be represented by Layer 2')
                    gl[value] = len(l2)
                    l2.append(value)
                e[2][b] = gl[value]
        entries[k] = e
    result.update(entries=entries, colour_count=len(l2), l2_palette=l2 + [0] * (256 - len(l2)))
    return result, report
