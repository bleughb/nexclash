"""Tape-set inputs: a game whose build reads its own tape files (one or several, used together) beside the start state.

Why (2026-11-07): some games exist in their full form only on tape, several files of it (The New Zealand Story: Ocean's
Side A .tap or .tzx plus the Side B .tzx; about ten queued 128K games are multiload tapes). Their build needs bytes the
start state does not hold (levels loaded later), so the tapes are inputs, as a snapshot and recordings are:
  - the start state stays the record's snapshot (`inputs.snapshot`, an emulator .z80 at the point the build starts from;
    it is what `auto` detects and the stub starts), so everything that reads one snapshot is unchanged;
  - the tapes are `inputs.tapes`: a list of ALTERNATIVE sets (releases of the game: the .tap and the .tzx of Side A), each
    an ordered list of files {name, md5, path}, as the .nxc format's sets of files (spec/NXC-FORMAT.md "Sets") are;
  - `nexclash.py auto ... --tape A --tape B` passes one set, in order; the engine checks it against the sets it accepts
    (its own list of MD5s: the user flow has no record) with match() and reads its data blocks here;
  - every alternative set must rebuild to the same outputs (selftest rebuilds each set it has and compares the MD5s).
Nothing here is game-specific: an engine finds its blocks by content (flag byte, header) with find(), not by position,
so a .tap and a .tzx of one release, whose block numbers differ, give the same build.

Data blocks are counted as in the .nxc format ("Tapes"): every block of a .tap; in a .tzx the standard (0x10), turbo
(0x11) and pure data (0x14) blocks, the other blocks of TZX 1.20 skipped; a block's bytes as stored (flag first,
checksum last on a standard block).

    python -m nexclash.tapeset FILE...      the set's files, MD5s and data blocks (flag, length, header name)
"""
import hashlib
import os
import sys

TZX_MAGIC = b'ZXTape!\x1a'
# data blocks: id -> (head bytes, where in the head the length is, its size)
TZX_DATA = {0x10: (4, 2, 2), 0x11: (18, 15, 3), 0x14: (10, 7, 3)}
# skipped blocks: id -> (head bytes, where a count is or None, its size, bytes per count)
TZX_SKIP = {0x12: (4, None, 0, 0), 0x13: (1, 0, 1, 2), 0x15: (8, 5, 3, 1), 0x18: (4, 0, 4, 1), 0x19: (4, 0, 4, 1),
            0x20: (2, None, 0, 0), 0x21: (1, 0, 1, 1), 0x22: (0, None, 0, 0), 0x23: (2, None, 0, 0), 0x24: (2, None, 0, 0),
            0x25: (0, None, 0, 0), 0x26: (2, 0, 2, 2), 0x27: (0, None, 0, 0), 0x28: (2, 0, 2, 1), 0x2A: (4, 0, 4, 1),
            0x2B: (4, 0, 4, 1), 0x30: (1, 0, 1, 1), 0x31: (2, 1, 1, 1), 0x32: (2, 0, 2, 1), 0x33: (1, 0, 1, 3),
            0x35: (20, 16, 4, 1), 0x5A: (9, None, 0, 0)}


