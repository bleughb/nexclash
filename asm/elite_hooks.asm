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
        INCLUDE "lib/hlib_iff.asm"      ; macros only: HLIB_IFF_DI (card patch.iff-safe-read)

L2_A      EQU 16            ; Layer 2 16K banks: 16-18 and 19-21 (8K pages 32-37, 38-43)
L2_B      EQU 19
BLANK_BK  EQU 22            ; Layer 2 16K banks 22-24 (8K pages 44-49): all transparent, shown on full-screen pages
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
S_FLIGHT  EQU 0x0026        ; byte: the flight loop (0x9C80) ran since the last h_flip (and no clear since)
S_FLIP2   EQU 0x0027        ; byte: a flight h_flip since the last clear: a later copy is the same picture, drawn on
S_RSP    EQU 0x0028        ; word: SP at render entry (render runs on RSTK)
S_RA     EQU 0x002A        ; byte: render's A argument across the stack switch
S_ISP    EQU 0x0032        ; word: SP at h_isr (it runs on HSTK)
S_HSP    EQU 0x0034        ; word: SP at h_ship / poll (they run on HSTK)
S_ULAC   EQU 0x0036        ; byte: the ULA viewport was cleared once (ulaclr)
ISTK     EQU 0x00C0        ; h_isr's stack top (0x00A0-0x00BF), apart from HSTK: an interrupt can come inside one
HSTK     EQU 0x0100        ; hooks' stack top in the state page (0x00A0-0x00FF): the game's own stack 0x4100
                           ; has 32 bytes with a screen row below it (M4: dashes on the pages)
S_HYP    EQU 0x002B        ; byte: 0x7EDD at h_stars (1: a streak pass, its stars are mirrored into the base)
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
S_STP     EQU 0x1F00        ; 32 bytes: the star table 0x7A39 before this pass's move (stsave), for stars_x
S_REGS    EQU 0x1F20        ; 12 bytes: IX, IY, AF', BC', DE', HL' around a render (render_regs)
REC       EQU 160
MAXREC    EQU 16
R_IX      EQU 0             ; word: slot
R_IY      EQU 2             ; word: blueprint
R_A       EQU 4             ; byte: the wrapper's 0xA79D value - A of the AF the ship loop pushed at 0x9D38
R_IN      EQU 5             ; NIN bytes: the draw's varying inputs (intab), as at the original draw
IN_B4END  EQU 0xB4A7        ; intab's 0xB452 range end (to 0xB4A6: 0x7898 via 0xF9A8): NIN and the table share it
NIN       EQU 1 + 1 + 12 + 1 + 1 + (IN_B4END - 0xB452) + 2     ; 103. It said 100 after the range grew: the slot copy
                                ; landed 3 bytes past R_SLOT, every render drew a shifted slot (verifier, 2026-11-23)
R_SLOT    EQU R_IN + NIN    ; 39 bytes: the slot as at the original draw
SLOTLEN   EQU 39
BASE_BK   EQU 14            ; Layer 2 16K banks 14-15: everything but ships, drawn by the logic pass (h_plot)
MIRF      EQU 0x581E        ; 0x40: the logic pass's draws go to the buffer only (NR $7F = C_NOMIRROR), 0: mirror;
                            ; 0x80 (flash, black on black): a render mirrors into the back buffer over the base.
                            ; Attribute row 0 col 30: untouched in all five recordings, 0 (black on black) in every
                            ; snapshot - 0x40 is bright black on black. Read with no stack (nomirror needed 6 bytes
                            ; through the port: page text at SP ~0x4104 reached the screen row below, M4).
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
        ld a,(MIRF)
        cp 0x40
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

; h_sun (0x759E, CALL 0x86D0 in 0x7584): the filled body (0x7107, the sun: yellow scanner icon) in C_SUN, then the
; colour as it was (the outlined planet 0x7110 follows via 0x86DE). Logic pass: the original call (tail jump, same
; stack). 0x86D0's inputs are memory only (0xFB31 loads A, EX AF,AF'); the caller reads A from 0x861D after.
h_sun:  call nomirror
        jp z,0x86D0
