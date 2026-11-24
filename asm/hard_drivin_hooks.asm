; Hard Drivin' (128K): the game's 3D render and view copy at 28 MHz, each held to the original's time (render: K x its
; 28 MHz lines, K measured at run time; copy: its own time measured at 3.5 MHz); the time that frees draws in-between
; views (camera interpolated from the last update's to this one's), each copied to the screen by the game's own copy
; while the beam is below the view: no tear, no second screen. games/hard_drivin.md "Build" has the design.
;
; Memory: hook code = page PG_CODE in MMU slot 1 (0x2000-0x3FFF) while a hook runs; the alt ROM (Sinclair's ROM 1,
; read by the game only below 0x1700 as render data, never run) carries the trampolines at SH, the same addresses
; in PG_CODE. Extra views and the calibration run on scratch copies of the game's pages: the game's own pages stay
; as the real render left them.
; Stacks: the game's stack only for what the original pushes there (the render and the copy are entered with the
; original SP and return address planted); the hook code and the tick run on their own stacks in PG_CODE.
; Interrupts: off in all play; a hook entered with interrupts on runs the original (plain path). The calibration
; alone runs with IM 2 through this page's table.
;
; Assemble: python tools/asm2profile.py hard_drivin -> docs/profiles/hard_drivin.json hooks.page (8K, the hook
; page) and hooks.rom (the alt ROM's bytes at SH). hard_drivin_wset.inc: the render's write set (bitmap).

        DEVICE NOSLOT64K
        OPT --zxnext

PG_CODE EQU 36                          ; 8K pages: 16K bank 18 = hook code (+ the next page unused)
PG_S4   EQU 38                          ; scratch copies of slots 4-7: pages 38-41 (banks 19-20)
PG_S2   EQU 43                          ; calib: scratch copies of slots 2-3 (pages 43-44)
PG_ROMC EQU 42                          ; calib: a RAM copy of the ROM's 0x0000-0x1FFF (the render POPs ROM bytes)
SH      EQU 0x3870                      ; trampolines (Sinclair's ROM is 0xFF at 0x386E-0x3CFF)
RENDER  EQU 0x9EA9
VCOPY   EQU 0xDC37
TICKT   EQU 0xD77D                      ; the tick site 0xD6FE's original target
RET_R   EQU 0x9E57                      ; return addresses the sites push
RET_C   EQU 0x9E6E
CARRY   EQU 0x912E                      ; render-to-render carry (tools/carry.py): 0x912E, 0x917A-B, 0x91CC-D, 43337 bit 0
CARRYN  EQU 0x91CE-0x912E               ; kept as one block: before the real render = the calibration's start
CPY_INIT EQU 279                        ; the plain copy in JNext: 0.898 frames (jl_plain: 180 copies, 0.896-0.905)
CAL_MIN EQU 1000                        ; lines: a shorter calibration render gives no sample
HOOK_OVH EQU 3                          ; lines: the hooks' entries / exits at 3.5 MHz (JNext: +3.3 an update, median)
CPY_LO  EQU 150                         ; a measured copy outside these lines is dropped
CPY_HI  EQU 420
CAM     EQU 43400                       ; x, y, z words; 43406 = a flag; orientation 43407-43409
    IFNDEF K_INIT
K_INIT  EQU 1690                        ; K x 256 until the first calibration (6.6: TECHNIQUES 1.0's hardware copies)
    ENDIF
    IFNDEF ISR_T
ISR_T   EQU 1136                        ; the calibration handler's mean T at 3.5 MHz, acceptance included (hd_verify:
                                        ; whole RZX: mean 1138, median 1006, 966-1660); a multiple of 8, up to 2040
    ENDIF
    IFNDEF CAL_EVERY
CAL_EVERY EQU 16                        ; updates between calibrations after the first three (JNext: 64 gains 0.4 %, 16 0.16 %)
    ENDIF
NMAX    EQU 7                           ; in-between views an update at most
BAND0   EQU 128                         ; copy start lines (0 = first pixel row): below the view, done before row 0
BAND1   EQU 262
CPYL    EQU 48                          ; a copy's lines at 28 MHz, upper bound
DEBTCAP EQU 1200                        ; lines (about 4 frames: a calibration update overruns by its 28 MHz render)
SCRL    EQU 110                         ; the scratch copy's lines (32K by DMA, 0.2 us a byte)

HLIB_PACE_NL EQU 311
        INCLUDE "lib/hlib_speed.asm"
        DEFINE HLIB_PACE_LEAN

; ---------------------------------------------------------------------------------------------------------------

        ORG 0x2000
; ---- h_render: the site 0x9E54 (CALL RENDER -> CALL t_render) ---------------------------------------------------
h_render:
        ld (g_sp),sp                    ; S-2: (S-2) = RET_R
        ld sp,STK
        push af
        ld a,i
        jp pe,plain_r                   ; interrupts on: the original
        push bc
        push de
        push hl
        HLIB_SPEED_IN_ABC spd
        call hlib_pace_open
        ld hl,CAM                       ; this update's camera
        ld de,cam1
        ld bc,10
        ldir
        ld hl,CARRY                     ; what the last render left for this one (a calibration renders from it)
        ld de,cal_cy
        ld bc,CARRYN
        ldir
        ld a,(43337)
        ld (de),a
        ld hl,(g_sp)                    ; return to h_post with the original SP
        ld (hl),low h_post
        inc hl
        ld (hl),high h_post
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)
        jp RENDER

plain_r:
        pop af
        ld sp,(g_sp)
        jp t_plr

h_post:
        ld (g_sp),sp                    ; S
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
        ex af,af'
        push af
        ex af,af'
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld (t_r),hl                     ; the real render's lines
        call mulk                       ; HL = its original time
        ld (t_l),hl
        ld hl,cal_cnt
        ld a,(hl)
        or a
        jr z,.cal
        dec (hl)
        call extras
        jr .w
.cal:   call calib
        ld a,1
        ld (cal_cpy),a                  ; this update's copy runs at 3.5 MHz: its original time (cpy35)
        ld a,(cal_tnt)
        or a
        ld a,1                          ; a dropped sample: again in two updates
        jr nz,.c2
        ld a,(cal_n)
        cp 3
        ld a,1                          ; every second update until three samples
        jr c,.c2
        ld a,CAL_EVERY
.c2:    ld (cal_cnt),a
.w:     ld hl,(t_l)
        call wait_to
h_wend:
        ld hl,cam1                      ; the next update's previous camera
        ld de,cam0
        ld bc,10
        ldir
        ld a,1
        ld (cam0ok),a
        ex af,af'
        pop af
        ex af,af'
        exx
        pop hl
        pop de
        pop bc
        exx
        pop iy
        pop ix
        HLIB_SPEED_OUT_A spd            ; flags kept
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)                    ; S
        push hl                         ; (S-2) = RET_R as the original left it
        ld hl,RET_R
        ex (sp),hl
        jp t_exit

