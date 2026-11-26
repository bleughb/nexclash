; Elite (Firebird 1985), the STANDARD 48K releases: engine 'elite_std' (nexclash/elite_std.py), games/elite_std.md.
; Assembled by tools/asm2profile.py elite_std into docs/profiles/elite_std.json.
;
; M2: the IM 2 fix. The game sets I = 0xFD (layout A: 0xD09E and 0xFF4C) over a table at 0xFD00-0xFE00 that is not
; uniform (vector 0xFEFE only for bus byte 0xFF; CSpect's bus byte is not 0xFF: games/elite.md M1). Both sites load
; 0x39 instead; the alt ROM image 1 (Sinclair's 48K ROM, the build's bytes in its free 0xFF area 0x386E-0x3CFF) holds
; a 257-byte table of 0x3A, so the vector is 0x3A3A for any bus byte, and 0x3A3A jumps to the game's handler 0xFEFE.
;
; M5: the title ship at 50 fps (games/elite_std.md "## Smooth title ship"). The title loop (clear, text, rotate +
; draw into the buffer, copy to the screen, keys) takes 8.5-11 frames a pass at 3.5 MHz: the ship turns in steps.
; Four same-length CALLs in each of the two title loops ("Load New Commander (Y/N)?", "Press Space, Commander";
; elite_std.py VERSIONS[v]['ttl']) come here:
;   h_top   (the clear's CALL)          28 MHz for the game's own pass; phase noted
;   h_bg    (the rotate + draw CALL)    the buffer as cleared + text kept (BUF_PG) for the renders
;   h_copy  (the copy's CALL)           the pass's time so far noted; HALT: the game's copy runs from a frame top
;   h_pre*  (the instruction after it)  the pass's length at 3.5 MHz estimated (L lines at 28 MHz * K); the
;                                       frames left until then get renders; 3.5 MHz again; the replaced instruction.
; The game's own pass is the original's (only faster); everything outside h_top..h_pre runs at 3.5 MHz as before.
; A render: buffer = the kept background (DMA), slot = this pass's ship moved on by w = j / D of the last pass's change
; (x, y, z and the 9 orientation components, extrapolated), the game's own draw, then after a HALT the game's own
; copy (4K at 28 MHz, inside the top border: no tearing). Afterwards the game's state is put back: the slot and the
; draw's work bytes (prm.rng) and the buffer, from STATE_PG. The renders run on a private stack in STATE_PG
; (mapped at slot 0, with 0xF3 0xAF at 0x0000: the draw reads 0x0000-0x0001 through its SP trick, as from the ROM).

        DEVICE ZXSPECTRUMNEXT

GAME_ISR  EQU 0xFEFE        ; the game's IM 2 handler (JR 0xFF25: the ISR body on its own stack 0xFFBF)
STATE_PG  EQU 26            ; 8K page (bank 13 lower, from the NEX): 0xF3 0xAF, variables, saves, private stack
BUF_PG    EQU 27            ; 8K page, mapped at slot 1 (0x2000) for a moment: the background (cleared + text) at
                            ; BG; at 0x3900-0x3A3C the alt ROM's IM 2 table and h_isr (elite_std.py): interrupts
                            ; work while it is there
BG        EQU 0x2000
SD_PG     EQU BUF_PG        ; also the SD save / load code, at its 0x1000 (slot 2: 0x5000; BG uses 0x0000-0x0FFF)
SLOT      EQU 0x6159        ; the title ship's slot (both layouts)
BPTR      EQU SLOT + 35     ; its blueprint pointer
FLINES    EQU 312           ; lines per 50 Hz frame
NREG      EQU 0x243B

; STATE_PG (at slot 0)
V_RINT  EQU 0x0002          ; raster line just after an interrupt (phase 0)
V_P0    EQU 0x0004          ; phase at h_top
V_P1A   EQU 0x0006          ; phase at h_bg (before keeping the background)
V_P1B   EQU 0x0008          ; phase after it
V_L     EQU 0x000A          ; lines of the game's pass at 28 MHz
V_ACC   EQU 0x000C          ; carried part of a frame (lines at 3.5 MHz; layouts without the loop's HALT)
V_WR    EQU 0x000E          ; frame tops passed inside the game's pass
V_D     EQU 0x000F          ; frames the pass takes at 3.5 MHz
V_RB    EQU 0x0010          ; frames for renders
V_F     EQU 0x0011          ; frames used by renders
V_W     EQU 0x0012          ; this render's weight (j * 256 / D)
V_VALID EQU 0x0013          ; 1: last pass and this one show the same ship: extrapolate
V_P2    EQU 0x0014          ; phase at a render's start
V_TP    EQU 0x0016          ; 3 bytes: prev value (extr1)
V_TC    EQU 0x0019          ; 3 bytes: cur value
V_K     EQU 0x001C          ; kind (extr1)
V_LOGI  EQU 0x001D          ; log index
V_SP    EQU 0x001E          ; the game's SP in pre
V_HALT  EQU 0x0060          ; 1: this title loop HALTs once a pass (h_prej)
S_PREV  EQU 0x0090          ; 29 bytes: slot 0..26 + blueprint, last pass
S_CUR   EQU 0x00B0          ; 29 bytes: this pass
SAVE    EQU 0x0800          ; the ranges (first: the slot, 0x28 bytes; 0x400 at most)
GBUF    EQU 0x0C00          ; the game's own buffer (4K)
PSTACK  EQU 0x1E00          ; (down to 0x1C00)
;          ; private stack top (pre and the renders)
V_LOG   EQU 0x1F00          ; 64 x (L lo, L hi, D, frame tops in the pass)

        ORG 0x3900
rom_start:
im2tab: ds 257, 0x3A        ; I = 0x39: vector 0x3A3A for any bus byte
        ds 0x3A3A - $, 0xFF
        ASSERT $ == 0x3A3A
h_isr:  jp GAME_ISR

; ---------------------------------------------------------------------------------------------- title hooks
; Entries in the alt ROM; the work in STATE_PG (p_*), which they map at slot 0 (the ROM's 0x0000-0x1FFF is not
; used while it is mapped: the IM 2 table and h_isr are at 0x3900-0x3A3C, slot 1).

h_top:  push hl
        push af
        push bc
        push de
        nextreg 0x50,STATE_PG
        jp p_top
h_bg:   push hl
        push af
        push bc
        push de
        nextreg 0x50,STATE_PG
        jp p_bg
h_copy: push hl
        push af
        push bc
        push de
        nextreg 0x50,STATE_PG
        jp p_copy
tail:   nextreg 0x50,0xFF               ; on to HL with the game's registers
        pop de
        pop bc
        pop af
        ex (sp),hl
        ret

h_prej: call pre1                       ; "Press Space, Commander" (layout A 0x73CF, B 0x71F1): the loop HALTs
        ld bc,0xFF1F
        ret
h_prea: call pre                        ; "Load New Commander (Y/N)?" layout A 0x7384
        ld a,(0xFC0D)
        ret
h_pree: call pre                        ; the same, layout B 0x71AE
        ld a,(0xFC13)
        ret
pre1:   nextreg 0x50,STATE_PG
        push af
        ld a,1
        jr pre_c
pre:    nextreg 0x50,STATE_PG
        push af
        xor a
pre_c:  ld (V_HALT),a
        pop af
        jp p_pre
pre_x:  nextreg 0x50,0xFF
        nextreg 0x07,0                  ; 3.5 MHz
        ret

; ---------------------------------------------------------------------------------------------- SD save / load
; The ACCESS MENU's tape CALLs (LD-BYTES 0x0562 / SA-BYTES 0x04C6; elite_std.py VERSIONS[v]['sd']) come here, with
; the game's IX = commander block, DE = its length. B = 1 load / 0 save, C = the extension's last letter, HL (load)
; = the typed name. The work runs from SD_PG mapped at slot 2 (0x4000: the ULA reads bank 5 itself, the screen
; stays; neither the game's stack nor its block nor the name buffer is there). Carry out = done, as the ROM's.
h_lda:  ld hl,0xDED0                    ; layout A: the name typed for a load
        ld c,'A'
        jr sd_ld
h_ldb:  ld hl,0xAC25                    ; layout B
        ld c,'B'
sd_ld:  ld b,1
        jr sd_go
h_sva:  ld c,'A'
        jr sd_sv
h_svb:  ld c,'B'
sd_sv:  ld b,0
sd_go:  di
        push bc
        ld bc,NREG
        ld a,0x52
        out (c),a
        inc b
        in a,(c)                        ; A = the game's slot 2 page
        pop bc
        nextreg 0x52,SD_PG
        jp sd_main
sd_back:
        nextreg 0x52,a                  ; flags kept: carry is the result
        ret
rom_end:
        ASSERT rom_end <= 0x3CEC
        SAVEBIN "elitestd_rom.bin", rom_start, rom_end - rom_start

; ---------------------------------------------------------------------------------------------- STATE_PG
; Assembled at 0x0000 (its place at slot 0); the NEX's bank 13 lower page (elite_std.py, with prm filled in).

        ORG 0x0000
page_start:
        db 0xF3, 0xAF               ; what the draw's POP AF at SP = 0x0000 reads (the ROM's first two bytes)
        ds 0x0062 - $, 0

; per-version parameters, written by elite_std.py (VERSIONS[v]['ttl'])
prm:
.draw:  dw 0                ; the ship draw (IX = slot, IY = blueprint)
.copy:  dw 0                ; buffer -> screen
.clear: dw 0                ; h_top's routine
.rot:   dw 0                ; h_bg's routine (rotate + draw)
.kf:    db 0                ; K = 8 + kf / 256: lines at 3.5 MHz per line at 28 MHz
.rng:   ds 4 * 8 + 2, 0     ; (address, length) ..., 0: the slot first (0x28 bytes)
prm_end:
        ds 0x0100 - $, 0

p_top:
        nextreg 0x07,3                  ; 28 MHz: the game's pass
        call phase
        ld (V_P0),hl
        ld hl,(prm.clear)
        jp tail

p_bg:
        call phase
        ld (V_P1A),hl
        nextreg 0x51,BUF_PG
        ld hl,0xC000                    ; the buffer as cleared, with the text (LDIR: the phase is not known here)
        ld de,BG
        ld bc,0x1000
        ldir
        nextreg 0x51,0xFF
        call phase
        ld (V_P1B),hl
        ld hl,(prm.rot)
        jp tail

p_copy:
        xor a
        ld (V_WR),a
        call phase                      ; L = (P1A - P0) + (P2 - P1B), each mod a frame; frame tops counted
        ld de,(V_P1B)
        call segm
        push hl
        ld hl,(V_P1A)
        ld de,(V_P0)
        call segm
        pop de
        add hl,de
        ld (V_L),hl
        ld hl,(V_P1B)
        ld de,(V_P1A)
        call segm
        ei
        halt                            ; the game's copy from a frame top
        call rline
        ld (V_RINT),hl
        ld hl,(prm.copy)
        jp tail

p_pre:
        ld (V_SP),sp
        ld sp,PSTACK
        push af
        push bc
        push de
        push hl
        push ix
        push iy
        ex af,af'
        push af
        exx
        push bc
        push de
        push hl
        call phase                      ; the copy's lines from the frame top
        ld de,(V_L)
        add hl,de
        ld (V_L),hl                     ; L
        ld a,(prm.kf)                   ; W = L * 8 + L * KF / 256: the pass's lines at 3.5 MHz
        ld d,l
        ld e,a
        mul d,e
        ld c,d
        ld d,h
        ld e,a
        mul d,e
        ld a,e
        add a,c
        ld e,a
        jr nc,.n
        inc d
.n:     add hl,hl
        add hl,hl
        add hl,hl
        add hl,de
        ld a,(V_HALT)
        or a
        jr z,.acc
        call div312                     ; the loop's HALT ends a pass on a frame top
        inc a
        jr .d
.acc:   ld de,(V_ACC)
        add hl,de
        call div312
        ld (V_ACC),hl
.d:     ld (V_D),a
        ld b,a
        ld a,(V_HALT)
        ld hl,V_WR
        add a,(hl)
        inc a                           ; the pass's frame tops that are not renders' (h_copy's HALT, the game's
        ld c,a                          ; pass, the loop's HALT)
        ld a,b
        sub c
        jr nc,.rb
        xor a
.rb:    ld (V_RB),a
        ld a,(V_LOGI)                   ; log: L, D, frame tops
        ld l,a
        ld h,high V_LOG
        ld de,(V_L)
        ld (hl),e
        inc l
        ld (hl),d
        inc l
        ld a,(V_D)
        ld (hl),a
        inc l
        ld a,(V_WR)
        ld (hl),a
        inc l
        ld a,l
        ld (V_LOGI),a
        ld hl,S_CUR                     ; prev = cur; cur = the slot now
        ld de,S_PREV
        ld bc,29
        ldir
        ld hl,SLOT
        ld de,S_CUR
        ld bc,27
        ldir
        ld hl,(BPTR)
        ld (S_CUR + 27),hl
        ld de,(S_PREV + 27)
        or a
        sbc hl,de
        ld a,1
        jr z,.v
        xor a
.v:     ld (V_VALID),a
        ld a,(V_RB)
        or a
        jr z,.out
        ld de,SAVE                      ; NC: save the ranges, then the game's buffer
        call ranges
        ld hl,0xC000
        ld de,GBUF
        ld bc,0x1000
        call dma
        xor a
        ld (V_F),a
.lp:    ld a,(V_RB)
        ld b,a
        ld a,(V_F)
        cp b
        jr nc,.end
        inc a
        call weight
        call render
        jr .lp
.end:   ld de,SAVE                      ; the game's state back
        scf
        call ranges
        ld hl,GBUF
        ld de,0xC000
        ld bc,0x1000
        call dma
.out:   pop hl
        pop de
        pop bc
        exx
        pop af
        ex af,af'
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        jp pre_x

; ranges: DE = save area; NC: game -> save, C: save -> game
; ranges: DE = save area; NC: game -> save, C: save -> game
ranges: ld ix,prm.rng
        push af
.r:     ld l,(ix+0)
        ld h,(ix+1)
        ld a,h
        or l
        jr z,.e
        ld c,(ix+2)
        ld b,(ix+3)
        pop af
        push af
        jr nc,.s
        ex de,hl
        ldir
        ex de,hl
        jr .x
.s:     ldir
.x:     ld bc,4
        add ix,bc
        jr .r
.e:     pop af
        ret

; render: one frame of the ship at weight V_W; HALT; the copy. V_F counts the frame tops used.
render: call phase
        ld (V_P2),hl
        nextreg 0x51,BUF_PG
        ld hl,BG                        ; buffer = background (just after a copy: no interrupt near, DMA safe)
        ld de,0xC000
        ld bc,0x1000
        call dma
        nextreg 0x51,0xFF
        ld hl,SAVE                      ; slot = this pass's (the draw changes a few of its bytes)
        ld de,SLOT
        ld bc,0x28
        ldir
        ld a,(V_VALID)
        or a
        call nz,extrap
        ld hl,(prm.draw)
        call game
        call phase
        ld de,(V_P2)
        or a
        sbc hl,de
        jr nc,.nw
        ld hl,V_F                       ; the draw ran past a frame top
        inc (hl)
.nw:    ei
        halt
        call rline
        ld (V_RINT),hl
        ld hl,V_F
        inc (hl)
        ld hl,(prm.copy)
game:   ld ix,SLOT                      ; HL = the game's routine: IX = slot, IY = blueprint
        ld iy,(BPTR)
        jp (hl)

; weight: A = j -> V_W = j * 256 / D (255 at most)
weight: ld h,a
        ld l,0
        ld a,(V_D)
        ld e,a
        ld d,0
        ld b,d
        or a
        jr z,.st
.dv:    or a
        sbc hl,de
        jr c,.st
        inc b
        jr nz,.dv
        dec b
.st:    ld a,b
        ld (V_W),a
        ret

; extrap: the slot's 12 values = cur + (cur - prev) * V_W / 256; a jump in any (a new ship, a new title) leaves the
; slot as the pass's
extrap: ld hl,S_PREV
        ld de,SLOT
        ld b,12
.f:     push bc
        ld a,b
        sub 10                          ; b = 12, 11, 10: x, y, z (kind 1)
        ld a,0
        adc a,a
        xor 1
        ld c,a
        call extr1
        jr c,.undo
        inc hl
        inc hl
        inc de
        inc de
        bit 0,c
        jr z,.k0
        inc hl
        inc de
.k0:    pop bc
        djnz .f
        ret
.undo:  pop bc
        ld hl,SAVE
        ld de,SLOT
        ld bc,27
        ldir
        ret

; extr1: HL = prev field, DE = slot field (cur, becomes cur + delta * V_W / 256), C = kind (1: position lo, hi,
; sign | bits 16-22; 0: component fraction, sign | magnitude). Keeps HL, DE, C. Carry: |delta| >= 0x2000 (a jump).
extr1:  push hl
        push de
        ld a,c
        ld (V_K),a
        call dec_v                      ; C:D:E = prev
        ld (V_TP),de
        ld a,c
        ld (V_TP + 2),a
        pop hl
        push hl
        ld a,(V_K)
        call dec_v                      ; C:D:E = cur
        ld (V_TC),de
        ld a,c
        ld (V_TC + 2),a
        ld hl,(V_TP)
        ex de,hl
        or a
        sbc hl,de
        ex de,hl                        ; DE = low 16 of cur - prev
        ld a,(V_TP + 2)
        ld b,a
        ld a,c
        sbc a,b
        ld c,a                          ; C:D:E = delta
        ld a,d
        rla
        ld a,0
        sbc a,0
        cp c
        jr nz,.jump                     ; not 16 bits
        ld a,d
        bit 7,c
        jr z,.ap
        cpl
.ap:    and 0xE0
        jr nz,.jump                     ; |delta| >= 0x2000
        bit 7,c
        jr z,.pos
        xor a
        sub e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a                          ; DE = |delta|
.pos:   ld a,(V_W)
        ld b,d
        ld d,a
        mul d,e                         ; lo * w
        ld l,d
        ld d,b
        ld e,a
        mul d,e                         ; hi * w
        ld a,e
        add a,l
        ld e,a
        jr nc,.nc
        inc d                           ; DE = |delta| * w / 256
.nc:    bit 7,c
        ld c,0
        jr z,.sum
        xor a
        sub e
        ld e,a
        ld a,0
        sbc a,d
        ld d,a
        ld a,0
        sbc a,0
        ld c,a                          ; C:D:E = -DE
.sum:   ld hl,(V_TC)
        add hl,de
        ex de,hl
        ld a,(V_TC + 2)
        adc a,c
        ld c,a                          ; C:D:E = cur + delta * w / 256
        pop hl
        push hl
        ld a,(V_K)
        call enc_v
        pop de
        pop hl
        ld a,(V_K)
        ld c,a
        or a
        ret
.jump:  pop de
        pop hl
        ld a,(V_K)
        ld c,a
        scf
        ret

; dec_v: HL = field, A = kind -> C:D:E two's complement. Clobbers A, HL. (asm/elite_render.inc)
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

; enc_v: C:D:E -> field at HL, A = kind. Clobbers A, B, C, D, E, HL. (asm/elite_render.inc)
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

; segm: HL = later phase, DE = earlier -> HL = lines between (mod a frame); a frame top between counts in V_WR
segm:   or a
        sbc hl,de
        ret nc
        ld de,FLINES
        add hl,de
        ld a,(V_WR)
        inc a
        ld (V_WR),a
        ret

; div312: HL -> A = HL / 312, HL = remainder
div312: ld de,FLINES
        xor a
.d:     or a
        sbc hl,de
        jr c,.e
        inc a
        jr .d
.e:     add hl,de
        ret

; rline: HL = raster line (NR 0x1E / 0x1F). Clobbers A, BC.
rline:  ld bc,NREG
.r:     ld a,0x1E
        out (c),a
        inc b
        in a,(c)
        dec b
        and 1
        ld h,a
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
        and 1
        cp h
        jr nz,.r
        ret

; phase: HL = lines since the last frame top (V_RINT). Clobbers A, BC, DE.
phase:  call rline
        ld de,(V_RINT)
        or a
        sbc hl,de
        ret nc
        ld de,FLINES
        add hl,de
        ret

; dma (in the table's gap): HL = source, DE = destination, BC = length, memory to memory, both incrementing
dma:    ld a,0x83
        out (0x6B),a            ; disable
        ld a,0x7D
        out (0x6B),a            ; WR0: A -> B, port A address and length follow
        ld a,l
        out (0x6B),a
        ld a,h
        out (0x6B),a
        ld a,c
        out (0x6B),a
        ld a,b
        out (0x6B),a
        ld a,0x14
        out (0x6B),a            ; WR1: port A memory, incrementing
        ld a,0x10
        out (0x6B),a            ; WR2: port B memory, incrementing
        ld a,0xAD
        out (0x6B),a            ; WR4: continuous, port B address follows
        ld a,e
        out (0x6B),a
        ld a,d
        out (0x6B),a
        ld a,0x82
        out (0x6B),a            ; WR5
        ld a,0xCF
        out (0x6B),a            ; load
        ld a,0x87
        out (0x6B),a            ; enable: runs now, the CPU waits
        ret
page_end:
        ASSERT page_end <= SAVE
        SAVEBIN "elitestd_page.bin", page_start, page_end - page_start

; ---------------------------------------------------------------------------------------------- SD_PG at slot 2
; Commander files on the SD card (esxDOS RST 8, the current drive and folder: the game's): one file per name, the
; first 8 characters + ".ELA" (layout A) / ".ELB" (layout B), the tape block as it was (A 0x66, B 0x68 bytes, the name
; first). Every save also writes "_LAST.ELx" ("_" is not a name character), which an empty name loads. A load with a
; name returns carry only when the file's name is the one typed (the game's own test after LD-BYTES), so a file of
; another name of the same first 8 characters is a load error, never a loop. While esxDOS runs, interrupts go
; to an EI / RETI in this page (I = SD_I: DivMMC overlays 0x0000-0x3FFF, the alt ROM's table and h_isr); DivMMC
; automap (NextReg 0x0A bit 4, off since the build's start) is on only for the call. elite_std.py puts the table
; (257 x 0x5D at 0x5B00) and the handler (0x5D5D) in the page.
SD_I     EQU 0x5B
SD_VEC   EQU 0x5D5D
V_MMU2   EQU 0x5E00             ; the game's slot 2 page
V_GSP    EQU 0x5E01             ; the game's SP
V_I      EQU 0x5E03
V_0A     EQU 0x5E04             ; NextReg 0x0A as it was
V_LEN    EQU 0x5E05             ; the block's length (DE)
V_IX     EQU 0x5E07             ; the block (IX)
V_NAME   EQU 0x5E09             ; the typed name (load)
V_LOAD   EQU 0x5E0B
V_HDL    EQU 0x5E0C
FNAME    EQU 0x5E20             ; 8 + 4 + 1
SD_BUF   EQU 0x5E40             ; a file read (0x80 at most)
SD_SP    EQU 0x6000             ; stack 0x5F00-0x5FFF

        ORG 0x5000
sd_start:
sd_main:
        ld (V_MMU2),a
        ld (V_GSP),sp
        ld sp,SD_SP
        ld (V_LEN),de
        ld (V_IX),ix
        ld (V_NAME),hl
        ld a,b
        ld (V_LOAD),a
        ld a,c
        ld (sd_ext+3),a
        ld a,i
        ld (V_I),a
        ld a,SD_I
        ld i,a
        ld bc,NREG
        ld a,0x0A
        out (c),a
        inc b
        in a,(c)
        ld (V_0A),a
        or 0x10                         ; DivMMC automap (cores from 3.01.10; older ones keep it on in NextReg 0x06)
        nextreg 0x0A,a
        ld a,(V_LOAD)
        or a
        jr nz,.ld
        call sd_save
        jr .out
.ld:    call sd_load
.out:   push af
        ld a,(V_0A)
        nextreg 0x0A,a
        ld a,(V_I)
        ld i,a
        pop af
        ld sp,(V_GSP)
        ld a,(V_MMU2)
        jp sd_back

sd_save:                                ; -> carry: saved
        ld hl,(V_IX)
        call mkname
        jr z,.last                      ; no name: only _LAST
        call sd_write
        ret nc
        call .last
        scf                             ; the commander's own file is what counts
        ret
.last:  ld hl,s_last
        call mkname
        jr sd_write

sd_load:                                ; -> carry: loaded (the block written only then)
        ld hl,(V_NAME)
        call mkname
        jr nz,.open
        ld hl,s_last
        call mkname
.open:  ld ix,FNAME
        ld b,0x01                       ; FA_READ
        call sd_open
        ret nc                          ; no such file
        ld ix,SD_BUF
        ld e,0x9D                       ; F_READ
        call sd_rw
        ret nc
        ld hl,(V_NAME)
        ld a,(hl)
        or a
        jr z,.ok                        ; no name typed: the game takes any (D966 / D340)
        ld de,SD_BUF
        ld b,11                         ; the game's test: equal up to the 0, all 11 equal is a mismatch
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.bad
        or (hl)
        jr z,.ok
        inc hl
        inc de
        djnz .cmp
.bad:   or a
        ret
.ok:    ld hl,SD_BUF
        ld de,(V_IX)
        ld bc,(V_LEN)
        ldir
        scf
        ret

sd_write:                               ; FNAME <- the block -> carry: written and closed
        ld b,0x0E                       ; FA_WRITE + FA_CREATE_AL (created or truncated)
        call sd_open
        ret nc
        ld ix,(V_IX)
        ld e,0x9E                       ; F_WRITE
sd_rw:                                  ; E = F_READ / F_WRITE of V_LEN bytes at IX, then close -> carry: all done
        ld bc,(V_LEN)
        call esx
        jr c,.err
        ld hl,(V_LEN)
        or a
        sbc hl,bc
        jr nz,.err
        ld a,(V_HDL)
        ld e,0x9B                       ; F_CLOSE
        call esx
        ccf
        ret
.err:   ld a,(V_HDL)
        ld e,0x9B
        call esx
        or a
        ret

sd_open:                                ; FNAME, B = mode -> carry: open (V_HDL)
        ld ix,FNAME
        ld a,'*'                        ; the current drive
        ld e,0x9A                       ; F_OPEN
        call esx
        ccf
        ret nc
        ld (V_HDL),a
        ret

mkname:                                 ; HL = a name -> FNAME = its first 8 characters (to the first below 0x21) +
        ld de,FNAME                     ; ".ELx", 0 -> NZ; Z: no name (FNAME left)
        ld b,8
.c:     ld a,(hl)
        cp 0x21
        jr c,.e
        cp 0x7F
        jr nc,.e
        ld (de),a
        inc hl
        inc de
        djnz .c
.e:     ld a,b
        cp 8
        ret z
        ld hl,sd_ext
        ld bc,5
        ldir                            ; Z kept (NZ)
        ret

esx:                                    ; RST 8 function E with A, B / BC, IX (HL = IX too) -> A, BC, carry = error.
        push iy                         ; Keeps IY and the alternate set; interrupts off after it
        exx
        push bc
        push de
        push hl
        exx
        ex af,af'
        push af
        ex af,af'
        push af
        ld a,e
        ld (.fn),a
        pop af
        push ix
        pop hl
        rst 8
.fn:    db 0
        di
        ex af,af'
        pop af
        ex af,af'
        exx
        pop hl
        pop de
        pop bc
        exx
        pop iy
        ret

s_last: db "_LAST",0
sd_ext: db ".ELA",0
sd_end:
        ASSERT sd_end <= 0x5900         ; 0x5900-0x5A3C: the alt ROM table's copy (BUF_PG at slot 1)
        SAVEBIN "elitestd_sd.bin", sd_start, sd_end - sd_start
