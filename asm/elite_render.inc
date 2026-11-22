; Elite engine M2 (included by elite_hooks.asm): end of pass, the tick wait and the 50 fps ship renderer.
; Design: games/elite.md "## M2 design".

; h_flip (0x7FBE, replaces LD HL,0xC000): end of a game pass. The ship list just recorded (h_ship) becomes cur, the
; one before prev. While waiting for the tick (TICK frames since the last one, counted by h_isr), render once per
; frame with weight d / TICK (d = frames since the tick); with interrupts off (a screen the game draws with DI)
; render cur once. Then the mono buffer is cleared and the original copy shows it (zeros) on the ULA viewport, which
; Layer 2 now covers. The original clobbers A, F, BC, DE, HL here too (LD HL / LD DE / the copy loops).
h_flip: ld a,i                          ; P/V = IFF2
        di
        nextreg 0x50,STATE_PG
        ld a,0
        jp po,.f0
        inc a
.f0:    ld (S_IFF),a
        ld hl,S_FLIGHT
        ld a,(hl)
        ld (hl),0
        or a
        jp z,.plain                     ; not after a flight pass (status, charts, equipment: the game draws the
                                        ; page into the buffer and this copy shows it): the original copy only
        call rowfix                     ; ULA row 56 below the game's stack: see rowfix
        ld a,(S_W)
        ld (S_CUR),a
        xor 1
        ld (S_W),a                      ; the next pass records into prev's list (emptied after the wait)
        ld a,0xFF
        ld (S_RD),a
        ld a,(S_IFF)
        or a
        jr nz,.w
        ld a,TICK
        call render
        jr .done
.w:     call fcount
        ld hl,(S_FRAME)
        ld de,(S_LAST)
        or a
        sbc hl,de                       ; frames since the last tick
        ld a,h
        or a
        jr nz,.tick
        ld a,l
        cp TICK
        jr nc,.tick
        ld hl,S_RD
        cp (hl)
        jr z,.halt
        ld (hl),a
        call render
.halt:  nextreg 0x50,0xFF               ; not HALT: polls only at the interrupt's own line never see the raster
        ei                              ; go round, so the wait never ended (2026-11-23); poll at every line
        nop                             ; instead, letting the interrupt in between
        nop
        di
        nextreg 0x50,STATE_PG
        jr .w
.tick:  ld a,(S_RD)
        inc a
        jr nz,.t2
        ld a,TICK                       ; the pass took the whole tick: show cur once
        call render
.t2:    ld hl,(S_FRAME)
        ld (S_LAST),hl
.done:  ld a,(S_W)
        ld hl,S_N
        add hl,a
        ld (hl),0                       ; prev is no longer needed: the next pass records there
        call mono_clear                 ; the copy then shows only the frame on the ULA viewport
        ld a,(S_IFF)
        nextreg 0x50,0xFF
        or a
        jr z,.nei
        ei
.nei:   ld hl,0xC000
        jp 0x7FC1
.plain: nextreg 0x12,BLANK_BK              ; M4: the original's screen only (launch, hyperspace, pages)
        ld a,(S_IFF)
        nextreg 0x50,0xFF
        or a
        jr z,.nei
        ei
        jr .nei

