; Target Renegade (Imagine 1988, 128K) - every figure of the masked plotter becomes 4-bit hardware
; sprites; scenery, HUD and text stay on the ULA. Facts: games/target_renegade.md.
;
; The game composes each game frame in a back buffer (0xC000-0xCFFF, bank 0 = screen rows 1-16):
; 59531 draws every figure (plotters 55276 / 55722, masked, undo stack), 62565 copies the buffer to
; the screen, 56332 restores the buffer. Interrupts are OFF at every hook site (checked over the RZX).
;
; Method - the game's own code runs unchanged, only its output is redirected:
;   plot entries   log the part (HL = part record, D = y, E = x, kind) into page H; the plot itself
;                  runs as the original (the buffer and the undo stack are the original's).
;   59531 entry    the buffer is plain scenery here (restored at the end of the last game frame):
;                  copied to screen rows 1-16 (28 MHz) - the ULA never shows a figure.
;   55267 CALL     the commit: sprites built from the log (pattern cache), attributes uploaded; then
;                  the game's copy runs with MMU slot 2 = page Q, so its 4K of screen writes (the
;                  figures) land in a page nobody shows; 62751 (its LD SP,(63222) / RET) maps the
;                  screen back. Registers, memory and the copy's timing (beeper) are the original's.
;   62821 entry    screen clear (level start, menus): every sprite hidden, the cache emptied.
; Hook code: alt ROM images 0 AND 1 (the game runs with ROM 0 selected; 0x10-0x14 while loading),
; 0x2000-0x34FF only: 0x3500-0x3508 of ROM 0 is read by the game (sound data), nothing at 0x3D00-.
;
; Patch sites (original bytes verified by renegade.py):
;   55276 E5 D5 2B  PUSH HL / PUSH DE / DEC HL  -> JP e_pn   plotter (as stored)
;   55722 E5 D5 2B  PUSH HL / PUSH DE / DEC HL  -> JP e_pm   plotter (mirrored)
;   59531 21 40 FF  LD HL,65344                 -> JP e_dr   draw all: scenery -> screen, log reset
;   62565 2A F7 F4  LD HL,(62711)               -> JP e_cm   copy (every caller): commit, then the
;                                                            copy into page Q
;   62751 ED 7B F6  LD SP,(63222) (+F6)         -> JP e_cx   copy exit: screen page back
;   62821 21 FF 5A  LD HL,23295                 -> JP e_clr  screen clear: hide all
;   58200 3E 38 08  LD A,56 / EX AF,AF'         -> JP e_rd   scenery redraw (buffer rewritten): log reset
;   56332 21 00 00  LD HL,0                     -> JP e_rs   buffer restore: log reset
;   62771 E5 D5 C5  PUSH HL / PUSH DE / PUSH BC -> JP e_tx   character print: scenery copy due
; The log = the figures in the buffer now (since 59531, unless a redraw or restore came after):
; a copy with an empty log copies the buffer itself to the screen (scroll transitions 57752).
; Interrupts: off at every site in the RZX; the hooks never touch slots 4/5 (IM 2 vector 0x9FFF,
; handler 0xBFBF) and keep SP on a stack with room (the game stack is in slot 5), so an interrupt
; inside a hook is harmless.

        DEVICE ZXSPECTRUMNEXT

HPG     EQU 26                  ; hook page, MMU slot 2 while a hook runs
QPG     EQU 27                  ; dummy page: slot 2 during the game's copy
SPG     EQU 10                  ; the screen page (bank 5 low) = the game's slot 2
SPG3    EQU 11                  ; the game's page at slot 3 (bank 5 high)
GPG7    EQU 1                   ; the game's page at slot 7 (bank 0 high; 7FFD = 0 at the commit)
STORE   EQU 28                  ; colour store: pages 28-39 (8-byte entries for 0x6000-0xBFFF)
INK     EQU 8                   ; default colours (Dean 2026-10-14: all characters grey = 7)
BODY    EQU 7
MAXLOG  EQU 64
NCE     EQU 48                  ; cache entries
MAXSPR  EQU 128

