; Cisco Heat (Image Works 1991, 128K): the smooth engine (games/cisco_heat.md "Design").
;
; The race loop (0x8BD4) runs one update per pass: 0x8AFE = logic + render into the linear back buffer
; 0x6000 + present (0x8827: copy to the hidden screen, flip at the next interrupt). Forward motion is
; per update (0x5BB3 = speed / 8), steering, keys, timer and music are per interrupt (0x9D6E). The
; original manages about 6 updates a second.
;
; This engine:
;  - h_upd (site 0x8BDE, CALL 0x8AFE): the real update, unchanged, at 28 MHz; then the update's
;    original time is estimated from its 28 MHz time (P = 8.02 * D + PACE_B, D without the present's
;    copy (measured, h_copy) and with the time the fast paths saved (v_sc): the six recordings' fit
;    scaled to the original as it runs on the Next) and the rest of that time is filled with
;    in-between frames; the next real update starts when P has passed (no debt carried).
;  - fast paths (v_fast; Patch.plain() turns them off for V1): h_copy (site 0x8847) copies the back
;    buffer to the screen by zxnDMA, a job a row; h_spr (site 0x91E3) runs the sprite blit's rows in
;    tight loops (LDIR, a mirror table). Each leaves RAM and registers as the game's code (unit tests).
;  - in-between ("spec") frame: the next update run ahead with a fraction f of its forward step, its
;    picture presented, then every byte the update writes put back (W ranges, saved in bank 6 via
;    MMU slot 0). The road stripes (advanced after the present) are set back by (1-f) of a step.
;    Interrupts during a spec frame run the game's handler on the real values: the bytes it shares
;    with the update (X ranges) are swapped around it. Display bytes stay live: 0x5B8B shown screen,
;    0x5B8C requested screen, 0x5B8E frame counter.
;  - h_pres (site 0x8827, the present's entry): inside h_upd the present first waits for the previous
;    flip (so the copy never targets the screen about to be shown), spec frames then wait for the
;    interrupt before their target one (2-frame cadence); every present flags the ISR to note its flip.
;  - h_isr (0x7D7D, JP 0x9D6E): a line clock (lines since start, updated every interrupt), the flip
;    times, the X swap while a spec frame runs.
;  - h_step (site 0x8AB6, LD (0x5BB3),A): spec frames store step * f / 256.
;  - h_load (site 0x8E33, CALL 0x8361): the stage tape blocks come from Next pages (no tape).
        DEVICE ZXSPECTRUMNEXT

; ------------------------------------------------------------------ game addresses
G_UPD   EQU 0x8AFE
G_COPY  EQU 0x8854              ; the present's copy (LDI)
G_ISR   EQU 0x9D6E
G_STEP  EQU 0x5BB3
G_STRIPE EQU 0x5BA6
G_LJSP  EQU 0x5B95              ; the race's saved SP: LD SP,(0x5B95) / RET leaves the race
G_BANK  EQU 0x5B8A              ; bank at 0xC000 (0x811C)
G_SHOWN EQU 0x5B8B              ; 0 / 8: screen shown (set by the ISR)
G_REQ   EQU 0x5B8C              ; 0 / 8: screen to show at the next interrupt (0x884A)
G_FRAMES EQU 0x5B8E             ; interrupt counter (16 bits)
G_CRASH EQU 0x5BAE              ; non-zero: the crash path 0xA26D
G_MODE2 EQU 0x5BC9              ; non-zero: the path 0xA3AD
G_STAGE EQU 0x8E4C              ; '1'..'5', 'X': the tape block's name digit
G_HDR   EQU 0x851C              ; the loader's header copy (16 bytes)
G_LEVEL EQU 0x5BA5              ; curve level -4..4 (track commands 1 / 2: 0x8204 / 0x81DB)
G_CTAB  EQU 0x5B27              ; the level's curve table: base + |level| * 208 (104 lines, 16 bits)
G_ROADN EQU 0x5B2D              ; road lines
G_OFFS  EQU 0x5BE7              ; per-line curve offsets (0x8220: +-table + the lateral shift)
G_LINES EQU 0xA83D              ; the line table from the offsets and the profile (0x8220's tail)
G_HILL  EQU 0xA053              ; the hill / horizon animation, by the step (after the road is drawn)
G_REDO  EQU 0x5BC3
G_LAT   EQU 0x5BB0              ; the player's offset across the road (0xAB9D: curve drift and steering by the step)
G_DRIFT EQU 0xAB9D
G_HZ    EQU 0x8191              ; the skyline band: (0x5B2B) rows of 26 bytes from bank 1 to (0x5B7F), stride 32
G_HZL   EQU 0x826F              ; the skyline bitmap a byte left (every second call: 0x8203 toggles)
G_HZR   EQU 0x82D7              ; ... a byte right
G_HZT   EQU 0x8203
G_HZROW EQU 0x5B7F
G_HZN   EQU 0x5B2B
HZ_TOP  EQU 0x6603              ; the band is clipped here (above: the panel)              ; non-zero: 0x8220 rebuilds the line table this update
G_DIST  EQU 0x8DF4              ; distance to the next track command (16 bits)
G_TRK   EQU 0x8DF6              ; track command pointer (bank 1)
P_LO    EQU 0x5B29              ; the profile 0xA053 animates: 0x5B29-0x5B80
P_LEN   EQU 0x58

NL      EQU 311                 ; lines a frame, 128K timing (50 Hz)
CAD     EQU 2                   ; frames between spec presents (25 a second)

; ------------------------------------------------------------------ hook RAM: 0x7B00-0x7D7C (bank 5),
; never read or written by the game in the six recordings (survey memory scan); the patch writes its
; initial values into the snapshot (Patch.apply).
V       EQU 0x7B00
v_spec  EQU V+0                 ; 1 while a spec frame runs
v_inupd EQU V+1                 ; 1 inside h_upd
v_en    EQU V+2                 ; spec frames on (setup: 1)
v_f     EQU V+3                 ; fraction of the step, 1..255
v_speed EQU V+4                 ; HLIB_SPEED latch of h_upd
v_prs   EQU V+5                 ; 1: a present is waiting for its flip (h_copy -> h_isr)
v_clk   EQU V+6                 ; line clock (16 bits, wraps)
v_lline EQU V+8                 ; video line at the last clock update
v_tint  EQU V+10                ; clock at the last interrupt
v_t0    EQU V+12                ; clock at the real update's start
v_D     EQU V+14                ; the real update's time, lines
v_dl    EQU V+16                ; deadline: clock at which the next real update starts
v_fr    EQU V+18                ; clock of the last real frame's flip
v_fn    EQU V+20                ; predicted clock of the next real frame's flip
v_tgt   EQU V+22                ; clock of the spec frame's flip
v_sp    EQU V+24                ; SP inside spec_frame (abort path)
v_tmp   EQU V+26
v_ljret EQU V+28                ; spec_abort: the fake return the race's LD SP,(0x5B95) / RET takes
v_ffl   EQU V+30                ; clock of the last flip (any present)
v_real  EQU V+32                ; 1: the pending present is the real update's
v_ns    EQU V+33                ; spec frames run (8 bits, wraps; diagnostics)
v_nab   EQU V+34                ; spec frames aborted
v_nlate EQU V+35                ; spec presents that missed their target interrupt
v_wt    EQU V+36                ; lines spent in frame waits (0x9EE6) during the update
v_w0    EQU V+38
v_regs  EQU V+40                ; the real update's exit registers: AF BC DE HL IX IY AF' BC' DE' HL'
HLIB_V_R EQU V+60               ; 3 bytes
v_xbuf  EQU V+64                ; the X bytes' real values while a spec frame runs (XLEN)
v_dma   EQU V+208               ; DMA program (DMA_LEN), copied from dma_tpl by the patch
v_isrsp EQU V+232                ; the interrupted SP (h_isr runs on its own stack)
v_itmp  EQU V+234
v_nfr   EQU V+236                ; frames from the real flip to the next real flip
v_wmode EQU V+237
v_wf0   EQU V+238
v_nwf   EQU V+240                ; wait_flip gave up (diagnostics)
v_pw    EQU V+241                ; lines the real present waited for the previous flip (not in D)
v_pw0   EQU V+243
v_cl    EQU V+245                ; curve level at the spec frame's start
v_cl2   EQU V+246                ; the level the next real update draws (track commands before it)
v_cbl   EQU V+247                ; 1: blend the curve offsets from v_cl to v_cl2 by f
v_tb    EQU V+248                ; h_curve: the v_cl2 table pointer
v_n     EQU V+250
v_rstep EQU V+251                ; the real step (h_step, spec frames)
v_dlat  EQU V+252                ; f of the offset across the road's change, in curve offset units (h_drift)
v_hsc   EQU V+254                ; this spec frame's skyline scroll: 1 left (0x826F), 0xFF right (0x82D7), 0 none
v_k     EQU V+255                ; h_hz: the pixel shift
VEND    EQU V+256
v_cp    EQU V+0x140              ; lines the real present's copy took (h_copy; not in D)
v_cp0   EQU V+0x142
v_fast  EQU V+0x144              ; 1: the fast paths (h_copy by zxnDMA, h_spr); setup: Patch fast
v_sc    EQU V+0x145              ; 3 bytes: the fast paths' credit this real update, 1/4096 lines (h_spr)
VEND2   EQU V+0x148
        ASSERT VEND2 <= TAIL_V
TAIL_V  EQU 0x7C80
v_prof  EQU 0x7C80               ; P_LEN: the profile the real update draws (the start-up tail's bytes, free
                                 ; once it has run)
ISR_STACK EQU V+0x140            ; h_isr's stack: V+0x100..V+0x13F

S_PAGE  EQU 12                  ; bank 6 lower 8K (never paged by the game, all zero): the W copy
SCR_PAGE EQU 27                 ; the snapshot's display bytes in a loading screen build (bank 13 upper)
STAGE_PAGE0 EQU 16             ; stage blocks: Next pages 16-19, 22, 23 (index 0-5: '1'..'5', 'X')

; ------------------------------------------------------------------ pace (fitted: games/cisco_heat.md)
; P (lines) = PACE_KI * D + (PACE_KF * D) / 256 + PACE_B
PACE_KI EQU 8                   ; 8.02 = 7.24 (the recordings' fit) * 1.108: the original as it runs on the
PACE_KF EQU 5                   ;   Next (JNext 1.2.0, plain .nex, 200 updates in lockstep: 9.39 frames an
PACE_B  EQU 645                 ;   update against 8.45 with the fit; games/cisco_heat.md "Pace")
RST_LN  EQU 96                  ; spec_back from its interrupt to the return (restore, the handler)
SPEC_X  EQU 40                  ; a spec frame's work beyond the real update's D (hill_f, 0x8220 forced, h_curve)
SAFE_LN EQU 180                ; a DI copy starts only this many lines after an interrupt or earlier

        ORG 0x2000
rom_start:
        INCLUDE "lib/hlib_iff.asm"
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_r.asm"

; ================================================================== time
; rline: HL = video line (0..NL-1). AF, BC lost. Leaves 0x243B selecting NextREG 7.
rline:  ld bc,0x243B
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
        cp h
        jr nz,.r
        ld a,h
        and 1
        ld h,a
        ld a,7
        out (c),a
        ret

; lsince: HL = lines from DE to the current line (mod NL). DE = a line. AF lost.
lsince: or a
        sbc hl,de
        ret nc
        push de
        ld de,NL
        add hl,de
        pop de
        ret

; now: HL = clock. AF, BC, DE lost. Interrupts stay as they are: a DI here would last longer than the
; Next's interrupt pulse at 28 MHz and a hook spinning on the clock would lose interrupts (the model's
; 32 T window, 2026-11-21). Instead it reads again when an interrupt came in between (v_clk moved; the
; handler's rline also leaves 0x243B selecting another register).
now:    ld de,(v_clk)
        push de
        call rline
        ld de,(v_lline)
        call lsince
        pop de
        add hl,de
        push hl
        ld hl,(v_clk)
        or a
        sbc hl,de
        pop hl
        jr nz,now
        ret

; isr_clock: advance the clock to the current line, note the interrupt (interrupts off).
; The interrupt comes at the same line every frame, so the lines since the last one read as a few
; (or NL less a few): a whole frame is added unless more than half a frame shows (an interrupt that
; was held off: lost interrupts are not counted).
isr_clock:
        call rline
        ld de,(v_lline)
        ld (v_lline),hl
        call lsince
        ld de,NL/2
        or a
        sbc hl,de
        add hl,de
        jr nc,.big
        ld de,NL
        add hl,de
.big:   ld de,(v_clk)
        add hl,de
        ld (v_clk),hl
        ld (v_tint),hl
        ld a,(v_prs)                    ; a present was waiting: this interrupt flips it
        or a
        ret z
        ld a,(G_REQ)
        ld b,a
        ld a,(G_SHOWN)
        cp b
        ret z                           ; the request came in too late for this one
        xor a
        ld (v_prs),a
        ld (v_ffl),hl
        ld a,(v_real)
        or a
        ret z
        ld (v_fr),hl
        xor a
        ld (v_real),a
        ret

; ================================================================== the interrupt
; The game may draw with SP (PUSH) while interrupts are on: on its stack the wrapper uses nothing
; beyond the CPU's own 2 bytes, as the original handler.
h_isr:  ld (v_isrsp),sp
        ld sp,ISR_STACK
        push af
        push bc
        push de
        push hl
        call isr_clock
        ld a,(v_spec)
        or a
        jr nz,.spec
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(v_isrsp)
        jp G_ISR
.spec:  call xswap
        pop hl
        pop de
        pop bc
        pop af
        ld (v_itmp),hl
        ld hl,isr_post
        push hl                         ; the handler saves this SP, restores it, RETI -> isr_post
        ld hl,(v_itmp)
        jp G_ISR
isr_post:
        di
        ld sp,ISR_STACK
        push af
        push bc
        push de
        push hl
        call xswap
        call repage0                    ; as the handler's exit: bank (0x5B8A), shown screen, ROM 0
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(v_isrsp)
        ei
        ret

; repage0: 7FFD = (0x5B8A) | (0x5B8B): the ISR's own exit value. AF, BC lost.
repage0:
        ld a,(G_SHOWN)
        ld b,a
        ld a,(G_BANK)
        or b
        ld bc,0x7FFD
        out (c),a
        ret

; page0: bank 0 at 0xC000 (shown screen kept). AF, BC lost.
page0:  ld a,(G_SHOWN)
        ld bc,0x7FFD
        out (c),a
        ret

; xswap: exchange the X bytes with v_xbuf. Interrupts off. Leaves bank 0 paged. AF BC DE HL lost.
xswap:  call page0
        ld de,v_xbuf
        ld hl,xtab
.rng:   ld a,(hl)
        inc hl
        or (hl)
        ret z
        push hl
        dec hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ex (sp),hl
        inc hl
        ld b,(hl)                       ; length (1..255)
        inc hl
        ex (sp),hl                      ; HL = address, (SP) = next entry
.b:     ld a,(de)
        ld c,(hl)
        ld (hl),a
        ld a,c
        ld (de),a
        inc hl
        inc de
        djnz .b
        pop hl
        jr .rng

; xsave: v_xbuf = the X bytes (DIR: copy into v_xbuf). xload: the X bytes = v_xbuf.
xsave:  call page0
        ld de,v_xbuf
        ld hl,xtab
.rng:   ld a,(hl)
        inc hl
        or (hl)
        ret z
        dec hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        push hl
        ld a,(hl)
        ld h,b
        ld l,c
        ld c,a
        ld b,0
        ldir
        pop hl
        inc hl
        jr .rng
xload:  call page0
        ld de,v_xbuf
        ld hl,xtab
.rng:   ld a,(hl)
        inc hl
        or (hl)
        ret z
        dec hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        push hl
        ld a,(hl)
        push bc
        ld c,a
        ld b,0
        pop hl                          ; HL = address
        ex de,hl                        ; DE = address, HL = v_xbuf position
        ldir
        ex de,hl                        ; DE = v_xbuf position
        pop hl
        inc hl
        jr .rng

; ================================================================== the update
h_upd:  HLIB_SPEED_IN v_speed
        ld a,1
        ld (v_inupd),a
        ld (v_real),a
        push hl
        push de
        push bc
        ld hl,P_LO                      ; the profile this update draws (0xA053 changes it after the road)
        ld de,v_prof
        ld bc,P_LEN
        ldir
        call now
        ld (v_t0),hl
        ld hl,0
        ld (v_wt),hl
        ld (v_pw),hl
        ld (v_cp),hl
        ld (v_sc),hl
        ld (v_sc+1),hl
        pop bc
        pop de
        pop hl
        call G_UPD                      ; the real update
        ld (v_regs+6),hl
        ld (v_regs+4),de
        ld (v_regs+2),bc
        push af
        pop hl
        ld (v_regs+0),hl
        ld (v_regs+8),ix
        ld (v_regs+10),iy
        exx
        ld (v_regs+14),bc
        ld (v_regs+16),de
        ld (v_regs+18),hl
        exx
        ex af,af'
        push af
        pop hl
        ld (v_regs+12),hl
        ex af,af'
        ; D = now - t0 - frame waits - the present's flip wait; P = K * D + B; deadline = t0 + P + frame waits
        call now
        ld de,(v_t0)
        or a
        sbc hl,de
        ld de,(v_wt)
        or a
        sbc hl,de
        jr c,.d0
        ld de,(v_pw)
        or a
        sbc hl,de
        jr c,.d0
        ld de,(v_cp)                    ; the present's copy, as measured (the fit left the copy out)
        or a
        sbc hl,de
        jr nc,.d
.d0:    ld hl,0
.d:     ld (v_D),hl
        ex de,hl                        ; pace on D + the time the fast paths saved (v_sc, rounded)
        ld hl,(v_sc+1)
        ld bc,8
        add hl,bc
        ld b,4
.cs:    srl h
        rr l
        djnz .cs
        add hl,de
        call pace                       ; HL = P
        ld de,(v_wt)
        add hl,de
        ld de,(v_t0)
        add hl,de
        ld (v_dl),hl
        ; spec frames
        ld a,(v_en)
        or a
        jp z,.wait
        ld a,(G_CRASH)
        ld hl,G_MODE2
        or (hl)
        jp nz,.wait
        call wait_flip                  ; v_fr = the real frame's flip
        jp c,.wait
        ; v_nfr = frames from v_fr to the first interrupt at or after deadline + D
        ld hl,(v_dl)
        ld de,(v_D)
        add hl,de
        ld de,(v_fr)
        or a
        sbc hl,de
        jp c,.wait
        ld de,NL
        ld b,0
.fn:    inc b
        or a
        sbc hl,de
        jr z,.fn0
        jr nc,.fn
.fn0:   ld a,b
        ld (v_nfr),a
        ld c,CAD                        ; C = frames from v_fr to this spec frame's flip
.next:  ld a,(v_nfr)
        cp c
        jp z,.wait
        jp c,.wait
        push bc
        ld hl,(v_fr)                    ; target = v_fr + C frames
        ld de,NL
        ld b,c
.tg:    add hl,de
        djnz .tg
        ld (v_tgt),hl
        or a
        sbc hl,de                       ; its present waits for target - NL, then copies and restores:
        ld bc,(v_cp)
        add hl,bc
        ld bc,48
        add hl,bc
        ex de,hl
        ld hl,(v_dl)
        or a
        sbc hl,de                       ; ... which must end by the deadline
        jp c,.stop
        call now                        ; and the frame's work must fit: E = now + D + 64 <= deadline,
        ld de,(v_D)                     ; or, when E falls SAFE_LN or more into a frame (spec_back's
        add hl,de                       ; wait_safe holds the restore to the next interrupt):
        ld de,64+SPEC_X                 ; next interrupt + RST_LN <= deadline
        add hl,de
        push hl
        ld de,(v_tint)
        or a
        sbc hl,de
        ld de,NL
.md:    or a
        sbc hl,de
        jr nc,.md
        add hl,de                       ; t = lines into E's frame
        ld de,SAFE_LN
        or a
        sbc hl,de
        jr c,.sf
        ex de,hl                        ; DE = t - SAFE_LN
        ld hl,NL-SAFE_LN+RST_LN
        or a
        sbc hl,de                       ; NL - t + RST_LN
        pop de
        add hl,de
        push hl
.sf:    pop de
        ld hl,(v_dl)
        or a
        sbc hl,de
        jp c,.stop
        pop bc
        push bc
        ld a,(v_nfr)                    ; f = C * 256 / frames
        ld e,a
        ld h,c
        ld l,0
        call div8
        ld (v_f),a
        call spec_frame
        pop bc
        ld a,c
        add a,CAD
        ld c,a
        jr .next
.stop:  pop bc
.wait:  call now                        ; wait for the deadline
        ld de,(v_dl)
        or a
        sbc hl,de
        bit 7,h
        jp nz,.wait
        xor a
        ld (v_inupd),a
        ld hl,(v_regs+12)
        push hl
        pop af
        ex af,af'
        exx
        ld bc,(v_regs+14)
        ld de,(v_regs+16)
        ld hl,(v_regs+18)
        exx
        ld ix,(v_regs+8)
        ld iy,(v_regs+10)
        ld bc,(v_regs+2)
        ld de,(v_regs+4)
        ld hl,(v_regs+0)
        push hl
        pop af
        ld hl,(v_regs+6)
        HLIB_SPEED_OUT v_speed
        ret

; wait_flip: until the real present's flip has happened (v_real = 0), so v_fr holds it.
; Carry set: no flip within 3 frames or by the deadline (an update without a present): no spec
; frames (counted in v_nwf).
wait_flip:
        call now
        ld (v_wf0),hl
.w:     ld a,(v_real)
        or a
        ret z
        call now
        push hl
        ld de,(v_dl)
        or a
        sbc hl,de
        ld a,h
        pop hl
        bit 7,a                         ; (now - deadline) >= 0: give up
        jr z,.to
        ld de,(v_wf0)
        or a
        sbc hl,de
        ld de,3*NL
        or a
        sbc hl,de
        jr c,.w
.to:    ld hl,v_nwf
        inc (hl)
        scf
        ret

; pace: HL = PACE_KI * D + PACE_KF * D / 256 + PACE_B (D without the copy: h_copy measures it).
; AF, BC, DE lost.
pace:   ld a,h                          ; HL = D
        cp 8
        jr c,.ok
        ld hl,0x07FF                    ; > 6 frames of 28 MHz time: cap
.ok:    ld b,h
        ld c,l
        ld de,0                         ; HL = D * PACE_KI
        ld a,PACE_KI
        ld hl,0
.mi:    add hl,bc
        dec a
        jr nz,.mi
        push hl
        ld d,c                          ; low byte * KF
        ld e,PACE_KF
        mul d,e
        ld a,d                          ; (lo * KF) >> 8
        ld d,b                          ; high byte * KF
        ld e,PACE_KF
        mul d,e                         ; DE = hi * KF (its >> 8 contributes DE fully shifted by 0)
        add a,e
        ld e,a
        ld a,d
        adc a,0
        ld d,a
        pop hl
        add hl,de
        ld de,PACE_B
        add hl,de
        ret

; div8: A = L = HL / E, H = remainder (needs H < E). B lost.
div8:   ld b,8
.l:     add hl,hl
        ld a,h
        jr c,.s
        cp e
        jr c,.n
.s:     sub e
        ld h,a
        inc l
.n:     djnz .l
        ld a,l
        ret

; ================================================================== the spec frame
; wait_safe: until the current frame is early enough for a DI copy (lines since the last interrupt).
wait_safe:
        call now
        ld de,(v_tint)
        or a
        sbc hl,de
        ld de,SAFE_LN
        or a
        sbc hl,de
        jr nc,wait_safe
        ret

spec_frame:
        call wait_safe
        di
        call w_save
        call xsave
        call c_next
        call repage0
        ld hl,spec_abort
        ld (v_ljret),hl
        ld hl,v_ljret
        ld (G_LJSP),hl
        ; road stripes: as if (1 - f) of the last step had not been driven yet
        ld a,(v_f)
        neg
        ld d,a
        ld a,(G_STEP)
        ld e,a
        mul d,e
        ld a,(G_STRIPE)
        add a,d
        and 31
        ld (G_STRIPE),a
        ld a,1
        ld (v_spec),a
        ld (v_sp),sp
        ei
        call hill_f
        call G_UPD
spec_back:
        call wait_safe
        di
        call w_load
        call xload
        xor a
        ld (v_spec),a
        call repage0
        ld hl,v_ns
        inc (hl)
        ei
        ret
spec_abort:
        ld sp,(v_sp)
        ld hl,v_nab
        inc (hl)
        jr spec_back

; hill_f: hills and horizon as 0xA053 leaves them after f of a step: the profile the real update drew,
; animated again with step * f. The road and the line table are then built from it (G_REDO).
hill_f: ld hl,v_prof
        ld de,P_LO
        ld bc,P_LEN
        ldir
        ld a,(G_STEP)
        push af
        call scale_a
        ld (G_STEP),a
        call G_HILL
        pop af
        ld (G_STEP),a
        ld a,1
        ld (G_REDO),a
        ret

; scale_a: A = round(A * f / 256), A unsigned. DE lost.
scale_a:
        ld d,a
        ld a,(v_f)
        ld e,a
        mul d,e
        ld a,e
        add a,a                         ; carry: the dropped half
        ld a,d
        adc a,0
        ret

; c_next: v_cl = the level now; v_cl2 and v_cbl = 1 when the race loop's track commands before the next
; real update change it (the loop reads commands when the distance runs out: 0x8BE1). Reads the
; script the way 0x8C24 would (bank 1 paged here; interrupts off): distances, the curve commands with
; their limits, the other commands skipped by length; a command it does not know ends the look (no blend).
c_next: xor a
        ld (v_cbl),a
        ld h,a
        ld l,a
        ld (v_dlat),hl
        ld (v_hsc),a
        ld a,(G_LEVEL)
        ld (v_cl),a
        ld hl,(G_DIST)
        ld a,(G_STEP)
        ld c,a
        ld b,0
        or a
        sbc hl,bc
        jr z,.go
        ret nc
.go:    ld a,(G_SHOWN)
        or 0x11
        ld bc,0x7FFD
        out (c),a
        ld hl,(G_TRK)
        ld a,(v_cl)
        ld e,a
        ld d,16
.cmd:   dec d
        ret z
        ld a,(hl)
        inc hl
        bit 7,a
        jr z,.nd
        and 0x7F                        ; a distance (0x8CFC): the look ends unless it is zero
        or (hl)
        inc hl
        ret nz
        jr .cmd
.nd:    cp 1
        jr z,.c1
        cp 2
        jr z,.c2
        ld b,3
        cp 3
        jr z,.sk
        cp 6
        jr z,.sk
        cp 7
        jr z,.sk
        cp 12
        jr z,.sk
        dec b
        cp 13
        jr z,.sk
        cp 8
        jr z,.sk
        cp 9
        jr z,.sk
        cp 15
        jr z,.sk
        cp 10
        jr z,.cmd
        cp 18
        jr z,.cmd
        cp 61
        jr z,.cmd
        cp 59
        jr z,.cmd
        cp 58
        ret nz                          ; 17, 63, unknown: no blend
        ld a,(hl)                       ; 58: jump (0x8D08)
        inc hl
        ld h,(hl)
        ld l,a
        jr .cmd
.sk:    inc hl
        djnz .sk
        jr .cmd
.c1:    ld a,e                          ; 0x8204: down one, not below -4 (then the loop reads on)
        or a
        jp m,.c1n
        jr z,.c1n
        dec a
        jr .done
.c1n:   cp 0xFC
        jr z,.cmd
        dec a
        jr .done
.c2:    ld a,e                          ; 0x81DB: up one, not above 4
        or a
        jp m,.c2u
        cp 4
        jr nc,.cmd
.c2u:   inc a
.done:  ld (v_cl2),a
        ld a,1
        ld (v_cbl),a
        ret

; h_curve (site 0x826B, CALL 0xA83D: 0x8220 has written the offsets from the current level's table):
; in a spec frame whose next real update draws another level, each line's offset moves f of the way
; to that level's (+-table: the sign is the level's); every line gets v_dlat (h_drift); then the line table
; as the game builds it.
h_curve:
        ld a,(v_spec)
        or a
        jp z,G_LINES
        ld a,(G_ROADN)
        or a
        jp z,G_LINES
        cp 105
        jp nc,G_LINES
        ld (v_n),a
        ld a,(v_cbl)
        or a
        jr z,.lat
        ld a,(G_LEVEL)
        ld hl,v_cl
        cp (hl)
        jr nz,.lat                      ; the level moved in this frame (0x9A39): no blend
        ld a,(v_cl)                     ; T' = T + (|L'| - |L|) * 208
        call abs_a
        ld c,a
        ld a,(v_cl2)
        call abs_a
        sub c
        ld hl,(G_CTAB)
        ld de,208
        jr z,.t
        jp p,.up
        ld de,-208
        neg
.up:    ld b,a
.ad:    add hl,de
        djnz .ad
.t:     ld (v_tb),hl
        ld ix,(G_CTAB)
        ld iy,G_OFFS
.lp:    ld e,(ix+0)
        ld d,(ix+1)
        ld a,(v_cl)
        or a
        call m,neg_de
        push de
        ld hl,(v_tb)
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (v_tb),hl
        ld a,(v_cl2)
        or a
        call m,neg_de
        pop hl
        ex de,hl
        or a
        sbc hl,de                       ; the level's offset change on this line
        call smul_f
        ld e,(iy+0)
        ld d,(iy+1)
        add hl,de
        ld (iy+0),l
        ld (iy+1),h
        inc ix
        inc ix
        inc iy
        inc iy
        ld hl,v_n
        dec (hl)
        jr nz,.lp
.lat:   ld hl,(v_dlat)                  ; f of the offset across the road's change (h_drift), every line
        ld a,h
        or l
        jp z,G_LINES
        ex de,hl
        ld hl,G_OFFS
        ld a,(G_ROADN)
        ld b,a
.ll:    ld a,(hl)
        add a,e
        ld (hl),a
        inc hl
        ld a,(hl)
        adc a,d
        ld (hl),a
        inc hl
        djnz .ll
        jp G_LINES

abs_a:  or a
        ret p
        neg
        ret

neg_de: xor a
        sub e
        ld e,a
        sbc a,a
        sub d
        ld d,a
        ret

; smul_f: HL = round(HL * f / 256), HL signed. AF, BC, DE lost.
smul_f: ld a,h
        or a
        push af
        jp p,.p
        ex de,hl
        call neg_de
        ex de,hl
.p:     ld a,(v_f)
        ld e,a
        ld d,l
        mul d,e
        ld c,d
        ld b,e
        ld a,(v_f)
        ld e,a
        ld d,h
        mul d,e
        ld l,c
        ld h,0
        add hl,de
        bit 7,b
        jr z,.r
        inc hl
.r:     pop af
        ret p
        ex de,hl
        call neg_de
        ex de,hl
        ret

; h_drift (site 0x8ADE, CALL 0xAB9D): the drift and steering amounts are table steps of the whole step, not
; proportional to it: a spec frame runs 0xAB9D with the real step (the steering as it is now) and shows f of
; the offset's change, as a fraction of a unit (v_dlat, added to every line's offset by h_curve).
h_drift:
        ld a,(v_spec)
        or a
        jp z,G_DRIFT
        ld a,(G_STEP)
        push af
        ld a,(v_rstep)
        ld (G_STEP),a
        ld a,(G_LAT)
        push af
        call G_DRIFT
        pop bc                          ; B = the offset before
        ld a,(G_LAT)
        sub b
        ld c,a
        ld a,b
        ld (G_LAT),a                    ; it stays (whole units); h_curve moves the road by f of the change
        ld hl,0
        ld a,c
        or a
        jr z,.z
        ld de,-832                      ; a unit across the road in the offsets: -832 (0xAC86)
        jp p,.m0
        ld de,832
        neg
.m0:    ld b,a
.m:     add hl,de
        djnz .m
        call smul_f
.z:     ld (v_dlat),hl
        pop af
        ld (G_STEP),a
        ret

; h_hzl / h_hzr (sites 0x8ADB, 0x8AD2: the skyline scroll by a byte on a curve): note a spec frame's scroll.
h_hzl:  ld a,1
        jr h_hzs
h_hzr:  ld a,0xFF
h_hzs:  push hl
        ld hl,v_spec
        bit 0,(hl)
        jr z,.go
        ld hl,G_HZT
        bit 0,(hl)                      ; 1: this call scrolls
        jr z,.go
        ld (v_hsc),a
.go:    dec a
        pop hl
        jp z,G_HZL
        jp G_HZR

; h_hz (site 0xA677, CALL 0x8191): after the band is drawn, a spec frame whose scroll moved the bitmap a
; byte shows f of it: the drawn rows shifted back by round(8 * (1 - f)) pixels (circular: the row is the
; whole bitmap row), with the barrel shifter.
h_hz:   call G_HZ
        ld a,(v_spec)
        or a
        ret z
        ld a,(v_hsc)
        or a
        ret z
        ld a,(v_f)
        neg
        add a,16
        jr c,.k8
        srl a
        srl a
        srl a
        srl a
        srl a
        jr .k
.k8:    ld a,8
.k:     or a
        ret z
        cp 8
        ret nc
        ld (v_k),a
        ld a,(G_HZN)
        or a
        ret z
        ld hl,(G_HZROW)
.row:   push af
        push hl
        ld de,HZ_TOP
        or a
        sbc hl,de
        pop hl
        jr c,.nx
        push hl
        ld a,(v_hsc)
        dec a
        call z,shr_row
        call nz,shl_row
        pop hl
.nx:    ld de,32
        add hl,de
        pop af
        dec a
        jr nz,.row
        ret

; shr_row: the 26 bytes at HL shifted right by v_k bits, circular. AF, BC, DE, HL lost; Z set on return.
shr_row:
        push hl
        ld de,25
        add hl,de
        ld c,(hl)                       ; the last byte comes in at the left
        pop hl
        ld a,26
.b:     ex af,af'
        ld d,c
        ld e,(hl)
        ld c,e
        ld a,(v_k)
        ld b,a
        bsrl de,b
        ld (hl),e
        inc hl
        ex af,af'
        dec a
        jr nz,.b
        ret

; shl_row: the 26 bytes at HL shifted left by v_k bits, circular. AF, BC, DE, HL lost.
shl_row:
        ld c,(hl)                       ; the first byte comes in at the right
        ld de,25
        add hl,de
        ld a,26
.b:     ex af,af'
        ld d,(hl)
        ld e,c
        ld c,d
        ld a,(v_k)
        ld b,a
        bsla de,b
        ld (hl),d
        dec hl
        ex af,af'
        dec a
        jr nz,.b
        ret

; sscale_a: A = round(A * f / 256), A signed. DE lost.
sscale_a:
        bit 7,a
        jp z,scale_a
        neg
        call scale_a
        neg
        ret

; h_cspd (sites 0x9835, 0x9933: LD C,(IX+12), a car's own speed in the relative motion step - speed):
; spec frames move the car by f of it, as the step.
h_cspd: ld c,(ix+12)
        push af
        ld a,(v_spec)
        or a
        jr z,.o
        push de
        ld a,c
        call scale_a
        ld c,a
        pop de
.o:     pop af
        ret

; h_lat (site 0x981A: ADD A,(IX+3), A = the car's lane change this update, signed): f of it.
h_lat:  push bc
        ld b,a
        ld a,(v_spec)
        or a
        ld a,b
        jr z,.add
        push de
        bit 7,b
        jr z,.pos
        neg
.pos:   call scale_a
        bit 7,b
        jr z,.p2
        neg
.p2:    pop de
.add:   pop bc
        add a,(ix+3)
        ret

; w_save / w_load: the W ranges <-> bank 6 (MMU slot 0 = S_PAGE, from 0x0000). Interrupts off.
w_save: ld a,1
        jr w_go
w_load: xor a
w_go:   ld (v_wmode),a
        nextreg 0x50,S_PAGE
        ld hl,wtab
        ld de,0                         ; position in the copy
.rng:   ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        jr z,.end
        push bc                         ; address
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)                       ; bank (0xFF: none)
        inc hl
        ex (sp),hl                      ; HL = address, (SP) = next entry
        push bc
        cp 0xFF
        jr z,.np
        push bc
        ld b,a
        ld a,(G_SHOWN)
        or b
        or 0x10
        ld bc,0x7FFD
        out (c),a
        nextreg 0x50,S_PAGE             ; a 7FFD write maps ROM back into slots 0-1
        pop bc
.np:    ld a,(v_wmode)
        or a
        jr nz,.sv
        ex de,hl                        ; load: copy -> address
        call copy
        ex de,hl
        jr .nx
.sv:    call copy                       ; save: address -> copy
.nx:    pop bc                          ; DE = copy position + length (both paths)
        pop hl
        jr .rng
.end:   nextreg 0x50,0xFF
        ret

; copy: BC bytes from HL to DE; HL, DE advanced past them (as LDIR). DMA from 16 bytes up.
copy:   ld a,b
        or a
        jr nz,.dma
        ld a,c
        cp 16
        jr nc,.dma
        ldir
        ret
.dma:   ld (v_dma+3),hl
        ld (v_dma+5),bc
        ld (v_dma+10),de
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        push hl
        push de
        ld hl,v_dma
        ld bc,DMA_LEN*256+0x6B
        otir
        pop de
        pop hl
        ld bc,0
        ret

; ================================================================== the step and the present
h_step: push af
        ld a,(v_spec)
        or a
        jr nz,.s
        pop af
        ld (G_STEP),a
        ret
.s:     pop af
        ld (v_rstep),a
        push de
        push af
        ld d,a
        ld a,(v_f)
        ld e,a
        mul d,e
        pop af
        ld a,d
        pop de
        ld (G_STEP),a
        ret

h_pres: push af
        ld a,(v_inupd)
        or a
        jr z,.go
        push bc
        push de
        push hl
.f0:    ld a,(G_REQ)                    ; the previous present's flip must have happened
        ld hl,G_SHOWN
        cp (hl)
        jr z,.fd
        call now                        ; (the original never waits: this time is not the update's,
        ld (v_pw0),hl                   ;  v_pw leaves it out of D)
.f:     ld a,(G_REQ)
        ld hl,G_SHOWN
        cp (hl)
        jr nz,.f
        ld a,(v_spec)
        or a
        jr nz,.fd
        call now
        ld de,(v_pw0)
        or a
        sbc hl,de
        ld (v_pw),hl
.fd:    ld a,(v_spec)
        or a
        jr z,.p
.w:     call now                        ; spec: present after the interrupt before the target
        ld de,(v_tgt)
        or a
        sbc hl,de
        ld de,NL
        add hl,de
        bit 7,h
        jr nz,.w
.p:     pop hl
        pop de
        pop bc
.go:    ld a,1
        ld (v_prs),a
        pop af
        push hl                         ; the displaced PUSH HL / PUSH DE / PUSH BC
        push de
        push bc
        jp 0x882A

; ================================================================== the copy
; h_copy (site 0x8847, CALL 0x8854: HL = 0x6000 the linear back buffer, DE = the hidden screen; A kept): the
; real update's copy is timed (v_cp, left out of D as the fit leaves the copy out). v_fast: the copy by
; zxnDMA, one 32-byte row a job (the rows in the screen's order), the attributes in 24 more, when it ends
; CP_SAFE lines or more before the next interrupt; else the game's LDI copy. A job holds the CPU and an
; interrupt pulse during one is lost (JNext: 49.94 interrupts a second, a 40.5 ms gap, before this check).
CP_SAFE EQU 90                          ; the DMA copy's lines (52 in the simulator) and a margin
h_copy: push af
        ld a,(v_inupd)
        or a
        jr z,.go
        ld a,(v_spec)
        or a
        jr nz,.go
        push hl
        push de
        call now
        ld (v_cp0),hl
        pop de
        pop hl
        call .cp
        call now
        ld de,(v_cp0)
        or a
        sbc hl,de
        ld (v_cp),hl
        pop af
        ret
.go:    call .cp
        pop af
        ret
.cp:    ld a,(v_fast)
        or a
        jp z,G_COPY
        push hl
        push de
        call now
        ld de,(v_tint)
        or a
        sbc hl,de
        ld de,NL
.md:    or a
        sbc hl,de
        jr nc,.md
        add hl,de                       ; lines into this frame
        ld de,NL-CP_SAFE
        or a
        sbc hl,de
        pop de
        pop hl
        jp nc,G_COPY                    ; too near the next interrupt
        ld c,0x6B
        ld a,0x83                       ; disable, then the fixed part: length 32, both memory, increment
        out (c),a
        ld a,0x7D
        out (c),a
        out (c),l
        out (c),h
        ld a,32
        out (c),a
        xor a
        out (c),a
        ld a,0x14
        out (c),a
        ld a,0x10
        out (c),a
        ld a,0xAD
        out (c),a
        out (c),e
        out (c),d
        ld a,0x82
        out (c),a
        ld b,24                         ; character rows
.cr:    push hl
        push bc
        ld b,8                          ; their pixel rows: 256 apart in the back buffer
.pr:    call dma_row
        inc h
        djnz .pr
        pop bc
        pop hl
        ld a,32
        add hl,a
        ld a,b
        dec a
        and 7
        jr nz,.n
        add hl,0x0700                   ; the next third
.n:     djnz .cr
        ld hl,0x7800                    ; attributes
        ld b,24
.ar:    call dma_row
        ld a,32
        add hl,a
        djnz .ar
        ret

; ================================================================== sprite rows (site 0x91E3, PUSH BC / LD A,(0x923F))
; The row loop of the sprite blit 0x9144, entered at its first row: B rows, C kept, DE the sprite bytes,
; HL the back buffer row; (0x923F) bytes a row drawn, (0x9240) bytes a row skipped; (0x5B94) mirrored
; (drawn right to left, bits reversed), (0x5BAB) stored, else ORed in. The game's loop costs 73..180 T a
; byte; these 21..64. Exit as the game's at 0x9233: B 0, C, DE, HL as it leaves them; AF' (the mode) is
; never touched, AF is set by 0x9233. Without v_fast: the displaced instructions, back to the loop.
h_spr:  ld a,(v_fast)
        or a
        jr nz,.f
        push bc
        ld a,(0x923F)
        jp 0x91E7
.f:     push bc
        push ix
        ld ixh,b
        push hl
        push de
        call spr_credit
        pop de
        pop hl
        ld a,(0x5B94)
        or a
        jr nz,.m
        ld a,(0x5BAB)
        or a
        jr z,.no
.ns:    push hl                         ; stored: LDIR
        ex de,hl
        ld bc,(0x923F)                  ; C width, B skip
        ld a,b
        ld b,0
        ldir
        add hl,a
        ex de,hl
        pop hl
        add hl,32
        dec ixh
        jr nz,.ns
        jr .x
.no:    push hl                         ; ORed
        ld a,(0x923F)
        ld b,a
.no1:   ld a,(de)
        or (hl)
        ld (hl),a
        inc de
        inc hl
        djnz .no1
        ld a,(0x9240)
        add de,a
        pop hl
        add hl,32
        dec ixh
        jr nz,.no
        jr .x
.m:     ld b,high mirt
        ld a,(0x5BAB)
        or a
        jr z,.mo
.ms:    push hl                         ; mirrored, stored
        ld a,(0x923F)
        ld ixl,a
.ms1:   ld a,(de)
        ld c,a
        ld a,(bc)
        ld (hl),a
        dec hl
        inc de
        dec ixl
        jr nz,.ms1
        ld a,(0x9240)
        add de,a
        pop hl
        add hl,32
        dec ixh
        jr nz,.ms
        jr .x
.mo:    push hl                         ; mirrored, ORed
        ld a,(0x923F)
        ld ixl,a
.mo1:   ld a,(de)
        ld c,a
        ld a,(bc)
        or (hl)
        ld (hl),a
        dec hl
        inc de
        dec ixl
        jr nz,.mo1
        ld a,(0x9240)
        add de,a
        pop hl
        add hl,32
        dec ixh
        jr nz,.mo
.x:     pop ix
        pop bc
        ld b,0
        jp 0x9233

; spr_credit: v_sc += the time the game's loop would take over h_spr's, in 1/4096 lines (pace runs on the
; original's time): rows * (width * CB + CR + skip * CS) - CC, CB/CR by mode (fitted in the simulator from
; the game's loop against this one: games/cisco_heat.md). IXH rows. AF BC DE HL lost.
CS      EQU 48
CC      EQU 1970
spr_credit:
        ld c,0
        ld a,(0x5B94)
        or a
        jr z,.c1
        ld c,8
.c1:    ld a,(0x5BAB)
        or a
        jr z,.c2
        set 2,c
.c2:    ld hl,ctab
        ld a,c
        add hl,a
        ld c,(hl)
        inc hl
        ld b,(hl)                       ; BC = CB
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)                       ; DE = CR
        push de
        ld a,(0x923F)
        ld d,c
        ld e,a
        mul d,e
        ex de,hl                        ; HL = CB lo * width
        ld d,b
        ld e,a
        mul d,e
        ld a,e
        add a,h
        ld h,a                          ; + (CB hi * width) << 8
        pop de
        add hl,de
        ld a,(0x9240)
        ld d,a
        ld e,CS
        mul d,e
        add hl,de                       ; HL = a row's credit
        ld a,ixh
        ld e,a
        ld d,l
        mul d,e                         ; DE = lo * rows
        ld b,h
        ld hl,v_sc
        ld a,(hl)
        add a,e
        ld (hl),a
        inc hl
        ld a,(hl)
        adc a,d
        ld (hl),a
        inc hl
        ld a,(hl)
        adc a,0
        ld (hl),a
        ld a,ixh
        ld e,a
        ld d,b
        mul d,e                         ; DE = hi * rows, << 8
        ld hl,v_sc+1
        ld a,(hl)
        add a,e
        ld (hl),a
        inc hl
        ld a,(hl)
        adc a,d
        ld (hl),a
        ld hl,(v_sc)                    ; - CC (never below 0)
        ld de,CC
        or a
        sbc hl,de
        ld (v_sc),hl
        ld a,(v_sc+2)
        sbc a,0
        ld (v_sc+2),a
        ret nc
        ld hl,0
        ld (v_sc),hl
        ld (v_sc+1),hl
        ret
ctab:   dw 165,67                       ; (CB, CR): ORed
        dw 161,37                       ; stored
        dw 373,57                       ; mirrored, ORed
        dw 323,57                       ; mirrored, stored

; dma_row: 32 bytes HL -> DE by the zxnDMA (C = 0x6B, the fixed part programmed); DE += 32. A lost.
dma_row:
        ld a,0x1D
        out (c),a
        out (c),l
        out (c),h
        ld a,0xAD
        out (c),a
        out (c),e
        out (c),d
        ld a,0xCF
        out (c),a
        ld a,0x87
        out (c),a
        ld a,32
        add de,a
        ret

; ================================================================== frame waits (0x9EE6) inside h_upd
; Their time is real time in the original too: it is left out of D and added to the deadline.
h_fwait:
        push af
        ld a,(v_inupd)
        or a
        jr nz,.t
        pop af
        push af                         ; the displaced PUSH AF / PUSH BC / LD A,(0x5B8E)
        push bc
        ld a,(G_FRAMES)
        jp 0x9EEB
.t:     pop af
        push hl
        push de
        push bc
        push af
        call now
        ld (v_w0),hl
        pop af
        pop bc
        pop de
        pop hl
        call .orig
        push hl
        push de
        push bc
        push af
        call now
        ld de,(v_w0)
        or a
        sbc hl,de
        ld de,(v_wt)
        add hl,de
        ld (v_wt),hl
        pop af
        pop bc
        pop de
        pop hl
        ret
.orig:  push af
        push bc
        ld a,(G_FRAMES)
        jp 0x9EEB

; ================================================================== the stage loader
; Entry as 0x8361: bank 1 paged, DE = 0xC000. The block: Next page STAGE_PAGE0 + index, data from
; 0x0000, its length at 0x1FFE, the loader's 16 header bytes at 0x1FE0. Exit: carry set (loaded).
h_load: HLIB_IFF_DI
        push af
        ld a,(G_STAGE)
        sub '1'
        cp 5
        jr c,.n
        ld a,5                          ; 'X'
.n:     ld hl,stage_pages
        add a,l
        ld l,a
        jr nc,.p
        inc h
.p:     ld a,(hl)
        nextreg 0x50,a
        ld hl,(0x1FFE)
        ld b,h
        ld c,l
        ld hl,0
        ld de,0xC000
        ldir
        ld hl,0x1FE0
        ld de,G_HDR
        ld bc,16
        ldir
        nextreg 0x50,0xFF
        pop af
        HLIB_IFF_EI
        scf                             ; loaded (the caller tests carry only; 0x8E40 on sets every register)
        ret
stage_pages:
        db STAGE_PAGE0, STAGE_PAGE0+1, STAGE_PAGE0+2, STAGE_PAGE0+3, 22, 23

; ================================================================== boot continuation
; NEXLOAD leaves NextZXOS's variables in 0x5B00-0x5BFF, where this game keeps its own: after the start-up
; tail has restored the registers, the snapshot's 256 bytes come back from here (Patch.apply fills
; printer_saved, boot_iff, boot_jump). Scratch stack in Next page 26 at slot 0. R as the snapshot's at the
; game's first instruction (delta: Chase H.Q.'s identical sequence, -23).
boot_resume:
        di
        nextreg 0x50,26
        ld (0x1F14),sp
        ld sp,0x1EF0
        push af
        push bc
        push de
        push hl
        ld a,r
        ld (HLIB_V_R),a
        nextreg 7,3
        ld hl,printer_saved
        ld de,0x5B00
        ld bc,256
        ldir
        ld a,(boot_scr)                 ; the file's bank 5 held the loading screen: the snapshot's display
        or a                            ; bytes come back from page SCR_PAGE (no stack while it is mapped)
        jr z,.ns
        nextreg 0x50,SCR_PAGE
        ld hl,0
        ld de,0x4000
        ld bc,6912
        ldir
        nextreg 0x50,26
.ns:    nextreg 7,0
        ld a,-23
        call hlib_r_set
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(0x1F14)
        nextreg 0x50,255
boot_iff:
        ei
boot_jump:
        jp 0
boot_scr:
        db 0                            ; 1: a loading screen build (Patch.set_boot)
printer_saved:
        ds 256

; ================================================================== tables
; X: bytes the handler shares with the update (address, length; 0 ends). Bank 0 at 0xC000 when used.
xtab:   dw 0x5BAA
        db 1
        dw 0x5BAF
        db 1
        dw 0x5BCC
        db 9
        dw 0x7D80
        db 16
        dw 0xD8C0
        db 112
        dw 0
XLEN    EQU 1+1+9+16+112
        ASSERT XLEN <= 144

; W: bytes the update writes (address, length, bank or 0xFF; 0 ends), the live display bytes
; 0x5B8B-0x5B8F left out.
wtab:   dw 0x5B00,0x008B
        db 0xFF
        dw 0x5B90,0x03F0
        db 0xFF
        dw 0x7D80,0x0010
        db 0xFF
        dw 0x8051,0x0001
        db 0xFF
        dw 0x8203,0x0001
        db 0xFF
        dw 0x8DF4,0x0002
        db 0xFF
        dw 0x8E4C,0x0001
        db 0xFF
        dw 0x8F40,0x0008
        db 0xFF
        dw 0x90C4,0x000D
        db 0xFF
        dw 0x923E,0x0004
        db 0xFF
        dw 0x92E6,0x00A8
        db 0xFF
        dw 0x9510,0x0007
        db 0xFF
        dw 0x96DE,0x0111
        db 0xFF
        dw 0xA26C,0x0001
        db 0xFF
        dw 0xA5AA,0x001B
        db 0xFF
        dw 0xA62D,0x0002
        db 0xFF
        dw 0xA826,0x0018
        db 0xFF
        dw 0xA8D6,0x0003
        db 0xFF
        dw 0xAB9C,0x0001
        db 0xFF
        dw 0xB127,0x0001
        db 0xFF
        dw 0xC400,0x0920
        db 1
        dw 0

dma_tpl:
        db 0x83,0xC3,0x7D
        dw 0,0
        db 0x14,0x10,0xAD
        dw 0
        db 0x82,0xCF,0x87
DMA_LEN EQU $-dma_tpl
        ASSERT DMA_LEN == 15

        ALIGN 256
mirt:                                   ; a byte's bits reversed (h_spr)
.x = 0
        DUP 256
        db ((.x&1)<<7)|((.x&2)<<5)|((.x&4)<<3)|((.x&8)<<1)|((.x&16)>>1)|((.x&32)>>3)|((.x&64)>>5)|((.x&128)>>7)
.x = .x + 1
        EDUP
regblock:
        ds 32
rom_end:
        ASSERT rom_end <= 0x3D00
        SAVEBIN "ch_rom.bin",rom_start,$-rom_start