; render (DI, state page at slot 0; A = frames since the tick, TICK or more = cur as it is): Layer 2 back buffer =
; base (planet, stars, text, lasers, crosshair: the logic pass's h_plot) + every ship of the cur list at its
; position and orientation interpolated from prev (same slot and blueprint) with weight A / TICK, drawn by the
; game's own ship draw 0xA6DF on the live slot through h_plot. All game RAM the draw writes (outtab, the slots
; included) is saved first and restored after, so the logic sees exactly what the original would (probe
; draw_deps.py). Then show it. Clobbers everything; keeps the state page mapping. Runs on its own stack RSTK (the
; game's RAM there saved and restored): the game's stack has 32 bytes and the scenery calls go deeper than the
; original's (2026-11-23: stack bytes in the screen row below it, white dashes at the right of the viewport).
render: ld (S_RA),a
        ld (S_RSP),sp
        ld hl,RSTK - RSTKLEN
        ld de,RSAVE
        ld bc,RSTKLEN
        ldir
        ld sp,RSTK
        ld a,(S_RA)
        call render_b
        ld sp,(S_RSP)
        ld hl,RSAVE
        ld de,RSTK - RSTKLEN
        ld bc,RSTKLEN
        ldir
        ret
        ASSERT RSAVE + RSTKLEN <= LIST0

render_b:
        ld b,a
        xor a
        ld (MIRF),a                     ; the render mirrors everything it draws
        ld a,b
        cp TICK
        ld b,0
        jr c,.part
        inc b
        xor a
.part:  ld hl,wtab
        add hl,a
        ld a,(hl)
        ld (S_WGT),a
        ld a,b
        ld (S_FULL),a
        ld a,(S_BACK)
        nextreg 0x13,a                  ; h_plot draws into the back buffer
        add a,a
        ld e,a                          ; E = back buffer's first 8K page
        ld d,BASE_BK * 2
        ld b,4
.cp:    push bc
        ld a,d
        nextreg 0x54,a
        ld a,e
        nextreg 0x56,a
        ld hl,dma_copy
        ld bc,(dma_copy_len << 8) | 0x6B
        otir                            ; base page -> back page, 8K
        call fcount
        pop bc
        inc d
        inc e
        djnz .cp
        nextreg 0x54,4
        nextreg 0x56,0
        call mono_clear                 ; every ship pixel is then a change h_plot mirrors
        ld hl,outtab
        ld de,SAVE
        call tab_save
        call scenery                    ; planet, sun, stars first: ships are drawn over them, as in the original
        nextreg 0x7F,0                  ; ship colours (IY)
        ld a,(S_CUR)                    ; cur list -> S_RP / S_RI, prev list -> S_PL / S_PN
        ld hl,S_N
        add hl,a
        ld b,(hl)
        xor 1
        ld hl,S_N
        add hl,a
        ld c,(hl)
        ld hl,LIST0
        ld de,LIST1
        or a
        jr z,.pl
        ex de,hl
.pl:    ld (S_PL),hl                    ; A = prev list index: HL = prev base, DE = cur base
        ld a,c
        ld (S_PN),a
        ld (S_RP),de
        ld a,b
        ld (S_RI),a
.rec:   ld a,(S_RI)
        or a
        jp z,.rdone
        dec a
        ld (S_RI),a
        ld hl,(S_RP)
        ld e,(hl)
        inc hl
        ld d,(hl)                       ; DE = slot
        push de
        ld bc,R_SLOT - 1
        add hl,bc
        ld bc,SLOTLEN
        ldir                            ; live slot = the slot as at the original draw
        ld hl,(S_RP)
        ld bc,R_A
        add hl,bc
        ld a,(hl)
        ld (0xA79D),a                   ; as the wrapper
        inc hl
        ex de,hl
        ld hl,intab
        call tab_load
        pop ix                          ; IX = slot
        ld a,(S_FULL)
        or a
        call z,interp
        ld a,(S_FULL)
        or a
        call z,ownrot
        ld hl,(S_RP)
        inc hl
        inc hl
        ld a,(hl)
        ld iyl,a
        inc hl
        ld a,(hl)
        ld iyh,a
        ld a,0xC9
        ld (0xFEFE),a                   ; as the wrapper: an interrupt during the draw returns without EI
        ld (S_SP),sp
        ld sp,0x4020                    ; the wrapper's stack
        nextreg 0x50,0xFF               ; the draw reads ROM (0x0127-0x0B26) and runs 0x22B0
        call 0xA6DF
        nextreg 0x50,STATE_PG
        ld sp,(S_SP)
        call fcount
        ld a,0x18
        ld (0xFEFE),a
        ld hl,(S_RP)
        ld bc,REC
        add hl,bc
        ld (S_RP),hl
        jp .rec
.rdone: ld hl,outtab
        ld de,SAVE
        call tab_load
        nextreg 0x7F,C_WHITE
        ld a,(S_BACK)
        nextreg 0x12,a                  ; show the render
        xor L2_A ^ L2_B                 ; the other one next (not NR $12 read back: it may be BLANK_BK, M4)
        ld (S_BACK),a
        nextreg 0x13,BASE_BK            ; the logic pass draws into base
        ret

; interp (IX = live slot holding cur, S_RP = its record): find prev's record of the same slot and blueprint; if
; found, each of x, y, z (lo, hi, sign | bits 16-22) and the 9 orientation components (fraction, sign | magnitude)
; = prev + (cur - prev) * S_WGT / 256, written into the live slot. A value that moved 0x8000 or more (a new ship in
; the slot, a jump) keeps cur.
interp: ld hl,(S_RP)
        ld de,S_KEY
        ld bc,4
        ldir                            ; S_KEY = slot, blueprint
        ld hl,(S_PL)
        ld a,(S_PN)
        ld b,a
.f:     ld a,b
        or a
        ret z
        push bc
        push hl
        ld de,S_KEY
        ld b,4
.c:     ld a,(de)
        cp (hl)
        jr nz,.n
        inc hl
        inc de
        djnz .c
        pop hl
        pop bc
        ld bc,R_SLOT
        add hl,bc                       ; HL = prev's slot copy
        push ix
        pop de                          ; DE = live slot (= cur)
        ld b,3
.p3:    push bc
        ld a,1
        call lerp1
        inc hl
        inc hl
        inc hl
        inc de
        inc de
        inc de
        pop bc
        djnz .p3
        ld b,9
.o9:    push bc
        xor a
        call lerp1
        inc hl
        inc hl
        inc de
        inc de
        pop bc
        djnz .o9
        ret
.n:     pop hl
        ld bc,REC
        add hl,bc
        pop bc
        dec b
        jr .f

; scenery (DI, state page at slot 0; M3b): planet, sun and stars, which the logic pass now draws to the buffer only,
; drawn at their state after the pass (live) moved on by S_WGT / 256 of one pass of the player's own motion - the
; controls' roll / pitch / speed bytes (0xFF09 / 0xFF0B / 0xFF0D) scaled, 0x713C turning them into the per-pass
; values, then the game's own code: 0x7853 moves planet and sun (0xA173 on 0x7107 / 0x7110, 0x9B68 the planet's
; axes), 0x7584 draws them (when 0x7103 = 0, as 0x74EA), 0x7898 moves and draws the stars. Planet, sun and stars
; only move with the player, so this is their place now, as ownrot puts the ships. Everything written is in outtab.
; A routine that ends EI would let h_isr in: DI again before the state page is mapped.
scenery:
        ld hl,0xFF08                    ; controls kept for ownrot (it turns the ships by a whole pass)
        ld de,S_CTL
        ld bc,6
        ldir
        ld a,(S_WGT)
        ld e,a
        nextreg 0x50,0xFF
        ld a,0xC9                       ; 0x7584 / 0x7898 end EI: h_isr then returns at once with interrupts off
        ld (0xFEFE),a                   ; (as during a ship draw; the frame is counted by the next poll)
        ld hl,0xFF09
        call scale_sm
        ld hl,0xFF0B
        call scale_sm
        ld a,(0xFF0D)                   ; 0xA173 moves z by (speed + 1) * 2 (0xFF: none): speed' = (speed + 1) * w / 256 - 1
        inc a
        ld d,a
        mul d,e
        ld a,d
        dec a
        ld (0xFF0D),a
        call 0x713C
        call 0x7853
        di
        call .poll
        ld a,(0x7103)
        or a
        jr nz,.nopl
        nextreg 0x7F,C_PLANET
        call 0x7584
        di
        call .poll
