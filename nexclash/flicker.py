"""`python -m nexclash.flicker BUILD.nex [--original ORIG] [--profile P.json] [--probe ADDR] --from F --frames N`
- flicker check: every video frame captured.

Plays the build (and the original, the control) in headless JNext with the profile's input and saves, for
each video frame F..F+N, the picture (PNG) and the machine (.jns: sprite attributes and patterns, palettes,
the ULA screen; nexclash/jnext.py renders the sprite layer from them exactly). Flags:
- OUT OF STEP: the sprite layer and the ULA under the figures change on different frames (sprites switched
  a frame before the game's ULA drawing under them caught up, or the reverse): the picture between shows
  new sprites over the old screen (Nightshade's blink, 2026-11-04: the commit switched every sprite before
  the game's own blits had drawn).
- VANISHED: a figure of the sprite layer missing for one frame and back the next.
- picture changes per game update (needs a probe: the address run once per update; from the profile or
  --probe): more than one change a game update means the screen showed in-between pictures. The original
  is the baseline (a game can tear on its own).
- attribute cells that change for one frame and change back (Atic Atac's red doors), and one-frame picture
  transients (pixels that change for one frame and back), build against original.
Keeps the pictures and snapshots of the flagged frames (flicker/build/flag_*) and a strip of them
(flicker/strip.png: before, the frame, after); the result block (flicker/RESULT.txt) is what a proof
record quotes. Warns, never refuses. Origin: pilot nightshade blinkstats / leonis_triage attrblink, blink.
docs/CHECKS.md.
"""
import argparse
import glob
import json
import os
import shutil
from . import jnext as J


def script(prog, prof, start, frames, seed, orig, d, probe):
    s = J.Script(J.start_frame(prog))
    s.start_line(prog)
    s.start_keys(prof, orig)
    s.frame_input(J.schedule(prof, start + frames + 2, seed, orig))
    if probe is not None:
        s.rule('on execute %d do\n  log "U F=${FRAME}"\nend\n' % probe)
    for f in range(start - 1, start + frames + 2):
        s.at(f, '  screenshot "%s/f%06d.png"\n  save_snapshot "%s/f%06d.jns"\n' % (d, f, d, f))
    s.exit_at(start + frames + 3)
    return s.text()


def cell_of(addr):
    """ULA screen offset (0-6911) -> attribute cell 0-767."""
    if addr >= 6144:
        return addr - 6144
    y = (addr >> 8 & 7) | (addr >> 2 & 0x38) | (addr >> 5 & 0xC0)
    return (y >> 3) * 32 + (addr & 31)


def changed_cells(a, b):
    return {cell_of(i) for i in range(6912) if a[i] != b[i]}


def attr_changes(a, b):
    return {i for i in range(768) if a[6144 + i] != b[6144 + i]}


def cells_of(mask, grow=1):
    out = set()
    for x, y in mask:
        cx, cy = x >> 3, y >> 3
        for dy in range(-grow, grow + 1):
            for dx in range(-grow, grow + 1):
                if 0 <= cx + dx < 32 and 0 <= cy + dy < 24:
                    out.add((cy + dy) * 32 + cx + dx)
    return out


def analyse(states):
    """states: [(frame, sprite layer {(x, y): rgb}, ULA bytes, [figure pixel sets])] in frame order ->
    out-of-step frames, vanished figures, attribute one-frame transients."""
    step, vanish, attr = [], [], []
    sig = [hash(frozenset(L.items())) for _, L, _, _ in states]
    for i in range(1, len(states) - 1):
        f, L, U, figs = states[i]
        _, Lp, Up, figp = states[i - 1]
        _, Ln, Un, _ = states[i + 1]
        area = cells_of(set(Lp) | set(L))
        s_now, s_next = sig[i] != sig[i - 1], sig[i + 1] != sig[i]
        u_now = bool(changed_cells(Up, U) & area)
        u_next = bool(changed_cells(U, Un) & cells_of(set(L) | set(Ln)))
        pts = set(Lp) | set(L) | set(Ln)
        box = (min(x for x, _ in pts) - 8, min(y for _, y in pts) - 8, max(x for x, _ in pts) + 9,
               max(y for _, y in pts) + 9) if pts else (0, 0, 256, 192)
        if s_now and not u_now and u_next and not s_next:
            step.append((f, 'sprites first', box))
        elif u_now and not s_now and s_next and not u_next:
            step.append((f, 'ULA first', box))
        for fig in figp:                              # a figure at i-1 missing at i and back at i+1
            if len(fig) < 8:
                continue
            xs, ys = [p[0] for p in fig], [p[1] for p in fig]
            box = (min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4)
            inb = lambda m: sum(1 for x, y in m if box[0] <= x <= box[2] and box[1] <= y <= box[3])
            if inb(L) < 0.3 * len(fig) and inb(Ln) >= 0.7 * len(fig):
                vanish.append((f, box))
        ev = [c for c in attr_changes(Up, U) if Up[6144 + c] == Un[6144 + c]]
        if ev:
            attr.append((f, [(c, Up[6144 + c], U[6144 + c]) for c in ev]))
    return step, vanish, attr