; ---- page H at 0x4000 ----
V_N     EQU 0x4000              ; parts logged since 59531
V_PREV  EQU 0x4001              ; sprites shown by the last commit
V_NS    EQU 0x4002              ; sprites in SPRTAB
V_COL   EQU 0x4003              ; 1 = the colour store has entries (Python / recolour)
V_SP    EQU 0x4004
V_RR    EQU 0x4006              ; cache round robin
V_NFREE EQU 0x4007              ; free patterns on the FREE stack
V_DROP  EQU 0x4008              ; parts dropped (cache full; diagnostic, never in the RZX)
V_GFX   EQU 0x400A
V_W     EQU 0x400C
V_R     EQU 0x400D
V_X     EQU 0x400E              ; byte column (signed)
V_Y     EQU 0x400F              ; buffer line 0-127
V_MIR   EQU 0x4010
V_E     EQU 0x4011              ; current cache entry (2)
V_TX    EQU 0x4013
V_TY    EQU 0x4014
V_ROW   EQU 0x4015
V_TW    EQU 0x4016
V_TH    EQU 0x4017
V_NT    EQU 0x4018
V_P     EQU 0x4019              ; pattern being built
V_OR    EQU 0x401A              ; OR of the pattern's bytes (0 = empty tile)
V_K     EQU 0x401B
V_M     EQU 0x401C              ; drawn mask / graphic byte
V_G     EQU 0x401D
V_CE    EQU 0x401E              ; colour entry valid for this byte
V_NIB   EQU 0x4020              ; 8 colour nibbles (one byte each) + transparent mask
V_TM    EQU 0x4028
V_PIX   EQU 0x4029              ; pixel pair accumulator
V_SX    EQU 0x402A              ; sprite X (16 bits, signed screen pixels)
V_SY    EQU 0x402C
V_LP    EQU 0x402E              ; log pointer (2)
V_LI    EQU 0x4030              ; log index
V_EI    EQU 0x4031              ; entry index loop counter
V_DIRTY EQU 0x4032              ; (2) non-zero = the screen's play area needs the scenery again
V_RP    EQU 0x4034              ; (2) graphic data of the current line (tile build)
V_KEY   EQU 0x4040              ; 9-byte key of the current part
LOG     EQU 0x4100              ; MAXLOG x 5: L, H, E, D, kind
CE      EQU 0x4300              ; NCE x 32: +0 flags (7 valid, 0 used, 1 shown), +1 key (9), +10 n,
                                ; +11 patterns (16; 0xFF = empty tile)
FREE    EQU 0x4900              ; free pattern stack (128)
SPRTAB  EQU 0x4A00              ; 128 x 5
HSTK    EQU 0x5F00

NIB0    EQU 0x2000              ; default pixel pairs: index = graphic nibble << 4 | mask nibble
NIB1    EQU 0x2100

; 0x2000-0x21FF: NIB0 / NIB1, written by renegade.py (default pixel pairs)
        ORG 0x2200

; ---- plot entries: the displaced PUSH HL / PUSH DE, log, DEC HL, back into the plotter ----
        MACRO PLOTLOG kind, back
        push hl
        push de
        nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push hl
        ld a,(V_N)
        cp MAXLOG
        jr nc,.full
        ld c,a
        inc a
        ld (V_N),a
        ld b,0
        ld h,b
        ld l,c
        add hl,hl
        add hl,hl
        add hl,bc                   ; 5 * index
        ld bc,LOG
        add hl,bc
        pop bc                      ; the plotter's HL
        push bc
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),kind
        jr .done
.full:  ld hl,V_DROP
        inc (hl)
.done:  pop hl
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x52,SPG
        dec hl
        jp back
        ENDM

e_pn:   PLOTLOG 0, 55279
e_pm:   PLOTLOG 1, 55725

