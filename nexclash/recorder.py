"""Automatic RZX recording: start the game, learn which inputs do something, explore rooms.

Input script format (for `record --script FILE` / `--start`), one step per line:
    wait 50               no input for 50 frames
    SPACE 5               hold SPACE for 5 frames (then released)
    Q+M 20                hold Q and M together
    K:RIGHT+K:FIRE 30     Kempston joystick (also KR KL KU KD KF)
    # comment
`--start "SPACE"` or `--start "4 5, wait 20, 0 5"` uses the same steps, comma-separated.
"""
import random
from .machine import Machine, parse_inputs, KEYPOS, KEMPSTON

START_CANDIDATES = ['SPACE', 'ENTER', '0', '1', '2', '3', '4', '5', 'S', 'P', 'K:FIRE', 'N', 'Y', 'J', 'K']
PLAY_ATTRS = slice(0x5860, 0x5AA0)          # attribute rows 3-20: identifies the room


def parse_script(text):
    steps = []
    for line in text.replace(',', '\n').splitlines():
        line = line.split('#')[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0].lower() == 'wait':
            steps.append((frozenset(), int(parts[1]) if len(parts) > 1 else 50))
        else:
            steps.append((parse_inputs(parts[0]), int(parts[1]) if len(parts) > 1 else 5))
    return steps


