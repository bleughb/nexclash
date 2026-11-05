"""Headless JNext for the play checks (`python -m nexclash.soak | pace | flicker | looksheet`; docs/CHECKS.md).

The checks run a build and the original in JNext 1.1.104 (`--headless --script`), drive them with the
same input, and read what JNext logs and saves: one line per event of interest, PNG pictures, .jns machine
snapshots (sprite attributes, patterns, palettes, the ULA screen). Nothing here knows a game: game facts
come from an input PROFILE (JSON, below) or the command line. Every check warns and never refuses.

Environment: the JNext binary from $NEXCLASH_JNEXT or PATH; an SD card image (NextZXOS, needed for every
load) from --card or $NEXCLASH_JNEXT_CARD, always opened read-only. HOME is set to a folder under the
check's output (or --jnext-home / $NEXCLASH_JNEXT_HOME), never the user's own: JNext keeps its settings and
the warm-start recording there, and a check must not touch the user's JNext windows or settings.

Frames: frame 0 is the program's start. A .nex starts on JNext's warm start, frame 500 (checked against the
log on every run: the START line); a .z80 / .sna / .szx at frame 0.

Profile (JSON; every key optional; frames from the program's start; keys as JNext names: a-z 0-9 space
enter sym+X caps+X left right up down; Kempston as K:LEFT K:RIGHT K:UP K:DOWN K:FIRE or J:<hex bits>):
  start / start_orig      [[frame, key, frames held], ...] to reach play (the original's own if it differs)
  play_from / play_from_orig  frame random play begins
  dirs, fire, jump        key choices (a list in dirs = keys held together); p_fire, p_jump (0.35, 0.2)
  hold_min, hold_max      frames (or updates) a random input is held (6, 40)
  restart, restart_every  [[key, frames], ...] pressed every N frames (game over -> new game; 600)
  probe                   address executed once per game update (pace, flicker), e.g. "0xA8ED"
  state                   addresses logged at every update (pace: lockstep check), e.g. ["0x6CB6"]
  waits                   PC spans that are known waits ("0x8DD4-0x8DE0"; soak)
"""
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import zipfile

NEX_START = 500                     # JNext 1.1.104 warm start: a --load .nex starts at frame 500
GENERIC = {'name': 'generic', 'start': [[f, k, 4] for f, k in zip(range(100, 500, 25), ['space', 'enter', '0', '1', 's',
           'p', '5', 'K:FIRE', 'space', 'enter', '0', '1', 's', 'p', '5', 'K:FIRE'])],
           'play_from': 520, 'dirs': ['q', 'a', 'o', 'p', 'left', 'right', 'up', 'down', 'K:LEFT', 'K:RIGHT', 'K:UP',
                                      'K:DOWN', ['q', 'o'], ['q', 'p'], ['K:UP', 'K:LEFT'], ['K:UP', 'K:RIGHT']],
           'fire': ['space', 'm', '0', 'K:FIRE'], 'jump': [], 'restart': [['space', 4], ['enter', 4], ['0', 4], ['K:FIRE', 4]],
           'restart_every': 900}
KEMPSTON = {'RIGHT': 0x01, 'LEFT': 0x02, 'DOWN': 0x04, 'UP': 0x08, 'FIRE': 0x10}
PAPER = (32, 32, 288, 224)          # the 256 x 192 paper in JNext's 320 x 256 picture (PNGs are 2x: 640 x 512)


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def load_profile(path):
    """A profile file, or the generic one (path None / 'generic')."""
    if not path or path == 'generic':
        return dict(GENERIC)
    p = json.load(open(path))
    p.setdefault('name', os.path.splitext(os.path.basename(path))[0])
    return p


def num(v):
    return v if isinstance(v, int) else int(str(v), 0)


def start_frame(prog):
    return NEX_START if prog.lower().endswith('.nex') else 0


def nex_pc(prog):
    """The .nex header's start PC (bytes 14-15), for the START line."""
    with open(prog, 'rb') as f:
        h = f.read(16)
    return h[14] | h[15] << 8 if h[:4] == b'Next' else None