; ---- 59531 draw all: log reset, scenery (the plain buffer) -> screen rows 1-16 ----
e_dr:   nextreg 0x07,3
        nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        xor a
        ld (V_N),a
        ld hl,(V_DIRTY)             ; scenery changed (redraw, screen clear, text) since the last copy?
        ld a,h
        or l
        call nz,scen
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x52,SPG
        nextreg 0x07,0
        ld hl,65344
        jp 59534

; scen: the buffer (lines 0-127, table 0xD000) -> screen lines 8-135; the screen page is viewed at
; slot 3 (0x6000 = 0x4000) meanwhile, so the hook stack in H (slot 2) stays usable
scen:   ld hl,0
        ld (V_DIRTY),hl
        nextreg 0x53,SPG
        ld hl,0xD000
        ld de,0x6020                ; screen line 8 in the slot-3 view
.ln:    ld c,(hl)
        inc l
        ld b,(hl)
        inc l
        push hl
        push de
        ld h,b
        ld l,c
        ld bc,32
        ldir
        pop de
        pop hl
        call scrdown
        ld a,l
        or a
        jr nz,.ln                   ; 128 lines = the table's 256 bytes
        nextreg 0x53,SPG3
        ret

; DE = screen address of a pixel line (column 0) -> the next line
scrdown:inc d
        ld a,d
        and 7
        ret nz
        ld a,e
        add a,32
        ld e,a
        ret c
        ld a,d
        sub 8
        ld d,a
        ret

; ---- 62565 copy entry (every caller): commit, then the game's copy into page Q ----
e_cm:   nextreg 0x07,3
        nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld a,(V_N)                  ; no figure in the buffer: the buffer is the scenery
        or a
        call z,scen
        call commit
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x07,0
        nextreg 0x52,QPG
        ld hl,(62711)
        jp 62568

; ---- 62751: the copy's exit ----
e_cx:   nextreg 0x52,SPG
        ld sp,(63222)
        ret

; ---- 58200 scenery redraw / 56332 restore: the buffer holds no figure afterwards ----
e_rd:   nextreg 0x52,HPG
        ld a,0
        ld (V_N),a
        ld a,56
        ld (V_DIRTY),a              ; the buffer's scenery is redrawn
        nextreg 0x52,SPG
        ex af,af'
        jp 58203

; ---- 62771 character print (text, also into the play area): the next 59531 copies the scenery ----
e_tx:   push hl
        push de
        push bc
        nextreg 0x52,HPG
        ld (V_DIRTY),sp             ; SP is never 0
        nextreg 0x52,SPG
        jp 62774

e_rs:   nextreg 0x52,HPG
        ld hl,V_N
        ld (hl),0
        ld hl,0
        nextreg 0x52,SPG
        jp 56335

; ---- 62821 screen clear: hide every sprite, empty the cache ----
e_clr:  nextreg 0x07,3
        nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call hideall
        ld (V_DIRTY),sp
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x52,SPG
        nextreg 0x07,0
        ld hl,23295
        jp 62824

; =====================================================================================
; commit: every logged part -> sprites (SPRTAB), then the attribute upload; cache flags aged
commit: xor a
        ld (V_NS),a
        ld (V_LI),a
        ld hl,LOG
        ld (V_LP),hl
.part:  ld a,(V_LI)
        ld hl,V_N
        cp (hl)
        jr nc,.upl
        inc a
        ld (V_LI),a
        call part
        ld hl,(V_LP)
        ld de,5
        add hl,de
        ld (V_LP),hl
        jr .part
.upl:   ld a,(V_NS)
        ld d,a
        ld e,0
        ld hl,SPRTAB
.c:     ld a,e
        cp d
        jr nc,.hide
        nextreg 0x34,a
        ld a,(hl)
        inc hl
        nextreg 0x35,a
        ld a,(hl)
        inc hl
        nextreg 0x36,a
        ld a,(hl)
        inc hl
        nextreg 0x37,a
        ld a,(hl)
        inc hl
        nextreg 0x38,a
        ld a,(hl)
        inc hl
        nextreg 0x39,a
        inc e
        jr .c
.hide:  ld a,(V_PREV)
        ld h,a
