"""Minimal RZX writer/reader (snapshot + input-recording segments)."""
import struct
from skoolkit.rzxplay import parse_rzx, InputRecording
from skoolkit.snapshot import Snapshot


def write_rzx(path, segments, creator='nexclash'):
    """segments: list of (z80_bytes, [(fetch_count, [in values]), ...])."""
    out = bytearray(b'RZX!' + bytes([0, 13]) + struct.pack('<I', 0))
    name = creator.encode()[:19].ljust(20, b'\0')
    out += bytes([0x10]) + struct.pack('<I', 29) + name + struct.pack('<HH', 1, 0)
    for z80, frames in segments:
        out += bytes([0x30]) + struct.pack('<IIII', 17 + len(z80), 0, 0x0030387A, len(z80)) + z80
        data = bytearray()
        for fc, ins in frames:
            data += struct.pack('<HH', fc, len(ins)) + bytes(ins)
        out += bytes([0x80]) + struct.pack('<IIBII', 18 + len(data), len(frames), 0, 0, 0) + data
    open(path, 'wb').write(out)


def read_segments(path):
    """Return a list of (Snapshot, InputRecording) pairs."""
    blocks = parse_rzx(path)
    segs, snap = [], None
    for b in blocks:
        if isinstance(b.obj, Snapshot):
            snap = b.obj
        elif isinstance(b.obj, InputRecording):
            segs.append((snap, b.obj, b.data))
    return segs


def merge(paths, out):
    """Concatenate the blocks of several RZX files (first file's header)."""
    body = bytearray()
    for p in paths:
        d = open(p, 'rb').read()
        i = 10
        while i < len(d):
            n = struct.unpack('<I', d[i + 1:i + 5])[0]
            if d[i] != 0x10 or not body:
                body += d[i:i + n]
            i += n
    open(out, 'wb').write(open(paths[0], 'rb').read()[:10] + bytes(body))


def strip(path, out):
    """Keep the first snapshot and every input block; drop later snapshots (Fuse autosave
    'checkpoints', which need interrupt repair). Replay then continues from the simulated
    state, as rzxplay --flags 4 does."""
    d = open(path, 'rb').read()
    body, i, snaps = bytearray(), 10, 0
    while i < len(d):
        n = struct.unpack('<I', d[i + 1:i + 5])[0]
        if d[i] == 0x30:
            snaps += 1
            if snaps > 1:
                i += n
                continue
        body += d[i:i + n]
        i += n
    open(out, 'wb').write(d[:10] + bytes(body))
    return snaps - 1


def info(path):
    segs = read_segments(path)
    frames = sum(len(r.frames) for _, r, _ in segs)
    return '%s: %d segment(s), %d frames (%.1f s at 50Hz)' % (path, len(segs), frames, frames / 50)