# ---- input ------------------------------------------------------------------------------------------------
def schedule(prof, length, seed=1, orig=False, unit='frame'):
    """Random play after the start keys: [(t, keys, held)]. t / held in frames (unit 'frame') or game updates
    ('update', pace); the same profile, length and seed give the same list for every build."""
    rnd = random.Random(seed)
    t0 = 0 if unit == 'update' else prof.get('play_from_orig', prof.get('play_from', 0)) if orig else prof.get('play_from', 0)
    dirs, fire, jump = prof.get('dirs', []), prof.get('fire', []), prof.get('jump', [])
    restart, every = prof.get('restart', []), prof.get('restart_every', 600)
    out, t, nxt = [], t0, t0 + every
    while t < length:
        if restart and t >= nxt:
            for k, d in restart:
                out.append((t, [k], d))
                t += d + 4
            nxt = t + every
            continue
        held = rnd.randint(prof.get('hold_min', 6), prof.get('hold_max', 40))
        keys = []
        if dirs and rnd.random() < 0.85:
            d = rnd.choice(dirs)
            keys += d if isinstance(d, list) else [d]
        if fire and rnd.random() < prof.get('p_fire', 0.35):
            keys.append(rnd.choice(fire))
        if jump and rnd.random() < prof.get('p_jump', 0.2):
            keys.append(rnd.choice(jump))
        if keys:
            out.append((t, sorted(set(keys)), held))
        t += held + rnd.randint(0, 4)
    return out


def _split(keys):
    j, kk = 0, []
    for k in keys:
        u = k.upper()
        if u.startswith('K:'):
            j |= KEMPSTON[u[2:]]
        elif u.startswith('J:'):
            j |= int(k[2:], 16)
        else:
            kk.append(k)
    return kk, j


def down(keys):
    kk, j = _split(keys)
    return ''.join('  press "%s"\n' % k for k in kk) + ('  joystick 1 %d\n' % j if j else '')


def up(keys):
    kk, j = _split(keys)
    return ''.join('  release "%s"\n' % k for k in kk) + ('  joystick 1 0\n' if j else '')


class Script:
    """A .jds script; frames are given from the program's start (`off` added)."""

    def __init__(self, off):
        self.off, self.vars, self.rules = off, [], []

    def var(self, name, v=0):
        self.vars.append('var %s = %d\n' % (name, v))

    def at(self, frame, body, when=None):
        self.rules.append('on frame %d%s do\n%send\n' % (frame + self.off, ' when %s' % when if when else '', body))

    def rule(self, text):
        self.rules.append(text if text.endswith('\n') else text + '\n')

    def hold(self, frame, keys, held, when=None):
        self.at(frame, down(keys), when)
        self.at(frame + held, up(keys), when)

    def start_keys(self, prof, orig=False, when=None):
        for f, k, d in prof.get('start_orig', prof.get('start', [])) if orig else prof.get('start', []):
            self.hold(f, [k], d, when)

    def frame_input(self, sched, when=None):
        for t, keys, held in sched:
            self.hold(t, keys, held, when)

    def update_input(self, sched, probe, counter='u'):
        """Input keyed to game updates: two builds of different pace see the same keys at the same update."""
        for t, keys, held in sched:
            self.rule('on execute %d when %s == %d do\n%send\n' % (probe, counter, t + 1, down(keys)))
            self.rule('on execute %d when %s == %d do\n%send\n' % (probe, counter, t + 1 + held, up(keys)))

    def start_line(self, prog):
        pc = nex_pc(prog)
        if pc is not None:
            self.rule('on execute %d once do\n  log "START F=${FRAME}"\nend\n' % pc)

    def exit_at(self, frame):
        self.at(frame + 3, '  exit 0\n')

    def text(self):
        return ''.join(self.vars) + ''.join(self.rules)


COUNTERS = ('var nint = 0\nvar nay = 0\nvar nbp = 0\nvar t28 = 0\nvar ts = 0\nvar ndi = 0\nvar li = 0\nvar mg = 0\n'
            'on interrupt do\n  set nint = nint + 1\n  if li != 0 and CYCLE - li > mg then\n    set mg = CYCLE - li\n  end\n'
            '  set li = CYCLE\nend\n'
            'on io_write mask 0xC002 value 0x8000 do\n  set nay = nay + 1\nend\n'
            'on io_write 0xFE do\n  set nbp = nbp + 1\nend\n'
            'on nextreg 7 do\n  if VALUE != 0 and ts == 0 then\n    set ts = CYCLE\n  end\n'
            '  if VALUE == 0 and ts != 0 then\n    set t28 = t28 + (CYCLE - ts)\n    set ts = 0\n  end\nend\n')