.h:     ld a,e
        cp h
        jr nc,.age
        nextreg 0x34,a
        nextreg 0x38,0
        inc e
        jr .h
.age:   ld a,d
        ld (V_PREV),a
        ld hl,CE
        ld de,32
        ld b,NCE
.f:     ld a,(hl)
        and 0x81                    ; valid + used -> valid + shown
        bit 0,a
        jr z,.f1
        xor 3
.f1:    ld (hl),a
        add hl,de
        djnz .f
        ret

; part: the log entry at V_LP -> parameters, cache entry (built on a miss), sprites
part:   ld hl,(V_LP)
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = part record (graphic word)
        inc hl
        ld c,(hl)                   ; C = E (x)
        inc hl
        ld b,(hl)                   ; B = D (y)
        inc hl
        ld a,(hl)
        ld (V_MIR),a
        ex de,hl                    ; HL = record
        push hl                     ; guard: the record and its offsets at 0x6000 or above (slot 2 is
        ld de,0x6002                ; page H while the commit runs)
        or a
        sbc hl,de
        pop hl
        ret c
        dec hl
        ld a,(hl)                   ; x offset
        ld (V_K),a
        dec hl
        ld a,b
        sub (hl)                    ; y - y offset
        and 127
        ld (V_Y),a
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        res 0,e
        ld (V_GFX),de
        ld a,d                      ; guard: the graphic at 0x6000 or above
        cp 0x60
        ret c
        ld a,(de)
        ld (V_W),a
        or a
        ret z
        cp 7                        ; the plotter's unrolled rows take at most 6 bytes
        ret nc
        inc de
        ld a,(de)
        ld (V_R),a
        or a
        ret z
        cp 65
        ret nc
        ld a,(V_MIR)
        or a
        ld a,c
        jr nz,.mx
        ld hl,V_K
        sub (hl)                    ; x = E - x offset
        jr .xs
.mx:    ld hl,V_K
        add a,(hl)
        inc a
        ld hl,V_W
        sub (hl)                    ; x = E + x offset + 1 - W
.xs:    ld (V_X),a
        ld a,(V_W)                  ; tiles: TW = (W + 1) / 2, TH = (R + 15) / 16
        inc a
        srl a
        ld (V_TW),a
        ld a,(V_R)
        add a,15
        rra
        srl a
        srl a
        srl a
        ld (V_TH),a
        call key
        call lookup                 ; -> V_E, carry = dropped
        ret c
        jp emit

; key: V_KEY = graphic (2), mirror, W, R, first 4 data bytes
key:    ld de,V_KEY
        ld hl,(V_GFX)
        ld a,l
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
        ld a,(V_MIR)
        ld (de),a
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld bc,4
        ldir
        ret

; lookup: the entry with V_KEY (hit) or a new one built (miss) -> V_E; carry = no room (dropped)
; (first key byte compared inline; the rest only for entries that match it)
lookup: ld hl,CE+1
        ld b,NCE
        ld de,32
        ld a,(V_KEY)
.e:     cp (hl)
        jr z,.cand
.nx:    add hl,de
        djnz .e
        call alloc                  ; miss
        ret c
        call build
        jr .use
.cand:  dec hl
        bit 7,(hl)                  ; valid?
        inc hl
        jr z,.nx
        push hl
        push bc
        inc hl
        ld de,V_KEY+1
        ld c,8
.cmp:   ld a,(de)
        cp (hl)
        jr nz,.ne
        inc hl
        inc de
        dec c
        jr nz,.cmp
        pop bc
        pop hl
        dec hl                      ; the entry
.use:   set 0,(hl)
        ld (V_E),hl
        or a
        ret
.ne:    pop bc
        pop hl
        ld de,32
        ld a,(V_KEY)
        jr .nx

; alloc: an invalid entry (or an idle one evicted) with TW * TH free patterns -> HL; carry = none
alloc:  ld a,(V_TW)
        ld b,a
        ld a,(V_TH)
        ld c,a
        xor a
.m:     add a,c
        djnz .m
        ld (V_NT),a
        ld hl,CE                    ; an invalid entry?
        ld b,NCE
        ld de,32
