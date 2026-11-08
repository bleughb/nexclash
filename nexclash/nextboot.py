"""Simulated Next boot of a .nex built by z80tonex: runs the stub, the alt ROM fill (if any) and the
start-up tail on a model of the Next memory system until the snapshot PC, then checks the result.

Model (Part A facts only): 8K pages; MMU slots 0-7 via NEXTREG $50-$57, $FF in slot 0/1 = ROM;
an unlocked 7FFD/1FFD write remaps slots 0/1 to ROM and 6/7 to the 7FFD bank; 7FFD bit 5 locks
paging, NEXTREG $08 bit 7 = 1 unlocks it; ROM number = 1FFD bit 2 (hi) + 7FFD bit 4 (lo);
alt ROM $8C: bit 7 enable, bit 6 write mode (reads ROM, writes alt), image = ROM number bit 0.
NEX launch state: paging UNLOCKED (every hardware-tested build pages with legacy writes without
unlocking first) and ROM 0 selected (worst case: the stub must select ROM3 itself). Only ROM3 (48K
BASIC) is modelled (ROMs 0-2 too when the 64K enNextZX.rom is given); reading another ROM fails the check.
NR 0x1E/0x1F read a line counter that steps one line per NR 0x1F read (raster()), so a set-up's wait on the
raster line (a loading picture's hold) ends; no key is ever pressed. The NEX entry bank is ignored: the boot
starts at bank 10's stub, so a _loading.nex's picture stub is not run here (its engine's loading_check runs it).

The system ROM3 is what the Next really has (docs/REFACTOR.md 7): ROM3 of NextZXOS's enNextZX.rom
(enNextLG.rom's ROM3 is byte-identical), from the file named by $NEXCLASH_NEXT_ROM or `--next-rom PATH`
(the whole 64K enNextZX.rom, or its 16K ROM3; never in this repo: copy it from your card,
MACHINES/NEXT/enNextZX.rom). Without it Sinclair's ROM stands in and rom_model() says so. Verifiers
take the alt ROM image from alt_image(patch): what the stub leaves there, over that ROM3.

    python -m nexclash.nextboot GAME_sprites.nex GAME.z80 [PATCHED_REFERENCE_UNUSED]
"""
import os
import sys
from .dizzy6 import _rw_simulator
from . import z80tonex as zt
from .build import rom48


def nex_screen_size(flags):
    """Bytes between a .nex header and its first bank, from header byte 10 (as NEXLOAD and nxc.screen_size read
    them): a 512-byte palette unless bit 7 or a ULA / hi-res / hi-colour screen, then each screen. 0 = none."""
    if not flags:
        return 0
    if flags & 0x60:
        raise ValueError('a .nex V1.3 loading screen (byte 10 bit 5 or 6) is not modelled')
    sizes = ((1, 49152), (2, 6912), (4, 12288), (8, 12288), (16, 12288))
    return (0 if flags & 0x9A else 512) + sum(n for bit, n in sizes if flags & bit)


def load_nex(path):
    d = open(path, 'rb').read()
    present = [b for b in range(112) if d[18 + b]]
    banks, off = {}, 512 + nex_screen_size(d[10])     # a header loading screen (Beyond the Ice Palace) comes first
    for b in zt.BANK_FILE_ORDER:
        if b in present:
            banks[b] = d[off:off + 16384]
            off += 16384
    return banks, d[12] | d[13] << 8, d[14] | d[15] << 8


NEXT_ROM = None             # set by `nexclash.py ... --next-rom PATH`; else $NEXCLASH_NEXT_ROM
_ROM3 = {}


def system_rom3():
    """-> (16K ROM3 the Next pages as ROM 3, label). NextZXOS's when a path is given, else Sinclair's."""
    import hashlib
    import os
    path = NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM')
    if path not in _ROM3:
        if not path:
            _ROM3[path] = (rom48(), "Sinclair's 48K ROM (no --next-rom / NEXCLASH_NEXT_ROM: NextZXOS's ROM3 NOT modelled)")
        else:
            d = open(path, 'rb').read()
            if len(d) not in (16384, 65536):
                raise ValueError('%s: %d bytes; want enNextZX.rom (64K) or its ROM3 (16K)' % (path, len(d)))
            _ROM3[path] = (d[-16384:], 'ROM3 of %s (file md5 %s)' % (os.path.basename(path), hashlib.md5(d).hexdigest()[:8]))
    return _ROM3[path]


def rom_model():
    """One report line: which ROM3 the boot model and the verifiers use."""
    return system_rom3()[1]


def alt_image(patch, sysrom=None):
    """Alt ROM image 1 as the stub leaves it on the Next (z80tonex.altrom_fill): Sinclair's ROM (the
    whole-image fill) or the system ROM3 (old builds: `--altrom-fill rom3`), then the build's bytes
    lo..hi from patch.page and patch.altrom_low. The shared base of every verifier's alt ROM model:
    bytes outside lo..hi are what the Next has, not the page's (BRIEFING C2 #5)."""
    lo, hi = patch.altrom
    rom3 = sysrom or system_rom3()[0]
    img = bytearray(rom48()) if zt.altrom_whole(patch) else zt.rom3_fixups(bytearray(rom3), rom3)
    img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    if getattr(patch, 'altrom_low', None):
        img[0:0x2000] = patch.altrom_low[1]
    return img