def counters(di_lines=()):
    """Running totals: interrupts taken, AY data writes (port 0xBFFD), port 0xFE writes, master cycles spent
    with NR 7 non-zero (hook time: every engine switches to 28 MHz on hook entry), samples of IFF1 = 0
    at the given scanlines (time with interrupts held off) and the longest gap between two interrupts taken
    (MG, master cycles; a caller resets mg to window it)."""
    s = COUNTERS
    for ln in di_lines:
        s += 'on scanline %d do\n  if IFF1 == 0 then\n    set ndi = ndi + 1\n  end\nend\n' % ln
    return s


CNT = 'INT=${nint} AY=${nay} BP=${nbp} T28=${t28} DI=${ndi} MG=${mg}'


# ---- running -----------------------------------------------------------------------------------------------
def binary():
    b = os.environ.get('NEXCLASH_JNEXT') or shutil.which('jnext')
    if not b:
        raise SystemExit('JNext not found: put jnext on PATH or set NEXCLASH_JNEXT (docs/CHECKS.md)')
    return b


def card(path=None):
    c = path or os.environ.get('NEXCLASH_JNEXT_CARD')
    if not c or not os.path.isfile(c):
        raise SystemExit('no SD card image: --card CARD.img or NEXCLASH_JNEXT_CARD (NextZXOS card; opened read-only)')
    return os.path.abspath(c)