def kind(path):
    """'tap' or 'tzx' from the file name; anything else is refused."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.tap', '.tzx'):
        raise ValueError('%s: a tape is a .tap or a .tzx' % os.path.basename(path))
    return ext[1:]


def data_blocks(data, kind_):
    """The tape's data blocks (bytes), in file order. ValueError on a damaged tape or an unknown TZX block."""
    out, i, end = [], 0, len(data)

    def take(at, size):
        if at + size > end:
            raise ValueError('damaged tape: a block runs past the end')
        return int.from_bytes(data[at:at + size], 'little')
    if kind_ == 'tap':
        while i < end:
            n = take(i, 2)
            i += 2
            if i + n > end:
                raise ValueError('damaged tape: a block runs past the end')
            out.append(bytes(data[i:i + n]))
            i += n
        return out
    if end < 10 or data[:8] != TZX_MAGIC or data[8] != 1:
        raise ValueError('not a TZX file of major version 1')
    i = 10
    while i < end:
        bid = data[i]
        i += 1
        if bid in TZX_DATA:
            head, at, size = TZX_DATA[bid]
            n = take(i + at, size)
            if i + head + n > end:
                raise ValueError('damaged tape: a block runs past the end')
            out.append(bytes(data[i + head:i + head + n]))
            i += head + n
        elif bid in TZX_SKIP:
            head, at, size, unit = TZX_SKIP[bid]
            n = 0 if at is None else take(i + at, size) * unit
            if i + head + n > end:
                raise ValueError('damaged tape: a block runs past the end')
            i += head + n
        else:
            raise ValueError('TZX block 0x%02X is not a tape block this reader knows' % bid)
    return out


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def match(paths, sets):
    """paths (the files given, in order) against sets (the accepted alternatives: lists of MD5s, in order) -> the index
    of the set they are, or ValueError naming what is wanted. Order matters: Side B first is refused."""
    got = [md5(p) for p in paths]
    for i, want in enumerate(sets):
        if got == list(want):
            return i
    names = ', '.join(os.path.basename(p) for p in paths) or 'no tapes'
    wants = '; or '.join(' + '.join(want) for want in sets)
    for want in sets:
        if sorted(got) == sorted(want):
            raise ValueError('tapes in the wrong order (%s): give them as %s' % (names, ' + '.join(want)))
    raise ValueError('tapes %s (MD5 %s) are not a release this build knows: it wants, in this order, MD5s %s' % (
        names, ' + '.join(got) or '-', wants))


class TapeSet:
    """One set of tape files, in order: .paths, .md5s, .blocks (per file: its data blocks)."""

    def __init__(self, paths):
        self.paths = list(paths)
        self.md5s = [md5(p) for p in self.paths]
        self.blocks = []
        for p in self.paths:
            try:
                self.blocks.append(data_blocks(open(p, 'rb').read(), kind(p)))
            except ValueError as e:
                raise ValueError('%s: %s' % (os.path.basename(p), e))

    def all_blocks(self):
        """[(file index, block index, bytes)] over the whole set, in order."""
        return [(f, k, b) for f, bl in enumerate(self.blocks) for k, b in enumerate(bl)]

    def find(self, pred, first_only=True):
        """The set's blocks for which pred(bytes) is true, in set order: the first one (or None), or all of them."""
        hits = [b for _, _, b in self.all_blocks() if pred(b)]
        return (hits[0] if hits else None) if first_only else hits

    def after(self, pred):
        """[(block, the next block of the same file or None)] for each block pred accepts: a header and its data block."""
        ab = self.all_blocks()
        return [(ab[i][2], ab[i + 1][2] if i + 1 < len(ab) and ab[i + 1][0] == ab[i][0] else None)
                for i in range(len(ab)) if pred(ab[i][2])]


def load(paths, sets):
    """Check paths against the accepted sets (MD5 lists) and read them -> (TapeSet, set index). ValueError when no tapes
    are given, a file is missing, or they are not an accepted set."""
    if not paths:
        raise ValueError('this game builds from its tapes: give them with --tape, in order (%s)' % '; or '.join(
            ' + '.join(s) for s in sets))
    for p in paths:
        if not os.path.isfile(p):
            raise ValueError('tape %s not found' % p)
    i = match(paths, sets)
    return TapeSet(paths), i


def record_sets(rec):
    """A record's alternative tape sets (inputs.tapes): [[{name, md5, path}, ...], ...]; [] for a snapshot-only game."""
    return [s['files'] for s in rec.get('inputs', {}).get('tapes', [])]


def check_record(rec):
    """Structural checks of a record's inputs.tapes -> list of problems: each set a name and 1+ files with name, md5
    (32 hex) and path; no two sets the same MD5s in the same order; a name used twice is the same file (MD5)."""
    bad, seen, by_name = [], set(), {}
    for s in rec.get('inputs', {}).get('tapes', []):
        if not s.get('set') or not s.get('files'):
            bad.append('tape set without a name or files: %s' % s)
            continue
        key = tuple(f.get('md5') for f in s['files'])
        if key in seen:
            bad.append('tape set %s repeats another set' % s['set'])
        seen.add(key)
        for f in s['files']:
            if not all(f.get(k) for k in ('name', 'md5', 'path')) or len(f['md5']) != 32:
                bad.append('tape set %s: a file needs name, md5 (32 hex) and path: %s' % (s['set'], f))
                continue
            kind(f['name'])
            if by_name.setdefault(f['name'], f['md5']) != f['md5']:
                bad.append('tape name %s names two different files' % f['name'])
    return bad


