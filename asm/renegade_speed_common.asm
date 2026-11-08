; Target Renegade (Imagine 1988, 128K) - every figure of the masked plotter becomes 4-bit hardware
; sprites; scenery, HUD and text stay on the ULA. Facts: games/target_renegade.md.
;
; HOOK-SPEED build (2026-11-04) of renegade_hooks.asm (default colours) and renegade_enh_hooks.asm
; (Enhanced colours, assembled with ENH defined: renegade_enh_speed_hooks.asm). The pictures are the
; same as theirs; only the hooks' time changes:
; - every hook that switches to 28 MHz first reads the speed it was entered at (NextReg 7) and restores
;   it on exit (never a fixed 3.5 MHz); the plot hooks now run their own work at 28 MHz too;
; - the commit finds a part's pattern-cache entry through a hash index (HIDX) before the full scan;
; - a second-level content cache (RC) in RAM pages RCPG.. keeps every built 16x16 pattern of the level:
;   a part whose patterns left the pattern RAM is uploaded again from RAM (128 OUTI a pattern) instead
;   of being rebuilt from the game's graphic. Directory page DPG (512 x 16 bytes, hashed on the key,
;   linear probe), tiles in RCN pages. Emptied (a new generation) at the screen clear 62821 (the level
;   graphics are loaded only at 0xD6EF, which clears the screen at 0xD74E before anything is drawn),
;   when the level found changes (Enhanced), and when full.
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
;   62821 entry    screen clear (level start, menus): every sprite hidden, both caches emptied.
; Hook code: alt ROM images 0 AND 1 (the game runs with ROM 0 selected; 0x10-0x14 while loading),
; 0x2000-0x34FF only: 0x3500-0x3508 of ROM 0 is read by the game (sound data), nothing at 0x3D00-.
; MMU slot 0 holds an RC page only inside the commit and the clear (restored to ROM, 0xFF, before
; they return); no code runs there.
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
STORE   EQU 28                  ; colour store: pages 28-39
DPG     EQU 46                  ; RC directory page (run time only; set to 0xFF by the set-up)
RCPG    EQU 48                  ; RC tile pages 48-63 (run time only), 64 patterns of 128 bytes each
RCN     EQU 16
RCMAX   EQU 64 * RCN            ; RC tile slots
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
V_OR    EQU 0x401A              ; non-zero = the pattern has an opaque pixel (0 = empty tile)
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
V_LVL   EQU 0x4050              ; level found by the commit (0 = none: default colours, palette 0)
V_PALB  EQU 0x4051              ; palette offset of the level's first class, << 4 (0 = none)
V_CLS   EQU 0x4052              ; class of the current part: 0 other, 1 player 1, 2 player 2
V_S     EQU 0x4060              ; the current byte's selection (stored bit order)
V_SD    EQU 0x4061              ; the selection as drawn (a selected clear pixel: a hole filled, speed5)
V_GA    EQU 0x4062              ; pass A graphic / mask
V_MA    EQU 0x4063
V_IA    EQU 0x4064              ; pass A / B symbol table index
V_IB    EQU 0x4065
V_O0    EQU 0x4066              ; pass A output bytes
V_O1    EQU 0x4067
V_SAP   EQU 0x4068              ; (2) colour table of colour A, of colour B
V_SBP   EQU 0x406A
V_LPG   EQU 0x406C              ; the level's first store page
V_LOF   EQU 0x406D              ; (2) the level's table offset in that page - 0x7800
V_CRNG  EQU 0x406F              ; the current part: 0 no colour lookups, 1 all in range, 2 check each
; speed build
V_SPD   EQU 0x4070              ; the speed (NextReg 7 bits 1-0) the running hook was entered at
V_GEN   EQU 0x4071              ; RC generation: a directory entry is valid when its +0 equals it
V_RCT   EQU 0x4072              ; (2) next free RC tile slot
V_RCE   EQU 0x4074              ; (2) directory entry for an insert (0xFFFF = none)
V_RCH   EQU 0x4076              ; (2) the key's first directory entry
V_RCS   EQU 0x4078              ; (2) the entry's first RC tile slot
V_EMK   EQU 0x407A              ; (2) empty tiles of the entry (bit k = tile k)
V_BIT   EQU 0x407C              ; (2) the current tile's bit
V_RCF   EQU 0x407E              ; 1 = the key was found in the RC
V_TK    EQU 0x407F              ; tile counter (RC upload)
V_PL    EQU 0x4080              ; (2) CE pattern list pointer (RC upload)
V_HX    EQU 0x4082              ; the key's hash (HIDX index)
V_LVO   EQU 0x4083              ; the level of the RC's contents (Enhanced: a change empties the RC)
V_CX    EQU 0x4084              ; (2) emit: X + 15 of the current tile
V_A2    EQU 0x4086              ; emit: attribute 2 without X8 (palette offset)