.i:     bit 7,(hl)
        jr z,.got
        add hl,de
        djnz .i
        call idle                   ; none: evict an idle entry
        ret c
        push hl
        call evict
        pop hl
.got:   ld (V_E),hl
.pat:   ld a,(V_NFREE)              ; enough free patterns?
        ld b,a
        ld a,(V_NT)
        cp b
        jr c,.ok
        jr z,.ok
        call idle
        jr c,.fail
        call evict
        jr .pat
.ok:    ld hl,(V_E)
        ld (hl),0x80
        inc hl
        ex de,hl
        ld hl,V_KEY
        ld bc,9
        ldir
        ex de,hl
        ld a,(V_NT)
        ld (hl),a
        ld hl,(V_E)
        or a
        ret
.fail:  ld hl,V_DROP
        inc (hl)
        scf
        ret

; idle: an entry valid, not used this commit, not on show, other than V_E -> HL (round robin);
; carry = none
idle:   ld a,(V_RR)
        ld c,NCE
.l:     cp NCE
        jr c,.in
        xor a
.in:    ld b,a
        push bc
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CE
        add hl,de
        pop bc
        ld a,(hl)
        and 0x83
        cp 0x80
        jr nz,.no
        ld de,(V_E)
        or a
        sbc hl,de
        add hl,de
        jr z,.no
        ld a,b
        inc a
        ld (V_RR),a
        or a
        ret
.no:    ld a,b
        inc a
        dec c
        jr nz,.l
        scf
        ret

; evict HL: its patterns back on the FREE stack, entry invalid
evict:  ld (hl),0
        ld de,10
        add hl,de
        ld b,(hl)                   ; n
        inc hl
.p:     ld a,b
        or a
        ret z
        ld a,(hl)
        inc hl
        dec b
        cp 0xFF
        jr z,.p
        push hl
        push af
        ld a,(V_NFREE)
        ld l,a
        inc a
        ld (V_NFREE),a
        ld h,high FREE
        pop af
        ld (hl),a
        pop hl
        jr .p

; build: the patterns of entry V_E (tile order: rows of tiles, left to right)
build:  xor a
        ld (V_TY),a
.ty:    xor a
        ld (V_TX),a
.tx:    call tile
        ld a,(V_TX)
        inc a
        ld (V_TX),a
        ld hl,V_TW
        cp (hl)
        jr c,.tx
        ld a,(V_TY)
        inc a
        ld (V_TY),a
        ld hl,V_TH
        cp (hl)
        jr c,.ty
        ld hl,(V_E)
        ret

; tile (V_TX, V_TY): a pattern from the FREE stack, 16 rows uploaded; an empty one goes back
tile:   ld a,(V_NFREE)
        dec a
        ld (V_NFREE),a
        ld l,a
        ld h,high FREE
        ld a,(hl)
        ld (V_P),a
        ld c,a                      ; select it: 0x303B = slot (P / 2) + 128-byte half
        srl a
        bit 0,c
        jr z,.s
        or 0x80
.s:     ld bc,0x303B
        out (c),a
        xor a
        ld (V_OR),a
        ld (V_ROW),a
        ld a,(V_W)                  ; V_RP = graphic + 2 + 2 W (16 TY): the tile's first line
        add a,a
        ld e,a
        ld d,0                      ; DE = 2 W
        ld hl,(V_GFX)
        inc hl
        inc hl
        ld a,(V_TY)
        or a
        jr z,.rp
        ld b,a
        push de
        ex de,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ex de,hl                    ; DE = 32 W
.rpl:   add hl,de
        djnz .rpl
        pop de
.rp:    ld (V_RP),hl
.r:     ld a,(V_TY)                 ; line = TY * 16 + row
        add a,a
        add a,a
        add a,a
        add a,a
        ld hl,V_ROW
        add a,(hl)
        ld hl,V_R
        cp (hl)
        jr nc,.blank
        ld b,a                      ; B = line
        ld a,(V_TX)
        add a,a
        ld c,a                      ; C = screen byte column in the part
        call pbyte
        inc c
        call pbyte
        ld a,(V_W)                  ; next line's data
        add a,a
        ld e,a
        ld d,0
        ld hl,(V_RP)
        add hl,de
        ld (V_RP),hl
        jr .nr