; ---- h_copy: the site 0x9E6B (CALL VCOPY -> CALL t_copy) ---------------------------------------------------------
h_copy:
        ld (g_sp),sp
        ld sp,STK
        push af
        ld a,i
        jp pe,plain_c
        push bc
        push de
        push hl
        HLIB_SPEED_IN_ABC spd
        call hlib_pace_open
        call band                       ; the beam below the view (counted in the window: the target holds it)
        ld hl,(HLIB_V_PACE+2)
        ld (t_b),hl
        ld a,(cal_cpy)                  ; a calibration update: the copy alone at the original's speed
        or a
        ld a,3
        jr z,.f
        xor a
.f:     ld (.spd+3),a
        ld hl,(g_sp)
        ld (hl),low h_cpost
        inc hl
        ld (hl),high h_cpost
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)
.spd:   nextreg 0x07,3                  ; (the value set above)
        jp VCOPY

plain_c:
        pop af
        ld sp,(g_sp)
        jp t_plc

h_cpost:
        nextreg 0x07,3                  ; at once: the copy's measurement ends here
        ld (g_sp),sp
        ld sp,STK
        push af
        push bc
        push de
        push hl
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld de,(t_b)
        or a
        sbc hl,de                       ; the copy's own lines
        ld a,(cal_cpy)
        or a
        jr z,.t
        xor a
        ld (cal_cpy),a
        ld de,CPY_LO                    ; at 3.5 MHz: its original time (a fixed 4K copy: 0.896-0.905 frames by
        or a                            ; its start line in JNext), unless out of range
        sbc hl,de
        add hl,de
        jr c,.t
        ld de,CPY_HI
        or a
        sbc hl,de
        add hl,de
        jr nc,.t
        ld (cpy35),hl