class Recorder:
    def __init__(self, z80, seed=1, inputs='auto', log=print, room_threshold=0.25):
        self.room_threshold = room_threshold
        self.m = Machine(z80)
        self.rng = random.Random(seed)
        self.inputs = inputs
        self.log = log
        self.first = []                         # frames of segment 0 (from the snapshot)
        self.first_z80 = self.m.z80_bytes()
        self.cov = set()
        self.report = {}

    def run(self, frames, held=frozenset(), rec=None):
        for _ in range(frames):
            f = self.m.frame(held)
            if rec is not None:
                rec.append(f)

    def play(self, steps):
        for held, n in steps:
            self.run(n, held, self.first)
            if held:
                self.run(2, frozenset(), self.first)

    def _cov_after(self, state, steps, frames):
        self.m.load(state)
        self.m.cov = set()
        for held, n in steps:
            self.run(n, held)
        self.run(frames)
        c = self.m.cov
        self.m.cov = self.cov
        return c

    def auto_start(self, rounds=3):
        chosen = []
        for _ in range(rounds):
            base = self.m.save()
            idle = self._cov_after(base, [], 150)
            scores = []
            for k in START_CANDIDATES:
                if self.inputs == 'keyboard' and k.startswith('K:'):
                    continue
                if self.inputs == 'kempston' and not k.startswith('K:'):
                    continue
                c = self._cov_after(base, [(parse_inputs(k), 5), (frozenset(), 2)], 150)
                scores.append((len(c - idle), k))
            scores.sort(reverse=True)
            self.m.load(base)
            if not scores or scores[0][0] < 40:
                break
            k = scores[0][1]
            chosen.append(k)
            self.play([(parse_inputs(k), 5), (frozenset(), 60)])
        self.report['start'] = ' then '.join(chosen) if chosen else 'none detected'
        return chosen

    def learn_inputs(self, keep=6):
        """Classify responsive inputs by effect, from 40 frames of holding each one:
        movement (screen changes, no attribute change), action (a few attribute cells,
        e.g. an inventory box) and menu (large attribute change: map, pause, other
        screens). Inputs with an identical effect are merged (Z / 6 / Sinclair keys)."""
        g = self.m.save()
        self.run(40)
        mem = self.m.sim.memory
        idle_ram, idle_attr = bytes(mem[0x5B00:]), bytes(mem[0x5800:0x5B00])
        seen, res = {}, []
        for k in list(KEYPOS) + list(KEMPSTON):
            if self.inputs == 'keyboard' and k in KEMPSTON:
                continue
            if self.inputs == 'kempston' and k in KEYPOS:
                continue
            self.m.load(g)
            self.run(40, frozenset([k]))
            mem = self.m.sim.memory
            ram = bytes(mem[0x5B00:])
            d = sum(1 for a, b in zip(ram, idle_ram) if a != b)
            if not d or ram in seen:
                continue
            seen[ram] = k
            c = sum(1 for a, b in zip(mem[0x5800:0x5B00], idle_attr) if a != b)
            res.append((d, k, c))
        self.m.load(g)
        res.sort(reverse=True)
        self.atoms = [k for d, k, c in res if c == 0][:keep]
        self.actions = [k for d, k, c in res if 0 < c <= 58][:3]
        self.menus = [k for d, k, c in res if c > 58][:3]
        if not self.atoms:
            self.atoms, self.actions = self.actions, []
        self.report['inputs'] = ' '.join(self.atoms) if self.atoms else 'none responded'
        if self.actions or self.menus:
            self.report['inputs'] += ' (actions: %s; menus: %s)' % (' '.join(self.actions) or '-', ' '.join(self.menus) or '-')
        return self.atoms

    def room(self):
        return bytes(self.m.sim.memory[PLAY_ATTRS])

    def find_room(self, rooms, attrs):
        """Index of the known room these attributes belong to, or None."""
        # same room if <= threshold of the play-area attribute cells differ (moving
        # objects, flashing items and sprites change a few cells, a new room most of them)
        limit = self.room_threshold * len(attrs)
        for i, r in enumerate(rooms):
            a = r[0]
            if sum(1 for x, y in zip(a, attrs) if x != y) <= limit:
                return i
        return None

    def action(self, atoms, prev):
        special = getattr(self, 'actions', []), getattr(self, 'menus', [])
        if special[0] and self.rng.random() < 0.06:
            return frozenset([self.rng.choice(special[0])]), self.rng.randint(4, 8)
        if special[1] and self.rng.random() < 0.01:
            return frozenset([self.rng.choice(special[1])]), self.rng.randint(4, 8)
        for _ in range(3):
            r = self.rng.random()
            if r < 0.10:
                held, n = frozenset(), self.rng.randint(10, 40)
            elif r < 0.40:
                held, n = frozenset([self.rng.choice(atoms)]), self.rng.randint(50, 150)   # commit: walk to an exit
            elif r < 0.80 or len(atoms) < 2:
                held, n = frozenset([self.rng.choice(atoms)]), self.rng.randint(6, 40)
            else:
                held, n = frozenset(self.rng.sample(atoms, 2)), self.rng.randint(6, 40)
            if held != prev or not held:
                break
        return held, n

    def explore(self, budget=20000, max_out=6000):
        atoms = self.atoms or ['SPACE']
        rooms = [[self.room(), [self.m.save()], 0]]      # [attributes, up to 4 start states, visits]
        segs, total, out, novel = [], 0, 0, 0
        while total < budget and out < max_out:
            i = min(range(len(rooms)), key=lambda k: (rooms[k][2], self.rng.random()))
            rooms[i][2] += 1
            self.m.load(self.rng.choice(rooms[i][1]))
            z80 = self.m.z80_bytes()
            frames, prev, new = [], None, False
            for _ in range(self.rng.randint(6, 12)):
                held, n = self.action(atoms, prev)
                prev = held
                self.run(n, held, frames)
                a = self.room()
                j = self.find_room(rooms, a)
                if j is None:
                    rooms.append([a, [self.m.save()], 0])
                    new = True
                elif self.rng.random() < 0.15:
                    st = rooms[j][1]
                    if len(st) < 4:
                        st.append(self.m.save())
                    else:
                        st[self.rng.randrange(4)] = self.m.save()
            total += len(frames)
            novel += new
            segs.append((z80, frames))
            out += len(frames)
        self.report.update(rooms=len(rooms), code_addresses=len(self.cov), explored_frames=total,
                           kept_segments=len(segs), kept_frames=out)
        return segs


def record(z80, out_rzx, start=None, script=None, inputs='auto', frames=6000, budget=20000, seed=1, keys=None,
           log=print, room_threshold=0.25):
    from .rzx import write_rzx
    r = Recorder(z80, seed, inputs, log, room_threshold)
    r.m.cov = r.cov
    r.run(20, frozenset(), r.first)
    if script:
        r.play(parse_script(script))
        r.report['start'] = 'script'
        segs = [(r.first_z80, r.first)]
        r.report['inputs'] = 'script'
    else:
        if start:
            r.play(parse_script(start))
            r.report['start'] = start
        else:
            r.auto_start()
        r.run(50, frozenset(), r.first)
        if keys:
            r.atoms = [k for k in keys]
            r.report['inputs'] = ' '.join(r.atoms) + ' (given)'
        else:
            r.learn_inputs()
        segs = [(r.first_z80, r.first)] + r.explore(budget, frames)
    write_rzx(out_rzx, segs)
    r.report['rzx'] = out_rzx
    r.report['frames'] = sum(len(f) for _, f in segs)
    return r.report