.nopl:  nextreg 0x7F,C_WHITE
        ld a,(0x7EDD)
        dec a
        jr nz,.stx
        call 0x7898                     ; hyperspace: the game's own (its streaks draw the stars several times)
        jr .std
.stx:   call stars_x                    ; not 0x7898 on the scaled controls: its step is speed / 2 + 1 whole
.std:   di                              ; pixels (0xFF on a small weight: stars ran ahead, then back: wobble)
        ld a,0x18
        ld (0xFEFE),a
        nextreg 0x50,STATE_PG
        ld hl,S_CTL
        ld de,0xFF08
        ld bc,6
        ldir
        ret
.poll:  nextreg 0x50,STATE_PG           ; a frame is lost if a whole one passes between polls (a big sun fill)
        call fcount
        nextreg 0x50,0xFF
        ret

; stars_x (slot 0 = ROM, DI): the star table 0x7A39 (16 x (y, x), sign | magnitude, FF FF = none; restored after
; the render, outtab) moved on by S_WGT of a pass along each star's last move (S_STP -> now), then drawn by the
; game's own draw loop 0x79CC (16 stars, 4 when 0x7103 != 0, as 0x790C). A star new this pass (none before, or
; a jump over STJMP) is drawn where it is. Keeps IX.
STJMP   EQU 32
stars_x:
        push ix
        nextreg 0x50,STATE_PG
        ld a,(S_WGT)
        ld c,a                          ; C = w
        ld hl,0x7A39
        ld ix,S_STP
        ld b,16