def selfcheck():
    """Synthetic tapes (no game bytes): a .tap and a .tzx of the same blocks read the same; TZX skip blocks are skipped;
    match() takes the right set, refuses the wrong order and an unknown file; a damaged tape is refused. -> failures"""
    import tempfile
    blocks = [b'\x00' + bytes(range(16)) + b'\x55', b'\xff' + bytes(300) + b'\x01', b'', b'\x81' + b'NEXCLASH' * 40]
    tap = b''.join(len(b).to_bytes(2, 'little') + b for b in blocks)
    tzx = bytearray(TZX_MAGIC + b'\x01\x14')
    tzx += b'\x30\x04test' + b'\x20\xe8\x03' + b'\x21\x02gr'
    for k, b in enumerate(blocks):
        if k == 1:                              # turbo
            tzx += b'\x11' + bytes(15) + len(b).to_bytes(3, 'little') + b
        elif k == 3:                            # pure data
            tzx += b'\x14' + bytes(7) + len(b).to_bytes(3, 'little') + b
        else:
            tzx += b'\x10\xe8\x03' + len(b).to_bytes(2, 'little') + b
        tzx += b'\x12' + bytes(4) + b'\x13\x02' + bytes(4)
    tzx += b'\x22' + b'\x32\x03\x00\x01\x00\x00'
    bad = []
    if data_blocks(tap, 'tap') != blocks:
        bad.append('tap blocks')
    if data_blocks(bytes(tzx), 'tzx') != blocks:
        bad.append('tzx blocks')
    for broken, k in ((tap[:-3], 'tap'), (bytes(tzx[:-12]), 'tzx'), (bytes(tzx[:10]) + b'\x99', 'tzx')):
        try:
            data_blocks(broken, k)
            bad.append('damaged %s accepted' % k)
        except ValueError:
            pass
    with tempfile.TemporaryDirectory() as d:
        pa, pz, pb = (os.path.join(d, n) for n in ('a.tap', 'a.tzx', 'b.tzx'))
        open(pa, 'wb').write(tap)
        open(pz, 'wb').write(bytes(tzx))
        open(pb, 'wb').write(bytes(tzx[:10]) + b'\x10\x00\x00\x02\x00\xaa\xbb')
        sets = [[md5(pa), md5(pb)], [md5(pz), md5(pb)]]
        if match([pa, pb], sets) != 0 or match([pz, pb], sets) != 1:
            bad.append('match: right set not taken')
        for wrong, why in (([pb, pa], 'order'), ([pa], 'short'), ([pa, pz], 'unknown')):
            try:
                match(wrong, sets)
                bad.append('match accepted %s' % why)
            except ValueError as e:
                if why == 'order' and 'wrong order' not in str(e):
                    bad.append('match order message: %s' % e)
        ts, i = load([pz, pb], sets)
        if i != 1 or ts.find(lambda b: b[:1] == b'\x81') != blocks[3] or ts.after(lambda b: b[:1] == b'\x00')[0][1] != blocks[1]:
            bad.append('TapeSet find/after')
        try:
            load([], sets)
            bad.append('no tapes accepted')
        except ValueError:
            pass
    return bad


def main(argv):
    if argv[:1] == ['selfcheck']:
        bad = selfcheck()
        print('\n'.join(bad) or 'tapeset selfcheck OK')
        return 1 if bad else 0
    if not argv:
        print(__doc__)
        return 2
    ts = TapeSet(argv)
    for p, m, bl in zip(ts.paths, ts.md5s, ts.blocks):
        print('%s  %s  %d data blocks' % (m, os.path.basename(p), len(bl)))
        for k, b in enumerate(bl):
            name = ''
            if len(b) == 19 and b[0] == 0:
                name = ' header %r' % b[2:12].decode('latin-1')
            print('  %3d flag %s len %5d%s' % (k, '%02X' % b[0] if b else '--', len(b), name))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