.t:     ld hl,(cpy35)                   ; the target from the window's start: band + copy + wait = the original copy,
        ld de,HOOK_OVH                  ; less the hooks' 3.5 MHz entry / exit code outside the windows
        or a
        sbc hl,de
        call wait_to
        HLIB_SPEED_OUT_A spd
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(g_sp)
        push hl
        ld hl,RET_C
        ex (sp),hl
        jp t_exit

; ---- tick: the site 0xD6FE (CALL TICKT -> CALL t_tick), inside the render; slot 1 = this page --------------------
tick:
        ld (t_sp),sp
        ld sp,STK2
        push af
        push bc
        push de
        push hl
        ld a,(HLIB_V_PACE+10)           ; hlib_pace_tick's work without the hold accounting (no hold / resume in
        or a                            ; this engine: the held total stays 0)
        jr z,.x
        call hlib_line
        ld de,(HLIB_V_PACE)
        ld (HLIB_V_PACE),hl
        or a
        sbc hl,de
        jr nc,.p
        ld de,HLIB_PACE_NL
        add hl,de
.p:     ld de,(HLIB_V_PACE+2)
        add hl,de
        ld (HLIB_V_PACE+2),hl
.x:     pop hl
        pop de
        pop bc
        pop af
        ld sp,(t_sp)
        jp TICKT

; ---- mulk: HL = HL x K256 / 256 (lines), saturating. AF, BC, DE lost --------------------------------------------
mulk:
        ld bc,(k256)                    ; B = K's integer part, C = its fraction
        ld (mk_r),hl
        ld d,l
        ld e,c
        mul d,e                         ; rl x kl
        ld l,d
        ld h,0                          ; acc = rl x kl / 256
        ld a,(mk_r)
        ld d,a
        ld e,b
        mul d,e                         ; + rl x kh
        add hl,de
        ld a,0
        adc a,a
        ld (mk_x),a
        ld a,(mk_r+1)
        ld d,a
        ld e,c
        mul d,e                         ; + rh x kl
        add hl,de
        ld a,(mk_x)
        adc a,0
        ld (mk_x),a
        ld a,(mk_r+1)
        ld d,a
        ld e,b
        mul d,e                         ; + rh x kh x 256
        ld a,h
        add a,e
        ld h,a
        ld a,(mk_x)
        adc a,d
        ret z
        ld hl,0xFFFF
        ret

