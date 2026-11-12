"""Minimal RZX writer/reader (snapshot + input-recording segments)."""
import os
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


def _block_length(d, i, path):
    """Length of the RZX block at i (its 1-byte id and 4-byte length included). A length below that head, or a head
    cut short, is a damaged file: without this check the walk never moves on (merge and strip hung on one)."""
    n = struct.unpack('<I', d[i + 1:i + 5])[0] if i + 5 <= len(d) else 0
    if n < 5:
        raise ValueError('%s: damaged RZX block at offset %d' % (path, i))
    return n


def merge(paths, out):
    """Concatenate the blocks of several RZX files (first file's header)."""
    body = bytearray()
    for p in paths:
        d = open(p, 'rb').read()
        i = 10
        while i < len(d):
            n = _block_length(d, i, p)
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
        n = _block_length(d, i, path)
        if d[i] == 0x30:
            snaps += 1
            if snaps > 1:
                i += n
                continue
        body += d[i:i + n]
        i += n
    open(out, 'wb').write(d[:10] + bytes(body))
    return max(snaps - 1, 0)                    # a file with no snapshot dropped none (was -1)


def extract(path, out=None, index=0):
    """Write snapshot `index` (0 = the recording's start state) of an RZX to a file: the .z80 when
    the user has only a recording (docs/MAINTAIN.md). Snapshot blocks (0x30) may be zlib-compressed
    (flag bit 1; SPIN, Fuse); encrypted ones (bit 0) are refused. out defaults to <rzx>.<ext>, the
    extension taken from the block (z80 / szx / sna). -> (out path, extension)."""
    import zlib
    d = open(path, 'rb').read()
    i, k = 10, 0
    while i + 5 <= len(d):
        n = struct.unpack('<I', d[i + 1:i + 5])[0]
        if n < 5:
            break
        if d[i] == 0x30:
            if k == index:
                flags = struct.unpack('<I', d[i + 5:i + 9])[0]
                if flags & 1:
                    raise ValueError('%s: snapshot %d is encrypted' % (path, index))
                ext = d[i + 9:i + 13].rstrip(b'\0').decode('ascii', 'replace').lower()
                body = d[i + 17:i + n]
                if flags & 2:
                    body = zlib.decompress(body)
                out = out or os.path.splitext(path)[0] + '.' + ext
                open(out, 'wb').write(body)
                return out, ext
            k += 1
        i += n
    raise ValueError('%s: no snapshot %d (%d in the file)' % (path, index, k))


def info(path):
    segs = read_segments(path)
    frames = sum(len(r.frames) for _, r, _ in segs)
    return '%s: %d segment(s), %d frames (%.1f s at 50Hz)' % (path, len(segs), frames, frames / 50)


# --- bookmarks: long recordings (a whole playthrough) are cut into short RZX files that start at
# a known point (Dean, 2026-10-19: "it should not be referred to in full"). C simulator replay.
def _replay(path, on_frame=None, stop=None):
    """Replay `path` (SkoolKit rzxplay, C simulator when built). on_frame(frame, memory) after
    every frame (before the frame's interrupt); a true result stops there. stop: stop after that
    many frames (interrupt accepted, as rzxplay --stop). -> (context, remaining RZX blocks)."""
    from types import SimpleNamespace
    import skoolkit.rzxplay as rp
    blocks = parse_rzx(path)
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)

    class Hook:
        def draw(self, scr, frame, border):
            return not (on_frame and on_frame(frame, ctx.simulator.memory))
    if on_frame:
        ctx.screen = Hook()
    for b in blocks:
        if isinstance(b.obj, InputRecording):
            ctx.total_frames += len(b.obj.frames)
    if stop:
        ctx.total_frames = min(stop, ctx.total_frames)
    opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=stop or 0, force=False)
    while blocks:
        rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
        if ctx.stop:
            break
    return ctx, blocks


def scan(path, on_frame):
    """Call on_frame(frame, memory) after every frame of the whole recording; -> frames replayed.
    Raises SkoolKitError (with the frame) where the recording desyncs."""
    ctx, _ = _replay(path, on_frame)
    return ctx.frame_count


def cut(path, start, frames, out):
    """Write `out`: an RZX starting at frame `start` of `path` (the machine state there as its
    snapshot) with the next `frames` frames (fewer at the end of the recording). -> frames written."""
    import skoolkit.rzxplay as rp
    ctx, _ = _replay(path, stop=start) if start else _replay(path, stop=1)
    if not start:
        raise ValueError('start must be >= 1 (use the recording itself from frame 0)')
    tr = ctx.simulator.tracer
    tr.frames = tr.frames[:tr.frame_index + frames]
    n = len(tr.frames) - tr.frame_index
    rp.write_rzx(out, ctx, [])
    return n


def trace(path, pcs, on_pc, stop=None, rom=None):
    """Replay `path` with the C simulator (rzxplay; ~400 frames/s with a hook) and call
    on_pc(pc, simulator) before every instruction whose address is in `pcs`. A recording that
    desyncs does not stop the caller: -> (frames replayed, None or the desync message).
    rom: {address: bytes} written into the simulator's ROM before the first instruction (a recording
    of a game whose ROM differs from Sinclair's, such as Quazatron's Centred-view reference)."""
    import skoolkit.rzxplay as rp
    from types import SimpleNamespace
    from skoolkit import SkoolKitError
    blocks = parse_rzx(path)
    while blocks and isinstance(blocks[-1].obj, Snapshot):
        blocks.pop()
    ctx = rp.RZXContext(None)
    for b in blocks:
        if isinstance(b.obj, InputRecording):
            ctx.total_frames += len(b.obj.frames)
    if stop:
        ctx.total_frames = min(stop, ctx.total_frames)

    class Sink:
        def write(self, s):
            pass
    ctx.tracefile = Sink()
    pcs = frozenset(pcs)

    fresh = [rom]

    def hook(tf, context, fc, pc):
        if fresh[0]:
            for a, b in fresh[0].items():
                context.simulator.memory[a:a + len(b)] = b
            fresh[0] = None
        if pc in pcs:
            on_pc(pc, context.simulator)
    old = rp.trace_exec
    rp.trace_exec = hook
    err = None
    try:
        opts = SimpleNamespace(cmio=False, python=False, quiet=True, stop=stop or 0, force=False)
        while blocks:
            rp.process_block(blocks.pop(0).obj, opts, 0, ctx)
            if ctx.stop:
                break
    except SkoolKitError as e:
        err = str(e)
    finally:
        rp.trace_exec = old
    return ctx.frame_count, err