def pictures(d, a, b):
    return {f: J.png_paper(os.path.join(d, 'f%06d.png' % f)) for f in range(a - 1, b + 3)
            if os.path.exists(os.path.join(d, 'f%06d.png' % f))}


def picture_stats(ims, a, b):
    """(frames whose picture changed, frames with one-frame transient pixels) over frames a..b."""
    from PIL import ImageChops
    ch, tr = [], []
    for f in range(a, b + 1):
        if f - 1 not in ims or f not in ims:
            continue
        if ImageChops.difference(ims[f], ims[f - 1]).getbbox():
            ch.append(f)
            if f + 1 in ims and not ImageChops.difference(ims[f - 1], ims[f + 1]).getbbox():
                tr.append(f)
    return ch, tr


def seen(ims, f, box):
    """A state-level out-of-step frame is SEEN when the picture inside the figures' box changes on two
    frames running among f, f+1, f+2 (an in-between picture was on screen). The snapshot is taken at the
    frame edge, the picture while the beam draws: a switch finished just after the edge but before the
    figures' lines is not seen (Nightshade's fixed build ends its burst on lines 0-7)."""
    from PIL import ImageChops
    c = []
    for g in (f, f + 1, f + 2):
        if g - 1 not in ims or g not in ims:
            return True
        c.append(bool(ImageChops.difference(ims[g].crop(box), ims[g - 1].crop(box)).getbbox()))
    return (c[0] and c[1]) or (c[1] and c[2])


def updates(d, off, a, b):
    return [r['F'] - off for t, r in J.records(os.path.join(d, 'run.log'), ('U',)) if a <= r['F'] - off <= b]


def load_states(d, a, b):
    out = []
    for f in range(a - 1, b + 2):
        p = os.path.join(d, 'f%06d.jns' % f)
        if os.path.exists(p):
            fr = J.Frame(p)
            sp = fr.sprites()
            figs = [{(x - J.PAPER[0], y - J.PAPER[1]) for x, y in g} for g in fr.figures()]
            out.append((f, fr.layer(sp), fr.ula, figs))
    return out


def strip(d, frames, out):
    from PIL import Image, ImageDraw
    rows = []
    for f in frames[:12]:
        row = Image.new('RGB', (3 * 256 + 4, 192), (40, 40, 40))
        for k, g in enumerate((f - 1, f, f + 1)):
            p = os.path.join(d, 'f%06d.png' % g)
            if os.path.exists(p):
                row.paste(J.png_paper(p), (k * 258, 0))
        ImageDraw.Draw(row).text((262, 2), 'frame %d (middle)' % f, fill=(255, 255, 0))
        rows.append(row)
    if not rows:
        return None
    im = Image.new('RGB', (rows[0].width, 194 * len(rows)), (0, 0, 0))
    for i, r in enumerate(rows):
        im.paste(r, (0, 194 * i))
    im.save(out)
    return out


def keep_flagged(d, frames):
    for f in set(frames):
        k = os.path.join(d, 'flag_%06d' % f)
        os.makedirs(k, exist_ok=True)
        for g in (f - 1, f, f + 1):
            for ext in ('png', 'jns'):
                p = os.path.join(d, 'f%06d.%s' % (g, ext))
                if os.path.exists(p):
                    shutil.copy(p, k)