.blank: ld b,8
        xor a
.z:     out (0x5B),a
        djnz .z
.nr:    ld a,(V_ROW)
        inc a
        ld (V_ROW),a
        cp 16
        jr c,.r
        ld a,(V_TX)                 ; record the pattern (or 0xFF) in the entry
        ld b,a
        ld a,(V_TY)
        ld c,a
        ld a,(V_TW)
        ld e,a
        xor a
.mul:   dec c
        jp m,.md
        add a,e
        jr .mul
.md:    add a,b
        ld e,a
        ld d,0
        ld hl,(V_E)
        add hl,de
        ld de,11
        add hl,de
        ld a,(V_OR)
        or a
        ld a,(V_P)
        jr nz,.keep
        ld a,(V_NFREE)              ; empty: the pattern goes back
        inc a
        ld (V_NFREE),a
        ld a,0xFF
.keep:  ld (hl),a
        ret

; pbyte: line B (V_RP = its data), screen byte column C of the part -> 4 pattern bytes out (zeros beyond W)
pbyte:  push bc
        ld a,(V_W)
        dec a
        cp c
        jp c,.zero                  ; C > W - 1
        ld a,(V_MIR)                ; stored column: mirrored = W - 1 - C
        or a
        ld a,c
        jr z,.nm
        ld a,(V_W)
        dec a
        sub c
.nm:    bit 0,b                     ; odd line: stored right to left
        jr z,.ev
        ld e,a
        ld a,(V_W)
        dec a
        sub e
.ev:    add a,a                     ; HL = V_RP + 2 index = the mask byte (the colour key)
        ld e,a
        ld d,0
        ld hl,(V_RP)
        add hl,de
        push hl
        ld a,(hl)
        ld d,a                      ; stored mask
        inc hl
        ld e,(hl)                   ; stored graphic
        ld a,(V_MIR)
        or a
        jr z,.dr
        ld h,0xD1                   ; the game's mirror table (0xD100)
        ld l,d
        ld d,(hl)
        ld l,e
        ld e,(hl)
.dr:    ld a,d
        ld (V_M),a
        ld a,e
        ld (V_G),a
        pop hl
        ld a,(V_COL)
        or a
        jr z,.def
        call colent                 ; colour entry for this byte?
        jr c,.col
.def:   ld a,(V_G)                  ; default colours: two table lookups per nibble
        and 0xF0
        ld b,a
        ld a,(V_M)
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        or b
        call nibout
        ld a,(V_G)
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld b,a
        ld a,(V_M)
        and 0x0F
        or b
        call nibout
        pop bc
        ret
.col:   call pixout
        pop bc
        ret
.zero:  xor a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        out (0x5B),a
        pop bc
        ret

nibout: ld l,a
        ld h,high NIB0
        ld a,(hl)
        out (0x5B),a
        ld b,a
        inc h
        ld a,(hl)
        out (0x5B),a
        or b
        ld hl,V_OR
        or (hl)
        ld (hl),a
        ret

; colent: HL = mask byte address -> carry = a valid colour entry (V_NIB / V_TM filled)
colent: ld a,h
        cp 0x60
        jr c,.no
        cp 0xC0
        jr nc,.no
        push hl
        ld a,(hl)                   ; check = mask ^ rotl(graphic) (stored bytes)
        inc hl
        ld b,(hl)
        rlc b
        xor b
        ld c,a
        pop hl
        ld de,0xA000                ; i = (A - 0x6000) / 2; page STORE + i / 1024; offset (i % 1024) * 8
        add hl,de
        srl h
        rr l                        ; HL = i
        ld a,h
        srl a
        srl a
        add a,STORE
        nextreg 0x57,a
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0xE000
        add hl,de
        ld a,(hl)
        or a
        jr z,.nm
        inc hl
        ld a,(hl)
        cp c
        jr nz,.nm
        inc hl
        ld de,V_NIB
        ld b,4