; ---- calib: K from this update's render. The scratch copy (taken after the real render: camera and state as it
; left them; a second render takes its time within 0.02 %) is rendered again at 3.5 MHz with the tick site put back
; (the original's code), interrupts on through this page's IM 2 table (im2t -> isr: counts frames, reads the line).
; Its lines / the real render's 28 MHz lines (t_r) = a sample of K; K = the first sample, then (3 K + sample) / 4.
; A sample outside 4-10 is dropped. AF, BC, DE, HL lost; IX, IY, the alternate set kept
calib:
        xor a
        ld (cal_tnt),a
        call scratch_on
        nextreg 0x54,PG_ROMC            ; the ROM's 0x0000-0x1FFF -> PG_ROMC (through slot 4), then slot 0
        ld hl,0
        ld (dma_src),hl
        ld hl,0x8000
        ld (dma_dst),hl
        ld hl,dma_pk
        ld bc,(dma_end-dma_pk)*256+0x6B
        otir
        nextreg 0x54,PG_S4
        ld bc,0x243B                    ; slots 2-3 too (no interrupt push can reach the game's own RAM)
        ld a,0x52
        out (c),a
        inc b
        in a,(c)
        ld (g_mmu23),a
        dec b
        ld a,0x53
        out (c),a
        inc b
        in a,(c)
        ld (g_mmu23+1),a
        ld hl,0
        ld (dma_dst),hl
        nextreg 0x50,PG_S2
        ld hl,0x4000
        ld (dma_src),hl
        ld hl,dma_pk
        ld bc,(dma_end-dma_pk)*256+0x6B
        otir
        nextreg 0x50,PG_S2+1
        ld hl,0x6000
        ld (dma_src),hl
        ld hl,dma_pk
        ld bc,(dma_end-dma_pk)*256+0x6B
        otir
        nextreg 0x50,PG_ROMC
        nextreg 0x52,PG_S2
        nextreg 0x53,PG_S2+1
        ld a,0xCD
        ld (0xD6FE),a
        ld hl,TICKT
        ld (0xD6FF),hl
cal_carry:
        ld hl,cal_cy                    ; the render-to-render state as the real render found it: the same render
        ld de,CARRY                     ; again (from what it left, update 532 took another path: -2.2 %)
        ld bc,CARRYN
        ldir
        ld a,(hl)
        ld (43337),a
        xor a
        ld (cal_f),a
        ld a,i
        ld (g_i),a
        ld a,high im2t
        ld i,a
.wl:    call hlib_line                  ; not near the frame interrupt (line 248 here): one that comes before the EI
        ld a,h                          ; is missed, and the first counted one is a frame later than the sum assumes
        or a
        jr nz,.wok
        ld a,l
        cp 240
        jr nc,.wl                       ; lines 240-255: wait (16 lines at most, inside the window)
.wok:   call hlib_pace_tick             ; the window counted up to here (its next reading: the render's end)
        nextreg 0x07,0
        call hlib_line
        ld (cal_l0),hl
        ld (cal_sp),sp                  ; the handler's way out of an abandoned render
        ei
cal_r0: call RENDER
cal_r1: di
        call hlib_line
        ld (cal_l1),hl
        nextreg 0x07,3
        nextreg 0x50,0xFF
        ld a,(g_mmu23)
        nextreg 0x52,a
        ld a,(g_mmu23+1)
        nextreg 0x53,a
        ld a,(g_i)
        ld i,a
        call scratch_off
        ld a,(cal_f)
        or a
        jr nz,.fr
        ld hl,(cal_l1)                  ; under a frame: one wrap at most
        ld de,(cal_l0)
        call sub311
        jr .e
.fr:    ld hl,(cal_l1)                  ; 311 x frames + (L1 - LI) mod 311 - (L0 - LI) mod 311
        ld de,(cal_li)
        call sub311
        push hl
        ld hl,(cal_l0)
        ld de,(cal_li)
        call sub311
        ex de,hl
        pop hl
        or a
        sbc hl,de
        ld b,h
        ld c,l
        ld a,(cal_f)
        ld e,a
        ld d,55
        mul d,e
        ld h,a
        ld l,0
        add hl,de
        add hl,bc
.e:     push hl                         ; the window: + all of it
        ld de,(HLIB_V_PACE+2)
        add hl,de
        ld (HLIB_V_PACE+2),hl
        ld hl,(cal_l1)
        ld (HLIB_V_PACE),hl
        ld a,(cal_f)                    ; the render alone: - the handler's time (ISR_T a frame after the first)
        ld e,a
        ld d,ISR_T/8
        mul d,e
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,228
        call div16
        ex de,hl
        pop hl
        or a
        sbc hl,de
        ld (cal_e),hl
        ld de,CAL_MIN                   ; a short render: the handler's spread (937-1679 T a frame) is too large a
        or a                            ; share of it (updates 963-964: +0.5-0.7 %): dropped like a hit
        sbc hl,de
        add hl,de
        jr nc,.long
        ld a,1
        ld (cal_tnt),a
.long:  ld de,(t_r)
        ld a,d
        or e
        ret z
        call div16r                     ; HL = e / r, DE = remainder
        ld a,h
        or a
        ret nz
        ld a,l
        cp 4
        ret c
        cp 10
        ret nc
        push af
        ex de,hl
        ld de,(t_r)
        call frac8
        ld l,a
        pop af
        ld h,a                          ; HL = the sample, K x 256
        ld (cal_s),hl
        ld a,(cal_tnt)                  ; a push hit the write set: the render may have gone another way
        or a
        ret nz
    IFDEF K_EMA                         ; (3 K + sample) / 4: lags the scene's own K changes (JNext: +1 % pace)
        ld a,(cal_n)
        or a
        jr z,.set
        ld de,(k256)
        add hl,de
        add hl,de
        add hl,de
        srl h
        rr l
        srl h
        rr l
    ENDIF
.set:   ld (k256),hl                    ; K = the latest sample (a second render repeats within 0.02 %)
        ld a,(cal_n)
        inc a
        ret z
        ld (cal_n),a
        ret

; sub311: HL = (HL - DE) mod 311 (both 0-310). F lost
sub311:
        or a
        sbc hl,de
        ret nc
        ld de,311
        add hl,de
        ret

; isr: a calibration frame (interrupts are on only in calib). Its own stack at once: only the CPU's push touches
; the render's SP data (object lists walked by POP, ROM bytes); those 2 bytes are put back from the genuine memory,
; then a JP to the return address (no RET through that data).
isr:    ld (isr_sp),sp
        ld sp,STK2                      ; the tick's stack (no tick in the calibration render)
        push af
        push bc
        push de
        push hl
        ld hl,cal_f
        inc (hl)
        ld a,(hl)
        dec a
        jr nz,.n1                       ; the line: at the first interrupt only (the frame interrupt's line)
        call hlib_line
        ld (cal_li),hl
.n1:    ld hl,(isr_sp)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (isr_jp+1),de
        dec hl
        call isr_taint                  ; the push's two bytes in the render's write set: no repair can be right
        inc hl                          ; (the render may have written them before, and writes them again)
        call isr_taint
        ld a,(cal_tnt)                  ; hit: the render may now follow a wrong byte (update 605: a pointer in
        or a                            ; 0x9C00, run away). Abandoned: everything it touches is scratch; the
        jr z,.ok                        ; sample is dropped, the time so far still counted (cal_r1 reads the line)
        ld sp,(cal_sp)
        jp cal_r1
.ok:    dec hl
        call isr_fix
        inc hl
        call isr_fix
        inc hl
        ld (isr_sp),hl
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(isr_sp)
        ei
isr_jp: jp 0

; isr_taint: HL in a 16-byte block of the write set (wmap) -> cal_tnt = 1. Constant time (the handler's time is
; subtracted as a constant). HL kept; AF, DE lost
isr_taint:
        push hl
        ld a,l
        rlca
        and 1
        ld e,a                          ; L >> 7
        ld a,h
        add a,a
        ld d,0
        rl d
        or e
        ld e,a                          ; DE = HL >> 7
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 7
        inc a                           ; (L >> 4) & 7, + 1 rotations: that bit to carry
        ld hl,wmap
        add hl,de
        ld d,(hl)
        ld e,a
        ld a,d
.s:     rrca
        dec e
        jr nz,.s
        pop hl
        ret nc
        ld a,1
        ld (cal_tnt),a
        ret

; isr_fix: (HL) = the byte the genuine memory holds there (slot 0: the ROM, into its copy PG_ROMC; slots 2-7: the
; game's page, into the scratch copy; slot 1: this page, nothing). HL kept; AF, BC lost
isr_fix:
        ld a,h
        and 0xE0
        cp 0x20
        ret z
        push hl
        rlca
        rlca
        rlca
        and 7
        ld b,0xFF
        jr z,.m
        ld c,a
        ld b,0
        push hl
        ld hl,g_mmu23-2
        add hl,bc
        ld b,(hl)
        pop hl
.m:     ld a,h
        and 0x1F
        ld h,a
        ld a,b
        nextreg 0x50,a
        ld c,(hl)
        nextreg 0x50,PG_ROMC
        pop hl
        ld (hl),c
        ret

; ---- wait_to: HL = the window's target (lines). Waits until its elapsed lines reach target - debt; an overrun
; goes to the debt (capped). AF, BC, DE, HL lost ----------------------------------------------------------------
wait_to:
        ld de,(debt)                    ; goal = target - debt, signed (a debt over the target carries on)
        or a
        sbc hl,de
        ld (t_goal),hl
        ld bc,0                         ; polls (an emulator without a line counter: give up)
.w:     push bc
        call hlib_pace_tick
        pop bc
        ld hl,(HLIB_V_PACE+2)
        ld de,(t_goal)
        or a
        sbc hl,de                       ; elapsed - goal (both under 16384 in size: no overflow)
        jp p,.done
        dec bc
        ld a,b
        or c
        jr nz,.w
        ld hl,0
.done:  ld de,DEBTCAP                   ; HL = overrun (0 when waited)
        ex de,hl
        or a
        sbc hl,de
        ex de,hl
        jr c,.cap                       ; over the cap
        ld (debt),hl
        jr .x
.cap:   ld hl,DEBTCAP
        ld (debt),hl
.x:     xor a
        ld (HLIB_V_PACE+10),a           ; window closed
        ret

; ---- band: wait until the beam is in BAND0..BAND1. AF, BC, DE, HL lost -------------------------------------------
band:
        ld de,0
.w:     push de
        call hlib_pace_tick
        call hlib_line
        pop de
        ld a,h
        or a
        jr nz,.hi
        ld a,l
        cp BAND0
        jr nc,.ok
        jr .no
.hi:    ld a,l
        cp BAND1-256+1
        jr c,.ok
.no:    dec de
        ld a,d
        or e
        jr nz,.w
.ok:    ret

; ---- extras: in-between views (scratch pages), shown at even times from now to the final view's time --------
extras:
        xor a
        ld (t_n),a
        ld a,(cam0ok)
        or a
        ret z
        call deltas                     ; CF: too far, or no movement
        ret c
        ld hl,(t_r)                     ; an extra view's estimate: the real render's lines + a copy + half a band
        ld de,CPYL+60
        add hl,de
        ld (t_e),hl
        call hlib_pace_tick
        ld hl,(t_l)                     ; slots = (L - now - SCRL) / estimate
        ld de,(HLIB_V_PACE+2)
        or a
        sbc hl,de
        ret c
        ld de,SCRL
        sbc hl,de
        ret c
        ld de,(t_e)
        call div16
        ld a,h
        or a
        jr nz,.big
        ld a,l
        cp NMAX+1
        jr c,.n
.big:   ld a,NMAX+1
.n:     sub 1                           ; n = slots - 1 (at least 1)
        ret c
        ret z
        ld (t_nn),a
        call scratch_on
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld (t_x0),hl                    ; t0
        ex de,hl
        ld hl,(t_l)
        or a
        sbc hl,de                       ; span (> 0: SCRL left for the copy)
        jp c,.done
        ld a,(t_nn)
        inc a
        ld e,a
        ld d,0
        call div16
        ld (t_st),hl                    ; step
        ld a,1
        ld (t_i),a
.loop:  ld hl,(t_st)                    ; s = t0 + i x step
        ld a,(t_i)
        ld b,a
        ex de,hl
        ld hl,(t_x0)
.m:     add hl,de
        djnz .m
        ld (t_s),hl
        call hlib_pace_tick             ; skip a slot that cannot be met
        ld hl,(HLIB_V_PACE+2)
        ld de,(t_e)
        add hl,de
        ex de,hl
        ld hl,(t_s)
        or a
        sbc hl,de
        jr c,.next
        ld hl,(t_s)                     ; f = s x 256 / L
        ld de,(t_l)
        call frac8
        call setcam
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld (t_y0),hl
        call RENDER
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)           ; the estimate = this view's lines + a copy + half a band
        ld de,(t_y0)
        or a
        sbc hl,de
        ld de,CPYL+60
        add hl,de
        ld (t_e),hl
.ws:    call hlib_pace_tick             ; its time
        ld hl,(HLIB_V_PACE+2)
        ld de,(t_s)
        or a
        sbc hl,de
        jr c,.ws
        call band
        call VCOPY
        ld hl,t_n
        inc (hl)
.next:  ld hl,t_i
        ld a,(t_nn)
        cp (hl)
        jr z,.done
        inc (hl)
        jr .loop
.done:  jp scratch_off

; deltas: cam1 - cam0 into dl_*; CF = no extras (a word step over 2047, an angle step over 64, or no change)
deltas:
        ld ix,cam0
        ld iy,cam1
        ld hl,dl_w
        ld b,3
        ld c,0                          ; OR of all steps
.w:     push bc
        ld e,(ix+0)
        ld d,(ix+1)
        ld a,(iy+0)
        sub e
        ld e,a
        ld a,(iy+1)
        sbc a,d
        ld d,a
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        pop bc
        ld a,d                          ; |d| < 2048
        bit 7,a
        jr z,.p
        cpl
.p:     and 0xF8
        jr nz,.no
        ld a,d
        or e
        or c
        ld c,a
        inc ix
        inc ix
        inc iy
        inc iy
        djnz .w
        ld ix,cam0+7
        ld iy,cam1+7
        ld b,3
.a:     ld a,(iy+0)
        sub (ix+0)
        ld (hl),a
        inc hl
        ld d,a
        or c
        ld c,a
        ld a,d
        add a,64
        cp 129
        jr nc,.no
        inc ix
        inc iy
        djnz .a
        ld a,c
        or a
        jr z,.no
        ret                             ; CF = 0 (OR)
.no:    scf
        ret

; setcam: A = f (0-255): camera = cam0 + step x f / 256 (rounded), written to the game's (scratch) variables
setcam:
        ld (t_f),a
        ld ix,cam0
        ld iy,dl_w
        ld hl,CAM
        ld b,3
.w:     push bc
        push hl
        ld e,(iy+0)
        ld d,(iy+1)
        ld c,0                          ; sign
        bit 7,d
        jr z,.p
        ld c,1
        xor a
        sub e
        ld e,a
        sbc a,a
        sub d
        ld d,a                          ; DE = |step|
.p:     ld a,(t_f)
        ld h,d                          ; hi x f
        ld l,a
        ld d,a                          ; lo x f
        mul d,e
        ex de,hl
        mul d,e                         ; DE = hi x f, HL = lo x f
        ld a,l
        add a,128
        ld a,h
        adc a,0
        ld l,a
        ld h,0                          ; (lo x f + 128) >> 8
        add hl,de                       ; + hi x f
        ld a,c
        or a
        jr z,.q
        xor a
        sub l
        ld l,a
        sbc a,a
        sub h
        ld h,a
.q:     ld e,(ix+0)
        ld d,(ix+1)
        add hl,de
        ex de,hl
        pop hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        inc ix
        inc ix
        inc iy
        inc iy
        pop bc
        djnz .w
        ld a,(cam1+6)                   ; 43406 as this update's
        ld (hl),a
        inc hl
sc_angix:
        inc ix                          ; cam0+7: the angles (past cam0's 43406)
        ld b,3
.a:     push bc
        ld a,(iy+0)                     ; signed angle step
        ld c,0
        bit 7,a
        jr z,.ap
        ld c,1
        neg
.ap:    ld e,a
        ld a,(t_f)
        ld d,a
        mul d,e
        ld a,e
        add a,128
        ld a,d
        adc a,0
        bit 0,c
        jr z,.aq
        neg
.aq:    add a,(ix+0)
        ld (hl),a
        inc hl
        inc ix
        inc iy
        pop bc
        djnz .a
        ret

; scratch_on: slots 4-7 copied (DMA) to PG_S4 .., then mapped; the game's pages kept in g_mmu
scratch_on:
        ld bc,0x243B
        ld hl,g_mmu
        ld d,0x54
.r:     out (c),d
        inc b
        in a,(c)
        dec b
        ld (hl),a
        inc hl
        inc d
        ld a,d
        cp 0x58
        jr nz,.r
        ld hl,0
        ld (dma_dst),hl
        ld a,PG_S4
        ld hl,0x8000
.c:     push af
        push hl
        nextreg 0x50,a
        ld (dma_src),hl
        ld hl,dma_pk
        ld bc,(dma_end-dma_pk)*256+0x6B
        otir
        pop hl
        ld de,0x2000
        add hl,de
        pop af
        inc a
        cp PG_S4+4
        jr nz,.c
        nextreg 0x50,0xFF
sco_map:                                ; (hard_drivin.negative_patches: the extra views on the game's pages)
        nextreg 0x54,PG_S4
        nextreg 0x55,PG_S4+1
        nextreg 0x56,PG_S4+2
        nextreg 0x57,PG_S4+3
        ret

scratch_off:
        ld a,(g_mmu)
        nextreg 0x54,a
        ld a,(g_mmu+1)
        nextreg 0x55,a
        ld a,(g_mmu+2)
        nextreg 0x56,a
        ld a,(g_mmu+3)
        nextreg 0x57,a
        ret

dma_pk: db 0x83,0xC3,0x7D
dma_src: dw 0x8000
        dw 0x2000
        db 0x14,0x10,0xAD
dma_dst: dw 0x0000
        db 0x82,0xCF,0x87
dma_end:

; ---- arithmetic -------------------------------------------------------------------------------------------------
; div16 / div16r: HL = HL / DE (unsigned, DE > 0), DE = the remainder. AF, BC lost
div16:
div16r:
        ld b,h
        ld c,l
        ld hl,0
        ld a,16
.l:     sla c
        rl b
        adc hl,hl
        or a
        sbc hl,de
        jr nc,.s
        add hl,de
        jr .n
.s:     inc c
.n:     dec a
        jr nz,.l
        ex de,hl
        ld h,b
        ld l,c
        ret

; frac8: A = HL x 256 / DE, HL < DE (else 255). BC, HL lost
frac8:
        or a
        sbc hl,de
        jr c,.ok
        ld a,255
        ret
.ok:    add hl,de
        ld b,8
        ld c,0
.l:     add hl,hl
        jr c,.ge
        or a
        sbc hl,de
        jr nc,.one
        add hl,de
        or a
        jr .bit
.ge:    or a
        sbc hl,de
.one:   scf
.bit:   rl c
        djnz .l
        ld a,c
        ret

; ---- variables --------------------------------------------------------------------------------------------------
g_sp:   dw 0                            ; the game's SP at a hook's entry / at the routine's return
t_sp:   dw 0                            ; the game's SP in a tick
spd:    db 0                            ; the incoming speed (HLIB_SPEED_IN latch)
cam0ok: db 0                            ; cam0 holds the last update's camera
cam0:   ds 10                           ; 43400-43409 of the last update
cam1:   ds 10                           ; of this update
dl_w:   ds 9                            ; steps: 3 words, 3 angle bytes
t_f:    db 0
t_r:    dw 0                            ; the real render's lines (28 MHz)
t_l:    dw 0                            ; its original time (lines)
t_b:    dw 0                            ; h_copy: the band wait
t_e:    dw 0                            ; an extra view's estimate
t_x0:   dw 0
t_y0:   dw 0
t_st:   dw 0
t_s:    dw 0
t_goal: dw 0
t_i:    db 0
t_nn:   db 0
t_n:    db 0                            ; in-between views shown this update
debt:   dw 0                            ; lines over the original, carried to the next window
g_mmu23: ds 2                           ; the game's MMU 2-3 (calib; g_mmu must follow: isr_fix's table)
g_mmu:  ds 4                            ; the game's MMU 4-7 while the scratch pages are mapped
isr_sp: dw 0
k256:   dw K_INIT                       ; K x 256: original time / the 28 MHz time (calib)
mk_r:   dw 0
mk_x:   db 0
cal_cnt: db 0                           ; updates to the next calibration (0: this one)
cal_n:  db 0                            ; samples taken
cal_f:  db 0                            ; frames (interrupts) in the calibration render
cal_l0: dw 0
cal_l1: dw 0
cal_li: dw 0                            ; the line at the last interrupt
cal_e:  dw 0                            ; the calibration render's lines
cal_s:  dw 0                            ; the last sample
cal_cy: ds CARRYN+1                     ; 0x912E-0x91CD and 43337 as the real render found them
cal_tnt: db 0
cal_sp: dw 0                            ; SP at the calibration render's call
cal_cpy: db 0                           ; 1: this update's copy runs at 3.5 MHz (h_post after a calibration)
cpy35:  dw CPY_INIT                     ; the copy's original time (lines), measured at calibrations                           ; a push hit the render's write set: the sample is dropped
g_i:    db 0
        INCLUDE "hard_drivin_wset.inc"
HLIB_V_PACE: ds 26
        INCLUDE "lib/hlib_pace.asm"
code_end:
        ASSERT code_end <= SH
        ORG SH
t_render:
        nextreg 0x51,PG_CODE
        jp h_render
t_copy: nextreg 0x51,PG_CODE
        jp h_copy
t_tick: jp tick
t_exit: nextreg 0x51,0xFF
        ret
t_plr:  nextreg 0x51,0xFF
        jp RENDER
t_plc:  nextreg 0x51,0xFF
        jp VCOPY
t_end:
        ORG 0x3A3A                      ; IM 2 (calibration only): every vector 0x3A3A
        jp isr
        ORG 0x3B00
im2t:   ds 257,0x3A
        ORG 0x3D80                      ; 0x3D00-0x3D7F: the tick's stack; 0x3D80-0x3FFD: the hooks' (and an extra view's render)
STK2:   ds 0x3FFE-0x3D80
STK:
        SAVEBIN "hdrivin_page.bin",0x2000,0x2000

; ---- the alt ROM's bytes at SH (the ROM side of each trampoline: the NEXTREG that maps this page into slot 1 is
; the last instruction run from the ROM; the page's JP at the same address runs next). Assembled here, at 0x4000
; (nothing else there), displaced to SH; each label equals its page-side twin.
        ORG 0x4000
        DISP SH
r_render:
        nextreg 0x51,PG_CODE
        ds 3,0xFF
r_copy: nextreg 0x51,PG_CODE
        ds 3,0xFF
r_tick: jp TICKT                        ; slot 1 = ROM: a render outside the hooks (0x6A32, 0xF652, 0xF752)
r_exit: nextreg 0x51,0xFF
        ret
r_plr:  nextreg 0x51,0xFF
        jp RENDER
r_plc:  nextreg 0x51,0xFF
        jp VCOPY
r_end:
        ENT
        ASSERT r_render == t_render && r_copy == t_copy && r_tick == t_tick && r_exit == t_exit
        ASSERT r_plr == t_plr && r_plc == t_plc && r_end == t_end
        SAVEBIN "hdrivin_rom.bin",0x4000,r_end-SH