LOG     EQU 0x4100              ; MAXLOG x 5: L, H, E, D, kind
CE      EQU 0x4300              ; NCE x 32: +0 flags (7 valid, 0 used, 1 shown), +1 key (9), +10 n,
                                ; +11 patterns (16; 0xFF = empty tile)
FREE    EQU 0x4900              ; free pattern stack (128)
SPRTAB  EQU 0x4A00              ; 128 x 5
HIDX    EQU 0x4D00              ; 256: key hash -> CE entry index + 1 (0 = none; a hint, the key is compared)
HSTK    EQU 0x5F00
        IFDEF ENH
REV     EQU 0x5200              ; page H: bit reverse (exact; the game's table differs at 58)
SUB     EQU 0x5400              ; page H: 16 colour tables of 16: symbol pair (4 s0 + s1) -> pattern byte
SIGT    EQU 0x5000              ; per level: n, then n x (address, byte); n = 0 ends
LPAR    EQU 0x5100              ; per level L at LPAR + 4 L: store page, table offset (2), palette base << 4
        ENDIF

NIB0    EQU 0x2000              ; pixel pairs (default) / symbols (Enhanced): index = graphic nibble << 4 | mask nibble
NIB1    EQU 0x2100

; a pattern byte: to the pattern RAM and to the RC tile being built (HL' = its address in slot 0)
        MACRO PUT
        out (0x5B),a
        exx
        ld (hl),a
        inc l
        exx
        ENDM

; enter 28 MHz, keeping the speed the hook was entered at (A, BC used)
        MACRO SPEED28
        ld bc,0x243B
        ld a,7
        out (c),a
        inc b
        in a,(c)
        nextreg 0x07,3
        IFDEF NEG_FORCE35
        xor a                       ; NEGATIVE CONTROL: a forced 3.5 MHz exit
        ELSE
        and 3
        ENDIF
        ld (V_SPD),a
        ENDM

; 0x2000-0x21FF: NIB0 / NIB1, written by renegade.py / renegade_enh.py
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
        SPEED28
        ld a,(V_N)
        cp MAXLOG
        jr nc,.full
        ld c,a
        inc a
        ld (V_N),a
        push hl
        ld b,0
        ld h,b
        ld l,c
        add hl,hl
        add hl,hl
        add hl,bc                   ; 5 * index
        ld bc,LOG
        add hl,bc
        pop bc                      ; the plotter's HL
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        IFDEF ENH
        ld a,(0xDCA9)               ; the object being drawn: player 1 (0x0A), player 2 (0x20), other
        cp 0x0A
        jr z,.p1
        cp 0x20
        ld a,kind
        jr nz,.k
        or 4
        jr .k
.p1:    ld a,kind | 2
.k:     ld (hl),a
        ELSE
        ld (hl),kind
        ENDIF
        ld h,b                      ; HL back
        ld l,c
        jr .done
.full:  ld a,(V_DROP)
        inc a
        ld (V_DROP),a
.done:  pop bc
        ld a,(V_SPD)
        nextreg 0x07,a
        pop af
        ld sp,(V_SP)
        nextreg 0x52,SPG
        dec hl
        jp back
        ENDM

e_pn:   PLOTLOG 0, 55279
e_pm:   PLOTLOG 1, 55725

; ---- 59531 draw all: log reset, scenery (the plain buffer) -> screen rows 1-16 ----
e_dr:   nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        SPEED28
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
        ld a,(V_SPD)
        nextreg 0x07,a
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x52,SPG
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
        DUP 32
        ldi
        EDUP
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
e_cm:   nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        SPEED28
        push de
        push hl
        exx
        push hl                     ; the game's HL' (the RC builder's pointer)
        exx
        ld a,(V_N)                  ; no figure in the buffer: the buffer is the scenery
        or a
        call z,scen
        call commit
        nextreg 0x57,GPG7
        nextreg 0x50,0xFF
        exx
        pop hl
        exx
        pop hl
        pop de
        ld a,(V_SPD)
        nextreg 0x07,a
        pop bc
        pop af
        ld sp,(V_SP)
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

; ---- 62821 screen clear: hide every sprite, empty both caches ----
e_clr:  nextreg 0x52,HPG
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        SPEED28
        push de
        push hl
        call hideall
        nextreg 0x50,0xFF
        ld (V_DIRTY),sp
        pop hl
        pop de
        ld a,(V_SPD)
        nextreg 0x07,a
        pop bc
        pop af
        ld sp,(V_SP)
        nextreg 0x52,SPG
        ld hl,23295
        jp 62824

; =====================================================================================
; commit: every logged part -> sprites (SPRTAB), then the attribute upload; cache flags aged
commit:
        IFDEF ENH
        ld a,(V_COL)
        or a
        call nz,detect
        ENDIF
        xor a
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
.upl:   ld a,(V_NS)             ; the shown sprites' 5 attribute bytes each through port 0x57 (from sprite 0)
        ld d,a
        or a
        jr z,.hide
        xor a
        ld bc,0x303B
        out (c),a
        ld hl,SPRTAB
        ld c,0x57
        ld e,d
.c:     outi
        outi
        outi
        outi
        outi
        dec e
        jr nz,.c
.hide:  ld e,d
        ld a,(V_PREV)
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
        ld hl,CE                    ; each entry's flags: valid + used -> valid + shown (table AGE)
        ld de,32
        ld b,high AGE
        DUP NCE
        ld c,(hl)
        ld a,(bc)
        ld (hl),a
        add hl,de
        EDUP
        ret

; part: the log entry at V_LP -> parameters, cache entry (built on a miss), sprites
part:
        IFDEF ENH
        nextreg 0x57,GPG7           ; slot 7 the game's (colent may have left a store page there)
        ENDIF
        ld hl,(V_LP)
        ld e,(hl)
        inc hl
        ld d,(hl)                   ; DE = part record (graphic word)
        inc hl
        ld c,(hl)                   ; C = E (x)
        inc hl
        ld b,(hl)                   ; B = D (y)
        inc hl
        ld a,(hl)
        IFDEF ENH
        push af
        and 1
        ld (V_MIR),a
        pop af
        srl a
        ld (V_CLS),a
        ELSE
        ld (V_MIR),a
        ENDIF
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
        IFDEF ENH
        ld a,(V_LVL)                ; V_CRNG: colour lookups for this part's graphic (colent)
        or a
        jr z,.c0
        ld a,(V_GFX + 1)
        cp 0x78
        jr c,.c0
        cp 0xBD                     ; a graphic takes at most 768 bytes: below 0xBD00 it ends below 0xC000
        ld a,1
        jr c,.cs
        inc a
        jr .cs
.c0:    xor a
.cs:    ld (V_CRNG),a
        ENDIF
        call key
        call lookup                 ; -> V_E, carry = dropped
        ret c
        jp emit

; key: V_KEY = graphic (2), mirror, W, R, first 4 data bytes; V_HX = its hash
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
        ld a,(V_KEY + 1)            ; hash: graphic high << 2 ^ graphic low >> 1 (bit 0 is 0) ^ mirror << 7
        rlca
        rlca
        ld b,a
        ld a,(V_KEY)
        rrca
        xor b
        ld b,a
        ld a,(V_MIR)
        rrca
        xor b
        ld (V_HX),a
        ret

; ceidx: HL = a CE entry -> A = its index + 1
ceidx:  ld a,h
        sub high CE
        rlca
        rlca
        rlca
        ld b,a
        ld a,l
        rlca
        rlca
        rlca
        and 7
        or b
        inc a
        ret

; lookup: the entry with V_KEY (hit) or a new one built (miss) -> V_E; carry = no room (dropped)
; The hash index names one candidate; on no match there the full scan decides, as before (keys are
; unique among valid entries: an entry is made only after a scan found none), so hits and misses are
; exactly the scan's.
lookup: ld a,(V_HX)
        ld l,a
        ld h,high HIDX
        ld a,(hl)
        or a
        jr z,.scan
        dec a
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,CE
        add hl,de
        bit 7,(hl)
        jr z,.scan
        push hl
        IFNDEF NEG_NOHKEY
        inc hl
        ld de,V_KEY
        ld b,9
.q:     ld a,(de)
        cp (hl)
        jr nz,.qn
        inc hl
        inc de
        djnz .q
        ENDIF                       ; (NEG_NOHKEY: the negative control trusts the hash without the key)
        pop hl
        jr .use
.qn:    pop hl
.scan:  ld hl,CE+1
        ld b,NCE
        ld de,32
        ld a,(V_KEY)
.e:     cp (hl)
        jr z,.cand
.nx:    add hl,de
        djnz .e
        call alloc                  ; miss
        ret c
        call ceset
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
        call ceset
.use:   set 0,(hl)
        ld (V_E),hl
        or a
        ret
.ne:    pop bc
        pop hl
        ld de,32
        ld a,(V_KEY)
        jr .nx

; ceset: HIDX[V_HX] = the entry HL (kept)
ceset:  push hl
        call ceidx
        ld hl,V_HX
        ld l,(hl)
        ld h,high HIDX
        ld (hl),a
        pop hl
        ret

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

; ---- the RC (second-level content cache) ----------------------------------------------
; rcfind: the directory entry of V_KEY (+ the level) -> V_RCF 1 (V_RCS, V_EMK), else V_RCF 0 and
; V_RCE = where to insert it (0xFFFF: 8 entries taken). Slot 0 = DPG afterwards.
rcfind: xor a
        ld (V_RCF),a
        ld a,(V_HX)                 ; first entry: (hash + 256 mirror) x 16
        ld l,a
        ld a,(V_MIR)
        and 1
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld (V_RCH),hl
        nextreg 0x50,DPG
        ld b,8
.p:     ld a,(V_GEN)
        cp (hl)
        jr nz,.free                 ; not valid: the key is not further on (nothing is ever removed)
        push hl
        push bc
        inc hl
        ld de,V_KEY
        ld b,9
.c:     ld a,(de)
        cp (hl)
        jr nz,.ne
        inc hl
        inc de
        djnz .c
        IFDEF ENH
        IFNDEF NEG_NOLVLWIPE
        ld a,(V_LVL)                ; the level is part of the key (its words colour the patterns)
        ELSE
        xor a                       ; (NEG_NOLVLWIPE: the negative control leaves the level out)
        ENDIF
        ELSE
        xor a
        ENDIF
        cp (hl)
        jr nz,.ne
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_RCS),de
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_EMK),de
        pop bc
        pop hl
        ld a,1
        ld (V_RCF),a
        ret
.ne:    pop bc
        pop hl
        ld de,16
        add hl,de
        res 5,h                     ; wrap in 0x0000-0x1FFF
        djnz .p
        ld hl,0xFFFF
.free:  ld (V_RCE),hl
        ret

; rcwipe: every RC entry invalid (a new generation), every tile slot free
rcwipe: ld a,(V_GEN)
        inc a
        cp 0xFF
        jr nz,.g
        nextreg 0x50,DPG            ; generations used up: the directory back to 0xFF
        ld hl,0
        ld de,1
        ld bc,0x1FFF
        ld (hl),0xFF
        ldir
        xor a
.g:     ld (V_GEN),a
        ld hl,0
        ld (V_RCT),hl
        ret

; rcmap: HL = RC tile slot -> its page at slot 0, HL = its address there
rcmap:  ld a,l
        rlca
        rlca
        and 3
        ld e,a
        ld a,h
        add a,a
        add a,a
        or e
        add a,RCPG
        nextreg 0x50,a
        ld a,l
        and 63
        srl a
        ld h,a
        ld a,0
        rra
        ld l,a
        ret

; select pattern A for upload (0x303B = slot A / 2 + the 128-byte half)
        MACRO PATSEL
        ld c,a
        srl a
        bit 0,c
        jr z,.s
        or 0x80
.s:     ld bc,0x303B
        out (c),a
        ENDM

; build: the patterns of entry V_E (tile order: rows of tiles, left to right): uploaded from the RC
; when it has the key, else built from the graphic (and kept in the RC)
build:  call rcfind
        ld a,(V_RCF)
        or a
        jp nz,rcload
        ld hl,(V_RCT)               ; room for NT tiles?
        ld a,(V_NT)
        ld e,a
        ld d,0
        add hl,de
        ld de,RCMAX + 1
        or a
        sbc hl,de
        jr c,.room
        call rcwipe
        ld hl,(V_RCH)               ; the directory is empty now: insert at the key's first entry
        ld (V_RCE),hl
.room:  ld hl,(V_RCT)
        ld (V_RCS),hl
        ld hl,0
        ld (V_EMK),hl
        inc hl
        ld (V_BIT),hl
        xor a
        ld (V_TY),a
.ty:    xor a
        ld (V_TX),a
.tx:    call tile
        ld hl,(V_BIT)
        jr nz,.full                 ; NZ: the tile has an opaque pixel (kept in the RC)
        ld de,(V_EMK)
        ld a,e
        or l
        ld e,a
        ld a,d
        or h
        ld d,a
        ld (V_EMK),de
.full:  add hl,hl
        ld (V_BIT),hl
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
        ld hl,(V_RCE)               ; the directory entry
        ld a,h
        and l
        inc a
        jr z,.done                  ; 0xFFFF: no room in the probe (the tiles stay unused until a wipe)
        nextreg 0x50,DPG
        ld a,(V_GEN)
        ld (hl),a
        inc hl
        ex de,hl
        ld hl,V_KEY
        ld bc,9
        ldir
        ex de,hl
        IFDEF ENH
        IFNDEF NEG_NOLVLWIPE
        ld a,(V_LVL)
        ELSE
        xor a
        ENDIF
        ld (hl),a
        ELSE
        ld (hl),0
        ENDIF
        inc hl
        ld de,(V_RCS)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(V_EMK)
        ld (hl),e
        inc hl
        ld (hl),d
.done:  ld hl,(V_E)
        ret

; rcload: the entry's patterns from the RC: each tile not empty -> a pattern from the FREE stack, its 128
; bytes uploaded (as tile would have built them)
rcload: xor a
        ld (V_TK),a
        ld hl,(V_E)
        ld de,11
        add hl,de
        ld (V_PL),hl
.k:     ld a,(V_TK)
        ld hl,V_NT
        cp (hl)
        jp nc,.done
        inc a
        ld (V_TK),a
        ld hl,(V_EMK)
        srl h
        rr l
        ld (V_EMK),hl
        ld hl,(V_PL)
        jr nc,.full
        ld (hl),0xFF                ; empty tile
        inc hl
        ld (V_PL),hl
        jr .k
.full:  ld a,(V_NFREE)
        dec a
        ld (V_NFREE),a
        push hl
        ld l,a
        ld h,high FREE
        ld a,(hl)
        pop hl
        ld (hl),a
        inc hl
        ld (V_PL),hl
        PATSEL
        ld hl,(V_RCS)
        push hl
        inc hl
        ld (V_RCS),hl
        pop hl
        call rcmap
        ld c,0x5B
        DUP 128
        outi
        EDUP
        jp .k
.done:  ld hl,(V_E)
        ret

; tile (V_TX, V_TY): a pattern from the FREE stack, 16 rows uploaded and written to RC slot V_RCT;
; an empty one goes back (the slot stays free). -> NZ (A = pattern) kept, Z empty
tile:   ld a,(V_NFREE)
        dec a
        ld (V_NFREE),a
        ld l,a
        ld h,high FREE
        ld a,(hl)
        ld (V_P),a
        PATSEL
        ld hl,(V_RCT)               ; the RC slot: HL' = its address in slot 0
        call rcmap
        push hl
        exx
        pop hl
        exx
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
.z:     PUT
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
        ld (hl),0xFF
        xor a
        ret
.keep:  ld (hl),a
        ld hl,(V_RCT)               ; kept: the RC slot is used
        inc hl
        ld (V_RCT),hl
        or 1                        ; NZ
        ret

        IFDEF ENH
; ---------------- Enhanced: pbyte with the colour words -----------------------------------
; pbyte: line B (V_RP = its data), screen byte column C of the part -> 4 pattern bytes out (zeros beyond W)
; NIB1: A = graphic nibble << 4 | mask nibble, DE = a colour table -> 2 pattern bytes out (4 pixels)
        MACRO NIB1
        ld l,a
        ld h,high NIB0
        ld b,(hl)                   ; symbols of pixels 0-1 (0 clear, 1 ink, 2 body)
        inc h
        ld c,(hl)                   ; pixels 2-3
        ld a,e
        add a,b
        ld l,a
        ld h,d
        ld a,(hl)
        PUT
        ld a,e
        add a,c
        ld l,a
        ld a,(hl)
        PUT
        ENDM

pbyte:  push bc
        ld a,(V_W)
        dec a
        cp c
        jp c,.zero                  ; C > W - 1
        ld e,a                      ; E = W - 1
        ld a,(V_MIR)
        or a
        jr nz,.mi
        ld a,c                      ; as stored: column C, odd lines right to left (W - 1 - C)
        bit 0,b
        jr z,.ev
        ld a,e
        sub c
.ev:    add a,a                     ; HL = V_RP + 2 index = the mask byte (the colour key)
        ld e,a
        ld d,0
        ld hl,(V_RP)
        add hl,de
        ld e,(hl)                   ; E = mask, D = graphic (as drawn)
        inc hl
        ld d,(hl)
        dec hl
        jr .dr
.mi:    ld a,e                      ; mirrored: stored column W - 1 - C (odd lines: C)
        sub c
        bit 0,b
        jr z,.ev2
        ld a,c
.ev2:   add a,a
        ld e,a
        ld d,0
        ld hl,(V_RP)
        add hl,de
        push hl
        ld a,(hl)
        inc hl
        ld l,(hl)
        ld h,0xD1                   ; the game's mirror table (0xD100)
        ld d,(hl)                   ; D = graphic
        ld l,a
        ld e,(hl)                   ; E = mask
        pop hl
.dr:    ld (V_M),de                 ; V_M = mask, V_G = graphic
        ld a,e                      ; every pixel clear (mask 0xFF, graphic 0): 4 zero bytes
        inc a
        jr nz,.nz
        ld a,d
        or a
        jp z,.zero
.nz:    ld a,1                      ; an opaque pixel: the tile is not empty (every colour is non-zero)
        ld (V_OR),a
        call colent                 ; -> DE = colour A's table, C = the selection (stored order), V_SBP,
        or a                        ; A = 0 one colour, 1 the selection black, 2 two colours
        jr z,.uni
        dec a
        jp nz,.mix
        ld a,(V_MIR)                ; the selection black: selected pixels drawn as ink (g | S)
        or a
        ld a,c
        jr z,.bs
        ld h,high REV
        ld l,c
        ld a,(hl)
.bs:    ld b,a                      ; S = the selection as drawn: its opaque pixels, and a clear pixel a word
        ld a,(V_G)                  ; selects (a hole filled: speed5, the bouncers' waist) drawn the same way
        or b
        ld (V_G),a
.uni:   ld a,(V_M)                  ; one colour: the symbol tables, then the colour's table
        swapnib
        and 0x0F
        ld b,a
        ld a,(V_G)
        and 0xF0
        or b
        NIB1
        ld a,(V_G)
        swapnib
        and 0xF0
        ld b,a
        ld a,(V_M)
        and 0x0F
        or b
        NIB1
        pop bc
        ret
.mix:   ld (V_SAP),de
        ld b,c                      ; S = the selection as drawn (opaque pixels, and a clear one = a hole filled)
        ld a,(V_MIR)
        or a
        jr z,.nr
        ld h,high REV
        ld l,b
        ld b,(hl)
.nr:    ld a,b                      ; (speed5: a selected clear pixel is filled too, as body colour B)
        ld (V_SD),a
        cpl
        ld c,a
        ld a,(V_G)                  ; pass A: the selected pixels taken out (g & ~S, m | S)
        and c
        ld (V_GA),a
        ld a,(V_SD)
        ld b,a
        ld a,(V_M)
        or b
        ld (V_MA),a
        ld a,(V_GA)
        and 0xF0
        ld b,a
        ld a,(V_MA)
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        or b
        ld (V_IA),a
        ld a,(V_SD)                 ; pass B: the selected pixels as body (graphic 0, mask ~S)
        cpl
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        ld (V_IB),a
        call nib2
        ld a,(V_GA)
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld b,a
        ld a,(V_MA)
        and 0x0F
        or b
        ld (V_IA),a
        ld a,(V_SD)
        cpl
        and 0x0F
        ld (V_IB),a
        call nib2
        pop bc
        ret
.zero:  xor a
        PUT
        PUT
        PUT
        PUT
        pop bc
        ret

; nib2: pass A (V_IA, colours V_SAP) OR pass B (V_IB, colours V_SBP) -> 2 pattern bytes out
nib2:   ld a,(V_IA)
        ld l,a
        ld h,high NIB0
        ld b,(hl)
        inc h
        ld c,(hl)
        ld de,(V_SAP)
        ld a,e
        add a,b
        ld l,a
        ld h,d
        ld a,(hl)
        ld (V_O0),a
        ld a,e
        add a,c
        ld l,a
        ld a,(hl)
        ld (V_O1),a
        ld a,(V_IB)
        ld l,a
        ld h,high NIB0
        ld b,(hl)
        inc h
        ld c,(hl)
        ld de,(V_SBP)
        ld a,e
        add a,b
        ld l,a
        ld h,d
        ld a,(hl)
        ld hl,V_O0
        or (hl)
        PUT
        ld a,e
        add a,c
        ld l,a
        ld h,d
        ld a,(hl)
        ld hl,V_O1
        or (hl)
        PUT
        ret

; colent: HL = mask byte address -> DE = colour A's table, C = the selection, A = 0 (one colour), 1 (the
; selection black), 2 (two colours: V_SBP = colour B's table). The level's word for the entry: colour A
; (top nibble), colour B, and the selection (low byte, stored bit order): selected opaque pixels take
; colour B (0: black, drawn as ink), other body pixels colour A (0: the default BODY), other ink INK. No
; word (or no level): A = BODY, nothing selected (the default build's colours).
colent: ld a,(V_CRNG)                ; the part: 0 no lookups, 1 all its entries in range, 2 check each
        dec a
        jr z,.in
        jp m,.no
        ld a,h
        cp 0x78
        jr c,.no
        cp 0xC0
        jr nc,.no
        call .in                    ; a graphic checked byte by byte: slot 7 back at once
        nextreg 0x57,GPG7
        ret
.in:    ld de,(V_LOF)               ; HL = the word's offset from the level's first store page
        add hl,de
        ld a,h
        rlca
        rlca
        rlca
        and 7
        ld e,a
        ld a,(V_LPG)
        add a,e
        nextreg 0x57,a
        ld a,h
        and 0x1F
        or 0xE0
        ld h,a
        ld b,(hl)                   ; B = colours A, B; C = the selection
        inc l
        ld c,(hl)                   ; (slot 7 back at the next part - records can lie at 0xE000- - and at
                                    ; the commit's end)
        ld a,b
        or c
        jr z,.no
        ld a,b
        and 0xF0
        ld e,a
        ld d,high SUB               ; DE = colour A's table (SUB + 16 A; A = 0: BODY's)
        ld a,c
        or a
        ret z                       ; A = 0: one colour
        ld a,b
        and 15
        ld a,1
        ret z                       ; colour B 0: the selection black
        ld a,b
        swapnib
        and 0xF0
        ld l,a
        ld h,high SUB
        ld (V_SBP),hl
        ld a,2
        ret
.no:    ld de,SUB
        ld c,0
        xor a
        ret

; detect: V_LVL = the first level whose signature bytes all match memory (0 = none); V_PALB; a level
; other than the RC's contents' empties the RC
detect: ld hl,SIGT
        ld c,1
.lv:    ld b,(hl)
        inc hl
        ld a,b
        or a
        jr z,.none
        ld d,1
.s:     ld e,(hl)
        inc hl
        ld a,(hl)
        inc hl
        push hl
        ld h,a
        ld l,e
        ld a,(hl)
        pop hl
        cp (hl)
        inc hl
        jr z,.ok
        ld d,0
.ok:    djnz .s
        ld a,d
        or a
        jr nz,.got
        inc c
        jr .lv
.none:  ld c,0
.got:   ld a,c
        ld (V_LVL),a
        ld hl,V_LVO
        cp (hl)
        jr z,.same
        ld (hl),a
        push af
        IFNDEF NEG_NOLVLWIPE
        call rcwipe                 ; (NEG_NOLVLWIPE: the negative control keeps the RC over a level change)
        ENDIF
        pop af
.same:  or a
        jr z,.pb
        add a,a
        add a,a
        ld l,a
        ld h,high LPAR
        ld a,(hl)
        ld (V_LPG),a                ; the level's first store page
        inc l
        ld e,(hl)
        inc l
        ld d,(hl)
        inc l
        ld a,(hl)
        push af
        ld hl,-0x7800               ; V_LOF = its table's offset - 0x7800
        add hl,de
        ld (V_LOF),hl
        pop af
.pb:    ld (V_PALB),a
        ret

        ELSE
; ---------------- default: pbyte with the default colours or the colour store -------------
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
        PUT
        PUT
        PUT
        PUT
        pop bc
        ret

nibout: ld l,a
        ld h,high NIB0
        ld a,(hl)
        PUT
        ld b,a
        inc h
        ld a,(hl)
        PUT
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
        PUT
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
        ENDIF

; emit: the entry's tiles -> SPRTAB (screen pixel X = 8 x + 16 TX, Y = 8 + y + 16 TY); tiles
; outside the screen columns or empty get no sprite (the same sprites, in the same order, as before:
; the loop keeps X + 15, attribute 1 and the SPRTAB slot running instead of recomputing them per tile)
emit:   ld a,(V_X)
        ld l,a
        rlca
        sbc a,a
        ld h,a                      ; HL = x (signed)
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,15
        add hl,de
        ld (V_SX),hl                ; X + 15 of tile column 0 (visible when 0..270)
        ld a,(V_Y)
        add a,40
        ld (V_SY),a                 ; attribute 1 of tile row 0: 32 + 8 + y
        IFDEF ENH
        ld a,(V_PALB)               ; palette offset: the level's base + the part's class
        or a
        jr z,.pz
        ld a,(V_CLS)
        rlca
        rlca
        rlca
        rlca
        ld b,a
        ld a,(V_PALB)
        add a,b
.pz:    ld (V_A2),a
        ELSE
        xor a
        ld (V_A2),a
        ENDIF
        ld hl,(V_E)
        ld de,11
        add hl,de
        ld (V_PL),hl                ; the pattern list
        ld a,(V_NS)                 ; DE = SPRTAB + 5 NS
        ld l,a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,hl
        add hl,de
        ld de,SPRTAB
        add hl,de
        ex de,hl
        ld a,(V_TH)
        ld (V_TY),a                 ; tile rows left
.ty:    ld hl,(V_SX)
        ld (V_CX),hl
        ld a,(V_TW)
        ld (V_TX),a                 ; tile columns left
.tx:    ld hl,(V_PL)
        ld a,(hl)
        inc hl
        ld (V_PL),hl
        cp 0xFF
        jr z,.nx
        ld c,a                      ; C = pattern
        ld a,(V_NS)
        cp MAXSPR
        jr nc,.nx
        ld hl,(V_CX)                ; X + 15 in 0..270?
        ld a,h
        or a
        jr z,.vis                   ; 0..255
        dec a
        jr nz,.nx                   ; negative or >= 512
        ld a,l
        cp 15
        jr nc,.nx                   ; 256..270 only
.vis:   ld a,(V_NS)
        inc a
        ld (V_NS),a
        ld a,l                      ; X + 32 = (X + 15) + 17: sprite coordinates, 9 bits
        add a,17
        ld (de),a                   ; attr 0: X low
        inc de
        ld a,h
        adc a,0
        and 1
        ld b,a                      ; X8
        ld a,(V_SY)
        ld (de),a                   ; attr 1: Y
        inc de
        ld a,(V_A2)
        or b
        ld (de),a                   ; attr 2: palette offset, X8
        inc de
        ld a,c
        srl a
        or 0xC0
        ld (de),a                   ; attr 3: visible, attr 4 on, slot P / 2
        inc de
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        ld (de),a                   ; attr 4: 4-bit, 128-byte half
        inc de
.nx:    ld hl,(V_CX)
        ld bc,16
        add hl,bc
        ld (V_CX),hl
        ld hl,V_TX
        dec (hl)
        jr nz,.tx
        ld a,(V_SY)
        add a,16
        ld (V_SY),a
        ld hl,V_TY
        dec (hl)
        jr nz,.ty
        ret

; hideall: every sprite hidden, both caches emptied, every pattern free
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
        IFDEF NEG_NOCLRWIPE
        ret                         ; NEGATIVE CONTROL: the RC kept over the screen clear
        ELSE
        jp rcwipe
        ENDIF
; AGE: a cache entry's flags after a commit (valid + used -> valid + shown; others: valid only)
        ALIGN 256
AGE:
.v = 0
        DUP 256
        db (.v & 0x80) | ((.v & 1) << 1)
.v = .v + 1
        EDUP
rom_end:

; --- setup routine (stub bank, 0xD000): alt ROM image 0 (ROM 0 + the hook bytes), palette,
; transparency, hide all, clip, sprites on, the RC directory emptied. Runs before the stub's image-1 fill.
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
        IFDEF ENH
        ld hl,pal                   ; 256 entries (16 offsets), 9-bit: two bytes each (NextReg 0x44)
        ld bc,512
.p:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,.p
        ELSE
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        ENDIF
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
        nextreg 0x50,DPG            ; the RC directory: every entry invalid (0xFF; generations are 0-254)
        ld hl,0
        ld de,1
        ld bc,0x1FFF
        ld (hl),0xFF
        ldir
        nextreg 0x50,0xFF
        ret
pal:                                ; palette bytes appended by Python

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

; (the SAVEBINs are in the two wrapper files)