def short(fr, n=10):
    return ', '.join(str(x) for x in fr[:n]) + (' ...' if len(fr) > n else '')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('build', help='the build (.nex)')
    ap.add_argument('--original', help='the control: the original .z80 or the plain .nex')
    ap.add_argument('--profile', help='input profile JSON (nexclash/jnext.py; default generic)')
    ap.add_argument('--probe', help='address run once per game update (default: the profile\'s)')
    ap.add_argument('--from', dest='start', type=int, required=True, help='first frame to check (from the program start)')
    ap.add_argument('--frames', type=int, default=300, help='video frames to check (default 300)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--card', help='NextZXOS SD card image (default $NEXCLASH_JNEXT_CARD)')
    ap.add_argument('--jnext-home', help='HOME for JNext (default OUT/.jnext_home)')
    ap.add_argument('-o', '--out', default='flicker', help='output folder (default ./flicker)')
    ap.add_argument('--keep', action='store_true', help='keep every frame (default: flagged frames only)')
    ap.add_argument('--reuse', action='store_true', help='analyse the frames a --keep run left, without running JNext')
    a = ap.parse_args(argv)
    prof = J.load_profile(a.profile)
    probe = a.probe or prof.get('probe')
    probe = J.num(probe) if probe else None
    card = J.card(a.card)
    out = os.path.abspath(a.out)
    runs = [('build', a.build, False)] + ([('original', a.original, True)] if a.original else [])
    jobs = []
    for tag, prog, orig in runs:
        d = os.path.join(out, tag)
        os.makedirs(d, exist_ok=True)
        if a.reuse:
            continue
        for x in glob.glob(os.path.join(d, 'f*.*')):
            os.remove(x)
        jobs.append((prog, script(prog, prof, a.start, a.frames, a.seed, orig, d, probe), d, a.start + a.frames + 5,
                     card, a.jnext_home))
    J.run_all(jobs)
    b0, b1 = a.start, a.start + a.frames - 1
    lines = ['FLICKER  %s (%s)%s, video frames %d-%d, probe %s, profile %s' % (
        os.path.basename(a.build), J.md5(a.build)[:8],
        ' vs %s (%s)' % (os.path.basename(a.original), J.md5(a.original)[:8]) if a.original else '',
        b0, b1, '0x%04X' % probe if probe is not None else 'none', prof.get('name'))]
    res, flagged = {}, []
    for tag, prog, orig in runs:
        d = os.path.join(out, tag)
        errs = J.errors(os.path.join(d, 'run.log'))
        if errs:
            lines.append('%-9s: JNext errors: %s' % (tag, '; '.join(errs[:2])))
        ims = pictures(d, b0, b1)
        ch, tr = picture_stats(ims, b0, b1)
        up = updates(d, J.start_frame(prog), b0, b1) if probe is not None else []
        st = load_states(d, b0, b1)
        cand, van, attr = analyse(st)
        step = [(f, k) for f, k, box in cand if seen(ims, f, box)]
        van = [(f, box) for f, box in van if seen(ims, f, tuple(max(0, v) for v in box))]
        res[tag] = dict(changes=len(ch), updates=len(up), transients=tr, step=step, vanish=van,
                        attr=[(f, len(c)) for f, c in attr], step_state_only=len(cand) - len(step))
        per = ' = %.2f a game update' % (len(ch) / len(up)) if up else ''
        lines.append('%-9s: picture changes %d in %d frames, game updates %d%s' % (tag, len(ch), b1 - b0 + 1, len(up), per))
        if tag == 'build' or step or van:
            lines.append('  out of step (sprites and the ULA under them on different frames, seen): %d frames%s%s' % (
                len(step), ' [%s]' % short(['%d %s' % x for x in step], 6) if step else '',
                '; %d more at the frame edge only, not on screen' % res[tag]['step_state_only'] if res[tag]['step_state_only'] else ''))
            lines.append('  figure vanished for one frame: %d%s' % (len(van), ' [%s]' % short([str(f) for f, _ in van]) if van else ''))
        lines.append('  attribute cells changed for one frame and back: %d frames, %d cells%s' % (
            len(attr), sum(len(c) for _, c in attr),
            ' (commonest %s)' % ', '.join('%02X->%02X x%d' % (k[0], k[1], n) for k, n in _pairs(attr)) if attr else ''))
        lines.append('  one-frame picture transients: %d frames%s' % (len(tr), ' [%s]' % short([str(x) for x in tr]) if tr else ''))
        if tag == 'build':
            flagged = sorted({f for f, _ in step} | {f for f, _ in van})
            keep_flagged(d, flagged + [f for f, _ in attr][:20])
            strip(d, flagged or [f for f, _ in attr], os.path.join(out, 'strip.png'))
    rb, ro = res['build'], res.get('original')
    warn = []
    if rb['step']:
        warn.append('%d out-of-step frames' % len(rb['step']))
    if rb['vanish']:
        warn.append('%d vanished figures' % len(rb['vanish']))
    if ro and rb['updates'] and ro['updates'] and rb['changes'] / rb['updates'] > ro['changes'] / ro['updates'] + 0.1:
        warn.append('more picture changes a game update than the original (%.2f against %.2f)' % (
            rb['changes'] / rb['updates'], ro['changes'] / ro['updates']))
    if ro and len(rb['attr']) > len(ro['attr']):
        warn.append('more one-frame attribute changes than the original (%d against %d frames)' % (len(rb['attr']), len(ro['attr'])))
    lines.append('RESULT: %s (warns only)%s' % ('WARNING: ' + '; '.join(warn) if warn else 'no flicker found',
                                                 '; strip %s' % os.path.join(a.out, 'strip.png') if flagged or rb['attr'] else ''))
    J.result_block(lines, os.path.join(a.out, 'RESULT.txt'))
    json.dump(res, open(os.path.join(a.out, 'flicker.json'), 'w'), indent=1, default=list)
    if not a.keep and not a.reuse:
        for tag, _, _ in runs:
            for x in glob.glob(os.path.join(out, tag, 'f*.*')):
                os.remove(x)
    return 0