cs_sun: nextreg 0x7F,C_SUN
        call 0x86D0
cs_pla1: nextreg 0x7F,C_PLANET           ; scenery's colour for 0x7584 (h_sun runs only there while mirroring)
        ret

; h_plot: (HL) = A, as the original LD (HL),A, and mirror the changed bits on the Layer 2 back buffer: a bit set
; takes the current colour; a bit cleared goes transparent in the logic pass (it draws the base itself) and back to
; the base's pixel in a render - two XOR lines of a ship or the planet crossing on a sight / text pixel left a hole
; in it (the verifier: Havoc 74575 / 74725, PoliceAnarchy 95725; 2026-11-23).
; Keeps every register and flag. Interrupts may be on. Stack: 12 bytes with the RST (5 pushes, no CALL) - the ship
; draw wrapper runs on a 32-byte stack at 0x4000-0x401F and reaches the writers with SP down to 0x400E (site_ctx probe):
; one byte more than 14 would push into the ROM and lose a return address (M1 first boot crashed that way).
h_plot: push af
        ld a,(MIRF)
        cp 0x40
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
        jp z,.out
        push de
        push hl
        ld e,a                          ; E = changed bits
        ld a,h                          ; the buffer is in screen layout at 0xC000: line k from HL as from a screen
        sub 0xC0                        ; address; the copy shows line k at screen y = k + 8 for k = 0-119 (it walks
        cp 0x10                         ; both pointers line by line, so there is no fixed address offset)
        jp nc,.skip                     ; not the buffer (the same writers also write game data above 0xCFE0)
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
        jp nc,.skip                     ; lines 120-127: never shown
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
        HLIB_IFF_DI                     ; P/V = IFF, DI. No interrupt while write-over is on: every write to
        push af                         ; 0x0000-0x3FFF goes to Layer 2, h_isr's stack and state included (it ran
                                        ; on garbage returns: the Docking hang, 2026-11-23)
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
        ld h,a                          ; HL = pixel address in the third; D = y
.bit:   sla e                           ; carry = this pixel changed
        jr nc,.next
        bit 7,c
        ld (hl),b
        jr nz,.next
        ld a,(MIRF)
        or a
        ld a,TRANS
        jr z,.put                       ; the logic pass
        ld a,d
        rlca
        rlca
        and 3
        add a,a
        add a,BASE_BK * 2
        nextreg 0x54,a                  ; the base's third at 0x8000 (DI, no stack use, this code is in the ROM)
        inc a
        nextreg 0x55,a
        set 7,h
        ld a,(hl)
        res 7,h
        nextreg 0x54,4
        nextreg 0x55,5
.put:   ld (hl),a
.next:  sla c
        inc l
        inc e
        dec e
        jr nz,.bit                      ; until no changed bit is left
.woff:  ld bc,0x123B
        ld a,P_SHOW
        out (c),a                       ; write-over off
        pop af
        jp po,.skip
        ei
.skip:  pop hl
        pop de
.out:   pop bc
        pop af
        ret

; ---- category hooks ----
SETMIR  MACRO v
        push af
        ld a,v
        ld (MIRF),a
        pop af
        ENDM
h_planet:                               ; M3b: planet, sun and stars are drawn by the renderer (scenery)
        call poll
        SETMIR 0x40
        nextreg 0x7F,C_NOMIRROR
        jp 0x7584
h_stars:
        call poll
        call rowfix                     ; the planet draw just before goes deepest on the game's stack
        call stsave
        push af
        ld a,(0x7EDD)
        dec a
        jr z,.hyp
        ld a,0x40
        ld (MIRF),a
        pop af
        nextreg 0x7F,C_NOMIRROR
        jp 0x7898