def system_roms():
    """NextZXOS's four ROMs (enNextZX.rom, 64K) when given, else None (only ROM3 is modelled)."""
    import os
    path = NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM')
    if path and os.path.getsize(path) == 65536:
        d = open(path, 'rb').read()
        return [d[k * 16384:(k + 1) * 16384] for k in range(4)]
    return None


def system_rom0():
    """-> (16K ROM 0 the Next pages as ROM 0, label): NextZXOS's (the first 16K of the 64K file) when
    given, else the 128K ROM 0 (SkoolKit's) stands in."""
    import os
    path = NEXT_ROM or os.environ.get('NEXCLASH_NEXT_ROM')
    if path and os.path.getsize(path) == 65536:
        return open(path, 'rb').read()[:16384], 'ROM0 of %s' % os.path.basename(path)
    return zt.rom128_0(), 'the 128K ROM 0 (NextZXOS ROM0 NOT modelled)'


def alt_image0(patch, rom0=None):
    """Alt ROM image 0 as the Next holds it: the 128K ROM 0 + the build's bytes (z80tonex.altrom0), or for
    an older build its setup's copy of the Next's ROM 0 + the hook bytes lo..hi (Target Renegade)."""
    a0 = zt.altrom0(patch)
    lo, hi = a0 or patch.altrom
    img = bytearray(zt.rom128_0() if a0 else (rom0 or system_rom0()[0]))
    img[lo:hi] = patch.page[lo - 0x2000:hi - 0x2000]
    return img


def rom_view(patch, sysrom=None):
    """What the game sees at 0x0000-0x3FFF on the Next once the tail has run: the alt ROM image
    (alt_image), or for a slot-1 build the system ROM3's 0x0000-0x1FFF + its RAM page, or the ROM3."""
    rom = sysrom or system_rom3()[0]
    if getattr(patch, 'altrom', None):
        image = alt_image(patch, rom)
        if getattr(patch, 'ram_slot1_after_alt', False):
            image[0x2000:0x4000] = patch.page
        return image
    if getattr(patch, 'slot1', None) is not None and getattr(patch, 'page', None) is not None:
        return bytearray(rom[0:0x2000]) + bytearray(patch.page)
    return bytearray(rom)


def start_pc(nex):
    """The snapshot PC a built .nex jumps to (tail_of)."""
    return tail_of(nex)[0]


def tail_of(nex):
    """-> (snapshot PC, tail address, tail length) of a built .nex: the tail's JP (z80tonex.build_tail; the
    stub copies the tail with LD DE,tail / LD BC,len / LDIR / LD (tail+p3),A / JP tail, its bytes after)."""
    banks, _, _ = load_nex(nex)
    st = banks[zt.STUB_BANK][:0x1000]
    for i in range(len(st) - 14):
        if st[i] == 0x11 and st[i + 3] == 0x01 and st[i + 6:i + 8] == b'\xED\xB0' and st[i + 8] == 0x32 \
                and st[i + 11] == 0xC3 and st[i + 12:i + 14] == st[i + 1:i + 3]:
            n = st[i + 4] | st[i + 5] << 8
            t = st[i + 14:i + 14 + n]
            for k in (n - 3, n - 23):                       # compact tail / tail + its 20-byte register block
                if k > 0 and t[k] == 0xC3:
                    return t[k + 1] | t[k + 2] << 8, st[i + 1] | st[i + 2] << 8, n
    raise ValueError('%s: no z80tonex start-up tail found' % nex)


def boot_restores(nex, tail_pc, z80, sysrom=None):
    """A build whose start-up tail jumps to its own boot code instead of the game (the patch moved the snapshot PC:
    Beyond the Ice Palace's boot_resume puts 0x5B00-0x5BFF back): the addresses 0x5B00-0xBFFF holding the snapshot's
    bytes when the game starts, booted as NEXLOAD leaves the printer buffer. Empty when the tail jumps straight to the
    game (every other build: nothing changes for it) or that boot does not reach the snapshot's PC."""
    if z80 is None:
        return set()
    snap = zt.Z80Snapshot(z80)
    if snap.pc == tail_pc:
        return set()
    try:
        st = boot(nex, snap.pc, sysrom=sysrom, nexload=True)
    except (ValueError, RuntimeError):
        return set()
    return {a for a in range(0x5B00, 0xC000) if st['mem'][a] == snap.read(a)}