def _pairs(attr, n=4):
    from collections import Counter
    c = Counter((a, b) for _, ev in attr for _, a, b in ev)
    return c.most_common(n)


def selfcheck():
    """Synthetic frames: a figure that switches a frame before the ULA under it (out of step), one that
    switches with it (clean), a figure missing for one frame (vanished), an attribute cell blinking."""
    bad = []
    blank = bytes(6912)

    def ula(at=None, val=0xFF, attr=None):
        u = bytearray(blank)
        if at is not None:
            u[at] = val
        if attr is not None:
            u[6144 + attr[0]] = attr[1]
        return bytes(u)

    def spr(x):
        return {(x + i, 8 + j): (255, 255, 255) for i in range(8) for j in range(8)}

    fig = lambda L: [set(L)] if L else []
    # frames 0-3: sprite moves at 1, ULA under it (cell row 1, byte at y=8 x=0..7) changes at 2 -> out of step at 1
    u1 = ula(0x0100 >> 8 << 8 | 0)                       # offset 0x0100 = y 1 in row 0 (cell 0)
    st = [(0, spr(0), blank, fig(spr(0))), (1, spr(2), blank, fig(spr(2))), (2, spr(2), u1, fig(spr(2))),
          (3, spr(2), u1, fig(spr(2)))]
    step, van, attr = analyse(st)
    if [f for f, _, _ in step] != [1]:
        bad.append(('out of step', step))
    st = [(0, spr(0), blank, fig(spr(0))), (1, spr(2), u1, fig(spr(2))), (2, spr(2), u1, fig(spr(2)))]
    if analyse(st)[0]:
        bad.append('clean switch flagged')
    st = [(0, spr(40), blank, fig(spr(40))), (1, {}, blank, []), (2, spr(40), blank, fig(spr(40)))]
    if [f for f, _ in analyse(st)[1]] != [1]:
        bad.append(('vanish', analyse(st)[1]))
    st = [(0, {}, ula(attr=(5, 0x43)), []), (1, {}, ula(attr=(5, 0x42)), []), (2, {}, ula(attr=(5, 0x43)), [])]
    if analyse(st)[2] != [(1, [(5, 0x43, 0x42)])]:
        bad.append(('attr', analyse(st)[2]))
    if cell_of(0x0100) != 0 or cell_of(0x0020) != 32 or cell_of(6144 + 33) != 33:
        bad.append('cell_of')
    return bad


if __name__ == '__main__':
    raise SystemExit(main())