.n:     ld a,(hl)
        rrca
        rrca
        rrca
        rrca
        and 15
        ld (de),a
        inc de
        ld a,(hl)
        and 15
        ld (de),a
        inc de
        inc hl
        djnz .n
        ld a,(hl)
        ld (V_TM),a
        nextreg 0x57,GPG7
        scf
        ret
.nm:    nextreg 0x57,GPG7
.no:    or a
        ret

; pixout: the 8 pixels of V_M / V_G with the colour entry -> 4 pattern bytes
pixout: ld c,0                      ; C = screen pixel 0-7
.px:    call pixel
        add a,a
        add a,a
        add a,a
        add a,a
        ld (V_PIX),a
        inc c
        call pixel
        ld hl,V_PIX
        or (hl)
        out (0x5B),a
        ld hl,V_OR
        or (hl)
        ld (hl),a
        inc c
        ld a,c
        cp 8
        jr c,.px
        ret

; pixel C (0 = left on screen) -> A = colour index (0 transparent)
pixel:  ld a,(V_MIR)                ; stored bit: mirrored = 7 - C
        or a
        ld a,c
        jr z,.sb
        ld a,7
        sub c
.sb:    ld e,a                      ; E = stored bit
        ld b,a
        inc b
        ld a,(V_TM)                 ; painted transparent?
.t:     rlca
        djnz .t
        jr c,.clr
        ld hl,V_NIB
        ld d,0
        add hl,de
        ld d,(hl)                   ; D = the bit's nibble (0 = default)
        ld b,c
        inc b
        ld a,(V_G)
.g:     rlca
        djnz .g
        jr nc,.ng
        ld a,d
        or a
        ret nz
        ld a,INK
        ret
.ng:    ld b,c
        inc b
        ld a,(V_M)
.m:     rlca
        djnz .m
        ld a,d
        ret c                       ; clear pixel: its nibble (0 = transparent)
        or a
        ret nz
        ld a,BODY
        ret
.clr:   xor a
        ret

; emit: the entry's tiles -> SPRTAB (screen pixel X = 8 x + 16 TX, Y = 8 + y + 16 TY); tiles
; outside the screen columns or empty get no sprite
emit:   ld a,(V_X)
        ld l,a
        rlca
        sbc a,a
        ld h,a                      ; HL = x (signed)
        add hl,hl
        add hl,hl
        add hl,hl
        ld (V_SX),hl
        ld a,(V_Y)
        add a,8
        ld (V_SY),a
        ld hl,(V_E)
        ld de,11
        add hl,de                   ; HL = pattern list
        xor a
        ld (V_TY),a
.ty:    xor a
        ld (V_TX),a
        push hl
.tx:    pop hl
        ld a,(hl)
        inc hl
        push hl
        cp 0xFF
        jp z,.nx
        ld (V_P),a
        ld a,(V_NS)
        cp MAXSPR
        jp nc,.nx
        ld a,(V_TX)                 ; X = SX + 16 TX; visible when -15 <= X <= 255
        add a,a
        add a,a
        add a,a
        add a,a
        ld e,a
        ld d,0
        ld hl,(V_SX)
        add hl,de
        ld de,15
        add hl,de                   ; X + 15 in 0..270
        ld a,h
        or a
        jr z,.vis                   ; 0..255
        dec a
        jp nz,.nx                   ; negative or >= 512
        ld a,l
        cp 15
        jp nc,.nx                   ; 256..270 only
