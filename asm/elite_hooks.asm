; Elite (Firebird 1985, Russian 128K hack) - engine 'elite', milestone M1 (early integrated diagnostic):
; the viewport is mirrored onto a double-buffered Layer 2 in colour (per ship model, per draw category).
; Design: games/elite.md "## Build plan". All hook code lives in alt ROM image 1 (stateless; the one state byte,
; the current colour, is NextReg $7F: 0 = ship mode, colour from the ship's blueprint in IY).
;
; The game ORs every line pixel into a mono back buffer (bank 0, 0xC000-0xCFDF, screen layout, shown at 0x4020 by
; the copy 0x7FBE). Each buffer write instruction is replaced by a one-byte RST:
;   LD (HL),A  (77)    -> RST 18h  (DF)      h_plot: does the write, then sets / clears the Layer 2 pixels whose
;   LD (HL),B  (70)    -> RST 10h  (D7)      buffer bit changed (0->1: current colour, 1->0: transparent)
;   LD (HL),FF (36 FF) -> RST 20h, NOP (E7 00)
; The buffer stays exactly the original's (the ULA copy keeps running underneath: anything not mirrored shows white).
; Category hooks (CALL / JP retargeted, original bytes checked by nexclash/elite.py):
;   0x74EE CALL Z,0x7584 planet / sun   0x74F1 CALL 0x7898 stars   0x74F4 CALL 0xD03C messages
;   0x74F7 CALL 0x9C80 combat (lasers, crosshair; ships through the wrapper below)
;   0x9E44 JP 0xF8B4 (ship draw wrapper) -> ship mode    0xF8D4 JP 0x9E47 (wrapper exit) -> combat colour
;   0x8080 buffer clear (DI / LD BC,30) -> also clears the Layer 2 back buffer, colour reset to white
;   0x7FBE buffer copy (LD HL,0xC000)   -> flips Layer 2 (NR $12 <-> NR $13) first

        DEVICE ZXSPECTRUMNEXT

L2_A      EQU 16            ; Layer 2 16K banks: 16-18 and 19-21 (8K pages 32-37, 38-43)
L2_B      EQU 19
TRANS     EQU 0xE3          ; Layer 2 transparent colour (NR $14 default)
C_WHITE   EQU 0xFF
C_RED     EQU 0xE0
C_PLANET  EQU 0x4B
C_SUN     EQU 0xFC          ; yellow: the filled body (0x7107 via 0x86D0, h_sun)
C_SHIPDEF EQU 0xFF
P_L2      EQU 0x0B          ; port 0x123B: write-over on (bit 0), visible (bit 1), shadow bank NR $13 (bit 3)
P_SHOW    EQU 0x02          ; visible only
TICK      EQU 10            ; frames per game pass (the original's mean, 9.7-10.5 over the five recordings)
STATE_PG  EQU 26            ; 8K page: engine state, mapped at slot 0 (0x0000) only under DI inside a hook
S_FRAME   EQU 0x0000        ; word: frames counted by h_isr
S_LAST    EQU 0x0002        ; word: S_FRAME at the last tick
S_PAT     EQU 0x0004        ; byte: position in pattab (0-24)
S_BACK    EQU 0x0005        ; byte: Layer 2 bank the next render draws into (the other of L2_A / L2_B is shown)
S_W       EQU 0x0006        ; byte: ship list (0 / 1) h_ship records into during a pass
S_CUR     EQU 0x0007        ; byte: ship list of the last pass (the other is the pass before: prev)
S_RD      EQU 0x0008        ; byte: frames-since-tick of the last render in this wait (0xFF: none yet)
S_IFF     EQU 0x0009        ; byte: interrupts were on at h_flip
S_WGT     EQU 0x000A        ; byte: interpolation weight of cur, 0-255 (/256)
S_FULL    EQU 0x000B        ; byte: 1 = draw cur as it is (no interpolation)
S_SP      EQU 0x000C        ; word: SP around a ship draw
S_RI      EQU 0x000E        ; byte: records left in this render
S_RP      EQU 0x0010        ; word: current cur record
S_LINE    EQU 0x0016        ; byte: raster line / 2 at the last fcount
S_OWE     EQU 0x0017        ; byte: game ISR bodies owed (pattab per counted frame, run one per interrupt)
S_INTL    EQU 0x0015        ; byte: raster line / 2 of the interrupt (0 in the zeroed page: setup sets 0xFF)
S_ISRF    EQU 0x0024        ; byte: an interrupt was counted since the last poll
S_PC      EQU 0x0025        ; byte: the last poll counted a frame
S_FLIGHT  EQU 0x0026        ; byte: the flight loop (0x9C80) ran since the last h_flip
S_RSP    EQU 0x0028        ; word: SP at render entry (render runs on RSTK)
S_RA     EQU 0x002A        ; byte: render's A argument across the stack switch
S_CTL    EQU 0x002C        ; 6 bytes: the controls 0xFF08-0xFF0D across scenery (it scales them in place)
RSAVE    EQU 0x0040        ; 0x60 bytes: game RAM under RSTK, saved around a render
RSTK     EQU 0x7470        ; render stack top: 0x7410-0x746F, inside 0x7366-0x7470, untouched in all five
RSTKLEN  EQU 0x60          ; recordings (scan_low / surveys); the game's own stack 0x4100-0x411F is 32
                           ; bytes, the row below it on screen (a render there showed as dashes)
S_PL      EQU 0x0012        ; word: prev list base
S_PN      EQU 0x0014        ; byte: prev list count
S_TP      EQU 0x0018        ; 3 bytes: lerp scratch (prev value, 24-bit two's complement)
S_KEY     EQU 0x001C        ; 4 bytes: slot and blueprint interp looks for
S_N       EQU 0x0020        ; 2 bytes: ship counts of list 0 / 1
LIST0     EQU 0x0100        ; ship records (REC bytes each, MAXREC per list)
LIST1     EQU 0x0B00
SAVE      EQU 0x1600        ; game RAM the ship draw writes (outtab), saved around a render
REC       EQU 160
MAXREC    EQU 16
R_IX      EQU 0             ; word: slot
R_IY      EQU 2             ; word: blueprint
R_A       EQU 4             ; byte: the wrapper's 0xA79D value - A of the AF the ship loop pushed at 0x9D38
R_IN      EQU 5             ; NIN bytes: the draw's varying inputs (intab), as at the original draw
NIN       EQU 100
R_SLOT    EQU R_IN + NIN    ; 39 bytes: the slot as at the original draw
SLOTLEN   EQU 39
BASE_BK   EQU 14            ; Layer 2 16K banks 14-15: everything but ships, drawn by the logic pass (h_plot)
C_NOMIRROR EQU 0x01         ; NR $7F: the logic pass's own ship draw - buffer only, the renderer draws ships

; ---------------------------------------------------------------------------------------------------------------
; RST vectors (alt ROM low image, 0x0010-0x0027; Sinclair's bytes there are never read by the game: access scan).
; Not RST 08h: CSpect (with -mmc) traps it as an esxDOS call and skips the next byte as the function number
; (the star writer's LD (HL),A / RET at 0xA84B lost its RET - the M1 build froze, 2026-11-23).
; ---------------------------------------------------------------------------------------------------------------
        ORG 0x0010
rst10:  push af                         ; LD (HL),B
        ld a,b
        call h_plot
        pop af
        ret
        ds 0x0018 - $, 0
rst18:  jp h_plot                       ; LD (HL),A
        ds 0x0020 - $, 0
rst20:  push af                         ; LD (HL),0xFF
        ld a,0xFF
        call h_plot
        pop af
        ret
rst28:  jp h_lddr                       ; LDDR (the sun's fill, 0x5E4B)
low_end:
        SAVEBIN "elite_low.bin", rst10, low_end - rst10

; ---------------------------------------------------------------------------------------------------------------
; Hooks (alt ROM 0x3000-0x3BFF; the game executes 0x22B0-0x22CA and reads 0x0127-0x0B26 and the font, never here)
; ---------------------------------------------------------------------------------------------------------------
        ORG 0x3000
rom_start:

; h_lddr: LDDR through h_plot, so every byte it copies is mirrored. The sun's fill (0x5E36) writes a row's right
; byte with LD (HL),A (hooked) and copies it left with LDDR at 0x5E4B: unhooked, only the first byte of each row
; reached Layer 2 (black bar through the sun, Witch, 2026-11-23); 0x8A81 (row fill after LD (HL),0xFF) the same.
; Keeps A and F (both sites are followed by code that sets the flags again). NR $7F = C_NOMIRROR (logic pass): the
; plain LDDR, so the game's tiny stack (0x4100-0x411F, the row below it is on screen) goes no deeper than 4 bytes.
h_lddr: push af
        call nomirror
        jr nz,.loop
        pop af
        lddr
        ret
.loop:  ld a,(hl)
        ex de,hl
        call h_plot
        ex de,hl
        dec hl
        dec de
        dec bc
        ld a,b
        or c
        jr nz,.loop
        pop af
        ret

; nomirror: Z if NR $7F = C_NOMIRROR (the logic pass's planet, stars and ship draws). Clobbers A, F only.
nomirror:
        push bc
        ld bc,0x243B
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        pop bc
        cp C_NOMIRROR
        ret

; Planet / sun fills' stack blit (0x8BCD, 0x8CCD, 0x8DC3: LD SP,0x8FB6 / POP AF / LD SP,HL / JR into 16 x PUSH AF,
; the JR offset patched to 16 - n): 2n bytes of 0xFF below HL. Each LD SP,0x8FB6 becomes JP to its stub. Not
; mirroring (logic pass): the original blit. Mirroring: the bytes through h_plot (fill2n), then on at the end of the
; push chain, which sets A / F again and reloads SP from 0x8623. Found 2026-11-23 (probe buf_pcs.py, Witch / Havoc /
; PoliceAnarchy whole): M1's writer list came from Docking only.
PFILL   MACRO site, off, cont
        call nomirror
        jr z,.orig
        ld a,(off)
        call fill2n
        jp cont
.orig:  ld sp,0x8FB6
        jp site + 3
        ENDM
pf_8BCD: PFILL 0x8BCD, 0x8BD3, 0x8BE4
pf_8CCD: PFILL 0x8CCD, 0x8CD3, 0x8CE4
pf_8DC3: PFILL 0x8DC3, 0x8DC9, 0x8DDA

; fill2n: A = the patched JR offset (16 - n): (HL - 1) .. (HL - 2n) = 0xFF through h_plot. Keeps HL, BC, DE.
fill2n: push hl
        push bc
        ld b,a
        ld a,16
        sub b
        add a,a
        jr z,.done
        ld b,a
.byte:  dec hl
        ld a,0xFF
        call h_plot
        djnz .byte
.done:  pop bc
        pop hl
        ret

; h_sun (0x759E, CALL 0x86D0 in 0x7584): the filled body (0x7107, the sun: yellow scanner icon) in C_SUN, then the
; colour as it was (the outlined planet 0x7110 follows via 0x86DE). Logic pass: the original call (tail jump, same
; stack). 0x86D0's inputs are memory only (0xFB31 loads A, EX AF,AF'); the caller reads A from 0x861D after.
h_sun:  call nomirror
        jp z,0x86D0
        push af
        nextreg 0x7F,C_SUN
        call 0x86D0
        pop af
        nextreg 0x7F,a
        ret

; rowfix: repaint ULA row y = 56 (0x40E0-0x40FF), just below the game's 32-byte stack 0x4100-0x411F, as the blank
; viewport row the copy shows (frame bits 0x80 at 0x40E1, 0x01 at 0x40FE), and the hack's save of it (0xFFD0-0xFFDF,
; taken at 0xF8EC, put back at 0xF907). Deep calls (the planet circle most) leave stack bytes there; the original's
; copy repaints the row soon after, here the copy waits for the tick - white dashes, at times the whole row
; (2026-11-23, user report). Only when SP is above the row. Keeps all registers.
rowfix: push af
        push hl
        push bc
        ld hl,0x40E0
        ld b,32
        xor a
.r1:    ld (hl),a
        inc l
        djnz .r1
        ld hl,0xFFD0
        ld b,16
.r2:    ld (hl),a
        inc l
        djnz .r2
        ld a,0x80
        ld (0x40E1),a
        ld a,0x01
        ld (0x40FE),a
        ld (0xFFDE),a
        pop bc
        pop hl
        pop af
        ret

; h_plot: (HL) = A, as the original LD (HL),A, and mirror the changed bits on the Layer 2 back buffer.
; Keeps every register and flag. Interrupts may be on. Stack: 10 bytes with the RST (4 pushes, no CALL) - the ship
; draw wrapper runs on a 32-byte stack at 0x4000-0x401F and reaches the writers with SP down to 0x400E (site_ctx probe):
; one byte more than 14 would push into the ROM and lose a return address (M1 first boot crashed that way).
h_plot: push af
        call nomirror
        jr nz,.mir
        pop af
        ld (hl),a                       ; the logic pass's planet / stars / ships: the write only (stack: 4 bytes)
        ret
.mir:   pop af
        push af
        push bc
        ld c,a                          ; C = new byte
        ld a,(hl)
        ld (hl),c                       ; the original write
        xor c                           ; A = changed bits
        jr z,.out
        push de
        push hl
        ld e,a                          ; E = changed bits
        ld a,h                          ; the buffer is in screen layout at 0xC000: line k from HL as from a screen
        sub 0xC0                        ; address; the copy shows line k at screen y = k + 8 for k = 0-119 (it walks
        cp 0x10                         ; both pointers line by line, so there is no fixed address offset)
        jr nc,.skip                     ; not the buffer (the same writers also write game data above 0xCFE0)
        ld a,l                          ; k = (H & 7) | ((L >> 2) & 0x38) | ((H << 3) & 0xC0)
        rrca
        rrca
        and 0x38
        ld b,a
        ld a,h
        and 7
        or b
        ld b,a
        ld a,h
        rlca
        rlca
        rlca
        and 0xC0
        or b
        cp 120
        jr nc,.skip                     ; lines 120-127: never shown
        add a,8
        ld d,a                          ; D = y
        ld a,l
        and 31
        jr z,.skip                      ; columns 0 and 31: outside the viewport frame (the copy leaves them out,
        cp 31                           ; stars plot there)
        jr z,.skip
        rlca
        rlca
        rlca
        ld l,a                          ; L = x of the byte's first pixel
        ld h,c                          ; H = new byte (C is needed for the ports)
        ld a,d
        and 0xC0
        or P_L2
        ld bc,0x123B
        out (c),a                       ; write-over: back buffer, third y >> 6
        ld bc,0x243B                    ; colour: NR $7F, or the ship's (IY blueprint) when it is 0
        ld a,0x7F
        out (c),a
        inc b
        in a,(c)
        cp C_NOMIRROR
        jr z,.woff                      ; the logic pass's ship draw: the renderer draws the ships
        or a
        jr nz,.col
        ld b,high shipcol
        ld a,iyl
        ld c,a
        ld a,(bc)
.col:   ld b,a                          ; B = colour
        ld c,h                          ; C = new byte
        ld a,d
        and 63
        ld h,a                          ; HL = pixel address in the third
        ld d,8
.bit:   sla e                           ; carry = this pixel changed
        jr nc,.next
        bit 7,c
        ld (hl),b
        jr nz,.next
        ld (hl),TRANS
.next:  sla c
        inc l
        dec d
        jr nz,.bit
.woff:  ld bc,0x123B
        ld a,P_SHOW
        out (c),a                       ; write-over off
.skip:  pop hl
        pop de
.out:   pop bc
        pop af
        ret

; ---- category hooks ----
h_planet:                               ; M3b: planet, sun and stars are drawn by the renderer (scenery)
        call poll
        nextreg 0x7F,C_NOMIRROR
        jp 0x7584
h_stars:
        call poll
        call rowfix                     ; the planet draw just before goes deepest on the game's stack
        nextreg 0x7F,C_NOMIRROR
        jp 0x7898
h_msg:  call poll
        nextreg 0x7F,C_WHITE
        jp 0xD03C
h_combat:
        call pollf
        nextreg 0x7F,C_RED
        jp 0x9C80
; h_ship (0x9E44, JP 0xF8B4 = the hack's draw wrapper): record this ship as the original draws it (slot, blueprint,
; the draw's varying inputs) into list S_W, for the renderer; the logic pass's own draw goes to the buffer only.
; The wrapper starts with DI and ends with EI anyway. Main stack (SP ~0x411x).
h_ship: di
        push af
        push bc
        push de
        push hl
        ld hl,9
        add hl,sp
        ld b,(hl)                       ; B = A of the AF pushed at 0x9D38 (the wrapper stores it at 0xA79D)
        nextreg 0x50,STATE_PG
        call fcount
        ld a,(S_W)
        ld hl,S_N
        add hl,a
        ld a,(hl)
        cp MAXREC
        jp nc,.full
        inc (hl)
        ld e,a
        ld d,REC
        mul d,e
        ld a,(S_W)
        ld hl,LIST0
        or a
        jr z,.l0
        ld hl,LIST1
.l0:    add hl,de                       ; HL = record
        ld a,ixl
        ld (hl),a
        inc hl
        ld a,ixh
        ld (hl),a
        inc hl
        ld a,iyl
        ld (hl),a
        inc hl
        ld a,iyh
        ld (hl),a
        inc hl
        ld (hl),b
        inc hl
        ex de,hl
        ld hl,intab
        call tab_save                   ; DE = record's slot copy
        push ix
        pop hl
        ld bc,SLOTLEN
        ldir
.full:  nextreg 0x50,0xFF
        pop hl
        pop de
        pop bc
        pop af
        nextreg 0x7F,C_NOMIRROR
        jp 0xF8B4
h_shipend:
        call poll
        nextreg 0x7F,C_RED
        jp 0x9E47

; poll (interrupts on or off, main stack): fcount from the logic pass - its DI stretches (the hack's ship draws,
; the game's own) lose interrupts, and the frame counter must see the raster at least once a frame. Keeps every
; register, flag and the interrupt state.
pollf:  push af                          ; poll, and mark this pass as flight (h_combat)
        ld a,i
        push af
        di
        nextreg 0x50,STATE_PG
        ld a,1
        ld (S_FLIGHT),a
        jr poll.f
poll:   push af
        ld a,i                          ; P/V = IFF2
        push af
        di
        nextreg 0x50,STATE_PG
.f:     call fcount
        nextreg 0x50,0xFF
        pop af
        jp po,.n
        ei
.n:     pop af
        ret

; h_clear (0x8080, replaces DI / LD BC,30): clear the back buffer's thirds 0 and 1 (rows 0-127) with the DMA,
; through slots 6 / 7 (bank 0 there again afterwards). Interrupts off from here on, as the original. No stack
; use while slots 6 / 7 are remapped (SP may be up there).
h_clear:
        call poll
        di
        push af                         ; the original keeps A (callers rely on it); pushed before the remap
        nextreg 0x7F,C_WHITE
        ld bc,0x243B
        ld a,0x13
        out (c),a
        inc b
        in a,(c)                        ; A = back buffer's 16K bank
        add a,a                         ; its first 8K page
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        inc a
        ld hl,dma_fill
        ld bc,(dma_fill_len << 8) | 0x6B
        otir
        nextreg 0x56,a
        inc a
        nextreg 0x57,a
        ld hl,dma_fill
        ld bc,(dma_fill_len << 8) | 0x6B
        otir
        nextreg 0x56,0
        nextreg 0x57,1
        pop af
        ld bc,30
        jp 0x8084

        INCLUDE "elite_render.inc"

; zxnDMA: fill 0xC000-0xFFFF with TRANS (port A fixed at trans_byte, port B incrementing, continuous)
dma_fill:
        db 0x83                         ; disable
        db 0x7D                         ; WR0: A -> B, port A address and length follow
        dw trans_byte
        dw 0x4000
        db 0x24                         ; WR1: port A memory, fixed
        db 0x10                         ; WR2: port B memory, increment
        db 0xAD                         ; WR4: continuous, port B address follows
        dw 0xC000
        db 0x82                         ; WR5: stop at end
        db 0xCF                         ; load
        db 0x87                         ; enable
dma_fill_len EQU $ - dma_fill
trans_byte:
        db TRANS

; zxnDMA: copy 0x8000-0x9FFF -> 0xC000-0xDFFF (one 8K page of base to the back buffer; slots 4 / 6 remapped)
dma_copy:
        db 0x83, 0x7D
        dw 0x8000
        dw 0x2000
        db 0x14                         ; WR1: port A memory, increment
        db 0x10                         ; WR2: port B memory, increment
        db 0xAD
        dw 0xC000
        db 0x82, 0xCF, 0x87
dma_copy_len EQU $ - dma_copy



; The ship draw's inputs that differ from ship to ship (read before written in the call, outside the slot; probe
; draw_deps.py INPUTS varying, union of the five recordings): recorded per ship by h_ship, set before each render
; draw. Scratch the previous draw left (vertex tables 0xA8FA- and 0xB452-, 0xB7AA) and view state.
; dw length, address; 0 ends.
intab:  dw 1, 0x6F42
        dw 1, 0x70E3
        dw 12, 0xA8FA
        dw 1, 0xA9C8
        dw 1, 0xAA0F
        dw 0xB4A7 - 0xB452, 0xB452      ; (to 0xB4A6: 0x7898 via 0xF9A8)
        dw 2, 0xB7AA
        dw 0
        ASSERT 1 + 1 + 12 + 1 + 1 + (0xB4A4 - 0xB452) + 2 == NIN
        ASSERT R_SLOT + SLOTLEN <= REC
        ASSERT LIST0 + MAXREC * REC <= LIST1 && LIST1 + MAXREC * REC <= SAVE

; Game RAM the ship draw writes (probe draw_deps.py OUTPUTS, union of the five recordings, small gaps merged),
; saved / restored around a render (same format). The slots 0x6048-0x617F (8 x 39) are written back whole: the
; render overwrites the live slot with each record and its interpolation.
outtab: dw 0x6180 - 0x6048, 0x6048
        dw 1, 0x6F42
        dw 2, 0x6FEB
        dw 0x7102 - 0x70E4, 0x70E4      ; ownrot, scenery (0x713C): per-pass roll / pitch / speed and derived
        dw 0x7119 - 0x7107, 0x7107      ; scenery (0x7853): planet and sun positions
        dw 1, 0x7120                    ; scenery (0x7584)
        dw 1, 0x7128                    ; scenery (0x7898, rare)
        dw 0x7583 - 0x757A, 0x757A      ; scenery (0x7584): planet work area
        dw 1, 0x78B5                    ; scenery (0x7898)
        dw 1, 0x7EDD                    ; scenery (0x7898 via 0xF9A8)
        dw 0x7A59 - 0x7A39, 0x7A39      ; scenery (0x7898): star table
        dw 0x8AA0 - 0x8A85, 0x8A85      ; scenery (0x7584, Havoc: planet markings)
        dw 0x8ACC - 0x8ABA, 0x8ABA      ; scenery (0x9B68): planet axis vectors
        dw 1, 0x8BD3                    ; scenery (0x7584)
        dw 1, 0x8CD3                    ; scenery (0x7584, Havoc)
        dw 1, 0x8DC9                    ; scenery (0x7584, Havoc)
        dw 0x9527 - 0x9522, 0x9522      ; scenery (0x7898 / 0x7584, rare)
        dw 1, 0x95AE
        dw 1, 0x95BD
        dw 2, 0x95F2                    ; scenery (0x7853, rare)
        dw 1, 0x96BF
        dw 1, 0xA1AD                    ; scenery (0x9B68 patches it)
        dw 0x862A - 0x861A, 0x861A
        dw 1, 0x9C97
        dw 2, 0x9F80                    ; ownrot: rotation bytes for 0xA0AB
        dw 1, 0xA6DE
        dw 1, 0xA79D
        dw 0xA951 - 0xA8FA, 0xA8FA
        dw 0xA9C9 - 0xA984, 0xA984
        dw 0xAA29 - 0xAA0E, 0xAA0E
        dw 3, 0xAC9F
        dw 0xB1C8 - 0xB1B5, 0xB1B5
        dw 0xB213 - 0xB20D, 0xB20D
        dw 1, 0xB231
        dw 3, 0xB25D
        dw 0xB4A7 - 0xB452, 0xB452      ; (to 0xB4A6: 0x7898 via 0xF9A8)
        dw 2, 0xB7AA
        dw 0xBCD4 - 0xBCC8, 0xBCC8
        dw 0x20, 0xCFE0                 ; scenery: line tables past the mono buffer
        dw 6, 0xFF08                    ; scenery: controls, scaled in place
        dw 0

; tab_save: copy every (length, address) of the table at HL to DE onwards. tab_load: from DE back to them.
; DE ends after the copies. Clobbers A, BC, HL.
tab_save:
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        ret z
        push hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ldir
        pop hl
        inc hl
        inc hl
        jr tab_save
tab_load:
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,b
        or c
        ret z
        push hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ex de,hl
        ldir
        ex de,hl
        pop hl
        inc hl
        inc hl
        jr tab_load

; Frame counting. Interrupts alone miss frames (the ship draws and the render run with DI: 16 % lost in the first
; M2 run), and raster polls alone miss them too (polls exactly one frame apart, as h_isr's own, never see the line
; go down: 5 %). So h_isr counts each interrupt (isrcount) and polls (fcount, at least once a frame through every
; DI stretch: render, h_ship, the logic-pass hooks) count the frames whose interrupt was lost: phase p = raster line
; / 2 from the interrupt's own line (S_INTL, taken at the first interrupt), a frame when p goes down. S_ISRF: an
; interrupt counted since the last poll (that poll then only takes the phase); S_PC: the last poll counted one (a
; late interrupt after it is the same frame). Each counted frame adds its pattab entry to S_OWE.
; Both: state page at slot 0, keep BC, DE, HL; clobber AF.
fcount: push bc
        push hl
        call phase
        ld hl,S_ISRF
        ld b,(hl)
        ld (hl),0
        ld hl,S_LINE
        ld c,(hl)
        ld (hl),a
        ld hl,S_PC
        ld (hl),0
        inc b
        dec b
        jr nz,.out                      ; first poll after an interrupt: phase only
        cp c
        jr nc,.out
        ld (hl),1
        call addframe
.out:   pop hl
        pop bc
        ret

isrcount:
        push bc
        push hl
        ld a,(S_INTL)
        inc a
        jr nz,.cal
        call rline
        ld (S_INTL),a                   ; the interrupt's line: the frame boundary from now on
.cal:   call phase
        ld hl,S_LINE
        ld c,(hl)
        ld (hl),a
        ld hl,S_ISRF
        ld b,(hl)
        ld (hl),1
        inc b
        dec b
        jr nz,.cnt                      ; no poll since the last interrupt: a new frame
        cp c
        jr c,.cnt                       ; phase went down since the last poll
        ld a,(S_PC)
        or a
        jr nz,.out                      ; that poll already counted this frame (the interrupt came late)
.cnt:   call addframe
.out:   pop hl
        pop bc
        ret

; phase: A = (raster line / 2 - S_INTL) mod 156 (0xFF in S_INTL: not yet known, 0 used). Clobbers BC, HL.
phase:  call rline
        ld hl,S_INTL
        ld b,(hl)
        inc b
        ret z
        sub (hl)
        ret nc
        add a,156
        ret

; rline: A = raster line / 2 (NR $1E bit 0, NR $1F; read again if bit 8 changed between). Clobbers BC, HL.
rline:  ld bc,0x243B
        ld a,0x1E
        out (c),a
        inc b
        in l,(c)
        dec b
        ld a,0x1F
        out (c),a
        inc b
        in h,(c)
        dec b
        ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        cp l
        jr nz,rline
        ld a,l
        rrca                            ; carry = bit 8
        ld a,h
        rra
        ret

; addframe: S_FRAME + 1, S_OWE + this frame's pattab entry (at most 2 owed). Clobbers A, HL.
addframe:
        ld hl,(S_FRAME)
        inc hl
        ld (S_FRAME),hl
        ld a,(S_PAT)
        inc a
        cp 25
        jr c,.p
        xor a
.p:     ld (S_PAT),a
        ld l,a
        ld h,high pattab
        ld a,(hl)
        ld hl,S_OWE
        add a,(hl)
        cp 3
        jr c,.o
        ld a,2
.o:     ld (hl),a
        ret

        ds 0x3900 - $, 0xFF
; IM 2 vector table: I = 0x39 (snapshot I and the game's LD A,0xFD at 0xFF4C changed by nexclash/elite.py), so the
; vector is 0xFEFE (the game's ISR entry) whatever byte the bus holds. The original table (I = 0xFD) has FE FE only
; at 0xFDFF / 0xFE00 and game code elsewhere: CSpect's IM 2 bus byte is not 0xFF, and the first interrupt jumped
; through 0xFD00 = 0xC903 into the buffer (plain conversion crashed in pass 2, 2026-11-23).
im2tab: ds 257, high h_isr             ; vector 0x3A3A = h_isr for any bus byte
        ds 0x3A3A - $, 0xFF

; h_isr (IM 2): count frames (fcount), then run the game's ISR body (0xFF25: keyboard, controls, sound) if one
; is owed - pattab gives 16 per 25 frames, the original's ~0.64 accepted interrupts per frame (probe pass_ints.py,
; all five recordings), so turn rate, timers and sound per second stay the original's at 28 MHz. Interrupts lost
; while ship draws run with DI are made up at the next one (at most 2 owed). The hack's own switch (0xFEFE = RET
; while a ship is drawn on the 0x4020 stack) is honoured first, before any push.
        ASSERT $ == 0x3A3A
h_isr:  push af
        ld a,(0xFEFE)
        cp 0xC9
        jr z,.off
        push bc
        push hl
        nextreg 0x50,STATE_PG
        call isrcount
        ld hl,S_OWE
        ld a,(hl)
        or a
        jr z,.no
        dec (hl)
        pop hl
        pop bc
        nextreg 0x50,0xFF
        pop af
        jp 0xFF25                       ; the game's ISR (ends EI / RET)
.no:    pop hl
        pop bc
        nextreg 0x50,0xFF
        pop af
        ei
        ret
.off:   pop af                          ; as the original RET at 0xFEFE: interrupts stay off
        ret


        ASSERT $ <= 0x3AE0
        ds 0x3AE0 - $, 0xFF
pattab:                                 ; 16 ones in 25, spread evenly
        db 1,0,1,1,0,1,0,1,1,0,1,1,0,1,0,1,1,0,1,1,0,1,0,1,0
        ASSERT $ - pattab == 25
        ds 0x3B00 - $, 0xFF
; ship colour per blueprint (index = low byte of IY); other values white. RRRGGGBB, never TRANS. Blueprints are
; 23-byte records from 0x61E3 (0x61E3 + 23 n, n = 0-22; low bytes all distinct); IY = the record while a ship's lines
; are drawn. Model names not yet identified; the station seen in Docking is 0x63C6 (n = 21). Provisional colours,
; repaintable later (design detail 1).
shipcol:
        ds 256, C_SHIPDEF
BP      MACRO lo, col
        ORG shipcol + lo
        db col
        ENDM
        BP 0xE3, 0x1F           ; n 0   cyan
        BP 0xFA, 0xF4           ; n 1   orange-pink
        BP 0x11, 0xFC           ; n 2   yellow
        BP 0x28, 0x1C           ; n 3   green
        BP 0x3F, 0xE3 ^ 0x40    ; n 4   (0xA3) purple
        BP 0x56, 0x5F           ; n 5   sky blue
        BP 0x6D, 0xE7           ; n 6   magenta
        BP 0x84, 0xD8           ; n 7   olive-yellow
        BP 0x9B, 0x7C           ; n 8   lime
        BP 0xB2, 0xEC           ; n 9   salmon
        BP 0xC9, 0xF0           ; n 10  orange
        BP 0xE0, 0x9B           ; n 11  sea green
        BP 0xF7, 0xCF           ; n 12  pink
        BP 0x0E, 0x3B           ; n 13  teal
        BP 0x25, 0x9F           ; n 14  mint
        BP 0x3C, 0x6F           ; n 15  lavender
        BP 0x53, 0xFE           ; n 16  pale yellow
        BP 0x6A, 0x3F           ; n 17  aqua
        BP 0x81, 0xEA           ; n 18  rose
        BP 0x98, 0x93           ; n 19  steel
        BP 0xAF, 0xB7           ; n 20  lilac
        BP 0xC6, 0xDB           ; n 21  station: light grey-blue
        BP 0xDD, 0xF8           ; n 22  amber
        ORG shipcol + 256
rom_end:
        SAVEBIN "elite_rom.bin", rom_start, rom_end - rom_start

; ---------------------------------------------------------------------------------------------------------------
; Set-up (stub bank, CALLed by the stub at 0xD000 before the tail; 3.5 MHz, stub stack in slot 6): Layer 2 banks,
; both cleared to transparent through slot 7 (the stub's upper page, mapped back afterwards), Layer 2 shown.
; ---------------------------------------------------------------------------------------------------------------
        ORG 0xD000
setup:  nextreg 0x07,3                  ; 28 MHz (the tail leaves NR $07 alone)
        nextreg 0x12,L2_A
        nextreg 0x13,BASE_BK            ; the logic pass draws into base; renders into S_BACK
        nextreg 0x14,TRANS
        nextreg 0x7F,C_WHITE
        nextreg 0x57,STATE_PG
        ld a,L2_B
        ld (0xE000 + S_BACK),a
        ld a,0xFF
        ld (0xE000 + S_INTL),a
        ASSERT BASE_BK + 2 == L2_A && L2_A + 3 == L2_B
        ld a,BASE_BK * 2
        ld e,16                         ; base, A, B: 8 x 2 pages
.pg:    nextreg 0x57,a
        ld hl,s_dma
        ld bc,(s_dma_len << 8) | 0x6B
        otir
        inc a
        dec e
        jr nz,.pg
        nextreg 0x57,21                 ; z80tonex.STUB_PAGE_HI
        ld bc,0x123B
        ld a,P_SHOW
        out (c),a
        ret
s_dma:  db 0x83, 0x7D
        dw s_trans
        dw 0x2000
        db 0x24, 0x10, 0xAD
        dw 0xE000
        db 0x82, 0xCF, 0x87
s_dma_len EQU $ - s_dma
s_trans:
        db TRANS
setup_end:
        SAVEBIN "elite_setup.bin", setup, setup_end - setup