def rom_paths(nexes, rzxs, stop=None, sysrom=None, z80=None, known=(), start_pc=None):
    """Every ROM byte the ORIGINAL game runs or reads in its recordings, against what each built .nex
    gives it on the Next: the .nex booted over the system ROM3 (system_rom3(): NextZXOS's when given) to
    the game start - its alt ROM images, slot-1 page or the ROM3 itself. The per-event verifiers run
    patched code only from a hook to its return, so a ROM path outside the hooks (IM 1, a ROM print) never
    runs there: Starquake's UDG print into the hooks passed them. One replay per recording for all builds.
    -> {nex: (kind, lines, faults, coverage)}: kind 'alt' / 'slot1' / 'plain' ('boot': the .nex never reached the
    game start in boot(), a BOOT FAILED line, nothing replayed); coverage {recording: {frames, of, how, desync, rom1}}:
    how 'as recorded', 'last frame' (its port readings run out in the recording's last frame) or 'partial' (the
    replay desyncs earlier: frames 1..frames checked, said in the lines; never a raise); rom1 '48K' when a 128K
    recording keeps sync only on Sinclair's 48K ROM as ROM 1 (Knight Tyme), which the check then compares with;
    segments True when it keeps sync only with each segment started from its own snapshot (kt_rooms 48, Spellbound's
    t_rooms 57: a room per segment). On SkoolKit's 128K ROM 1 its keypad code (0x386E-0x3CFF) is listed,
    not compared, while it runs (the Next's ROM 3 has none: its fetches and its own reads, PC inside it); its call sites
    (0x004B ...) against the 48K ROM's bytes; game code reading those bytes as data is compared like any other read. faults = ROM addresses the game RUNS
    whose byte differs on the Next ('alt' / 'slot1': the build owns that ROM, each is a fault; 'plain':
    the Next's own ROM3 runs, reported only), and data reads of differing bytes that come from the Next's
    own ROM (the byte equals NextZXOS's there: Target Renegade e0b246e3's sound data); data reads of bytes
    the build wrote (an IM 2 vector) are listed only. Also the start-up tail (z80tonex): its bytes stay in
    game RAM, so the game must never read one before writing it (Match Day: the trophy's attributes).
    z80 (the build's snapshot): also the printer buffer bytes the .nex starts with differently, booted
    as NEXLOAD leaves it (NEXLOAD_PRINTER) - a warning: the stub puts it back only with
    keep_printer_buffer (BRIEFING C2 #36). A build whose tail jumps to its own boot code (boot_restores) is
    credited with the bytes that code puts back before the game starts: neither list holds those.
    start_pc: optional proven post-loader entry. Boot each NEX to this PC and begin ROM/tail
    observation only when the original replay reaches it. The engine must separately prove exact
    boot registers and game RAM there. A missing entry is INCOMPLETE, never silently skipped;
    the coverage records the excluded loader prefix. Default checks the entire recording.
    known: [(image, lo, hi, why)] differences a game's record accepts (its "rom_paths_known": Knight Tyme's Bridge
    star map, read from alt image 0 = the Next's ROM 0): listed as KNOWN, not faults; any other is a MISMATCH."""
    from skoolkit import ROM48, ROM128, read_bin_file
    from .simrun import play_rzx, rzx_frames
    builds, sysr = [], system_roms() or [None, None, None, sysrom or system_rom3()[0]]
    if sysrom is not None:
        sysr[3] = sysrom
    tails, out, restored = {}, {}, {}
    for nex in nexes:
        try:
            tails[nex] = tail_of(nex)
            st = boot(nex, tails[nex][0] if start_pc is None else start_pc, sysrom=sysrom or system_rom3()[0], nexload=z80 is not None)
            restored[nex] = boot_restores(nex, tails[nex][0], z80, sysrom or system_rom3()[0])
        except (ValueError, RuntimeError) as e:          # no tail / the boot never reaches the game start
            out[nex] = ('boot', ['%s: BOOT FAILED in the Next model (%s): its ROM paths are not checked'
                                 % (os.path.basename(nex), e)], {'boot': str(e)}, {})
            continue
        alt_on = bool(st['nr'].get(0x8C, 0) & 0x80)
        kind = 'alt' if alt_on else ('slot1' if st['mmu'][1] != 0xFF else 'plain')
        builds.append((nex, kind, alt_on, st, bytes(st['mem'][a] for a in range(0x4000)), 2 if st['p1ffd'] & 4 else 0))
    out.update({nex: (kind, [], {}, {}) for nex, kind, *_ in builds})
    if not builds:
        return out
    o48 = list(read_bin_file(ROM48, 16384))
    o128 = [list(read_bin_file(ROM128[0], 16384)), list(read_bin_file(ROM128[1], 16384))]
    pbuf = {}
    if z80 is not None:
        snap = zt.Z80Snapshot(z80)
        for nex, kind, alt_on, st, *_x in builds:
            pbuf[nex] = [a for a in range(0x5B00, 0x5C00) if st['mem'][a] != snap.read(a) and a not in restored[nex]]
    watch = {a for n in tails for a in range(tails[n][1], tails[n][1] + tails[n][2])} | {a for v in pbuf.values() for a in v}

    def replay(r, rom1, segs=False):
        """One replay of r; rom1: the ROM 1 a 128K recording ran on (None: SkoolKit's 128K ROM 1); segs: each
        segment from its own snapshot (simrun.play_rzx keep_snapshots)."""
        frame, seen, tabs, written, tread, desync, is128, only = [0], set(), [], set(), {}, [], [False], {}
        k128 = set()            # ROM 1 bytes only SkoolKit's 128K ROM 1 has (its keypad code; set in on_sim)
        entry_frame = [None if start_pc is not None else 0]
        later = [False]         # a later segment: the tail / printer buffer reads concern only the first

        class H:
            def on_sim(h, sim):
                h.is128 = is128[0] = hasattr(sim.memory, 'o7ffd')
                if h.is128 and rom1 is not None:            # the recording's ROM 1 (Knight Tyme: Sinclair's 48K ROM)
                    m = sim.memory
                    m.roms = (m.roms[0], list(rom1))
                    m.out7ffd(m.o7ffd)
                if tabs:                                    # the next segment's snapshot: same tables, same results;
                    later[0] = True                         # its RAM is that snapshot's, not the .nex's start state
                    return
                orig = ([o128[0], list(rom1)] if rom1 is not None else o128) if h.is128 else [o48, o48]
                if h.is128 and rom1 is None:
                    # SkoolKit's 128K ROM 1 is the 48K ROM + keypad code: new code at 0x386E-0x3CFF and 6 call sites
                    # into it (0x004B ...). The Next's ROM 3, a 128K game's ROM 1 there, is the 48K ROM: the call
                    # sites are compared with the 48K ROM's bytes, the keypad code is listed, not compared.
                    hy = list(o128[1])
                    for a in range(0x4000):
                        if hy[a] != o48[a]:
                            if a < KEYPAD_CODE:
                                hy[a] = o48[a]
                            else:
                                k128.add(a)
                    orig = [o128[0], hy]
                tabs[:] = []
                for nex, kind, alt_on, st, view, hi_rom in builds:
                    nx, d = {}, {}
                    for sel in (0, 1):
                        img = st['alt'][sel if h.is128 else 1] if alt_on else (
                            None if h.is128 and (hi_rom | sel) != 3 else view)      # another system ROM: not modelled
                        nx[sel] = img
                        d[sel] = {a for a in range(0x4000) if img[a] != orig[sel][a]} if img is not None else None
                    tabs.append((nex, nx, d, orig, {}))

            def on_read(h, a, pc, mem):
                if entry_frame[0] is None:
                    if pc != start_pc:
                        return
                    entry_frame[0] = frame[0]
                if a >= 0x4000:
                    if a in watch and a not in written and a not in tread and not later[0]:   # data or code fetch
                        if not (KEYPAD_CODE <= pc < 0x4000 and (mem.o7ffd >> 4) & 1):   # not by 128K-only ROM code
                            tread[a] = (pc, frame[0])
                    return
                sel = (mem.o7ffd >> 4) & 1 if h.is128 else 1
                seen.add((sel, a))
                if sel and a in k128 and KEYPAD_CODE <= pc < 0x4000:   # the 128K keypad code running: no Next ROM has
                    only.setdefault(a, (pc, frame[0]))       # it; a read of these bytes by any other code is compared
                    return
                ex = pc <= a <= pc + 3
                for nex, nx, d, orig, diff in tabs:
                    ds = d[sel]
                    if ds is None:
                        diff.setdefault(('?', sel, ''), (pc, frame[0]))
                    elif a in ds:
                        own = sysr[3 if sel else 0]          # where an old fill's byte came from (ROM3 / ROM 0)
                        k = (sel, a, 'run' if ex else ('next' if own is not None and own[a] == nx[sel][a] else 'data'))
                        if k not in diff:
                            diff[k] = (pc, frame[0], orig[sel][a], nx[sel][a])

            def on_write(h, a, v, pc, mem):
                if entry_frame[0] is not None and a in watch:
                    written.add(a)

            def on_frame(h, n):
                frame[0] = n

            def on_desync(h, n, msg):
                desync[:] = [n, msg]
        n = play_rzx(r, H(), stop=stop, keep_snapshots=segs)
        return dict(n=n, seen=seen, tabs=tabs, tread=tread, desync=desync, is128=is128[0], rom1=rom1, only=only,
                    segs=segs, entry_frame=entry_frame[0])

    for r in rzxs:
        name, (total, snaps) = os.path.basename(r), rzx_frames(r)
        want = min(stop, total) if stop else total
        # What real recordings contain (2026-11-04): a 128K recording made with Sinclair's 48K ROM as ROM 1 (Knight
        # Tyme: the 128K ROM 1 has keypad code at 0x386E on its ISR path), and one made of segments, each a new
        # start state (kt_rooms: a room per segment, by poke), where the stripped replay (autosaves) desyncs at the
        # second. A replay that desyncs before its last frame is tried that way too; the one that keeps sync longest
        # is the recording's, and says so.
        rp, early = replay(r, None), (lambda x: x['desync'] and x['desync'][0] < want)
        for rom1, segs in ((o48, False), (None, True), (o48, True)):
            if not early(rp) or (rom1 is not None and not rp['is128']) or (segs and snaps < 2):
                continue
            alt = replay(r, rom1, segs)
            if not alt['desync'] or alt['desync'][0] > rp['desync'][0]:
                rp = dict(alt, other=rp.get('other') or rp['desync'][0])
        seen, tabs, tread = rp['seen'], rp['tabs'], rp['tread']
        done = rp['desync'][0] - 1 if rp['desync'] else want         # frames replayed in sync
        how = ('as recorded' if not rp['desync'] else 'last frame' if rp['desync'][0] >= total else 'partial')
        rom1 = '; '.join(x for x in ("ROM 1 = Sinclair's 48K ROM" if rp['rom1'] is not None else '',
                                     'each of its %d segments from its own snapshot' % snaps if rp['segs'] else '') if x)
        rom1 = '%s (the first replay desyncs at frame %d)' % (rom1, rp['other']) if rp.get('other') else ''
        for (nex, nx, d, orig, diff), (_, kind, alt_on, *_x) in zip(tabs, builds):
            lines, faults, cover = out[nex][1], out[nex][2], out[nex][3]
            cover[name] = dict(frames=done, of=want, how=how, desync=rp['desync'][1] if rp['desync'] else None,
                               rom1='48K' if rp['rom1'] is not None else ('128K' if rp['is128'] else '48K machine'),
                               segments=rp['segs'])
            kn = sorted(k for k in diff if k[0] != '?' and any(k[0] == i and lo <= k[1] <= hi for i, lo, hi, _ in known))
            run_d = sorted(k for k in diff if k[0] != '?' and k[2] in ('run', 'next') and k not in kn)
            data_d = sorted(k for k in diff if k[0] != '?' and k[2] == 'data' and k not in kn)
            unk = sorted({k[1] for k in diff if k[0] == '?'})
            cover[name]['unmodelled'] = unk
            if start_pc is not None:
                cover[name]['start_pc'] = start_pc
                cover[name]['entry_frame'] = rp['entry_frame']
                if rp['entry_frame'] is None:
                    cover[name]['how'] = 'partial'
                    lines.append('Original replay never reached required runtime entry 0x%04X' % start_pc)
                else:
                    lines.append('ROM observation starts at proven runtime entry 0x%04X in frame %d; earlier loader prefix excluded' % (start_pc, rp['entry_frame']))
            img = (lambda sel: 'image %d ' % sel) if alt_on else (lambda sel: '')
            head = '%s: %s %d frames, %d ROM bytes used' % (os.path.basename(nex), name, done, len(seen))
            if run_d and kind != 'plain':
                faults[name] = run_d
                lines.append('%s; MISMATCH: the Next gives other ROM bytes at %d addresses the game runs or reads '
                             '(the Next\'s own ROM there): %s' % (head, len(run_d), ', '.join(
                                 '%s0x%04X %s (%02X here, %02X recorded; PC 0x%04X frame %d)' % (
                                     (img(k[0]), k[1], 'run' if k[2] == 'run' else 'read') + (diff[k][3], diff[k][2]) + diff[k][:2])
                                 for k in run_d[:4])))
            elif run_d:
                ad = sorted({k[1] for k in run_d})
                lines.append('%s; plain build (the Next\'s own ROM3 runs): %d bytes it runs or reads differ from the recording\'s ROM, e.g. %s'
                             % (head, len(ad), ', '.join('0x%04X' % a for a in ad[:6])))
            else:
                lines.append('%s; every byte the game runs is as recorded' % head)
            if kn:
                lines.append('            KNOWN (the record\'s rom_paths_known): %d addresses, first %s0x%04X %s (PC 0x%04X frame %d): %s'
                             % (len(kn), img(kn[0][0]), kn[0][1], 'run' if kn[0][2] == 'run' else 'read', diff[kn[0]][0],
                                diff[kn[0]][1], '; '.join(sorted({w for i, lo, hi, w in known
                                                                  if any(k[0] == i and lo <= k[1] <= hi for k in kn)}))))
            if rom1:
                lines.append('            %s' % rom1)
            if rp['only']:
                o = sorted(rp['only'])
                lines.append('            128K ROM 1 only: %d bytes the game runs or reads are the 128K ROM 1\'s keypad code '
                             '(first 0x%04X, PC 0x%04X frame %d), which the Next\'s ROM 3 never had: not compared; its call '
                             'sites are compared with the 48K ROM'
                             % (len(o), o[0], rp['only'][o[0]][0], rp['only'][o[0]][1]))
            if how == 'last frame':
                lines.append('            port readings end in the recording\'s last frame (%d): frames 1-%d checked' % (total, done))
            elif how == 'partial':
                lines.append('            partial coverage: the replay desyncs at frame %d of %d (%s): frames 1-%d checked'
                             % (rp['desync'][0], want, rp['desync'][1], done))
            if data_d:
                lines.append('            reads %d ROM bytes held differently on the Next (data: the build\'s own, e.g. a '
                             'vector, or a fault): %s' % (len(data_d), ', '.join('%s0x%04X' % (img(k[0]), k[1]) for k in data_d[:8])))
            if unk:
                lines.append('            ROM select %s not modelled (a Next system ROM other than ROM3)' % ', '.join(map(str, unk)))
            ta, tn = tails[nex][1], tails[nex][2]
            rd = sorted(a for a in tread if ta <= a < ta + tn and a not in restored.get(nex, ()))
            back = all(a in restored.get(nex, ()) for a in range(ta, ta + tn))
            if rd:
                faults.setdefault(name, []).append(('tail', rd[0]))
                lines.append('            MISMATCH: the game reads the start-up tail\'s bytes before writing them: %d of '
                             '0x%04X-0x%04X, first 0x%04X (PC %d, frame %d); they hold the tail, not the snapshot\'s'
                             % (len(rd), ta, ta + tn - 1, rd[0], tread[rd[0]][0], tread[rd[0]][1]))
            elif back:
                lines.append('            tail 0x%04X-0x%04X: put back to the snapshot\'s bytes by the build\'s boot code '
                             'before the game starts' % (ta, ta + tn - 1))
            else:
                lines.append('            tail 0x%04X-0x%04X: never read before written' % (ta, ta + tn - 1))
            pb = sorted(a for a in tread if a in pbuf.get(nex, ()) and not ta <= a < ta + tn)
            if pb:
                lines.append('            WARNING: the game reads %d printer buffer bytes before writing them, which the .nex '
                             'leaves as NEXLOAD wrote them (first 0x%04X, PC %d, frame %d): keep_printer_buffer '
                             '(BRIEFING C2 #36)' % (len(pb), pb[0], tread[pb[0]][0], tread[pb[0]][1]))
    return out


