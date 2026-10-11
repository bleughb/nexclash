"""Engine identification and automatic profile derivation (byte patterns only)."""


def _find(m, pat):
    """All addresses where pat (list of ints, None = any byte) matches."""
    out = []
    first = pat[0]
    i = m.find(bytes([first]))
    n = len(pat)
    while i != -1 and i + n <= len(m):
        if all(p is None or m[i + k] == p for k, p in enumerate(pat)):
            out.append(i)
        i = m.find(bytes([first]), i + 1)
    return out


def _p(s):
    return [None if t == '??' else int(t, 16) for t in s.split()]


def w(m, a):
    return m[a] | m[a + 1] << 8


KNOWN = {
    # games with a hand-made builder (engine variants the generic template does not cover)
    'treasure_island_dizzy': ('tid_legacy', [(61578, 'CD 5E 9B'), (63000, 'CD 7D F3'), (40087, 'F3 ED 73')]),
    'dizzy1': ('dizzy1_xor', [(58159, '3A 75 E1'), (58184, '77'), (60228, 'C5 E5 3A')]),
}


def identify(mem):
    """mem: 64K bytes. Returns dict with 'engine' and, for the TID engine, a profile."""
    m = bytes(mem)
    for name, (engine, sites) in KNOWN.items():
        if all(m[a:a + len(_p(b))] == bytes(_p(b)) for a, b in sites):
            return {'engine': engine, 'game': name}
    from .dizzy5 import identify5          # Dizzy V engine (also its inert loader-stage copy)
    d5 = identify5(m)
    if d5:
        return d5
    notes = []
    seq = _find(m, _p('A1 A8 D9 47 AE 12 70'))
    if not seq:
        xor = _find(m, _p('1A AE 77 23 13'))
        return {'engine': 'unknown', 'hint': 'XOR sprite loop found at %s' % xor[:4] if xor else
                'no known sprite engine signature'}
    P = seq[0] - 115
    if m[P] != 0x32 and m[P - 1] == 0x32 and m[P + 2:P + 4] == bytes([0xDD, 0xE5]):
        P -= 1   # Prince of the Yolkfolk variant: LD (nn),A sits one byte earlier (plotter+116)
    if m[P] != 0x32:
        return {'engine': 'tid_like', 'hint': 'TID-style masked plot at %d but plotter entry not recognised' % seq[0]}
    er = [a for a in _find(m, _p('F3 ED 73 ?? ??')) if P < a < P + 400]
    if not er:
        return {'engine': 'tid_like', 'hint': 'plotter at %d, eraser not found' % P}
    E = er[0]
    spsave = w(m, E + 3)
    pw = [a for a in range(P, E) if m[a] == 0x70 and m[a - 1] == 0x12]
    ew = [a for a in range(E, E + 52) if m[a] == 0x77 and m[a - 1] in (0xA9, 0xA8)]
    entries = [a for a in _find(m, [0xC3, P & 255, P >> 8]) + _find(m, [0xCD, P & 255, P >> 8])]
    # frame table / graphics base: operand pair t, t+78 referenced in the plotter
    ops = {w(m, a) for a in range(P, E)}

    def frames_ok(t):
        try:
            offs = [w(m, t + 2 * i) for i in range(39)]
            return all(1 <= m[t + 78 + o] <= 32 for o in offs) and len(set(offs)) > 30
        except IndexError:
            return False
    ft = [t for t in ops if t + 78 in ops and frames_ok(t)]
    wipe = [a for a in _find(m, _p('DD 21 ?? ?? 3E 88 11 01 00'))]
    box = [a for a in _find(m, _p('3A ?? ?? C6 04 CB 3F 32'))]
    isr = [a + 3 for a in _find(m, _p('CC ?? ?? CD ?? ??'))]
    ptest = _find(m, _p('4F 06 00 CB 39 38'))
    prof = {
        'engine': 'tid', 'plotter': P, 'eraser': E, 'eraser_spsave': spsave, 'eraser_cont': E + 5,
        'plotter_writes': pw, 'eraser_writes': ew,
        'plot_site': entries[0] if len(entries) == 1 else None, 'plot_site_kind': None,
        'frame_table': min(ft) if ft else None, 'frame_base': min(ft) + 78 if ft else None,
        'wipe': wipe[0] if len(wipe) == 1 else None, 'box': box[0] if len(box) == 1 else None,
        'isr_hide_call': None, 'pixel_test': ptest[0] if len(ptest) == 1 else None,
    }
    if prof['plot_site'] is None and len(entries) == 2:
        # Prince of the Yolkfolk: a second (mirrored) copy of the player is plotted from an actor
        # loop (CALL after LD L,(IX+3)) with its own undo buffer; the player is the other site.
        sec = [a for a in entries if m[a] == 0xCD and m[a - 3:a] == bytes([0xDD, 0x6E, 0x03])]
        if len(sec) == 1:
            prof['plot_site'] = [a for a in entries if a != sec[0]][0]
            prof['plot_site2'] = sec[0]
            notes_extra = 'second player copy plotted at %d (own undo buffer): needs the dizzy6 builder' % sec[0]
            prof['engine'] = 'tid_mirror'
            prof['mirror_note'] = notes_extra
    if prof['plot_site'] is not None:
        prof['plot_site_kind'] = 'JP' if m[prof['plot_site']] == 0xC3 else 'CALL'
    if prof['wipe'] is not None:
        prof['wipe_ix'] = w(m, prof['wipe'] + 2)
        prof['wipe_cont'] = prof['wipe'] + 4
    if prof['box'] is not None:
        prof['box_var'] = w(m, prof['box'] + 1)
        prof['box_cont'] = prof['box'] + 3
    # in-game ISR: 'CALL Z,tick / CALL sound' inside a handler that starts with DI and pushes
    for a in isr:
        start = [s for s in range(a - 60, a) if m[s] == 0xF3 and m[s + 1] == 0xF5]
        if start:
            prof['isr_hide_call'] = a
            prof['sound_tick'] = w(m, a + 1)
            break
    # undo buffer: the eraser loads SP (LD SP,nn) or HL with it
    for a in range(E, E + 20):
        if m[a] == 0x31:
            prof['undo_buffer'] = w(m, a + 1)
            break
        if m[a:a + 2] == bytes([0xED, 0x7B]):   # LD SP,(ptr): undo buffer selected via a pointer
            prof['undo_ptr'] = w(m, a + 2)
            prof['undo_buffer'] = w(m, w(m, a + 2))
            break
    if len(pw) != 7 or len(ew) != 4:
        notes.append('screen-write sites: %d plotter, %d eraser (expected 7 and 4)' % (len(pw), len(ew)))
    for k in ('plot_site', 'frame_table', 'wipe', 'isr_hide_call', 'pixel_test'):
        if prof.get(k) is None:
            notes.append('%s not found uniquely' % k)
    if prof['box'] is None:
        notes.append('no box routine found (fine if the game has no inventory/dialogue boxes)')
    prof['notes'] = notes
    prof['ok'] = not [n for n in notes if not n.startswith('no box')]
    return prof
