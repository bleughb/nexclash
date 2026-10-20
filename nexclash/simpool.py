"""Reusable SkoolKit simulators for the per-event differential tests.

Building a SkoolKit Simulator costs ~3 ms (create_opcodes builds ~1,800 closures bound to the
registers list and the memory object). A verify run builds two or three per patched call, so on
Lode Runner (2,000 frames) construction was 86 s of 183 s - more than running the game.

`machine(Sim, mem, regs, slot)` returns a simulator of class Sim that runs on `mem` with registers
`regs`, reusing one built earlier for the same (Sim, slot). The closures stay bound to a proxy
object; the proxy takes on the target's class and shares its __dict__, so every access runs the
target's own __getitem__ / __setitem__ (no extra call) and every write lands in the target. The
dispatch tables and tracer state are restored to the freshly built ones on every reuse, so an
engine's own patches to a table (NEXTREG handlers, a tracer) never leak into the next event.

Rules: one live simulator per slot - the pair runner uses 'o' (original), 'p' (patched), 'c'
(a third copy) - and the target must be an instance of a plain Python class (dict-backed, no
__slots__). A flat 64K bytearray / list gets a freshly built simulator, as before, unless the caller
passes copy=True: then the simulator runs on a pooled buffer filled from `mem`, and the caller must
call copy_back(sim, mem) before reading `mem` (writes do not reach it until then).
NEXCLASH_SIMPOOL=0 turns pooling off (A/B timing, or to rule it out when a check fails).
"""
import os

_POOL = {}
_TABLES = ('opcodes', 'after_CB', 'after_DD', 'after_ED', 'after_FD', 'after_DDCB', 'after_FDCB')
ENABLED = os.environ.get('NEXCLASH_SIMPOOL', '1') != '0'


class _Proxy(object):
    """Stand-in memory object; takes on the target's class and attributes per use."""


_OK = {}


def _poolable(mem):
    """A plain Python class the proxy can take on (a list / bytearray subclass cannot: other layout)."""
    t = type(mem)
    if t not in _OK:
        try:
            q = _Proxy()
            q.__class__ = t
            _OK[t] = hasattr(t, '__getitem__')
        except TypeError:
            _OK[t] = False
    return ENABLED and _OK[t]


def machine(Sim, mem, regs=None, slot='o', copy=False):
    if copy and ENABLED and isinstance(mem, (bytearray, list)) and len(mem) == 65536:
        key = (Sim, slot, type(mem))
        ent = _POOL.get(key)
        if ent is None:
            sim = Sim(bytearray(65536) if isinstance(mem, bytearray) else [0] * 65536, {})
            saved = {t: list(getattr(sim, t)) for t in _TABLES}
            state = {k: v for k, v in vars(sim).items() if k not in _TABLES and k not in ('memory', 'registers')}
            ent = _POOL[key] = (sim, None, saved, state)
        sim, _, saved, state = ent
        sim.memory[:] = mem
        _restore(sim, saved, state, regs)
        return sim
    if not _poolable(mem):
        sim = Sim(mem, {})
        if regs is not None:
            sim.registers[:] = regs
        return sim
    key = (Sim, slot)
    ent = _POOL.get(key)
    if ent is None:
        proxy = _Proxy()
        proxy.__class__ = type(mem)
        proxy.__dict__ = mem.__dict__
        sim = Sim(proxy, {})
        saved = {t: list(getattr(sim, t)) for t in _TABLES}
        state = {k: v for k, v in vars(sim).items() if k not in _TABLES and k not in ('memory', 'registers')}
        ent = _POOL[key] = (sim, proxy, saved, state)
    sim, proxy, saved, state = ent
    proxy.__class__ = type(mem)
    proxy.__dict__ = mem.__dict__
    _restore(sim, saved, state, regs)
    return sim


def _restore(sim, saved, state, regs):
    for t, v in saved.items():
        getattr(sim, t)[:] = v
    for k, v in state.items():
        setattr(sim, k, v)
    if regs is not None:
        sim.registers[:] = regs


def copy_back(sim, mem):
    """After machine(..., copy=True): the run's memory -> mem (no-op when sim runs on mem itself)."""
    if sim.memory is not mem:
        mem[:] = sim.memory
