; Shared hook library: the pace limiter for the ORIGINAL target (card patch.pace-limiter). After Three
; Weeks' pace window (pilot runs/three_weeks, three_weeks_hooks.asm x_line / x_tick / x_pad). NEW
; engines only (Dean's rule). Unit tests and negative control: nexclash/hooklib.py (selftest.py --tools).
;
; A hook that replaces slow original code (a blit, a plot) can be FASTER than it: sprite drawing costs
; less than the ULA plot, and its own work runs at 28 MHz. Under the ORIGINAL pace target the game must
; still take the original's time, so the hook waits on the video line (NR 0x1E / 0x1F) until the
; displaced code's time has passed, less the hook time spent outside the window since the last one
; (the debt). Time over the window carries in the debt to the next windows.
;
;   CALL hlib_pace_open        at the window's start (the hook's entry)
;   ... the hook's work, any speed (CALL hlib_pace_tick at least once a frame in a long window)
;   HL = target (1/16 lines at 3.5 MHz: hooklib.lines16), A = the latched incoming speed, CALL hlib_pace_wait
;   CALL hlib_debt_open / A = unmeasured part (1/16 lines), CALL hlib_debt_close  around a hook outside
;   any window whose added time the next window repays (never inside an open window: counted twice);
;   CALL hlib_debt_tick at least once a frame in between when that hook can run longer than a frame
; The target scales with the incoming speed (>> A): a caller at 7 MHz had the original at 7 MHz.
; With interrupts on at the site, wait at the latched speed (HLIB_SPEED_OUT first): the game's ISR then
; runs at its own clock during the wait. A wait gives up after 65536 polls (an emulator with no line
; counter), so a missing NR 0x1E never hangs the game.
;
; The engine defines, before the INCLUDE:
;   HLIB_V_PACE EQU <14 bytes of hook RAM, zero at start>
;       +0 last line read, +2 lines elapsed in the window, +4 debt (1/16 lines), +6 lines a frame
;       (the engine's setup stores the timing mode's when it is chosen at run time, 60 Hz; 0 = HLIB_PACE_NL;
;       never learned from a poll), +8 line at an outside hook's start, +10 window open, +12 polls left
;   HLIB_PACE_NL EQU <lines a frame of the game's timing mode: 312 48K, 311 128K / +3 (50 Hz)>
; hlib_line keeps DE; the others keep nothing but IX, IY and the alternate set.

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
