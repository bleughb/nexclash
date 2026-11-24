; Hard Drivin' (128K), route 2a "steps" (prototype hd4): every original update runs as N sub-steps (N = 1, 2, 4;
; s = log2 N) at 28 MHz, each advancing game time by 1 / N, so the controls are read and the view drawn N times an
; update at the original's game speed, paced to real time. games/hard_drivin.md "Route 2" has the design; the
; reference rules are nexclash/hard_drivin.py (Spec, the "steps" section), which verify_steps checks this code against.
;
; - Sub-steps: the driver (CALL t_drv replaces CALL 0x9E34 at 0x9E2F and 0xFC4C) runs N x (PUSH CONT; JP 0x9E34). The
;   car physics' accumulations are divided by N (8-bit fractions kept here, not in game RAM: positions, angles,
;   heading, speed, skid velocity, steering; relaxation toward the road with C = 75 / 41 at N = 2 / 4); counters,
;   traffic, timers, gravity, the clock flash and manual gear shifts run once per update through one-byte gates the driver writes
;   (g_first / g_last); N = 1 = the original game byte for byte.
; - Pace (real time): each original update = UPD_L = 10 frames x 311 lines (5 updates = one lap-clock second). A
;   line clock (lclk, NR 0x1E/0x1F polled: clk) is advanced at the driver entry / exit, in the copy hook and at the
;   render's tick site D6FE. Sub-step i's view is copied no earlier than sbase + (i + 1) x UPD_L / N (off_tab), then
;   only while the beam is below the view (lines 128..262: no tear); late: no wait (the debt carried by the absolute
;   schedule), capped at DEBTCAP at the driver entry; resync (x_live = 0) at boot, on a plain update and at 9E12.
; - N (adaptive): from c_sub = the last update's busy lines per sub-step (waits excluded) with hysteresis: from N = 4
;   stay at 4 while c <= C4ST, else 2 while c <= C2ST, else 1; from 1 / 2 up to 4 only when c <= C4UP, to 2 when
;   c <= C2UP (from 1) / C2ST (staying at 2). n_force (0 = none) fixes N (the verify's fixed-N cases).
; - Time-out update (950B = 4, 91DC = 950C = 950D = 0): PLAIN pass-through (page unmapped, JP 9E34 with the loop's
;   return address): the original update exactly, so its escape (A3ED POP / POP) leaves nothing of the driver behind.
; - 9E12 (CALL F487 -> CALL T_ESC): x_live := 0; inside the driver every data patch back, the incoming speed.
; - Push-out A4DB JP A834 -> JP T_BNC: one WHOLE step (the original's escape from an object).
; - 9E88 (CALL E92E -> CALL T_RMAP): the page mapped again after the update's OUTs to 7FFD (9E7C / 9E86): on the Next
;   a write to 7FFD sets MMU slots 0-1 back to ROM.
; - Render guards (all N, in and out of the driver; latent in the original, reached with new camera positions):
;   clip-vertex append CEB9 (drop a vertex past 9E11), span fill C7C0 (skip a polygon with a vertex y >= 80h), shift
;   stub A0E7 / D758 (scale clamped to 1..6).
; - Exact speedups (in the driver; outside it the ROM side runs the original): Z80N MUL for the object multiply's
;   shift-add (C541 -> C588) and the clip multiply's 8 x 8 path (D030 -> CFBE), every register / flag as the
;   original; the view copy by zxnDMA (128 rows of 32 bytes, 28 MHz), then the original's last row from DE07 (its
;   registers, DE49 / DE4F and its inner CALL's stack word as the original).
; - Heading blend (display only; bl_on, default 1): the render's camera matrix interpolated toward the next heading
;   unit by the heading's fraction A9A5 (h_blend at 9EE3), the game's matrix back after the render (h_rpost).
; Memory: the hook page PG_CODE in MMU slot 1 (0x2000-0x3FFF) for the whole driver. Each site calls / jumps to a
; trampoline at SH (8-byte slots): the alt ROM's bytes there are the ORIGINAL instruction(s), the page's bytes at the
; same address jump to the hook. Stacks: the hooks run on their own stack (STK). Interrupts: off in play, never
; enabled. Labels named in nexclash/hard_drivin.py STEPS_NEG mark the negative controls' page-byte patches.
; Assemble: python tools/asm2profile.py hard_drivin_steps -> docs/profiles/hard_drivin_steps.json hooks.page (8K)
; and hooks.rom (the alt ROM's bytes at SH).

        DEVICE NOSLOT64K
        OPT --zxnext

PG_CODE EQU 36
SH      EQU 0x3870                      ; trampolines (Sinclair's ROM is 0xFF at 0x386E-0x3CFF)
LOOP    EQU 0x9E34
RENDER  EQU 0x9EA9
VCOPY   EQU 0xDC37
RET_R   EQU 0x9E57
RET_C   EQU 0x9E6E
UPD_L   EQU 3110                        ; lines of one original update (10 frames x 311)
NLINES  EQU 311
DEBTCAP EQU 933                         ; lines (3 frames)
BAND0   EQU 128                         ; copy start lines: below the view (rows 0-127)
BAND1   EQU 262
C4ST    EQU 660                         ; lines a sub-step: 4 x 660 + 4 band waits (~56) = 2864 = 92 % of UPD_L
C4UP    EQU 600                         ; 4 x 600 + 224 = 2624 = 84 %
C2ST    EQU 1350                        ; 2 x 1350 + 112 = 2812 = 90 %
C2UP    EQU 1200                        ; 2 x 1200 + 112 = 2512 = 81 %
C_INIT  EQU 1000                        ; c_sub before any measurement: N = 2

; trampoline slots (8 bytes each; the same addresses on both sides)
T_DRV   EQU SH+0*8
T_POS   EQU SH+1*8
T_ANG   EQU SH+2*8
T_VPRE  EQU SH+3*8
T_VPOST EQU SH+4*8
T_VR    EQU SH+5*8
T_SPEED EQU SH+6*8
T_STM   EQU SH+7*8
T_STP   EQU SH+8*8
T_GUARD EQU SH+9*8
T_REND  EQU SH+10*8
T_COPY  EQU SH+11*8
T_CONT  EQU SH+12*8
T_DEXIT EQU SH+13*8
T_GEXIT EQU SH+29*8                     ; 16 bytes (stage 2 had 8 here: its 10 bytes ran into T_FILL)
T_FILL  EQU SH+15*8
T_FEXIT EQU SH+16*8                     ; 16 bytes
T_SHIFT EQU SH+18*8
T_SEXIT EQU SH+19*8                     ; 16 bytes
T_SHIFT2 EQU SH+21*8
T_SEXIT2 EQU SH+22*8                    ; 16 bytes
T_BNC   EQU SH+24*8
T_ESC   EQU SH+25*8
T_EEXIT EQU SH+26*8
T_TICK  EQU SH+27*8
T_PLAIN EQU SH+28*8
T_RMAP  EQU SH+31*8
T_RMEXIT EQU SH+32*8
T_MUL8  EQU SH+33*8
T_MUL88 EQU SH+34*8
T_BLEND EQU SH+35*8
T_END   EQU SH+36*8

        ORG 0x2000

; ---- the driver: CALL t_drv replaces CALL 0x9E34 at 0x9E2F (practice loop) and 0xFC4C (race / replay loop) ------
drv:    ld (d_sp),sp                    ; S: (S) = the loop's return address (9E32 / FC4F)
        ld sp,STK
        push af
        push bc
        push de
        push hl
        ld a,1
        ld (in_drv),a
        ld hl,(d_sp)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (hs_ret),de
        ld bc,0x243B                    ; the incoming speed (NR 0x07), restored after render / copy and at exit
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        ld (d_spd),a
.tp:    ld a,(0x950B)                   ; the time-out predicate: this update may leave by A3ED (POP, POP): PLAIN
        cp 4
        jr nz,.nt
        ld a,(0x91DC)
        ld hl,0x950C
        or (hl)
        inc hl
        or (hl)
        jr nz,.nt
        ld hl,(n_tout)
        inc hl
        ld (n_tout),hl
        xor a
        ld (x_live),a                   ; the pace resyncs at the next entry
        ld (in_drv),a
        inc a
        ld (hs_n),a                     ; (spec: N = 1, s = 0)
        dec a
        ld (hs_s),a
        ld hl,(d_sp)                    ; (S) = the loop's return address, as CALL 9E34 left it
        ld de,(hs_ret)
        ld (hl),e
        inc hl
        ld (hl),d
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(d_sp)
        jp T_PLAIN                      ; slot 1 = ROM, then JP 9E34: the original update
.nt:
        ld a,3
        nextreg 0x07,3                  ; the logic at 28 MHz
        ld (g_spd),a
        ; ---- pace: the line clock, this update's schedule base
        call clk
        ld (busy0),hl
        ld a,(x_live)
        or a
        jr nz,.live
        ld (sbase),hl                   ; resync: this update starts now
        jr .pc
.live:  ld de,(sbase)                   ; late = now - sbase (sbase advanced at the last exit)
        or a
        sbc hl,de
        bit 7,h
        jr nz,.pc                       ; early (not expected): the schedule stands
        ld de,DEBTCAP+1
        or a
        sbc hl,de
        add hl,de
        jr c,.pc
        ld hl,(busy0)                   ; over the cap: sbase := now - DEBTCAP
        ld de,DEBTCAP
        or a
        sbc hl,de
        ld (sbase),hl
        ld hl,(n_cap)
        inc hl
        ld (n_cap),hl
.pc:    ld hl,0
        ld (wsum),hl
        ; ---- N for this update
        ld a,(n_force)                  ; (a test override; 0 = none)
        or a
        jr nz,.tn
        ld hl,(c_sub)                   ; adaptive, with hysteresis
        ld a,(n_cur)
        cp 4
        jr z,.f4
        ld de,C4UP+1                    ; from 1 / 2: up to 4?
        or a
        sbc hl,de
        add hl,de
        ld a,4
        jr c,.got
        ld a,(n_cur)
        cp 2
        ld de,C2ST+1                    ; staying at 2
        jr z,.f2
        ld de,C2UP+1                    ; from 1 up to 2
.f2:    or a
        sbc hl,de
        add hl,de
        ld a,2
        jr c,.got
        ld a,1
        jr .got
.f4:    ld de,C4ST+1
        or a
        sbc hl,de
        add hl,de
        ld a,4
        jr c,.got
        ld de,C2ST+1
        or a
        sbc hl,de
        add hl,de
        ld a,2
        jr c,.got
        ld a,1
.got:   ld (n_cur),a
.tn:    ld (hs_n),a
        push af
        ld hl,n_cnt-1                   ; statistics: updates at N = 1 / 2 / 4 (n_cnt + N - 1, bytes x 2)
        ld e,a
        ld d,0
        add hl,de
        add hl,de
        dec hl                          ; n_cnt + 2 (N - 1)
        inc (hl)
        jr nz,.sc
        inc hl
        inc (hl)
.sc:    pop af
        ld b,0                          ; s
        srl a
        jr z,.s0
.s1:    inc b
        srl a
        jr nz,.s1
.s0:    ld a,b
        ld (hs_s),a
        ld e,b
        ld d,0
        ld hl,c_tab
        add hl,de
        ld a,(hl)
        ld (hs_c),a
        ld hl,st_tab                    ; throttle words: step = 500 >> s, limit = 7500 + step
        add hl,de
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (0xA6A4),de
        ld (0xA6B7),de
        ld hl,7500
        add hl,de
        ld (0xA6A8),hl
        xor a
        ld (hs_i),a
        ; ---- a sub-step: the gates for hs_i, (S) = CONT, the game's registers, JP 9E34
.sub:   ld a,(hs_i)                     ; 'first' gates: open on sub-step 0
        ld hl,g_first
        ld b,G_FIRSTN
        call setg
        ld a,(hs_n)                     ; 'last' gates: open on sub-step N-1
        ld b,a
        ld a,(hs_i)
        inc a
        sub b                           ; 0 on the last
        ld hl,g_last
        ld b,G_LASTN
        call setg
        ld hl,(d_sp)
        ld (hl),low T_CONT
        inc hl
        ld (hl),high T_CONT
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(d_sp)
        jp LOOP

; cont: 9E34 returned (to T_CONT), SP = S + 2
cont:   ld (d_sp),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        ld hl,(d_sp)
        dec hl
        dec hl
        ld (d_sp),hl                    ; S again
        ld hl,hs_i
        inc (hl)
        ld a,(hs_n)
        cp (hl)
        jr nz,drv.sub
        ; ---- the whole update done: every data patch back to the original byte
        call restore
        ; ---- pace: this update's busy lines (from the last exit, or this entry after a resync), waits excluded
        call clk
        ld a,(x_live)
        or a
        ld de,(t_exit)
        jr nz,.cx
        ld de,(busy0)
.cx:    or a
        sbc hl,de
        ld de,(wsum)
        or a
        sbc hl,de
        jr nc,.cp
        ld hl,0
.cp:    ld (cost),hl
        ld a,(hs_s)
        or a
        jr z,.cs
.cr:    srl h
        rr l
        dec a
        jr nz,.cr
.cs:    ld (c_sub),hl
        ld hl,(lclk)
        ld (t_exit),hl
        ld hl,(sbase)
        ld de,UPD_L
        add hl,de
        ld (sbase),hl                   ; the next update's base
        ld a,1
        ld (x_live),a
        ld hl,(d_sp)
        ld de,(hs_ret)
        ld (hl),e
        inc hl
        ld (hl),d
        xor a
        ld (in_drv),a
        ld a,(d_spd)
        nextreg 0x07,a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(d_sp)                    ; (S) = the loop's return address: RET as the original's
        jp T_DEXIT

; restore: every data patch back to the original byte (gates open, throttle words). AF, BC, DE, HL lost
restore:
        ld hl,g_first
        ld b,G_FIRSTN+G_LASTN           ; (g_last follows g_first)
        xor a
        call setg
.tw:    ld hl,500
        ld (0xA6A4),hl
        ld (0xA6B7),hl
        ld hl,8000
        ld (0xA6A8),hl
        ret

; clk: the line clock. HL = lclk advanced by the lines since the last reading (one unseen wrap at most: callers are
; under a frame apart while the clock is live); (lprev) = this reading (0 = the first pixel row .. 310). AF, BC, DE lost
clk:    ld bc,0x243B
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
        ld de,(lprev)
        ld (lprev),hl
        or a
        sbc hl,de
        jr nc,.p
        ld de,NLINES
        add hl,de
.p:     ld de,(lclk)
        add hl,de
        ld (lclk),hl
        ret

; pace_view: before sub-step hs_i's copy: wait until lclk >= sbase + off_tab[s][i], then until the beam is in
; BAND0..BAND1; the waited lines go to wsum. Gives up after 65536 polls (no line counter). AF, BC, DE, HL lost
pace_view:
        call clk
        ld (w0),hl
        ld a,(hs_s)
        add a,a
        add a,a
        add a,a                         ; s x 8
        ld e,a
        ld a,(hs_i)
        add a,a
        add a,e
        ld e,a
        ld d,0
        ld hl,off_tab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(sbase)
        add hl,de
        ld (tgt),hl
        ld hl,0
        ld (pcnt),hl
.w:     ld hl,(lclk)
        ld de,(tgt)
        or a
        sbc hl,de
        bit 7,h
        jr z,.b                         ; lclk - tgt >= 0 (signed)
        call poll
        jr nz,.w
        jr .d
.b:     ld hl,(lprev)                   ; the band: BAND0 <= line <= BAND1
        ld de,BAND0
        or a
        sbc hl,de
        jr c,.bw
        ld hl,(lprev)
        ld de,BAND1+1
        or a
        sbc hl,de
        jr c,.d
.bw:    call poll
        jr nz,.b
.d:     ld hl,(lclk)
        ld de,(w0)
        or a
        sbc hl,de
        ld de,(wsum)
        add hl,de
        ld (wsum),hl
        ret

; poll: clk once more; Z when the poll budget is spent
poll:   call clk
        ld hl,(pcnt)
        dec hl
        ld (pcnt),hl
        ld a,h
        or l
        ret

off_tab:
        dw UPD_L, 0, 0, 0                                       ; s = 0
        dw UPD_L/2, UPD_L, 0, 0                                 ; s = 1
        dw UPD_L/4, UPD_L/2, (3*UPD_L)/4, UPD_L                 ; s = 2

; ---- tick: the render's site D6FE (CALL D77D -> CALL T_TICK; page side here, inside the driver) ----------------
tick:   ld (t_sp),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        call clk
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(t_sp)
        jp 0xD77D                       ; (the site's CALL pushed D701)

; ---- h_esc: 9E12 CALL F487 (CALL T_ESC), everywhere (interrupts may be on: menus) -------------------------------
h_esc:  ld (e_sp),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        xor a
        ld (x_live),a                   ; the pace resyncs at the next driver entry
        ld a,(in_drv)
        or a
        jr z,.x
        call restore                    ; an escape from inside the driver: every data patch back, speed back
        xor a
        ld (in_drv),a
        ld a,(d_spd)
        nextreg 0x07,a
        ld hl,(n_esc)
        inc hl
        ld (n_esc),hl
.x:     pop hl
        pop de
        pop bc
        pop af
        ld sp,(e_sp)
        jp T_EEXIT

; ---- h_bounce: A4DB JP A834 (JP T_BNC): the collision push-out, one WHOLE step (spec bounce 'full') ---------------
h_bounce:
        ld (g_sp),sp
        ld sp,STK
        push af
        ld a,(hs_s)
        or a
        jr z,.orig
        push bc
        push de
        push hl
        push ix
        ld de,(0xA99C)
        call mkinc0
        ld hl,0xA988
        ld ix,fr_px
        call acc16w
        ld de,(0xA99E)
        call mkinc0
        ld hl,0xA98A
        ld ix,fr_py
        call acc16w
        ld de,(0xA9A0)
.z:     call mkinc0
        ld hl,0xA98C
        ld ix,fr_pz
        call acc16w
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)
        ret
.orig:  pop af
        ld sp,(g_sp)
        jp 0xA834                       ; the pos site: s = 0 there too (the original)

; ---- h_rmap: 9E88 CALL E92E (CALL T_RMAP), everywhere: the update's OUTs to 7FFD (9E7C / 9E86, the sound bank
; around EA60) set MMU slot 1 back to ROM on the Next; inside the driver the page is mapped again here (the hooks
; after 9E88 and T_CONT need it); outside, slot 1 goes back to ROM
h_rmap: ld (m_sp),sp
        ld sp,STK
        push af
        ld a,(in_drv)
        or a
        jr z,.out
        pop af
        ld sp,(m_sp)
.j:     jp 0xE92E                       ; (the site's CALL pushed 9E8B)
.out:   pop af
        ld sp,(m_sp)
        jp T_RMEXIT

; mkinc0: inc24 = DE << 8 (a whole step). AF lost
mkinc0: xor a
        ld (inc24),a
        ld (inc24+1),de
        ret

; setg: HL = gate table (addr, open, closed), B = entries, A = 0: open, else closed. AF, DE, HL, B lost
setg:   ld c,a
.l:     ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        inc hl
        inc c
        dec c
        jr z,.o
        ld a,(hl)
.o:     inc hl
        ld (de),a
        djnz .l
        ret

g_first:
        dw 0x9E38 : db 0x28,0x18        ; crash timer 958B + F5D5 start
        dw 0xF4AD : db 0xC0,0xC9        ; odometer F4A9
g_gear: dw 0xA658 : db 0xC8,0xC9        ; manual gears 96AB (A65C-A67E: W / S, indicator, 91DE): once an update
G_FIRSTN EQU ($-g_first)/4
g_last:
        dw 0xFAD6 : db 0x20,0x18        ; traffic / ghost / scripted-path move
        dw 0xA3B4 : db 0x20,0x18        ; clock flash XOR 5A3A
        dw 0xA3C4 : db 0x3C,0x00        ; clock sub-count 950B
        dw 0xFD5F : db 0x20,0x18        ; 91DC countdown
        dw 0x9E94 : db 0xC8,0xC9        ; timer 91DD
        dw 0xA82D : db 0x0C,0x00        ; gravity
        dw 0xFD8E : db 0x02,0x00        ; message timer 91CF (race)
        dw 0xFDA8 : db 0x02,0x00        ; message timer 91CE
        dw 0xFDCE : db 0x02,0x00        ; message timer 91CF (practice)
        dw 0xE92E : db 0x3A,0xC9        ; obstacle-box crash test
G_LASTN EQU ($-g_last)/4

sw_tab: db 4,2,4,1                      ; (unused: the prototype's switching variant; kept, the bytes = hd4's)
c_tab:  db 0,75,41                      ; relaxation constant by s (x/256)
st_tab: dw 500,250,125                  ; throttle step by s

; ---- common entry / exit of the physics hooks (JP / CALL from the site; game SP saved, own stack) -----------------
; mkinc: inc24 = (DE << 8) >> s (arithmetic). AF, BC lost
mkinc:  ld c,0
        ld a,(hs_s)
        or a
        jr z,.st
        ld b,a
.l:     sra d
        rr e
        rr c
.dj:    djnz .l
.st:    ld a,c
        ld (inc24),a
        ld (inc24+1),de
        ret

; fcheck16: DE = the game's value V; IX = fraction record (F, SH lo, SH hi, valid): V != SH or not valid -> F = 0x80
fcheck16:
        ld a,(ix+3)
        or a
        jr z,.r
        ld a,(ix+1)
        cp e
        jr nz,.r
        ld a,(ix+2)
        cp d
        ret z
.r:     ld (ix+0),0x80
        ret

; fcheck8: E = V (byte)
fcheck8:
        ld a,(ix+3)
        or a
        jr z,.r
        ld a,(ix+1)
        cp e
        ret z
.r:     ld (ix+0),0x80
        ret

; acc16w: [word at HL : F](24) += inc24; SH := the new word, valid. AF, DE lost (HL kept)
acc16w: ld e,(hl)
        inc hl
        ld d,(hl)
        dec hl
        call fcheck16
        push hl
        ld hl,inc24
        ld a,(ix+0)
        add a,(hl)
        ld (ix+0),a
        inc hl
        ld a,e
        adc a,(hl)
        ld e,a
        inc hl
        ld a,d
        adc a,(hl)
        ld d,a
        pop hl
        ld (hl),e
        inc hl
        ld (hl),d
        dec hl
        ld (ix+1),e
        ld (ix+2),d
        ld (ix+3),1
        ret

; acc8: [byte at HL : F](16) += inc24 (low 16 bits); SH := the new byte, valid. AF, DE lost
acc8:   ld e,(hl)
        call fcheck8
        ld a,(inc24)
        add a,(ix+0)
        ld (ix+0),a
        ld a,(inc24+1)
        adc a,e
        ld (hl),a
        ld (ix+1),a
        ld (ix+3),1
        ret

; ---- h_pos: A834 (JP): positions += velocity / N ----------------------------------------------------------------
h_pos:  ld (g_sp),sp
        ld sp,STK
        push af
        ld a,(hs_s)
        or a
        jr z,.orig
        push bc
        push de
        push hl
        push ix
        ld de,(0xA99C)
        call mkinc
        ld hl,0xA988
        ld ix,fr_px
        call acc16w
        ld de,(0xA99E)
        call mkinc
        ld hl,0xA98A
        ld ix,fr_py
        call acc16w
.mz:    ld de,(0xA9A0)
        call mkinc
        ld hl,0xA98C
        ld ix,fr_pz
        call acc16w
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)
        ret
.orig:  pop af
        ld sp,(g_sp)
        ld hl,(0xA988)
        jp 0xA837

; ---- h_ang: A856 (JP): angles / heading += rates / N; relaxation toward 960D / 960E when called from A7BA ---------
h_ang:  ld (g_sp),sp
        ld sp,STK
        push af
        ld a,(hs_s)
        or a
        jp z,.orig
        push bc
        push de
        push hl
        push ix
        ld hl,(g_sp)                    ; the return address: A7BD = from A7BA (relaxation)
        ld a,(hl)
        cp 0xBD
        jr nz,.n
        inc hl
        ld a,(hl)
        cp 0xA7
        jr nz,.n
        ld a,1
        jr .r
.n:     xor a
.r:     ld (relax),a
        ld hl,0xA98F
        ld ix,fr_a0
        ld bc,0x960D
        ld de,0xA9A2
        call ang1
        ld hl,0xA991
        ld ix,fr_a2
.t2:    ld bc,0x960E
        ld de,0xA9A4
        call ang1
        ; heading [A990:A9A5:F_HD] += (A9A3:A9A6 << 8) >> s
        ld a,(0xA9A6)
        ld e,a
        ld a,(0xA9A3)
        ld d,a
        call mkinc
        ld a,(0xA9A5)
        ld e,a
        ld a,(0xA990)
        ld d,a
        ld ix,fr_hd
        call fcheck16
        ld hl,inc24
        ld a,(ix+0)
        add a,(hl)
        ld (ix+0),a
        inc hl
        ld a,e
        adc a,(hl)
        ld e,a
        inc hl
        ld a,d
.hc:    adc a,(hl)
        ld d,a
        ld a,e
        ld (0xA9A5),a
        ld a,d
        ld (0xA990),a
        ld (ix+1),e
        ld (ix+2),d
        ld (ix+3),1
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)
        ret
.orig:  pop af
        ld sp,(g_sp)
        ld a,(0xA98F)
        jp 0xA859

; ang1: HL = the angle byte, IX = its record, BC = the relaxation target, DE = the rate byte
ang1:   ld a,(relax)
        or a
        jr nz,.rx
        ld a,(de)                       ; inc = (s8(rate) << 8) >> s
        ld e,a
        rla
        sbc a,a
        ld d,a
        call mkinc
        jp acc8
.rx:    push hl
        ld e,(hl)
        call fcheck8
        ld a,(bc)                       ; g = target - A (signed byte)
        sub e
        ld d,a
        ld a,0x80                       ; gap = g * 256 + 0x80 - F, clamped to 16-bit signed
        sub (ix+0)
        ld l,a
        ld a,d
        sbc a,0
        ld h,a
        jp po,.g
        ld hl,0x8000
.g:     ld a,(hs_c)                     ; P = |gap| x C (24-bit), negated when gap < 0
        ld c,h                          ; C = sign source
        bit 7,h
        jr z,.p
        xor a                           ; |gap| (0x8000 stays 0x8000 as unsigned)
        sub l
        ld l,a
        ld a,0
        sbc a,h
        ld h,a
        ld a,(hs_c)
.p:     ld b,a                          ; B = C
        ld d,l
        ld e,b
        mul d,e                         ; DE = lo x C
        push de
        ld d,h
        ld e,b
        mul d,e                         ; DE = hi x C
        pop hl                          ; HL = lo x C: P0 = L, P1 = H + E, P2 = D + carry
        ld a,h
        add a,e
        ld h,a                          ; P1
        ld a,d
        adc a,0
        ld d,a                          ; P2
        ld e,l                          ; P0
        bit 7,c
        jr z,.q
        xor a                           ; P = -P (24-bit)
        sub e
        ld e,a
        ld a,0
        sbc a,h
        ld h,a
        ld a,0
        sbc a,d
        ld d,a
.q:     ld a,e                          ; P += 128; inc = P >> 8 (16-bit: P2:P1)
        add a,128
        ld a,h
        adc a,0
        ld (inc24),a
        ld a,d
        adc a,0
        ld (inc24+1),a
        pop hl
        jp acc8

; ---- h_vpre: A71B (JP): V0 := velocity (every N), then LD A,(951E) ------------------------------------------------
h_vpre: ld (g_sp),sp
        ld sp,STK
        push hl
        ld hl,(0xA99C)
        ld (v0),hl
        ld hl,(0xA99E)
        ld (v0+2),hl
.z:     ld hl,(0xA9A0)
        ld (v0+4),hl
        pop hl
        ld sp,(g_sp)
        ld a,(0x951E)
        jp 0xA71E

; ---- h_vpost: A793 (CALL A88B -> CALL here): skid mode (965D = 1) keeps 1/N of the velocity change -------------
h_vpost:
        ld (g_sp),sp
        ld sp,STK
        push af
        ld a,(hs_s)
        or a
        jr z,.x
        ld a,(0x965D)
        cp 1
        jr nz,.x
        push bc
        push de
        push hl
        push ix
        ld hl,0xA99C
        ld de,v0
        ld ix,fr_vx
        call vax
        ld hl,0xA99E
        ld de,v0+2
        ld ix,fr_vy
        call vax
        ld hl,0xA9A0
        ld de,v0+4
        ld ix,fr_vz
        call vax
        pop ix
        pop hl
        pop de
        pop bc
.x:     pop af
        ld sp,(g_sp)
        jp 0xA88B                       ; (the site's CALL pushed A796, as CALL A88B)

; vax: HL = velocity word, DE = its V0, IX = record: d = vel - V0; vel := V0; [vel:F] += (d << 8) >> s
vax:    push hl
        ld a,(de)
        ld c,a
        inc de
        ld a,(de)
        ld b,a                          ; BC = V0
        ld e,(hl)
        inc hl
        ld d,(hl)                       ; DE = vel
.st:    ld (hl),b
        dec hl
        ld (hl),c
        ex de,hl
        or a
        sbc hl,bc
        ex de,hl                        ; DE = d
        call mkinc
        pop hl
        jp acc16w

; ---- h_vr: A7F6 (JP): VR := the velocity rebuilt from the speed, VRF := 1; then LD HL,(965B) ---------------------
h_vr:   ld hl,(0xA99C)                  ; (HL: the original's next instruction loads it)
        ld (vr),hl
        ld hl,(0xA99E)
        ld (vr+2),hl
        ld hl,(0xA9A0)
        ld (vr+4),hl
.f:     ld hl,vrf
        ld (hl),1
        ld hl,(0x965B)
        jp 0xA7F9

; ---- h_speed: A8BB (CALL F568 -> CALL here), HL = the new speed (projection) -------------------------------------
h_speed:
        ld (g_sp),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        push ix
        ld (sp_new),hl
        ld a,(hs_s)
        or a
        jr z,.clr
        ld a,(0x965D)
        or a
        jr nz,.clr
.vc:    ld a,(vrf)                      ; scaled only after this road sub-step's own rebuild (VRF, V0 = VR in x, z)
        or a
        jr z,.whole
        ld hl,(v0)
        ld de,(vr)
        or a
        sbc hl,de
        jr nz,.whole
        ld hl,(v0+4)
        ld de,(vr+4)
        or a
        sbc hl,de
        jr nz,.whole
.scl:   xor a
        ld (vrf),a
        ld de,(0x965B)                  ; old (not written here: F568 erases the needle drawn for it)
        ld ix,fr_sp
        call fcheck16
        ld hl,(sp_new)
        or a
        sbc hl,de                       ; d = new - old
        push de
        ex de,hl
        call mkinc
        pop de
        ld hl,inc24
        ld a,(ix+0)
        add a,(hl)
        ld (ix+0),a
        inc hl
        ld a,e
        adc a,(hl)
        ld e,a
        inc hl
        ld a,d
        adc a,(hl)
        ld d,a
        ld (sp_new),de
        ld (ix+1),e
        ld (ix+2),d
        ld (ix+3),1
        jr .x
.whole: xor a                           ; the velocity came from elsewhere: the whole change, F_SP reset
        ld (vrf),a
        ld a,0x80
        ld (fr_sp),a
        xor a
        ld (fr_sp+3),a
        jr .x
.clr:   xor a
        ld (vrf),a
.x:     pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld hl,(sp_new)
        ld sp,(g_sp)
        jp 0xF568                       ; (the site's CALL pushed A8BE)

; ---- h_steer: A6D2 / A6DC (JP): steering 96AC -+ 30 / N with F_ST, clamped to [-120.0, +120.0] -----------------
h_stm:  ld (g_sp),sp
        ld sp,STK
        push af
        ld a,(hs_s)
        or a
        jr z,.orig
        push de
        ld de,-30
        jr h_steer
.orig:  pop af
        ld sp,(g_sp)
        ld a,(0x96AC)
        jp 0xA6D5

h_stp:  ld (g_sp),sp
        ld sp,STK
        push af
        ld a,(hs_s)
        or a
        jr z,.orig
        push de
        ld de,30
        jr h_steer
.orig:  pop af
        ld sp,(g_sp)
        ld a,(0x96AC)
        jp 0xA6DF

h_steer:                                ; AF, DE pushed; DE = the step
        push bc
        push hl
        push ix
        call mkinc                      ; inc24 = (step << 8) >> s (|inc| <= 7680: 16 bits)
        ld a,(0x96AC)
        ld e,a
        ld ix,fr_st
        call fcheck8
        ld h,e
        ld l,(ix+0)                     ; HL = v * 256 + F (signed)
        ld de,(inc24)
        or a
        adc hl,de
        jp pe,.ovf                      ; past 16 bits: beyond either bound
        ld a,h                          ; clamp: compare with the sign bit flipped (unsigned order)
        xor 0x80
        ld h,a
.hi1:   ld de,0xF881                    ; + 120.0 = 0x7880 (^ 0x8000 = 0xF880): HL' >= F881 -> F880
        or a
        sbc hl,de
        add hl,de
        jr c,.lo
.hi2:   ld hl,0xF880
.lo:    ld de,0x0880                    ; - 120.0 = 0x8880 (^ 0x8000 = 0x0880): HL' < 0880 -> 0880
        or a
        sbc hl,de
        add hl,de
        jr nc,.ok
        ex de,hl
.ok:    ld a,h
        xor 0x80
        ld h,a
        jr .w
.ovf:   ld hl,0x7880                    ; overflow toward the step's sign
        ld a,(inc24+1)
        bit 7,a
        jr z,.w
        ld hl,0x8880
.w:     ld a,h
        ld (0x96AC),a
        ld (ix+0),l
        ld (ix+1),h
        ld (ix+3),1
        pop ix
        pop hl
        pop bc
        pop de
        pop af
        ld sp,(g_sp)
        ret

; ---- h_guard: CEB9 LD A,(910A) (JP), all N, in and out of the driver: the clip-vertex append CEB1 writes 2 bytes at
; 9E00 + (910A); from (910A) = 12h on they would overwrite the update loop's code at 9E12: the vertex is dropped (RET)
h_guard:
        ld (gd_sp),sp
        ld sp,STK
        push af
        ld a,(0x910A)
.th:    cp 0x12
        jr nc,.drop
        ld a,(in_drv)
        or a
        jr z,.rk
        pop af
        ld sp,(gd_sp)
        ld a,(0x910A)
        jp 0xCEBC
.rk:    pop af
        ld sp,(gd_sp)
        jp T_GEXIT
.drop:  push hl
        ld hl,(n_drop)
        inc hl
        ld (n_drop),hl
        pop hl
        ld a,(in_drv)
        or a
        jr z,.rr
        pop af
        ld sp,(gd_sp)
        ret
.rr:    pop af
        ld sp,(gd_sp)
        jp T_DEXIT

; ---- h_fill: C7C0 PUSH HL; LD A,(910A) (JP; C7C3 is never reached), all N, in and out of the driver. The span fill
; C7C0 draws the polygon in 9E00 (x, y bytes, (910A) / 2 vertices) into the back buffer 8000-8FFF, rows 0-127: a vertex
; y >= 80h (the unclipped path D9B4 -> D9D2 copies the low bytes of vertices behind the camera, flagged 80h in their
; x high byte) runs the row pointer past 8FFF and the fill writes FF over 9000-96E5 (stage 1, run 150 N=4): skipped
; (RET, every register as at entry). Never reached by the original in the capture (max y 7Fh over 28,681 polygons).
h_fill: ld (fl_sp),sp
        ld sp,STK
        push af
        push bc
        push hl
        ld a,(0x910A)
        srl a
        jr z,.ok
        ld b,a
        ld hl,0x9E01
.l:     ld a,(hl)
.t:     rla
        jr c,.skip
        inc hl
        inc hl
        djnz .l
.ok:    pop hl
        pop bc
        ld a,(in_drv)
        or a
        jr z,.rk
        pop af
        ld sp,(fl_sp)
        push hl
        ld a,(0x910A)
        jp 0xC7C4
.rk:    pop af
        ld sp,(fl_sp)
        jp T_FEXIT
.skip:  ld hl,(n_skip)
        inc hl
        ld (n_skip),hl
        pop hl
        pop bc
        ld a,(in_drv)
        or a
        jr z,.rr
        pop af
        ld sp,(fl_sp)
        ret
.rr:    pop af
        ld sp,(fl_sp)
        jp T_DEXIT

; ---- h_shift: A0E7 RES 7,B; LD A,7 (JP; A0EA is never reached), all N, in and out of the driver. The render writes
; a shift stub at 91BA: B-1 x ADD HL,HL (A0F2) then 6-B NOPs (A0FB) before the RET at 91BF, B = the object's scale
; byte. B = 0 (DJNZ: 255 writes) or B >= 7 overwrite the RET and 91C0-92B8 (game state) and the stub runs into data
; (stage 2: run 150 N=4, update 167, camera inside an object). Clamped to 1..6 (the original's range: 1-6 over
; 28,877 objects in the capture, N = 1); B = 0 -> 1 (the nearest scale).
h_shift2:                               ; the same stub written by D756 (D758 RES 7,B; LD A,7 -> D75C SUB B)
        ld (sh_sp),sp
        ld sp,STK
        push af
        ld a,1
        jr h_shift.c
h_shift:
        ld (sh_sp),sp
        ld sp,STK
        push af
        xor a
.c:     ld (sh_which),a
        res 7,b
.cl:    ld a,b
        or a
        jr nz,.n0
        inc b
        jr .cnt
.n0:    cp 7
        jr c,.ok
        ld b,6
.cnt:   ld a,(n_clamp)
        inc a
        jr z,.ok
        ld (n_clamp),a
.ok:    ld a,(sh_which)
        or a
        jr nz,.two
        ld a,(in_drv)
        or a
        jr z,.rk
        pop af
        ld sp,(sh_sp)
        ld a,7
        jp 0xA0EB
.rk:    pop af
        ld sp,(sh_sp)
        jp T_SEXIT
.two:   ld a,(in_drv)
        or a
        jr z,.rk2
        pop af
        ld sp,(sh_sp)
        ld a,7
        jp 0xD75C
.rk2:   pop af
        ld sp,(sh_sp)
        jp T_SEXIT2

; ---- render / copy at 28 MHz (sites 0x9E54 / 0x9E6B): the return address planted, the speed restored after ----------
h_rend: ld (r_sp),sp                    ; S - 2: (S - 2) = RET_R
        ld sp,STK
        push hl
        ld hl,(r_sp)
        ld (hl),low h_rpost
        inc hl
        ld (hl),high h_rpost
        pop hl
        ld sp,(r_sp)
        nextreg 0x07,3
        jp RENDER
h_rpost:
        ld (r_sp),sp                    ; S
        ld sp,STK
        push af
        push hl
        ld a,(bl_act)                   ; the heading blend: the game's own camera matrix back (display only)
        or a
.rs:    call nz,bl_rest
        ld a,(g_spd)
        nextreg 0x07,a
        ld hl,(r_sp)
        dec hl
        ld (hl),high RET_R              ; the original's CALL left RET_R there
        dec hl
        ld (hl),low RET_R
        pop hl
        pop af
        ld sp,(r_sp)
        jp RET_R

h_copy: ld (r_sp),sp
        ld sp,STK
.pv:    call pace_view
        nextreg 0x07,3
vgo:    ld hl,dmatab                    ; the view by DMA (28 MHz): row r (8000 + 32 r) -> the screen's pixel row r
        ld bc,0x006B
        otir
        otir
        otir
        otir
        ld b,DMALEN-1024
        otir
        ld hl,(r_sp)                    ; the original's side effects: DE4F = its SP (S), DE49 = 1, its inner CALL's
        ld (0xDE4F),hl                  ; DC41 at S - 2; (S) = the way back to h_cpost
        ld a,1
        ld (0xDE49),a
        ld (hl),low h_cpost
        inc hl
        ld (hl),high h_cpost
        dec hl
        dec hl
        ld (hl),0xDC
        dec hl
        ld (hl),0x41
        exx
        ld hl,0x4FEF                    ; its state at DE07 in the last row: H'L' (screen), HL (8FE0); the rest of the
        exx                             ; original (that row's 32 bytes again) sets every register as the original
        ld hl,0x8FE0
        jp 0xDE07
h_cpost:
        ld (r_sp),sp
        ld sp,STK
        push af
        push hl
        ld a,(g_spd)
        nextreg 0x07,a
        ld hl,(r_sp)
        dec hl
        ld (hl),high RET_C
        dec hl
        ld (hl),low RET_C
        pop hl
        pop af
        ld sp,(r_sp)
        jp RET_C

; ---- exact speedups (Z80N MUL), all N, in the driver (outside it the trampolines' ROM side runs the original) ----
; h_mul8: C541 LD C,0; LD H,C (JP): the object multiply C52C after its sign / magnitude part: A = |A| (0..80h), DE =
; |DE| (0..8000h). The original's shift-add (bit 7 of A ignored) leaves at C588: A:HL = 2 x (A & 7Fh) x DE >> 8 by
; ADD HL,HL / ADC A,A on P = (A & 7Fh) x DE (the same last two instructions here: A, F the same), C = 0, DE kept;
; A & 7Fh = 0: HL = 0, A = 0, F of ADD A,A (40h).
h_mul8: and 0x7F
        jr z,.z
        ld (mtmp),de
        ld c,e
        ld e,a
        mul d,e                         ; hi = m x D
        ex de,hl
        ld d,a
        ld e,c
        mul d,e                         ; lo = m x E
        ld a,l
        add a,d
        ld l,e
        ld e,a
        ld a,h
.ac:    adc a,0
        ld h,e                          ; A:HL = P
        ld de,(mtmp)
        ld c,0
        add hl,hl
        adc a,a
        ld l,h
        ld h,a
        jp 0xC588
.z:     ld c,a
        ld h,a
        ld l,a
        add a,a
        jp 0xC588

; h_mul88: D030 RR E; JR C (JP): the clip multiply CEF2's 8 x 8 path (both high bytes 0: D = H = A = 0): the
; original leaves DE = L x E, L = H (0) at CFBE (POP AF there sets A, F)
h_mul88:
        ld d,l
        mul d,e
.lh:    ld l,h
        jp 0xCFBE

;  ---- heading blend (display only), all N in the driver: 9EE3 LD A,(A949) (JP), right after the render built its
; camera matrix A96B-A973 (D1A5 from the byte angles A94B-A94D, copied from A962-A96A). d = A9A5 - 80h (the heading's
; own fraction, centred: 80h = the byte heading exactly): M2 = D1A5 at heading A94C + sign(d) (A962-A96A, then put
; back), each entry M + sign(M2 - M) x ((|M2 - M| x |d| + 80h) >> 8) into A96B-A973 for the render (at most half a
; unit). h_rpost puts the game's matrix back (bl_rest): logic reads A96D / A970 / A973. bl_on = 0: off (Spec.blend).
h_blend:
        ld (bl_sp),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        exx
        push bc
        push de
        push hl
        exx
        ld a,(bl_on)
        or a
        jr z,.out
        ld a,(0xA9A5)
        sub 0x80
        jr z,.out
        ld (bl_d),a
        ld hl,0xA96B
        ld de,bl_m
        ld bc,9
        ldir
        ld a,(0xA94C)
        ld (bl_h),a
        ld b,a
        ld a,(bl_d)
        or a
        ld a,b
        jp m,.dn
        inc a
        jr .h
.dn:    dec a
.h:     ld (0xA94C),a
        call 0xD1A5                     ; A962-A96A = M2
        ld a,(bl_h)
        ld (0xA94C),a
        ld a,(bl_d)
        or a
        jp p,.w
        neg
.w:     ld c,a                          ; |d| 1..80h
        ld hl,bl_m
        ld ix,0xA962
        ld b,9
.l:     ld a,(hl)
        xor 0x80
        ld e,a
        ld a,(ix+0)
        xor 0x80
        sub e                           ; M2 - M (biased: unsigned order = signed order)
        jr nc,.p
        neg
        call .q
        ld e,a
        ld a,(hl)
        sub e
        jr .st
.p:     call .q
.pa:    add a,(hl)
.st:    ld (ix+9),a                     ; A96B + i: the blended entry
        ld a,(hl)
        ld (ix+0),a                     ; A962 + i: as the original left it
        inc hl
        inc ix
        djnz .l
        ld a,1
        ld (bl_act),a
.out:   exx
        pop hl
        pop de
        pop bc
        exx
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(bl_sp)
        ld a,(0xA949)
        jp 0x9EE6
.q:     ld d,a                          ; A = (A x |d| + 80h) >> 8
        ld e,c
        mul d,e
        ld a,e
        add a,0x80
        ld a,d
        adc a,0
        ret

; bl_rest: A96B-A973 := bl_m, bl_act := 0. AF lost (BC, DE, HL kept)
bl_rest:
        push bc
        push de
        push hl
        ld hl,bl_m
        ld de,0xA96B
        ld bc,9
        ldir
        xor a
        ld (bl_act),a
        pop hl
        pop de
        pop bc
        ret

bl_on:  db 1
bl_act: db 0
bl_d:   db 0
bl_h:   db 0
bl_sp:  dw 0
bl_m:   ds 9

; the view copy's DMA program: reset, A -> B 32 bytes, both memory + increment, continuous; then per row A and B
dmatab: db 0x83,0xC3
        db 0x7D
        dw 0x8000,32
        db 0x14,0x10,0xAD
        dw 0x4000
        db 0x82,0xCF,0x87
vrow = 1
        DUP 127
        db 0x1D
        dw 0x8000+vrow*32
        db 0xAD
        dw 0x4000+((vrow&0xC0)<<5)+((vrow&7)<<8)+((vrow&0x38)<<2)
        db 0xCF,0x87
vrow = vrow+1
        EDUP
dmaend:
DMALEN  EQU dmaend-dmatab
        ASSERT DMALEN == 1031
mtmp:   dw 0

; ---- hook state (Spec's names) -----------------------------------------------------------------------------------
hstate:
hs_n:   db 1
hs_s:   db 0
hs_i:   db 0
hs_c:   db 0
hs_ret: dw 0
; fraction records: F, SH lo, SH hi, valid (spec: SH None = not valid)
fr_px:  db 0x80,0,0,0
fr_py:  db 0x80,0,0,0
fr_pz:  db 0x80,0,0,0
fr_a0:  db 0x80,0,0,0
fr_a2:  db 0x80,0,0,0
fr_hd:  db 0x80,0,0,0
fr_sp:  db 0x80,0,0,0
fr_vx:  db 0x80,0,0,0
fr_vy:  db 0x80,0,0,0
fr_vz:  db 0x80,0,0,0
fr_st:  db 0x80,0,0,0
v0:     ds 6
vr:     ds 6
vrf:    db 0
hstate_end:
in_drv: db 0
sw_cnt: db 0                            ; (unused, as sw_tab)
n_force: db 0
n_tout: dw 0                            ; updates the time-out predicate forced to N = 1
n_drop: dw 0                            ; clip vertices dropped by the guard
n_skip: dw 0                            ; polygons skipped by the fill guard
n_clamp: db 0                           ; scale bytes clamped by the shift guard (saturating)
d_spd:  db 0                            ; the incoming speed (NR 0x07 bits 1-0)
g_spd:  db 0                            ; the speed render / copy return to
relax:  db 0
inc24:  ds 3
sp_new: dw 0
d_sp:   dw 0
g_sp:   dw 0
gd_sp:  dw 0
fl_sp:  dw 0
sh_sp:  dw 0
sh_which: db 0
r_sp:   dw 0
; ---- pace state (stage 3) ----
x_live: db 0                            ; 1: the last driver exit was this loop's (the clock and schedule run on)
lclk:   dw 0                            ; the line clock
lprev:  dw 0                            ; the last NR 1E/1F reading
sbase:  dw 0                            ; this update's schedule base (lines)
busy0:  dw 0                            ; lclk at this driver entry
t_exit: dw 0                            ; lclk at the last driver exit
wsum:   dw 0                            ; lines waited in this update
cost:   dw 0                            ; the last update's busy lines
c_sub:  dw C_INIT                       ; ... per sub-step (cost >> s)
n_cur:  db 2                            ; the adaptive N (hysteresis state)
w0:     dw 0
tgt:    dw 0
pcnt:   dw 0
n_cnt:  ds 8                            ; updates at N = 1, 2, (3), 4 (words)
n_cap:  dw 0                            ; entries over the debt cap
n_esc:  dw 0                            ; 9E12 reached inside the driver
t_sp:   dw 0
e_sp:   dw 0
m_sp:   dw 0
code_end:
        ASSERT code_end <= SH

; ---- the page's side of the trampolines ------------------------------------------------------------------------
        ORG T_DRV
        nextreg 0x51,PG_CODE
        jp drv
        ORG T_POS
        jp h_pos
        ORG T_ANG
        jp h_ang
        ORG T_VPRE
        jp h_vpre
        ORG T_VPOST
        jp h_vpost
        ORG T_VR
        jp h_vr
        ORG T_SPEED
        jp h_speed
        ORG T_STM
        jp h_stm
        ORG T_STP
        jp h_stp
        ORG T_GUARD
        nextreg 0x51,PG_CODE
        jp h_guard
        ORG T_REND
        jp h_rend
        ORG T_COPY
        jp h_copy
        ORG T_CONT
        jp cont
        ORG T_DEXIT
        nextreg 0x51,0xFF
        ret
        ORG T_GEXIT
        nextreg 0x51,0xFF
        ld a,(0x910A)
        jp 0xCEBC
        ORG T_FILL
        nextreg 0x51,PG_CODE
        jp h_fill
        ORG T_FEXIT
        nextreg 0x51,0xFF
        push hl
        ld a,(0x910A)
        jp 0xC7C4
        ORG T_SHIFT
        nextreg 0x51,PG_CODE
        jp h_shift
        ORG T_SEXIT
        nextreg 0x51,0xFF
        ld a,7
        jp 0xA0EB
        ORG T_SHIFT2
        nextreg 0x51,PG_CODE
        jp h_shift2
        ORG T_SEXIT2
        nextreg 0x51,0xFF
        ld a,7
        jp 0xD75C
        ORG T_BNC
        jp h_bounce
        ORG T_ESC
        nextreg 0x51,PG_CODE
        jp h_esc
        ORG T_EEXIT
        nextreg 0x51,0xFF
        jp 0xF487
        ORG T_TICK
        jp tick
        ORG T_PLAIN
        nextreg 0x51,0xFF
        jp LOOP
        ORG T_RMAP
        nextreg 0x51,PG_CODE
        jp h_rmap
        ORG T_RMEXIT
        nextreg 0x51,0xFF
        jp 0xE92E
        ORG T_MUL8
        jp h_mul8
        ORG T_MUL88
        jp h_mul88
        ORG T_BLEND
        jp h_blend
        ORG T_END
        ORG 0x3D00
        ds 0x3FFE-0x3D00
STK:
        SAVEBIN "hdsteps_page.bin",0x2000,0x2000

; ---- the alt ROM's bytes at SH: the original instruction(s) of each site, then back into the game (a site reached
; outside the driver behaves as the original). Assembled at 0x4000 (nothing else there), displaced to SH, slot by
; slot in address order (gaps 0).
        ORG 0x4000
        DISP SH
        ds T_DRV-$
r_drv:  nextreg 0x51,PG_CODE            ; -> the page's t_drv+4: jp drv
        ds 4,0xFF
        ds T_POS-$
        ld hl,(0xA988)                  ; A834
        jp 0xA837
        ds T_ANG-$
        ld a,(0xA98F)                   ; A856
        jp 0xA859
        ds T_VPRE-$
        ld a,(0x951E)                   ; A71B
        jp 0xA71E
        ds T_VPOST-$
        jp 0xA88B                       ; A793 CALL A88B (the CALL to here pushed A796)
        ds T_VR-$
        ld hl,(0x965B)                  ; A7F6
        jp 0xA7F9
        ds T_SPEED-$
        jp 0xF568                       ; A8BB CALL F568
        ds T_STM-$
        ld a,(0x96AC)                   ; A6D2
        jp 0xA6D5
        ds T_STP-$
        ld a,(0x96AC)                   ; A6DC
        jp 0xA6DF
        ds T_GUARD-$
        nextreg 0x51,PG_CODE            ; the guard runs everywhere (all N, in or out of the driver)
        ds 4,0xFF
        ds T_REND-$
        jp RENDER
        ds T_COPY-$
        jp VCOPY
        ds T_CONT-$
        ds 8,0xFF                       ; only reached inside the driver
        ds T_DEXIT-$
        nextreg 0x51,0xFF
        ret
        ds T_FILL-$
        nextreg 0x51,PG_CODE            ; the fill guard runs everywhere (all N, in or out of the driver)
        ds 4,0xFF
        ds T_FEXIT-$
        nextreg 0x51,0xFF
        push hl                         ; C7C0's instructions
        ld a,(0x910A)
        jp 0xC7C4
        ds T_SHIFT-$
        nextreg 0x51,PG_CODE            ; the shift-stub guard runs everywhere
        ds 4,0xFF
        ds T_SEXIT-$
        nextreg 0x51,0xFF
        ld a,7                          ; A0E9's instruction (B already RES 7 and clamped)
        jp 0xA0EB
        ds T_SHIFT2-$
        nextreg 0x51,PG_CODE
        ds 4,0xFF
        ds T_SEXIT2-$
        nextreg 0x51,0xFF
        ld a,7                          ; D75A's instruction
        jp 0xD75C
        ds T_BNC-$
        jp 0xA834                       ; A4DB JP A834
        ds T_ESC-$
        nextreg 0x51,PG_CODE            ; 9E12 (CALL F487 -> CALL here): runs everywhere
        ds 4,0xFF
        ds T_EEXIT-$
        nextreg 0x51,0xFF
        jp 0xF487
        ds T_TICK-$
        jp 0xD77D                       ; D6FE CALL D77D (outside the driver: the original)
        ds T_PLAIN-$
        nextreg 0x51,0xFF
        jp LOOP
        ds T_GEXIT-$
        nextreg 0x51,0xFF
        ld a,(0x910A)                   ; CEB9's instruction
        jp 0xCEBC
        ds T_RMAP-$
        nextreg 0x51,PG_CODE            ; 9E88 CALL E92E (after the OUTs to 7FFD at 9E7C / 9E86: on the Next a write
        ds 4,0xFF                       ; to 7FFD sets MMU 0-1 back to ROM): runs everywhere
        ds T_RMEXIT-$
        nextreg 0x51,0xFF
        jp 0xE92E
        ds T_MUL8-$
        ld c,0                          ; C541's instructions
        ld h,c
        jp 0xC544
        ds T_MUL88-$
        rr e                            ; D030's (the JR C as JP C)
        jp c,0xD053
        jp 0xD034
        ds T_BLEND-$
        ld a,(0xA949)                   ; 9EE3's instruction
        jp 0x9EE6
        ds T_END-$
r_end:
        ENT
        SAVEBIN "hdsteps_rom.bin",0x4000,r_end-SH