# What NEXLOAD leaves in the 48K printer buffer before the stub runs (NextZXOS paging routines and
# system variables live at 0x5B00-0x5BFF; hardware 2026-10-20, Match Day): modelled as a pattern no
# game data matches, so a check with nexload=True shows every byte the stub does not put back.
NEXLOAD_PRINTER = bytes((0xA5 ^ k) for k in range(256))


RASTER_LINES = 312          # video lines a frame (50 Hz, 48K timing)
KEYPAD_CODE = 0x386E        # SkoolKit's 128K ROM 1: its keypad code from here (the 48K ROM's spare 0xFF bytes)


def raster(st, reg):
    """The raster line as NR 0x1E (bit 8) / NR 0x1F (bits 0-7) read it during boot: a model beam that moves one
    line on at every NR 0x1F read and wraps after RASTER_LINES, so a set-up's wait for a line (the loading
    picture's hold: one frame = until line 192, then until not 192; 250 frames or a key) ends, and a read of
    0x1E, 0x1F, 0x1E sees a stable bit 8 (Spellbound, Three Weeks). No key is ever pressed (port 0xFE reads 0xFF), so
    a hold runs its full timeout. Not cycle-timed: a hook that paces itself by the line is checked by its
    engine's own model (Three Weeks, Nightshade)."""
    if reg == 0x1F:
        st['line'] = (st.get('line', -1) + 1) % RASTER_LINES
        return st['line'] & 0xFF
    return max(st.get('line', 0), 0) >> 8