.vis:   ld de,32 - 15
        add hl,de                   ; HL = X + 32 (sprite coordinates, 9 bits)
        ex de,hl
        ld a,(V_NS)
        ld l,a
        inc a
        ld (V_NS),a
        ld h,0
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc
        ld bc,SPRTAB
        add hl,bc
        ld (hl),e                   ; attr 0: X low
        inc hl
        ld a,(V_TY)                 ; attr 1: Y = 32 + SY + 16 TY
        add a,a
        add a,a
        add a,a
        add a,a
        ld b,a
        ld a,(V_SY)
        add a,b
        add a,32
        ld (hl),a
        inc hl
        ld a,d
        and 1
        ld (hl),a                   ; attr 2: X8
        inc hl
        ld a,(V_P)
        ld c,a
        srl a
        or 0xC0
        ld (hl),a                   ; attr 3: visible, attr 4 on, slot P / 2
        inc hl
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        ld (hl),a                   ; attr 4: 4-bit, 128-byte half
.nx:    ld a,(V_TX)
        inc a
        ld (V_TX),a
        ld hl,V_TW
        cp (hl)
        jp c,.tx
        pop hl
        ld a,(V_TY)
        inc a
        ld (V_TY),a
        ld de,V_TH
        ld a,(de)
        ld b,a
        ld a,(V_TY)
        cp b
        jp c,.ty
        ret

; hideall: every sprite hidden, the cache emptied, every pattern free
hideall:xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp MAXSPR
        jr nz,.h
        xor a
        ld (V_PREV),a
        ld (V_NS),a
        ld (V_N),a
        ld (V_RR),a
        ld hl,CE
        ld de,32
        ld b,NCE
.c:     ld (hl),a
        add hl,de
        djnz .c
        ld hl,FREE
.f:     ld (hl),a
        inc l
        inc a
        cp 128
        jr nz,.f
        ld (V_NFREE),a
        ret
rom_end:

; --- setup routine (stub bank, 0xD000): alt ROM image 0 (ROM 0 + the hook bytes), palette,
; transparency, hide all, clip, sprites on. Runs before the stub's image-1 fill.
        ORG 0xD000
setup:  nextreg 0x54,20             ; stub page alias at 0x8000, hook image page at 0xA000
        nextreg 0x55,24
        jp .alias - 0x4000
.alias: ld bc,0x243B                ; unlock 7FFD paging (NextReg $08 bit 7)
        ld a,8
        out (c),a
        inc b
        in a,(c)
        or 0x80
        nextreg 0x08,a
        ld bc,0x1FFD                ; ROM 0 (the 128K ROM = alt image 0)
        xor a
        out (c),a
        ld b,0x7F
        out (c),a
        nextreg 0x8C,0xC0           ; alt ROM write mode: reads ROM, writes the image
        ld hl,0
        ld de,0
        ld bc,0x4000
        ldir
        ld hl,0xA000
        ld de,0x2000
        ld bc,rom_end + 20 - 0x2000 ; hook bytes + the register block (pre-filled by Python)
        ldir
        nextreg 0x8C,0
        nextreg 0x56,20
        nextreg 0x57,21
        jp .back
.back:  nextreg 0x54,4
        nextreg 0x55,5
        nextreg 0x43,0x20           ; sprite palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0              ; index 0 transparent
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2              ; sprite clip window = the play area (screen rows 1-16)
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,8
        nextreg 0x19,135
        nextreg 0x15,0x01           ; sprites on, SLU, higher number on top
        ret
pal:                                ; 16 palette bytes appended by Python

; --- front end (start snapshot, 0x6480; write-first game RAM 0x6400-0x9EFF) ----------------
; The loading screen is up (the loader's PAUSE 0): wait until no key is held, then for a key;
; restore A and F, JP 23340 with every register as the loader left them after its entry code.
        ORG 0x6480
front:  di
.up:    xor a
        in a,(0xFE)
        cpl
        and 31
        jr nz,.up
.dn:    xor a
        in a,(0xFE)
        cpl
        and 31
        jr z,.dn
        ld sp,f_af
        pop af
        ld sp,24553
        jp 23340
f_af:   dw 0x0440                   ; A = 4, F = 0x40 (the entry state's AF; checked by Python)
front_end:

        SAVEBIN "tr_rom.bin",0x2200,rom_end-0x2200
        SAVEBIN "tr_setup.bin",0xD000,pal-0xD000
        SAVEBIN "tr_front.bin",0x6480,front_end-0x6480