.hyp:   ld (MIRF),a                     ; 0x7EDD = 1 (launch, hyperspace): 0x7898 clears it and draws every star three
        ld a,(cs_sta + 3)               ; times (streaks). Only this pass has them: mirrored into the base in the
        nextreg 0x7F,a                  ; stars' colour, and scenery leaves the stars out (S_HYP). The render drew
        pop af                          ; one dot per star (the verifier: Havoc 73425, Reidquat 145050; 2026-11-23)
        jp 0x7898
h_msg:  call poll
        SETMIR 0
cs_msg: nextreg 0x7F,C_WHITE
        jp 0xD03C
h_combat:
        call pollf
        SETMIR 0
cs_las: nextreg 0x7F,C_RED
        jp 0x9C80
; h_ship (0x9E44, JP 0xF8B4 = the hack's draw wrapper): record this ship as the original draws it (slot, blueprint,
; the draw's varying inputs) into list S_W, for the renderer; the logic pass's own draw goes to the buffer only.
; The wrapper starts with DI and ends with EI anyway. Main stack (SP ~0x411x).
h_ship: di
        nextreg 0x50,STATE_PG
        ld (S_HSP),sp                   ; on HSTK: nothing below the game's SP (the original JP uses none)
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld hl,(S_HSP)
        inc hl
        ld b,(hl)                       ; B = A of the AF pushed at 0x9D38 (the wrapper stores it at 0xA79D)
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
.full:  ld a,0x40
        ld (MIRF),a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(S_HSP)
        nextreg 0x50,0xFF
        nextreg 0x7F,C_NOMIRROR
        jp 0xF8B4
h_shipend:
        call poll
        SETMIR 0
cs_sig: nextreg 0x7F,C_RED
        jp 0x9E47

; poll (interrupts on or off, main stack): fcount from the logic pass - its DI stretches (the hack's ship draws,
; the game's own) lose interrupts, and the frame counter must see the raster at least once a frame. Keeps every
; register, flag and the interrupt state.
pollf:  push af                          ; poll, and mark this pass as flight (h_combat)
        HLIB_IFF_DI
        push af
        nextreg 0x50,STATE_PG
        ld a,1
        ld (S_FLIGHT),a
        push hl                         ; drop ship records from passes since the last h_flip that drew no
        ld a,(S_W)                      ; flight view (a page in flight, 0x74C3, still moves and records ships)
        ld hl,S_N
        add hl,a
        ld (hl),0
        pop hl
        jr poll.f
poll:   push af
        HLIB_IFF_DI                     ; P/V = IFF
        push af
        nextreg 0x50,STATE_PG
.f:     ld (S_HSP),sp
        ld sp,HSTK
        call fcount
        ld sp,(S_HSP)
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
        nextreg 0x50,STATE_PG           ; the picture starts again: a second clear after the flight loop (launch
        xor a                           ; tunnel, hyperspace: 0x74F7 then 0x8080 again, then the copy) is not a
        ld (S_FLIGHT),a                 ; flight view - the render showed the stars on the original's blank frame
        ld (S_FLIP2),a                  ; (verifier, Witch pass 1300, 2026-11-23)
        nextreg 0x50,0xFF
        xor a
        ld (MIRF),a
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
        dw IN_B4END - 0xB452, 0xB452
        dw 2, 0xB7AA
        dw 0
        ASSERT $ - intab == 7 * 4 + 2           ; seven ranges + the end mark (NIN above sums their lengths)
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
; (the gap up to h_isr)
; ulaclr (first flight h_flip): the ULA viewport inside its frame (rows 9-126, x 9-246) cleared once; the frame
; (rows 8/127, x 8/247) kept. The snapshot's own screen is there (lines mid-draw) and the copy that clears it comes
; only after this pass's renders (the original's within ~3 frames, ours ~10). Not at setup: the start-up tail runs
; at 0x4800. Clobbers AF, BC, DE, HL.
ulaclr: ld a,1
        ld (S_ULAC),a
        ld d,9
.r:     ld e,8
        pixelad                         ; HL = screen address of (E, D)
        ld a,(hl)
        and 0x80                        ; keep x 8 (left frame line)
        ld (hl),a
        inc l
        ld b,28
        xor a
.c:     ld (hl),a
        inc l
        djnz .c
        ld a,(hl)
        and 0x01                        ; keep x 247 (right frame line)
        ld (hl),a
        inc d
        ld a,d
        cp 127
        jr nz,.r
        ret

; phase: A = (raster line / 2 - S_INTL) mod 156 (0xFF in S_INTL: not yet known, 0 used). Clobbers BC, HL.
; (moved here from the main block: alt ROM space, 2026-11-23)
phase:  call rline
        ld hl,S_INTL
        ld b,(hl)
        inc b
        ret z
        sub (hl)
        ret nc
        add a,156
        ret

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
        push bc                         ; the interrupted code may have the state page mapped (a render takes an
        ld bc,0x243B                    ; interrupt in its EI stretches): slot 0's page is kept, not assumed ROM
        ld a,0x50                       ; (the verifier: Reidquat 145425, 2026-11-23)
        out (c),a
        inc b
        in a,(c)                        ; A = slot 0's page (0xFF ROM, or STATE_PG)
        nextreg 0x50,STATE_PG
        ld (S_ISP),sp                   ; on ISTK (the interrupted stack keeps only PC, AF, BC)
        ld sp,ISTK
        push hl
        push af
        call isrcount
        ld a,(0x7104)                   ; M4: a full-screen page (docked: 0x7104 = 0; view 0x70E3 >= 4: charts,
        or a                            ; status, inventory in flight) - Layer 2 off (the blank buffer); the
        jr z,.pg                        ; next render shows it again (design detail 5)
        ld a,(0x70E3)
        cp 4
        jr c,.npg
.pg:    nextreg 0x12,BLANK_BK
        nextreg 0x15,0                  ; and the condition light sprite (h_light) off
.npg:   pop af
        push af
        cp 0xFF
        jr nz,.no                       ; state page was mapped: no body now (it stays owed, waitpt runs it)
        ld hl,S_OWE
        ld a,(hl)
        or a
        jr z,.no
        dec (hl)
        pop af
        pop hl
        ld sp,(S_ISP)
        nextreg 0x50,a
        pop bc
        pop af
        jp 0xFF25                       ; the game's ISR (ends EI / RET)
.no:    pop af
        pop hl
        ld sp,(S_ISP)
        nextreg 0x50,a                  ; slot 0 as the interrupted code had it
        pop bc
        pop af
        ei
        ret
.off:   pop af                          ; as the original RET at 0xFEFE: interrupts stay off
        ret

; h_light (0x99D7: LD HL,0x5A28 + the four LD (HL),D of the condition light's attributes, now CALL + 9 NOPs):
; the light drawn by sprite 0 in its colour (D = attribute: ink 2 red / 4 green / 6 yellow, 0 = off while it
; blinks), its two right-hand cells (r17-18 c09, which the scanner also draws into) white instead, so scanner sticks
; there show white, not in the light's colour (HUD clash survey, games/elite.md). The left cells keep D. No sprite
; when docked (0x7104 = 0: a page). Exit as the original: HL = 0x5A49, AF and flags kept.
h_light:
        push af
        ld hl,0x5A28
        ld (hl),d
        ld a,d
        or a
        jr z,.z
        ld a,7
.z:     inc hl
        ld (hl),a
        ld hl,0x5A49
        ld (hl),a
        dec hl
        ld (hl),d
        ld a,(0x7104)
        or a
        jr z,.off
        ld a,d
        or a
        jr z,.off
        nextreg 0x34,0
        nextreg 0x35,96                 ; x 64 + 32
        nextreg 0x36,168                ; y 136 + 32
        add a,a
        add a,a
        add a,a
        and 0xF0                        ; palette offset D / 2: pixel 1 -> sprite palette 0x11 / 0x21 / 0x31
        nextreg 0x37,a
        nextreg 0x38,0x80               ; visible, pattern 0
        nextreg 0x15,1                  ; sprites on, S L U
        jr .x
.off:   nextreg 0x15,0
.x:     ld hl,0x5A49
        pop af
        ret


        ASSERT $ <= 0x3AE7                  ; pattab (25 bytes) ends at shipcol
        ds 0x3AE7 - $, 0xFF
pattab:                                 ; 16 ones in 25, spread evenly
        db 1,0,1,1,0,1,0,1,1,0,1,1,0,1,0,1,1,0,1,1,0,1,0,1,0
        ASSERT $ - pattab == 25
        ASSERT $ == 0x3B00
; ship colour per blueprint (index = low byte of IY); other values white. RRRGGGBB, never TRANS. Blueprints are
; 23-byte records from 0x61E3 (0x61E3 + 23 n, n = 0-22; low bytes all distinct); IY = the record while a ship's lines
; are drawn. Model names not yet identified; the station seen in Docking is 0x63C6 (n = 21). Defaults from the colour
; sheet palette (nexclash/elite_colours.py PAL8); recolour / the build's colour map rewrite these bytes.
shipcol:
        ds 256, C_SHIPDEF
BP      MACRO lo, col
        ORG shipcol + lo
        db col
        ENDM
        BP 0xE3, 0x1F           ; n 0   cyan
        BP 0xFA, 0xF0           ; n 1   orange
        BP 0x11, 0xFC           ; n 2   yellow
        BP 0x28, 0x1C           ; n 3   green
        BP 0x3F, 0xA3           ; n 4   purple
        BP 0x56, 0x5F           ; n 5   sky blue
        BP 0x6D, 0xE7           ; n 6   magenta
        BP 0x84, 0x7C           ; n 7   lime
        BP 0x9B, 0xEF           ; n 8   pink
        BP 0xB2, 0x3B           ; n 9   teal
        BP 0xC9, 0xB6           ; n 10  grey
        BP 0xE0, 0x4B           ; n 11  blue
        BP 0xF7, 0xE0           ; n 12  red
        BP 0x0E, 0xFF           ; n 13  white
        BP 0x25, 0xF0           ; n 14  orange
        BP 0x3C, 0x1C           ; n 15  green
        BP 0x53, 0xFC           ; n 16  yellow
        BP 0x6A, 0x5F           ; n 17  sky blue
        BP 0x81, 0xA3           ; n 18  purple
        BP 0x98, 0x7C           ; n 19  lime
        BP 0xAF, 0xEF           ; n 20  pink
        BP 0xC6, 0xDB           ; n 21  pale blue  (station)
        BP 0xDD, 0x3B           ; n 22  teal
        ORG shipcol + 256

; waitpt (h_flip's tick wait, state page mapped, DI): the wait's interrupt point. A render holds DI for most of a
; frame and the INT pulse lasts 32 T at 3.5 MHz (~256 T at 28 MHz), so an interrupt rarely lands in the EI window
; (the verifier: 9 of 9 lost in a pass, bodies not run; CSpect holds INT until accepted). An owed game ISR body
; runs here as at an interrupt (CALL = its push; it ends EI / RET); else the window opens. Back to the wait.
waitpt: ld a,(S_OWE)
        or a
        jr z,.win
        ld a,(0xFEFE)
        cp 0xC9
        jr z,.win                       ; the hack's switch: no body (as h_isr)
        ld hl,S_OWE
        dec (hl)
        nextreg 0x50,0xFF
        call 0xFF25
        di
        nextreg 0x50,STATE_PG
        jp h_flip.w
.win:   nextreg 0x50,0xFF               ; not HALT: polls only at the interrupt's own line never see the raster
        ei                              ; go round, so the wait never ended (2026-11-23); poll at every line
        nop                             ; instead, letting the interrupt in between
        nop
        di
        nextreg 0x50,STATE_PG
        jp h_flip.w

; render_regs / render_back (state page mapped, RSTK): IX, IY and the alternate set kept across a render - the
; ship draw changes them, the original copy (0x7FBE) does not (the verifier: IY, AF'..HL' differed after a pass).
; Clobbers HL (render does anyway).
render_regs:
        ld (S_REGS),ix
        ld (S_REGS + 2),iy
        ex af,af'
        push af
        pop hl
        ld (S_REGS + 4),hl
        ex af,af'
        exx
        ld (S_REGS + 6),bc
        ld (S_REGS + 8),de
        ld (S_REGS + 10),hl
        exx
        ret
render_back:
        ld ix,(S_REGS)
        ld iy,(S_REGS + 2)
        ld hl,(S_REGS + 4)
        push hl
        ex af,af'
        pop af
        ex af,af'
        exx
        ld bc,(S_REGS + 6)
        ld de,(S_REGS + 8)
        ld hl,(S_REGS + 10)
        exx
        ret
; (moved here from the main block: alt ROM space, 2026-11-23)
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
; (moved here from the main block: alt ROM space, 2026-11-23)
; stsave: the star table as the last pass left it -> S_STP (stars_x extrapolates from it). Keeps all registers.
stsave: push af
        push bc
        push de
        push hl
        HLIB_IFF_DI                     ; P/V = IFF; h_isr unmaps the state page on its way out
        push af
        nextreg 0x50,STATE_PG
        ld hl,0x7A39
        ld de,S_STP
        ld bc,32
        ldir
        ld a,(0x7EDD)
        ld (S_HYP),a
        nextreg 0x50,0xFF
        pop af
        jp po,.n
        ei
.n:     pop hl
        pop de
        pop bc
        pop af
        ret
; (moved here from the main block: alt ROM space, 2026-11-23)
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
        ASSERT BASE_BK + 2 == L2_A && L2_A + 3 == L2_B && L2_B + 3 == BLANK_BK
        ld a,BASE_BK * 2
        ld e,22                         ; base, A, B, blank: 11 x 2 pages
.pg:    nextreg 0x57,a
        ld hl,s_dma
        ld bc,(s_dma_len << 8) | 0x6B
        otir
        inc a
        dec e
        jr nz,.pg
        nextreg 0x43,0x20               ; sprite palette 1: the light's colours (the ULA's red / green / yellow)
        ld hl,s_lpal
        ld b,3
.lp:    ld a,(hl)
        inc hl
        nextreg 0x40,a
        ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .lp
        nextreg 0x43,0
        xor a                           ; all 128 sprite records hidden (another program's may be left visible:
        ld bc,0x303B                    ; tools/probes/sprite_leftovers.py), then pattern 0 (8-bit): the light's
        out (c),a                       ; disc, pixel 1, else TRANS (0xE3)
        ld b,a
.hd:    out (0x57),a
        out (0x57),a
        djnz .hd
        ld bc,0x303B
        out (c),a
        ld hl,s_light
        ld e,32
.lb:    ld d,(hl)
        inc hl
        ld b,8
.lt:    sla d
        ld a,0xE3
        jr nc,.lo
        ld a,1
.lo:    out (0x5B),a
        djnz .lt
        dec e
        jr nz,.lb
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
s_lpal: db 0x11, 0xA0, 0x21, 0x14, 0x31, 0xB4
s_light:                                ; the light as the game draws it (Docking / Witch snapshots, r17-18 c08-09)
        db 0x00,0x00, 0x03,0xC0, 0x0F,0xF3, 0x1F,0xFC, 0x3F,0xFF, 0x3F,0xFF, 0x7F,0xFF, 0x7F,0xFF
        db 0x7F,0xFE, 0x7F,0xFE, 0x7F,0xFE, 0x3F,0xFC, 0x3F,0xFC, 0x1F,0xF8, 0x0F,0xF0, 0x03,0xC0
setup_end:
        SAVEBIN "elite_setup.bin", setup, setup_end - setup