def boot(nex, pc_stop, limit=5_000_000, nexload=False, sysrom=None):
    """Run the NEX from its entry point until PC == pc_stop. Returns the machine state dict.
    nexload: start with the printer buffer overwritten as NEXLOAD leaves it (NEXLOAD_PRINTER).
    sysrom: the system ROM3 (default Sinclair's: a check of the stub alone, as the engines' own boot
    checks expect; check() and rom_paths() pass system_rom3(), NextZXOS's when given; pass a different
    ROM to prove an image does not depend on it, BRIEFING C2 #5)."""
    banks, sp, pc = load_nex(nex)
    with open(nex, 'rb') as f:
        entry_bank = f.read(512)[139]  # NEX entry bank; loading wrappers may use bank 32
    if entry_bank not in banks:
        raise ValueError('NEX entry bank %d is not present' % entry_bank)
    pages = {}
    for b, data in banks.items():
        pages[2 * b] = bytearray(data[0:8192])
        pages[2 * b + 1] = bytearray(data[8192:16384])
    if nexload and 10 in pages:
        pages[10][0x1B00:0x1C00] = NEXLOAD_PRINTER
    rom = sysrom if sysrom is not None else rom48()
    others = system_roms()                     # NextZXOS's ROMs 0-2 when the 64K file is given
    st = {'mmu': [0xFF, 0xFF, 10, 11, 4, 5, 2 * entry_bank, 2 * entry_bank + 1], 'nr': {0x8C: 0, 0x08: 0}, 'p7ffd': 0x00, 'p1ffd': 0,
          'alt': [bytearray(16384), bytearray(16384)], 'bad': [], 'sel': 0, 'ports': {}, 'nrlog': []}

    def page(n):
        return pages.setdefault(n, bytearray(8192))

    def romn():
        return ((st['p1ffd'] >> 2) & 1) << 1 | ((st['p7ffd'] >> 4) & 1)

    class Mem(list):
        def __getitem__(s, a):
            m = st['mmu'][a >> 13]
            if m == 0xFF:
                n, r = romn(), st['nr'][0x8C]
                if r & 0xC0 == 0x80:
                    return st['alt'][n & 1][a]
                if n != 3:
                    st['bad'].append(('read of ROM %d' % n, a))
                    return others[n][a] if others else 0
                return rom[a]
            return page(m)[a & 0x1FFF]

        def __setitem__(s, a, v):
            m = st['mmu'][a >> 13]
            if m == 0xFF:
                if st['nr'][0x8C] & 0xC0 == 0xC0:
                    st['alt'][romn() & 1][a] = v
                return
            page(m)[a & 0x1FFF] = v

    Sim = _rw_simulator()
    sim = Sim(Mem([0] * 65536), {'PC': pc, 'SP': sp})
    R, ed = sim.registers, sim.after_ED
    from skoolkit.simulator import R2

    def nextreg(reg, val):
        st['nr'][reg] = val
        st['nrlog'].append((reg, val))         # every NEXTREG write in order (palette uploads)
        if 0x50 <= reg <= 0x57:
            st['mmu'][reg - 0x50] = val
        elif reg == 0x08 and val & 0x80:
            st['p7ffd'] &= ~0x20

    def nn():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], sim.memory[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536

    def na():
        p = R[24]
        nextreg(sim.memory[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs, port):
            if port == 0x253B and st['sel'] in (0x1E, 0x1F):
                return raster(st, st['sel'])
            return st['nr'].get(st['sel'], 0) if port == 0x253B else 0xFF

        def write_port(s, regs, port, value, *x):
            st['ports'][port] = value          # last value written to each port (e.g. 0x123B)
            if port == 0x243B:
                st['sel'] = value
            elif port in (0x7FFD, 0x1FFD) and not st['p7ffd'] & 0x20:
                st['p7ffd' if port == 0x7FFD else 'p1ffd'] = value
                b = st['p7ffd'] & 7
                st['mmu'][0:2] = [0xFF, 0xFF]
                st['mmu'][6:8] = [2 * b, 2 * b + 1]
    sim.set_tracer(Tr())
    ops, mem, n = sim.opcodes, sim.memory, 0
    while R[24] != pc_stop:
        ops[mem[R[24]]]()
        n += 1
        if n > limit:
            raise RuntimeError('boot did not reach PC %d (at %d)' % (pc_stop, R[24]))
    st['R'], st['mem'] = R, mem
    return st


def regblock_overlap(patch, regs):
    """Hook bytes under the stub's register block (z80tonex.build_tail: 20 bytes at patch.slot1[1], written at boot):
    the boot overwrites them. regs = the block's bytes. -> their addresses. Not hook bytes: the 48K ROM's, 0x00, 0xFF,
    or the block's own value (an engine that stores it in its page: Ikari Warriors). Inferno m3a's cap_in sat here:
    every hook crashed on hardware while check() passed, 2026-11-08."""
    slot1, page = getattr(patch, 'slot1', None), getattr(patch, 'page', None)
    if slot1 is None or page is None:
        return []
    rom = rom48()
    return [slot1[1] + i for i, v in enumerate(regs) if 0x2000 <= slot1[1] + i < 0x4000 and
            page[slot1[1] + i - 0x2000] not in (rom[slot1[1] + i], 0, 0xFF, v)]


def check(nex, z80, patch=None, tail=None, nexload=False, sysrom=None):
    """Boot the NEX and compare with the snapshot: registers (except R), RAM 0x4000-0xFFFF (patched
    RAM from the NEX's own banks 5/2/0, except the tail bytes), what slots 0/1 show (ROM3 or
    ROM3 + alt ROM patch bytes), paging lock, $8C. Returns a list of problems (empty = OK).
    nexload=True: the printer buffer starts as NEXLOAD leaves it (a build must put it back)."""
    import copy
    s = zt.Z80Snapshot(z80)
    if patch is not None:
        patch = copy.deepcopy(patch)          # apply() again on a fresh snapshot, caller's object untouched
        patch.apply(s)
    sysrom = sysrom if sysrom is not None else system_rom3()[0]
    st = boot(nex, s.pc, nexload=nexload, sysrom=sysrom)
    R, mem, bad = st['R'], st['mem'], list(st['bad'])
    w = lambda h, l: R[h] * 256 + R[l]
    got = {'BC': w(2, 3), 'DE': w(4, 5), 'HL': w(6, 7), 'AF': w(0, 1), 'IX': w(8, 9), 'IY': w(10, 11),
           "BC'": w(18, 19), "DE'": w(20, 21), "HL'": w(22, 23), "AF'": w(16, 17), 'SP': R[12], 'I': R[14],
           'IM': R[27], 'IFF': R[26]}
    exp = {'BC': s.bc, 'DE': s.de, 'HL': s.hl, 'AF': s.a * 256 + s.f, 'IX': s.ix, 'IY': s.iy,
           "BC'": s.bc_, "DE'": s.de_, "HL'": s.hl_, "AF'": s.a_ * 256 + s.f_, 'SP': s.sp, 'I': s.i,
           'IM': s.im, 'IFF': s.iff1}
    bad += [('register', k, got[k], exp[k]) for k in exp if got[k] != exp[k]]
    ram = s.banks[5] + s.banks[2] + s.banks[0]
    t0, t1 = tail if tail else (0, 0)
    diffs = [a for a in range(0x4000, 0x10000) if mem[a] != ram[a - 0x4000] and not t0 <= a < t1]
    if diffs:
        bad.append(('RAM differs', len(diffs), diffs[:6]))
    img = bytearray(sysrom)
    if getattr(patch, 'altrom', None) or getattr(patch, 'slot1', None):
        regs = zt.build_tail(s, 0x8000, patch.slot1, bool(getattr(patch, 'altrom', None)), getattr(patch, 'ram_slot1_after_alt', False))[3]
        rb = patch.slot1[1]
        if getattr(patch, 'altrom', None):
            img = rom_view(patch, sysrom)                    # hidden ROM with optional writable hook page
        else:
            img[0x2000:0x4000] = patch.page
        hit = regblock_overlap(patch, regs)              # the line below would hide them from the comparison
        if hit:
            bad.append(('hook bytes under the stub register block', len(hit), ['%04X' % a for a in hit[:6]]))
        img[rb:rb + len(regs)] = regs                    # register block written by the stub
    if zt.altrom0(patch):                                # alt image 0 = the 128K ROM 0 + the build's bytes
        lo0, hi0 = zt.altrom0(patch)
        img0 = bytearray(zt.rom128_0())
        img0[lo0:hi0] = patch.page[lo0 - 0x2000:hi0 - 0x2000]
        if bytes(st['alt'][0]) != bytes(img0):
            bad.append(('alt image 0 differs from the 128K ROM 0 + the build\'s bytes',))
    if getattr(patch, 'altrom', None):
        if st['nr'][0x8C] != 0x80:
            bad.append(('$8C', st['nr'][0x8C]))
    elif st['nr'][0x8C] != 0:
        bad.append(('$8C', st['nr'][0x8C]))
    view = bytes(mem[a] for a in range(0x4000))
    if view != bytes(img):
        d = [a for a in range(0x4000) if view[a] != img[a]]
        bad.append(('slots 0/1 differ from the expected ROM image', len(d), d[:6]))
    locked = st['p7ffd'] & 0x30 == 0x30
    as_saved = s.is128 and st['p7ffd'] & 0x30 == s.port7ffd & 0x30      # a 128K game pages: unlocked as saved
    if not (locked or as_saved) or not st['p1ffd'] & 4:                 # (Three Weeks, 2026-11-04)
        bad.append(('paging', hex(st['p7ffd']), hex(st['p1ffd'])))
    s1 = patch.slot1[0] if getattr(patch, 'slot1', None) and (not getattr(patch, 'altrom', None) or getattr(patch, 'ram_slot1_after_alt', False)) else 0xFF
    if st['mmu'] != [0xFF, s1, 10, 11, 4, 5, 0, 1]:
        bad.append(('MMU', st['mmu']))
    return bad


def selfcheck():
    """Synthetic cases (no game data; selftest --tools): the raster model ends a loading picture's hold (and a
    frozen line, the old model, never does), NR 0x1E/0x1F read as the hardware counts, and rom_paths reports a
    .nex whose boot never reaches the game start instead of raising (Spellbound, Three Weeks, Knight Tyme). -> list of failures."""
    import tempfile
    bad = []
    st = {}
    lo = [raster(st, 0x1F) for _ in range(RASTER_LINES)]
    hi = [raster(st, 0x1E) for _ in range(1)]
    if lo != [n & 0xFF for n in range(RASTER_LINES)] or hi != [1] or raster(st, 0x1F) != 0 or raster(st, 0x1E) != 0:
        bad.append('raster: NR 0x1F / 0x1E do not count lines 0-%d' % (RASTER_LINES - 1))
    # the set-up's hold (Spellbound / Three Weeks / the loading stubs): 250 frames of "until line 192, until not"
    code = bytes.fromhex('21FA00' 'CD10C0' '2B' '7C' 'B5' '20F8' '00' + '00' * 4 +      # C000: LD HL,250 / CALL fr / ..
                         'CD20C0' 'FEC0' '20F9' 'CD20C0' 'FEC0' '28F9' 'C9' + '00' +   # C010 fr: one frame
                         '013B24' '3E1F' 'ED79' '04' 'ED78' 'C9')                     # C020 po: A = NR 0x1F
    hdr = bytearray(512)
    hdr[0:8] = b'NextV1.2'
    hdr[12:16] = bytes((0xF0, 0xBF, 0x00, 0xC0))             # SP 0xBFF0, PC 0xC000
    hdr[18 + 10] = 1
    hdr[139] = 10
    fd, nex = tempfile.mkstemp(suffix='.nex')
    os.write(fd, bytes(hdr) + code + bytes(16384 - len(code)))
    os.close(fd)
    try:
        st = boot(nex, 0xC00B)
        if st.get('line') != 193:
            bad.append('raster: the hold ended at line %s, want 193 after 250 frames' % st.get('line'))
        old = globals()['raster']
        globals()['raster'] = lambda st, reg: 0              # the old model: NR 0x1F reads 0, the hold never ends
        try:
            boot(nex, 0xC00B, limit=300000)
            bad.append('raster control: a frozen line still ended the hold')
        except RuntimeError:
            pass
        finally:
            globals()['raster'] = old
        r = rom_paths([nex], [nex + '.rzx'])                 # no start-up tail: reported, nothing replayed
        if r[nex][0] != 'boot' or 'BOOT FAILED' not in r[nex][1][0]:
            bad.append('rom_paths: a .nex that does not boot was not reported (%s)' % (r[nex][:2],))
    except Exception as e:                                   # noqa: BLE001
        bad.append('nextboot selfcheck raised %r' % e)
    finally:
        os.remove(nex)
    return bad + regblock_selfcheck()


def regblock_selfcheck():
    """A synthetic 48K snapshot + hook page, booted through the real stub: clean hooks pass check(); hook bytes under
    the register block are reported (the Inferno m3a layout). -> list of failures."""
    import tempfile
    from .build import altrom_image
    hdr = bytearray(30)
    hdr[6:8] = (0x00, 0x80)                                  # PC 0x8000
    hdr[8:10] = (0x00, 0x90)                                 # SP 0x9000
    hdr[29] = 1                                              # IM 1; byte 12 = 0: uncompressed
    ram = bytearray(49152)
    ram[0x8000 - 0x4000] = 0x76

    class P:
        stub_extra, setup_call, hook_page_data, extra_banks, uses_printer_buffer = b'', None, b'', {}, False
        tail_addr = 0xA000

        def apply(self, snap):
            pass
    bad = []
    with tempfile.TemporaryDirectory() as d:
        z80, nex = os.path.join(d, 'g.z80'), os.path.join(d, 'g.nex')
        with open(z80, 'wb') as f:
            f.write(bytes(hdr) + bytes(ram))
        for label, under in (('clean', False), ('overlap', True)):
            p = P()
            page, rb, span = altrom_image(rom48(), 0x386E, bytes([0xC9] * 16))
            p.slot1, p.altrom = (24, rb), span
            if under:                                            # cap_in at rom_end + 3, as Inferno m3a
                page = bytearray(page)
                page[rb + 3 - 0x2000:rb + 8 - 0x2000] = bytes.fromhex('F3ED910703')
            p.page = bytes(page)
            p.extra_banks = {12: p.page + bytes(8192)}
            try:
                _, t, data, _ = zt.convert(z80, nex, quiet=True, patch=p)
                got = check(nex, z80, p, (t, t + len(data)))
            except Exception as e:                                # noqa: BLE001
                bad.append('regblock %s raised %r' % (label, e))
                continue
            found = [x for x in got if x[0] == 'hook bytes under the stub register block']
            if under and (not found or found[0][1] != 5):
                bad.append('regblock: hook bytes under the register block not reported (%s)' % (got,))
            if not under and got:
                bad.append('regblock: clean layout reported %s' % (got,))
    return bad


if __name__ == '__main__':
    print(check(sys.argv[1], sys.argv[2]) or 'OK')
