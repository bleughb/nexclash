; Shared hook library: the pace limiter for the ORIGINAL target (card patch.pace-limiter). After Three
; Weeks' pace window (three_weeks_hooks.asm x_line / x_tick / x_pad), with the parts Quazatron, Match Day
; v2.1 and Atic Atac v1.4 each wrote for themselves (pilot runs/quazatron, dean_match_day, atic_atac):
; interrupt time left out of every window, game-routine windows scaled by K, the debt repaid from the
; game's own delay, a configurable debt cap. The default for every new engine. Unit tests and negative
; controls: nexclash/hooklib.py (selftest.py --tools).
;
; A hook that replaces slow original code (a blit, a plot) can be FASTER than it: sprite drawing costs
; less than the ULA plot, and its own work runs at 28 MHz. Under the ORIGINAL pace target the game must
; still take the original's time, so the hook waits on the video line (NR 0x1E / 0x1F) until the
; displaced code's time has passed, less the hook time spent outside the window since the last one
; (the debt). Time over the window carries in the debt to the next windows.
;
; Windows (a hook that displaces original code whose time is known):
;   CALL hlib_pace_open        at the window's start (the hook's entry)
;   ... the hook's work, any speed (CALL hlib_pace_tick at least once a frame in a long window)
;   HL = target (1/16 lines at 3.5 MHz: hooklib.lines16; Match Day's per-call tables are such targets),
;   A = the latched incoming speed, CALL hlib_pace_wait
; Game-routine windows (the game's own routine run at 28 MHz, Quazatron's E656): open, CALL the routine,
;   A = K (the routine's original time per unit of its 28 MHz time, x 16: about 104 at JNext's 6.5),
;   C = the latched incoming speed, CALL hlib_pace_waitk. K comes from a JNext measurement per routine.
; Debt (hook time outside any window): CALL hlib_debt_open / A = unmeasured part (1/16 lines), CALL
;   hlib_debt_close around the hook (never inside an open window: counted twice); CALL hlib_debt_tick at
;   least once a frame in between when that hook can run longer than a frame; HL = sixteenths, CALL
;   hlib_debt_add for a constant cost (a hook's 3.5 MHz entry and exit).
; The game's own delay repays the debt (Quazatron's DD80): HL = the delay's time (1/16 lines, real),
;   CALL hlib_debt_repay -> HL = the part to skip; the engine shortens the loop by that much.
; Interrupts: the engine's ISR wrapper (interrupts off) CALLs hlib_pace_hold at its start and
;   hlib_pace_resume at its end: the handler's time is left out of every window and debt window, as it
;   lengthened the original's code too (Match Day's ISRACC, Quazatron's isr_in / isr_out). Readings are a
;   consistent (line, held) pair: a hold / resume between them makes the reading start again, which also
;   covers an ISR that selected another NextREG between OUT (0x243B) and IN (0x253B). An ISR wrapper that
;   selects NextREGs (HLIB_SPEED_IN) must call the pair. One level: nothing else calls hold / resume.
; The target scales with the incoming speed (>> A): a caller at 7 MHz had the original at 7 MHz.
; With interrupts on at the site, wait at the latched speed (HLIB_SPEED_OUT first): the game's ISR then
; runs at its own clock during the wait. A wait gives up after 65536 polls (an emulator with no line
; counter), so a missing NR 0x1E never hangs the game.
;
; The engine defines, before the INCLUDE:
;   HLIB_V_PACE EQU <26 bytes of hook RAM, zero at start>
;       +0 window: line at the last reading, +2 lines elapsed in the window, +4 debt (1/16 lines),
;       +6 lines a frame (the engine's setup stores the timing mode's when it is chosen at run time, 60 Hz;
;       0 = HLIB_PACE_NL; never learned from a poll), +8 debt window: line at the last reading, +10 window
;       open, +12 polls left, +14 held lines in total (hold / resume), +16 line at the hold, +18 window:
;       held total at the last reading, +20 debt window: the same, +22 / +24 the last reading (line, held)
;   HLIB_PACE_NL EQU <lines a frame of the game's timing mode: 312 48K, 311 128K / +3 (50 Hz)>
;   DEFINE HLIB_PACE_CAP <the debt cap, 1/16 lines> (optional; default 0xBFFF: 3,072 lines, about 10 frames;
;       Quazatron used 4 frames, Match Day 1,280 lines)
;   HLIB_PACE_LEAN (optional, DEFINE): windows and debt only - no K windows, repay, hold / resume (about 420 bytes
;       instead of 533: Three Weeks' alt ROM span). hlib_line_di is assembled only when called (IFUSED): an engine
;       that calls it INCLUDEs hlib_iff.asm (macros) first.
;   HLIB_PACE_V1 (DEFINE): the first library unchanged, for the engines verified with it (14 bytes of state)
; hlib_line keeps DE; the others keep nothing but IX, IY and the alternate set.

    IFNDEF HLIB_PACE_CAP
HLIB_PACE_CAP EQU 0xBFFF
    ENDIF

; hlib_line: HL = the video line (0 = the first ULA pixel row), read until the MSB holds still. AF, BC lost.
hlib_line:
        ld bc,0x243B
.r:     ld a,0x1E
        out (c),a
        inc b
        in h,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        xor h
        and 1
        jr nz,.r
        ld a,h
        and 1
        ld h,a
        ret

    IFUSED hlib_line_di          ; assembled only when an engine calls it (it needs hlib_iff.asm's macros):
                                ; engines that never call it keep their bytes and need no hlib_iff.asm
; hlib_line_di: HL = the video line (hlib_line) with interrupts off only for the
; reading (under 256 T at 28 MHz = 32 T at 3.5 MHz, the /INT length, so no interrupt is lost; hooklib
; checks the window), then the caller's IFF back. With interrupts on, a NEXTREG selection made by an
; interrupt between OUT (0x243B) and IN (0x253B) would read the wrong register (an ISR wrapper that
; saves the speed selects register 7). AF, BC lost; DE kept.
hlib_line_di:
        HLIB_IFF_DI
        push af
        call hlib_line
        pop af
        HLIB_IFF_EI
        ret
    ENDIF

    IFDEF HLIB_PACE_V1
; ---- the first library (2026-11-04), byte for byte: engines verified with it DEFINE HLIB_PACE_V1 before the INCLUDE
; (Cobra, Gryzor, Cauldron 1.1): 14 bytes of HLIB_V_PACE, no interrupt accounting, no K windows, no repay.

; hlib_since: HL = lines from DE (an earlier reading) to now, one unseen wrap allowed; +0 = now. AF, BC, DE lost
hlib_since:
        push de
        call hlib_line
        ld (HLIB_V_PACE),hl
        pop de
        or a
        sbc hl,de
        ret nc
        ld de,(HLIB_V_PACE + 6)
        ld a,d
        or e
        jr nz,.n
        ld de,HLIB_PACE_NL
.n:     add hl,de
        ret

; hlib_pace_open: start a window
hlib_pace_open:
        call hlib_line
        ld (HLIB_V_PACE),hl
        ld hl,0
        ld (HLIB_V_PACE + 2),hl
        ld a,1
        ld (HLIB_V_PACE + 10),a
        ret

; hlib_pace_tick: the window's elapsed lines brought up to now (callers under a frame apart)
hlib_pace_tick:
        ld de,(HLIB_V_PACE)
        call hlib_since
        ld de,(HLIB_V_PACE + 2)
        add hl,de
        ld (HLIB_V_PACE + 2),hl
        ret

; hlib_pace_wait: HL = the displaced original's time (1/16 lines at 3.5 MHz), A = incoming speed 0-3.
; Waits until the window has lasted target - debt; what is left over goes to the debt (capped).
hlib_pace_wait:
        ld b,a
        ld a,(HLIB_V_PACE + 10)
        or a
        ret z                   ; no window open
        xor a
        ld (HLIB_V_PACE + 10),a
        inc b
        jr .sc
.sh:    srl h
        rr l
.sc:    djnz .sh                ; target at the incoming clock
        push hl
        call hlib_pace_tick
        pop hl
        ld de,(HLIB_V_PACE + 4)
        or a
        sbc hl,de               ; target - debt, sixteenths
        jr c,.neg
        push hl
        ld b,4
.q:     srl h
        rr l
        djnz .q
        ex de,hl                ; DE = lines to reach
        ld hl,0
        ld (HLIB_V_PACE + 12),hl
        ld hl,(HLIB_V_PACE + 2)
.lp:    push hl
        or a
        sbc hl,de
        pop hl
        jr nc,.ok
        ld bc,(HLIB_V_PACE + 12)
        dec bc
        ld (HLIB_V_PACE + 12),bc
        ld a,b
        or c
        jr z,.ok                ; no line counter: give up
        push hl
        push de
        call hlib_line
        ld bc,(HLIB_V_PACE)
        ld (HLIB_V_PACE),hl
        or a
        sbc hl,bc               ; lines since the last poll
        jr nc,.d
        ld bc,(HLIB_V_PACE + 6) ; a wrap: + the timing mode's lines a frame, never learned from a poll (at
        ld a,b                  ; 3.5 MHz a poll can miss the frame's last line)
        or c
        jr nz,.wr
        ld bc,HLIB_PACE_NL
.wr:    add hl,bc
.d:     pop de
        pop bc
        add hl,bc
        jr .lp
.ok:    ld (HLIB_V_PACE + 2),hl
        call .x16
        pop de
        or a
        sbc hl,de               ; past the target (under a line), sixteenths
        jr nc,.st
        ld hl,0
        jr .st
.neg:   ex de,hl                ; no wait: the debt beyond this window, plus all of the window's time
        ld hl,0
        or a
        sbc hl,de               ; HL = debt - target
        ex de,hl
        ld hl,(HLIB_V_PACE + 2)
        call .x16
        add hl,de
        jr c,.cap
.st:    ld a,h
        cp 0xC0
        jr c,.w
.cap:   ld hl,0xBFFF            ; at most 3,072 lines (about 10 frames) carried
.w:     ld (HLIB_V_PACE + 4),hl
        ret
.x16:   ld a,h                  ; HL x 16, 0xFFFF when it would overflow
        and 0xF0
        jr nz,.big
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ret
.big:   ld hl,0xFFFF
        ret

; hlib_debt_open: an outside hook starts (its time goes to the debt)
hlib_debt_open:
        call hlib_line
        ld (HLIB_V_PACE + 8),hl
        ret

; hlib_debt_tick: debt += 16 x lines since the last open / tick (capped). Call it at least once a frame
; in a hook that can run longer than a frame (a room build), or the line count wraps unseen.
hlib_debt_tick:
        ld de,(HLIB_V_PACE + 8)
        call hlib_since
        ld de,(HLIB_V_PACE)
        ld (HLIB_V_PACE + 8),de
        call hlib_pace_wait.x16
        jr hlib_debt_close.add

; hlib_debt_close: A = the hook's unmeasured part (1/16 lines: its 3.5 MHz entry and exit, about 7 with
; HLIB_SPEED_IN); debt += 16 x lines since the last open / tick + A, capped
hlib_debt_close:
        push af
        call hlib_debt_tick
        pop af
        ld l,a
        ld h,0
.add:   ld de,(HLIB_V_PACE + 4)
        add hl,de
        jr c,.cap
        ld a,h
        cp 0xC0
        jr c,.w
.cap:   ld hl,0xBFFF
.w:     ld (HLIB_V_PACE + 4),hl
        ret
    ELSE
; ---- the current library ----
; hlib_now: HL = the video line, DE = the held total at that line, a consistent pair (read again when a hold /
; resume came between). AF, BC lost.
hlib_now:
.r:     ld de,(HLIB_V_PACE + 14)
        call hlib_line
        push hl
        ld hl,(HLIB_V_PACE + 14)
        or a
        sbc hl,de
        pop hl
        jr nz,.r
        ret

; hlib_nl: BC = lines a frame (+6, else HLIB_PACE_NL). AF lost.
hlib_nl:
        ld bc,(HLIB_V_PACE + 6)
        ld a,b
        or c
        ret nz
        ld bc,HLIB_PACE_NL
        ret

; hlib_since_c: DE = line, BC = held total at an earlier reading -> HL = lines since, less the time held since
; (>= 0), one unseen wrap allowed; +22 / +24 = this reading. AF, BC, DE lost.
hlib_since_c:
        push bc
        push de
        call hlib_now
        ld (HLIB_V_PACE + 22),hl
        ld (HLIB_V_PACE + 24),de
        pop de
        or a
        sbc hl,de
        jr nc,.p
        call hlib_nl
        add hl,bc
.p:     ex de,hl                ; DE = lines
        ld hl,(HLIB_V_PACE + 24)
        pop bc
        or a
        sbc hl,bc               ; HL = held since
        ex de,hl
        or a
        sbc hl,de
        ret nc
        ld hl,0
        ret

; hlib_since: HL = the window's lines since its last reading (held time left out); the reading = now.
; AF, BC, DE lost.
hlib_since:
        ld de,(HLIB_V_PACE)
        ld bc,(HLIB_V_PACE + 18)
        call hlib_since_c
        ld de,(HLIB_V_PACE + 22)
        ld (HLIB_V_PACE),de
        ld de,(HLIB_V_PACE + 24)
        ld (HLIB_V_PACE + 18),de
        ret

; hlib_pace_open: start a window
hlib_pace_open:
        call hlib_now
        ld (HLIB_V_PACE),hl
        ld (HLIB_V_PACE + 18),de
        ld hl,0
        ld (HLIB_V_PACE + 2),hl
        ld a,1
        ld (HLIB_V_PACE + 10),a
        ret

; hlib_pace_tick: the window's elapsed lines brought up to now (callers under a frame apart)
hlib_pace_tick:
        call hlib_since
        ld de,(HLIB_V_PACE + 2)
        add hl,de
        ld (HLIB_V_PACE + 2),hl
        ret

    IFNDEF HLIB_PACE_LEAN
; hlib_pace_waitk: A = K (x 16), C = incoming speed 0-3: the window's target is its elapsed lines x K
; (hlib_pace_wait's), saturating; a game-routine window. A, BC, DE, HL lost.
hlib_pace_waitk:
        push bc
        push af
        call hlib_pace_tick
        pop af
        ld hl,(HLIB_V_PACE + 2)
        call hlib_mul8
        pop bc
        ld a,c
        jr hlib_pace_wait

; hlib_mul8: HL = HL x A, 0xFFFF when it overflows. AF, B, DE lost.
hlib_mul8:
        ex de,hl
        ld hl,0
        ld b,8
.l:     add hl,hl
        jr c,.ov
        rla
        jr nc,.n
        add hl,de
        jr c,.ov
.n:     djnz .l
        ret
.ov:    ld hl,0xFFFF
        ret
    ENDIF

; hlib_pace_wait: HL = the displaced original's time (1/16 lines at 3.5 MHz), A = incoming speed 0-3.
; Waits until the window has lasted target - debt; what is left over goes to the debt (capped).
hlib_pace_wait:
        ld b,a
        ld a,(HLIB_V_PACE + 10)
        or a
        ret z                   ; no window open
        xor a
        ld (HLIB_V_PACE + 10),a
        inc b
        jr .sc
.sh:    srl h
        rr l
.sc:    djnz .sh                ; target at the incoming clock
        push hl
        call hlib_pace_tick
        pop hl
        ld de,(HLIB_V_PACE + 4)
        or a
        sbc hl,de               ; target - debt, sixteenths
        jr c,.neg
        push hl
        ld b,4
.q:     srl h
        rr l
        djnz .q
        ex de,hl                ; DE = lines to reach
        ld hl,0
        ld (HLIB_V_PACE + 12),hl
        ld hl,(HLIB_V_PACE + 2)
.lp:    push hl
        or a
        sbc hl,de
        pop hl
        jr nc,.ok
        ld bc,(HLIB_V_PACE + 12)
        dec bc
        ld (HLIB_V_PACE + 12),bc
        ld a,b
        or c
        jr z,.ok                ; no line counter: give up
        push hl
        push de
        call hlib_now           ; a poll: HL = line, DE = held (inline hlib_since: a 3.5 MHz poll is the wait's
        ld bc,(HLIB_V_PACE + 18) ; granularity)
        ld (HLIB_V_PACE + 18),de
        ex de,hl
        or a
        sbc hl,bc
        push hl                 ; held since the last poll
        ld hl,(HLIB_V_PACE)
        ex de,hl
        ld (HLIB_V_PACE),hl
        or a
        sbc hl,de               ; lines since the last poll; a wrap adds the timing mode's lines a frame, never
        jr nc,.d                ; learned from a poll (at 3.5 MHz a poll can miss the frame's last line)
        call hlib_nl
        add hl,bc
.d:     pop bc
        or a
        sbc hl,bc               ; held time left out
        jr nc,.e
        ld hl,0
.e:     pop de
        pop bc
        add hl,bc
        jr .lp
.ok:    ld (HLIB_V_PACE + 2),hl
        call .x16
        pop de
        or a
        sbc hl,de               ; past the target (under a line), sixteenths
        jr nc,hlib_debt_set
        ld hl,0
        jr hlib_debt_set
.neg:   ex de,hl                ; no wait: the debt beyond this window, plus all of the window's time
        ld hl,0
        or a
        sbc hl,de               ; HL = debt - target
        ex de,hl
        ld hl,(HLIB_V_PACE + 2)
        call .x16
        add hl,de
        jr nc,hlib_debt_set
        ld hl,0xFFFF
        jr hlib_debt_set
.x16:   ld a,h                  ; HL x 16, 0xFFFF when it would overflow
        and 0xF0
        jr nz,.big
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ret
.big:   ld hl,0xFFFF
        ret

; hlib_debt_set: debt = HL, at most HLIB_PACE_CAP. AF, DE lost.
hlib_debt_set:
        ld de,HLIB_PACE_CAP
        push hl
        or a
        sbc hl,de
        pop hl
        jr c,.w
        ex de,hl
.w:     ld (HLIB_V_PACE + 4),hl
        ret

; hlib_debt_open: an outside hook starts (its time goes to the debt)
hlib_debt_open:
        call hlib_now
        ld (HLIB_V_PACE + 8),hl
        ld (HLIB_V_PACE + 20),de
        ret

; hlib_debt_tick: debt += 16 x lines since the last open / tick, held time left out (capped). Call it at least
; once a frame in a hook that can run longer than a frame (a room build), or the line count wraps unseen.
hlib_debt_tick:
        ld de,(HLIB_V_PACE + 8)
        ld bc,(HLIB_V_PACE + 20)
        call hlib_since_c
        ld de,(HLIB_V_PACE + 22)
        ld (HLIB_V_PACE + 8),de
        ld de,(HLIB_V_PACE + 24)
        ld (HLIB_V_PACE + 20),de
        call hlib_pace_wait.x16
        jr hlib_debt_add

; hlib_debt_close: A = the hook's unmeasured part (1/16 lines: its 3.5 MHz entry and exit, about 7 with
; HLIB_SPEED_IN); debt += 16 x lines since the last open / tick + A, capped
hlib_debt_close:
        push af
        call hlib_debt_tick
        pop af
        ld l,a
        ld h,0
; hlib_debt_add: debt += HL (1/16 lines), capped. AF, DE, HL lost.
hlib_debt_add:
        ld de,(HLIB_V_PACE + 4)
        add hl,de
        jr nc,hlib_debt_set
        ld hl,0xFFFF
        jr hlib_debt_set

    IFNDEF HLIB_PACE_LEAN
; hlib_debt_repay: HL = the time the game's own delay is about to spend (1/16 lines) -> HL = the part of it to
; skip (all of the debt it can take), the debt less that. The engine shortens its delay loop by HL (Quazatron's
; t_dly: DD80 starts shorter). AF, DE lost.
hlib_debt_repay:
        ex de,hl
        ld hl,(HLIB_V_PACE + 4)
        or a
        sbc hl,de
        jr c,.all               ; less debt than the delay: skip the debt
        ld (HLIB_V_PACE + 4),hl ; skip the whole delay
        ex de,hl
        ret
.all:   ld hl,(HLIB_V_PACE + 4)
        ld de,0
        ld (HLIB_V_PACE + 4),de
        ret

; hlib_pace_hold / hlib_pace_resume: the time between is left out of every window and debt window (the engine's
; ISR wrapper, interrupts off). AF, BC, HL lost; DE kept.
hlib_pace_hold:
        call hlib_line
        ld (HLIB_V_PACE + 16),hl
        ret

hlib_pace_resume:
        push de
        call hlib_line
        ld de,(HLIB_V_PACE + 16)
        or a
        sbc hl,de
        jr nc,.p
        call hlib_nl
        add hl,bc
.p:     ld de,(HLIB_V_PACE + 14)
        add hl,de
        ld (HLIB_V_PACE + 14),hl        ; one 16-bit write: a reading sees it whole
        pop de
        ret
    ENDIF
    ENDIF