.st:    ld a,(hl)
        inc hl
        and (hl)
        dec hl
        inc a
        jr z,.nx                        ; no star now
        ld a,(ix+0)
        and (ix+1)
        inc a
        jr z,.nx                        ; no star before: new
        ld e,(ix+0)
        ld a,(hl)
        call exco
        jr c,.nx
        push af                         ; new y
        inc hl
        ld e,(ix+1)
        ld a,(hl)
        call exco
        dec hl
        jr c,.nx1
        inc hl
        ld (hl),a
        dec hl
        pop af
        ld (hl),a
        jr .nx
.nx1:   pop af
.nx:    inc hl
        inc hl
        inc ix
        inc ix
        djnz .st
        nextreg 0x50,0xFF
        pop ix
        ld a,(0x7103)
        and a
        ld a,16
        jr z,.n16
        ld a,4
.n16:   ld hl,.ret
        push hl
        push af                         ; the loop's count (B), as 0x79AB leaves it
        ld hl,0x7A39
        jp 0x79CC
.ret:   ret

; exco: A = now, E = before (sign | magnitude), C = w: A = now + (now - before) * w / 256 as sign | magnitude
; (magnitude at most 127); carry: |now - before| > STJMP. Keeps BC.
exco:   call sm2s
        ld d,a                          ; D = now
        ld a,e
        call sm2s
        ld e,a
        ld a,d
        sub e                           ; A = move
        jp pe,.big
        push bc
        ld b,a
        bit 7,a
        jr z,.p
        neg
.p:     cp STJMP + 1
        jr nc,.big2
        push de
        ld d,a
        ld e,c
        mul d,e
        ld a,d                          ; |move| * w / 256
        pop de
        bit 7,b
        jr z,.a
        neg
.a:     add a,d
        jp po,.ok
        ld a,d                          ; past the end: the end on now's side
        rlca
        ld a,127
        jr nc,.ok
        ld a,-127
.ok:    cp 0x80
        jr nz,.ok2
        ld a,-127
.ok2:   pop bc
        or a                            ; carry clear, S = sign
        ret p
        neg
        or 0x80
        ret                             ; or clears carry
.big2:  pop bc
.big:   scf
        ret

; sm2s: A sign | magnitude -> two's complement.
sm2s:   bit 7,a
        ret z
        and 0x7F
        neg
        ret

; scale_sm: (HL) = sign | magnitude byte, magnitude * E / 256. Keeps E, HL.
scale_sm:
        ld a,(hl)
        ld b,a
        and 0x7F
        ld d,a
        push de
        mul d,e
        ld a,d
        pop de
        ld c,a
        ld a,b
        and 0x80
        or c
        ld (hl),a
        ret

; ownrot (IX = live slot, interpolated; state page at slot 0): M3, own turning without lag. The interpolated
; scene is one tick behind the logic; turn it by one pass of the player's roll / pitch as the controls stand now
; (0xFF09 / 0xFF0B, the bytes 0x713C copies each pass), with the game's own code: 0xA173 rotates the position
; (and moves z by speed: speed byte 0xFF there = no move, so a render never reaches its overflow exit 0x5FD5),
; 0xA0AB x 3 the orientation (as 0x9FA8-0x9FB5). Outputs 0x70E4-0x70E6, 0x9F80-0x9F81 are in outtab.
ownrot: nextreg 0x50,0xFF
        ld a,(0xFF09)
        ld (0x70E4),a
        ld a,(0xFF0B)
        ld (0x70E5),a
        ld a,0xFF
        ld (0x70E6),a
        call 0xA173
        ld hl,(0x70E4)
        ld (0x9F80),hl
        push ix
        ld de,9
        add ix,de
        call 0xA0AB
        call 0xA0AB
        call 0xA0AB
        pop ix
        nextreg 0x50,STATE_PG
        ret

