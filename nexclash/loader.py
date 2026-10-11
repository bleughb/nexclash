"""Loader-stage snapshots: replay a recording until the game's code is in place.

Some snapshots are taken while a BASIC loader waits (e.g. PAUSE 0 before RANDOMIZE USR) and
the game then relocates itself, so its engine exists only after the loader has run. prerun()
replays the RZX exactly (as rzxplay does), stops at the first frame boundary where
test(memory) holds, finishes any block copy in progress (so the relocation is complete and
the game's own start-up code - e.g. joystick detection - still runs on the real machine),
and returns that state as a .z80 file plus the frame number."""
import os, tempfile
import skoolkit.rzxplay as rzxplay
from skoolkit.simutils import get_state
from skoolkit.snapshot import write_snapshot


class _Found(Exception):
    pass


def _finish_block_copy(sim):
    regs, mem = sim.registers, sim.memory
    pc = regs[24]
    while mem[pc] == 0xED and mem[(pc + 1) & 0xFFFF] in (0xB0, 0xB8):   # LDIR / LDDR
        sim.run(pc, (pc + 2) & 0xFFFF)
        pc = regs[24]


def prerun(rzx_path, test, out_z80=None, max_frames=5000):
    orig = rzxplay.RZXTracer.next_frame
    found = {}

    def next_frame(self):
        sim = self.simulator
        n = self.context.frame_count + (1 if self.frame_index >= 0 else 0)
        if n > max_frames:
            raise _Found()
        if test(sim.memory):
            _finish_block_copy(sim)
            found['frame'] = n
            found['state'] = get_state(sim)
            found['pc'] = sim.registers[24]
            raise _Found()
        return orig(self)

    rzxplay.RZXTracer.next_frame = next_frame
    try:
        rzxplay.main(['--quiet', '--no-screen', '--fps', '0', rzx_path])
    except (_Found, SystemExit):
        pass
    finally:
        rzxplay.RZXTracer.next_frame = orig
    if 'state' not in found:
        return None, None, None
    ram, regs, state, machine = found['state']
    if out_z80 is None:
        fd, out_z80 = tempfile.mkstemp(suffix='.z80')
        os.close(fd)
    write_snapshot(out_z80, ram, regs, state, machine)
    return out_z80, found['frame'], found['pc']