def launch(prog, script, d, frames, card_img, home=None, extra=()):
    """Start one headless run in folder d (run.jds, run.log); returns the Popen. frames = from the start."""
    os.makedirs(d, exist_ok=True)
    home = os.path.abspath(home or os.environ.get('NEXCLASH_JNEXT_HOME') or os.path.join(d, '..', '.jnext_home'))
    os.makedirs(home, exist_ok=True)
    tmp = os.path.join(home, 'tmp')
    os.makedirs(tmp, exist_ok=True)
    open(os.path.join(d, 'run.jds'), 'w').write(script)
    cmd = [binary(), '--headless', '--silent', '--sdcard', card_img, '--sdcard-readonly', '--load', os.path.abspath(prog),
           '--script', 'run.jds', '--delayed-automatic-exit-frames', str(frames + start_frame(prog) + 400),
           '--log-file', 'run.log'] + list(extra)
    env = dict(os.environ, HOME=home, TMPDIR=tmp)
    return subprocess.Popen(cmd, cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def run_all(jobs, timeout=7200):
    """jobs: [(prog, script, d, frames, card, home)] run in parallel -> [return codes]."""
    ps = [launch(*j) for j in jobs]
    out = []
    for p in ps:
        try:
            out.append(p.wait(timeout=timeout))
        except subprocess.TimeoutExpired:
            p.kill()                        # our own child, by PID
            out.append('timeout')
    return out


LINE = re.compile(r'\] (\w+) ((?:\w+=-?\d+ ?)+)\s*\[client')


def records(log, tags=None):
    """Script log lines `TAG k=v ...` (decimal values) -> [(tag, {k: v})], in order."""
    out = []
    for ln in open(log, errors='replace'):
        m = LINE.search(ln)
        if m and (tags is None or m.group(1) in tags):
            out.append((m.group(1), {k: int(v) for k, v in (kv.split('=') for kv in m.group(2).split())}))
    return out


def unwrap(rows, keys=('C', 'T28')):
    """JNext script arithmetic is 32-bit signed: CYCLE (the 28 MHz clock) wraps after about 76 s. Rows in
    order -> the same rows with those counters made monotonic."""
    for k in keys:
        add, last = 0, None
        for r in rows:
            if k not in r:
                continue
            v = r[k] + add
            if last is not None and v < last - (1 << 30):
                add += 1 << 32
                v += 1 << 32
            r[k] = last = v
    return rows


def check_start(log, prog):
    """'' or a warning: the .nex did not start at the frame the schedule assumed."""
    st = [r['F'] for t, r in records(log, ('START',))]
    if prog.lower().endswith('.nex') and st and st[0] != NEX_START:
        return 'WARNING: %s started at frame %d, not %d: inputs are offset' % (os.path.basename(prog), st[0], NEX_START)
    return ''


def errors(log):
    return [ln.strip()[:160] for ln in open(log, errors='replace') if '[error]' in ln][:5]


# ---- machine state (.jns) ---------------------------------------------------------------------------------
def rgb333(v):
    r, g, b = v >> 6 & 7, v >> 3 & 7, v & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


class Frame:
    """One JNext .jns snapshot: the sprite layer (rendered), the ULA screen bytes and palettes."""

    def __init__(self, path):
        z = zipfile.ZipFile(path)
        self.path = path
        self.spr = json.loads(z.read('state/sprites.json'))
        self.pal = json.loads(z.read('state/palette.json'))
        self.ren = json.loads(z.read('state/renderer.json'))
        self.patterns = z.read('mem/sprite-patterns.bin')
        vram = z.read('mem/bank5-vram.bin')
        shadow = self.ren.get('shadow_screen_en') and 'mem/bank7-bram.bin' in z.namelist()
        self.ula = (z.read('mem/bank7-bram.bin') if shadow else vram)[:6912]
        self.attrs = bytes.fromhex(self.spr['attributes'])
        p = bytes.fromhex(self.pal['sprite_rgb333'])
        base = 512 if self.pal.get('active_spr_second') else 0
        self.spal = [rgb333(p[base + 2 * i] | p[base + 2 * i + 1] << 8) for i in range(256)]
        u = bytes.fromhex(self.pal['ula_rgb333'])
        base = 512 if self.pal.get('active_ula_second') else 0
        self.upal = [rgb333(u[base + 2 * i] | u[base + 2 * i + 1] << 8) for i in range(256)]
        self.transp = self.pal.get('sprite_transparency', 0xE3)
        self.on = self.spr.get('sprites_visible', True) and self.ren.get('sprite_en', True)

    def sprites(self):
        """Visible sprites: [dict(n, x, y, w, h, px={(dx, dy): rgb}, anchor, sig)] in display coordinates
        (paper top-left = (32, 32)). Anchors, composite and unified relatives, 4- and 8-bit patterns, mirror,
        rotate and scale; not handled: the clip window beyond the paper, collision, priorities."""
        out, anc = [], None
        a = self.attrs
        for n in range(128):
            b0, b1, b2, b3 = a[5 * n:5 * n + 4]
            b4 = a[5 * n + 4] if b3 & 0x40 else 0
            rel = b3 & 0x40 and (b4 & 0xC0) == 0x40
            if not rel:
                h4 = bool(b4 & 0x80)
                anc = dict(n=n, x=b0 | (b2 & 1) << 8, y=b1 | (b4 & 1) << 8, vis=bool(b3 & 0x80), pat=b3 & 0x3F,
                           h4=h4, n6=b4 >> 6 & 1 if h4 else 0, pal=b2 >> 4, xm=b2 >> 3 & 1, ym=b2 >> 2 & 1,
                           rot=b2 >> 1 & 1, sx=1 << (b4 >> 3 & 3), sy=1 << (b4 >> 1 & 3), uni=bool(b4 & 0x20))
                s = dict(anc)
            else:
                if anc is None:
                    continue
                dx, dy = b0 - 256 if b0 > 127 else b0, b1 - 256 if b1 > 127 else b1
                xm, ym, rot = b2 >> 3 & 1, b2 >> 2 & 1, b2 >> 1 & 1
                sx, sy = 1 << (b4 >> 3 & 3), 1 << (b4 >> 1 & 3)
                if anc['uni']:
                    if anc['rot']:
                        dx, dy = -dy, dx
                    if anc['xm']:
                        dx = -dx
                    if anc['ym']:
                        dy = -dy
                    dx, dy = dx * anc['sx'], dy * anc['sy']
                    xm, ym, rot = xm ^ anc['xm'], ym ^ anc['ym'], rot ^ anc['rot']
                    sx, sy = anc['sx'], anc['sy']
                s = dict(n=n, x=(anc['x'] + dx) & 0x1FF, y=(anc['y'] + dy) & 0x1FF, vis=anc['vis'] and bool(b3 & 0x80),
                         pat=((anc['pat'] if b4 & 1 else 0) + (b3 & 0x3F)) & 0x3F, h4=anc['h4'],
                         n6=b4 >> 5 & 1 if anc['h4'] else 0, pal=((anc['pal'] if b2 & 1 else 0) + (b2 >> 4)) & 15,
                         xm=xm, ym=ym, rot=rot, sx=sx, sy=sy)
            if not s['vis']:
                continue
            px = self._pixels(s)
            if not px:
                continue
            s['anchor'] = anc['n']
            s['px'] = px
            s['w'], s['h'] = 16 * s['sx'], 16 * s['sy']
            s['sig'] = hashlib.md5(repr(sorted(px.items())).encode()).hexdigest()[:12]
            out.append(s)
        return out

    def _pixels(self, s):
        if s['h4']:
            off = (s['pat'] << 1 | s['n6']) * 128
            raw = self.patterns[off:off + 128]
            idx = [v for b in raw for v in (b >> 4, b & 15)]
            tr = self.transp & 15
            col = lambda v: None if v == tr else self.spal[(s['pal'] << 4 | v) & 255]
        else:
            off = s['pat'] * 256
            idx = list(self.patterns[off:off + 256])
            col = lambda v: None if v == self.transp else self.spal[(v + (s['pal'] << 4)) & 255]
        px = {}
        for i, v in enumerate(idx):
            c = col(v)
            if c is None:
                continue
            x, y = i & 15, i >> 4
            if s['rot']:
                x, y = 15 - y, x
            if s['xm']:
                x = 15 - x
            if s['ym']:
                y = 15 - y
            for yy in range(s['sy']):
                for xx in range(s['sx']):
                    px[(x * s['sx'] + xx, y * s['sy'] + yy)] = c
        return px

    def layer(self, sprites=None):
        """{(x, y): rgb} of the sprite layer over the paper (later sprites on top, as the Next draws them
        with zero_on_top off), paper coordinates 0-255 x 0-191."""
        out = {}
        if not self.on:
            return out
        x0, y0, x1, y1 = PAPER
        for s in (self.sprites() if sprites is None else sprites):
            for (dx, dy), c in s['px'].items():
                x, y = (s['x'] + dx) & 0x1FF, (s['y'] + dy) & 0x1FF
                if x0 <= x < x1 and y0 <= y < y1:
                    out[(x - x0, y - y0)] = c
        return out

    def figures(self):
        """Sprites joined into figures: an anchor with its relatives, then figures whose boxes touch."""
        groups = {}
        for s in self.sprites():
            groups.setdefault(s['anchor'], []).append(s)
        figs = []
        for ss in groups.values():
            px = {}
            for s in ss:
                for (dx, dy), c in s['px'].items():
                    px[((s['x'] + dx) & 0x1FF, (s['y'] + dy) & 0x1FF)] = c
            figs.append(px)
        merged = True
        while merged:
            merged = False
            for i in range(len(figs)):
                for j in range(i + 1, len(figs)):
                    if _touch(figs[i], figs[j]):
                        figs[i].update(figs.pop(j))
                        merged = True
                        break
                if merged:
                    break
        return figs

    def attr_rgb(self, cell):
        """(ink, paper) colours of an attribute cell from the ULA palette (bright: entries 8-15 / 24-31)."""
        a = self.ula[6144 + cell]
        br = 8 if a & 0x40 else 0
        return self.upal[(a & 7) + br], self.upal[16 + (a >> 3 & 7) + br]


def _touch(a, b):
    if not a or not b:
        return False
    ax = [p[0] for p in a]
    ay = [p[1] for p in a]
    bx = [p[0] for p in b]
    by = [p[1] for p in b]
    if min(ax) > max(bx) + 1 or min(bx) > max(ax) + 1 or min(ay) > max(by) + 1 or min(by) > max(ay) + 1:
        return False
    sb = set(b)
    return any((x + dx, y + dy) in sb for x, y in a for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def png_paper(path):
    """The paper area of a JNext PNG (640 x 512 = 2x), as a 256 x 192 RGB image."""
    from PIL import Image
    im = Image.open(path).convert('RGB')
    s = im.width // 320
    x0, y0, x1, y1 = PAPER
    return im.crop((x0 * s, y0 * s, x1 * s, y1 * s)).resize((256, 192), Image.NEAREST)


def contact(paths, out, cols=6, label=True):
    """A contact sheet of JNext PNGs (half size, file names on them)."""
    from PIL import Image, ImageDraw
    paths = [p for p in paths if p and os.path.exists(p)]
    if not paths:
        return None
    ims = [Image.open(p).convert('RGB') for p in paths]
    w, h = ims[0].width // 2, ims[0].height // 2
    sheet = Image.new('RGB', (w * min(cols, len(ims)), h * ((len(ims) + cols - 1) // cols)))
    for i, (p, im) in enumerate(zip(paths, ims)):
        im = im.resize((w, h))
        if label:
            ImageDraw.Draw(im).text((3, 3), os.path.basename(os.path.dirname(p)) + '/' + os.path.basename(p), fill=(255, 255, 0))
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)
    return out


def result_block(lines, path=None):
    """Print the result block (the lines a proof record quotes) and keep a copy in path."""
    txt = '\n'.join(lines)
    print(txt)
    if path:
        open(path, 'w').write(txt + '\n')
    return txt



# ---- selftest --tools -------------------------------------------------------------------------------------
def selfcheck():
    """Each play check's detectors on synthetic data: [(name, failures)]."""
    from . import soak, pace, flicker, looksheet
    bad = []
    rows = unwrap([dict(C=v) for v in (2 ** 31 - 10, -2 ** 31 + 5, -2 ** 31 + 50)])
    if [r['C'] for r in rows] != [2 ** 31 - 10, 2 ** 31 + 5, 2 ** 31 + 50]:
        bad.append(('unwrap', rows))
    s = schedule(GENERIC, 3000, 7)
    if s != schedule(GENERIC, 3000, 7) or not s or s[0][0] < GENERIC['play_from']:
        bad.append('schedule not repeatable')
    if down(['q', 'K:FIRE', 'K:UP']) != '  press "q"\n  joystick 1 24\n':
        bad.append(('keys', down(['q', 'K:FIRE', 'K:UP'])))
    return [('play checks: jnext runner (32-bit cycle unwrap, repeatable input, keys)', bad),
            ('soak: still-picture and tight-loop detectors (synthetic)', soak.selfcheck()),
            ('pace: penalty by update windows, quiet / busy thirds, lockstep (synthetic)', pace.selfcheck()),
            ('flicker: out of step, vanished figure, one-frame attribute change (synthetic)', flicker.selfcheck()),
            ('looksheet: straight cut, drawn line, vanishing colour, white rim (synthetic)', looksheet.selfcheck())]


def live_check(z80, work):
    """JNext end to end on a reference game: the original against itself must pace at exactly 0% in
    lockstep and soak with the same pictures. -> (name, ok, info), or None without JNext and a card."""
    import contextlib
    import io as _io
    try:
        binary()
        card()
    except SystemExit:
        return None
    from . import soak, pace
    out = os.path.join(work, 'play')
    with contextlib.redirect_stdout(_io.StringIO()):
        pace.main([z80, '--original', z80, '--probe', '40092', '--updates', '100', '--window', '10',
                   '-o', os.path.join(out, 'pace')])
        soak.main([z80, '--original', z80, '--minutes', '0.5', '--static', '5', '-o', os.path.join(out, 'soak')])
    p = json.load(open(os.path.join(out, 'pace', 'pace.json')))['result'] or {}
    k = json.load(open(os.path.join(out, 'soak', 'soak.json')))
    pen = p.get('phases', [[None, {}]])[0][1].get('penalty')
    same = k['build']['distinct'] == k['original']['distinct'] > 10 and not k['build']['static'] and not k['build']['loops']
    return ('play checks in JNext: Chuckie Egg against itself paces at 0.00% over 100 updates (probe 40092) '
            'and soaks 0.5 min with the same pictures', pen == 0.0 and same, (pen, k['build']['distinct'], k['original']['distinct']))