; lerp1: one value. HL = prev field, DE = live (cur) field, A = kind (1: 3-byte position lo, hi, sign | bits 16-22;
; 0: 2-byte component fraction, sign | magnitude). Keeps HL, DE.
lerp1:  push hl
        push de
        push af
        call dec_v                      ; C:D:E = prev
        ld (S_TP),de
        ld a,c
        ld (S_TP + 2),a
        pop af
        pop hl                          ; HL = live field
        push hl
        push af
        call dec_v                      ; C:D:E = cur
        ld hl,(S_TP)
        ex de,hl
        or a
        sbc hl,de                       ; low 16 of cur - prev
        ex de,hl                        ; DE = delta low
        ld a,(S_TP + 2)
        ld b,a
        ld a,c
        sbc a,b
        ld c,a                          ; C:D:E = delta
        ld a,d
        rla                             ; carry = bit 15
        ld a,0
        sbc a,0                         ; A = 0x00 / 0xFF: what C must be for a 16-bit delta
        cp c
        jr nz,.keep                     ; jumped: keep cur
        ld a,c
        or a
        push af                         ; sign of delta
        jp p,.pos
        xor a
        sub e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a                          ; DE = |delta| (0x8000 at most)
.pos:   ld a,(S_WGT)
        ld b,d                          ; |delta| * w / 256 = hi * w + (lo * w) >> 8
        ld d,a
        mul d,e                         ; DE = lo * w
        ld c,d
        ld d,b
        ld e,a
        mul d,e                         ; DE = hi * w
        ld a,e
        add a,c
        ld e,a
        jr nc,.nc
        inc d
.nc:    pop af
        jp p,.add
        xor a                           ; negative: DE = -DE, C = 0xFF
        sub e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a
        ld c,0xFF
        jr .sum
.add:   ld c,0
.sum:   ld hl,(S_TP)
        add hl,de
        ex de,hl
        ld a,(S_TP + 2)
        adc a,c
        ld c,a                          ; C:D:E = prev + delta * w / 256
        pop af
        pop hl                          ; HL = live field
        push hl
        call enc_v
        pop de
        pop hl
        ret
.keep:  pop af
        pop de
        pop hl
        ret

; dec_v: HL = field, A = kind (as lerp1) -> C:D:E two's complement. Clobbers A, HL.
dec_v:  ld e,(hl)
        inc hl
        or a
        jr z,.c2
        ld d,(hl)
        inc hl
        ld a,(hl)
        ld c,a
        res 7,c
        jr .sg
.c2:    ld a,(hl)
        ld d,a
        res 7,d
        ld c,0
.sg:    rla
        ret nc
        xor a
        sub e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a
        ld a,0
        sbc a,c
        ld c,a
        ret

; enc_v: C:D:E -> field at HL, A = kind (as lerp1). Clobbers A, B, C, D, E, HL.
enc_v:  ld b,a
        ld a,c
        rla
        ld a,0
        jr nc,.p
        xor a
        sub e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a
        ld a,0
        sbc a,c
        ld c,a
        ld a,0x80
.p:     ld (hl),e
        inc hl
        dec b
        jr nz,.k2
        or c                            ; position: sign | bits 16-22
        ld (hl),d
        inc hl
        ld (hl),a
        ret
.k2:    or d                            ; component: sign | magnitude
        ld (hl),a
        ret

; mono_clear (DI, state page at slot 0): the game's own buffer clear body 0x8084 (BC = 30): empty viewport plus
; its frame (left / right / bottom lines, written there by plain LDs, not the hooked writers). It ends EI / RET:
; an interrupt may come before the DI here (h_isr then counts it and unmaps slot 0), so the state page is mapped
; again. Clobbers everything.
mono_clear:
        ld bc,30
        call 0x8084
        di
        nextreg 0x50,STATE_PG
        jp fcount

; weight of cur per frames since the tick (d * 256 / TICK, d = 0 .. TICK - 1)
wtab:
WK = 0
        DUP TICK
        db (WK * 256) / TICK
WK = WK + 1
        EDUP
