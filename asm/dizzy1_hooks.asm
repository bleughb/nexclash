; Dizzy: The Ultimate Cartoon Adventure (Dizzy 1, 48K) - every figure off the ULA onto Layer 2.
;
; The game draws every figure by XOR (plotter 1 = Dizzy 58113, plotter 2 = everything else 57983),
; no masks, no undo buffers. Converted writes go into a 1-bit SHADOW screen (+ shadow attributes)
; instead of the ULA, so at every moment ULA XOR SHADOW == the original screen (XOR is linear):
;   - a figure write XORs the shadow; the Layer 2 pixels of the changed bits follow it
;   - the room renderer / HUD / text (plotter 2's KEEP callers) still write the ULA, exactly;
;     the game switches plotter 2 between XOR C / OR C / LD A,C (58079) and the attribute write
;     between XOR (HL) / NOP (58709): the hooks compute the original's new byte from the virtual
;     old one and put the change into the shadow (converted) or the ULA (kept)
;   - logic that reads figure pixels / cells gets the virtual value (collision 60244 / 60251,
;     attribute read 58712); overwriters fold the shadow back into the ULA first (room wipe
;     58634 / 58666, the effect strips 55935 / 57095), so their results are the original's.
; Layer 2 (bank L2B, 256x192, palette 0-15, index 0 transparent) shows the shadow in colour: per
; pixel the painted colour of its graphics bit (colour plane, pages PLPG..), else the plot's
; default (Dizzy bright white; plotter 2: the bright ink of C ^ 7 when it paints its cells, else
; bright white).
;
; Memory: hook code in alt ROM image 1 at 0x2000- (the game reads no ROM byte above 0x0369);
; variables + hook stack in the printer buffer 0x5B40-0x5BC0 (never touched by the game: RZX scan;
; the interrupt handler's stack is 0x5BCF-0x5BFE); MMU slot 3 (never touched by the interrupt
; handler) switches between the shadow page PG, the Layer 2 pages and the colour plane during a
; hook and is the game's page 11 again at every exit. Interrupts stay ON (the ROM 0x0038 handler
; is installed at every hook site in the RZX: it keeps every register, reads IY): hooks never
; change IY, I, IFF or the alternate registers and always run on a stack with room.
;
; Patch sites (original bytes verified by dizzy1.py):
;   57983 CB 83 32 6D E1  RES 0,E / LD (57709),A   -> JP e_p2    plotter 2 entry (caller, colour)
;   58113 32 6D E1        LD (57709),A               -> JP e_dz    Dizzy plotter entry
; Both entries switch to 28 MHz for the whole plot and swap the return address for t_p2 / t_dz,
; which put it back (the dead stack slot holds what the original leaves) and return at 3.5 MHz:
; the game has no frame sync, so the hooks must not add time (they make a plot slightly faster).
;   58076 7E 4F 1A        LD A,(HL)/LD C,A/LD A,(DE) -> JP e_p2w  plotter 2 screen write
;   58182 1A AE 77        LD A,(DE)/XOR (HL)/LD (HL),A -> JP e_dw Dizzy's screen write
;   58702 F5 CD 3B        PUSH AF / CALL 58683       -> JP e_at   attribute routine (58709 is the game's)
;   58712 CD 3B E5        CALL 58683                 -> JP e_ar   attribute read (+ LD A,(HL), RET)
;   60244 7E E6 F0        LD A,(HL) / AND 240        -> JP e_c1   collision read
;   60251 7E E6 0F        LD A,(HL) / AND 15         -> JP e_c2   collision read
;   58634 DD 21 D6 5C     LD IX,23766                -> JP e_wipe room wipe (pixels)
;   58666 21 A0 58        LD HL,22688                -> JP e_wipea room wipe (attributes)
;   55935 DD 7E 0B        LD A,(IX+11)               -> JP e_f3   type-3 effect dispatch
;   57095 DD 4E 0B        LD C,(IX+11)               -> JP e_f7   type-7 rotator

        DEVICE ZXSPECTRUMNEXT

PG      EQU 26                  ; shadow page (slot 3 during hooks): ink shadow + shadow attributes
PG2     EQU 27                  ; fill shadow (figures' enclosed paper, display only)
PG3     EQU 28                  ; Dizzy's shadow (his XOR bits; he is shown as hardware sprites 0-3)
SPP     EQU 30                  ; sprite patterns: pages 30-31 (uploaded once by setup)
GPG     EQU 11                  ; the game's page at slot 3 (48K: bank 5 upper half)
L2B     EQU 16                  ; Layer 2 16K bank -> 8K pages L2PG..L2PG+5
L2PG    EQU 32
PLPG    EQU 40                  ; plane pages 40-54: 8 bytes per graphics byte = 8 colour nibbles (0 =
                                ; default), interior mask (enclosed paper), transparent mask
P2BASE  EQU 43485               ; plotter 2 graphics (frame data) start; plane index 0
P2LEN   EQU 9663                ; up to the frame table at 53148
DZBASE  EQU 24290               ; Dizzy graphics start; plane index P2LEN
DZLEN   EQU 4760
LTAB    EQU 23750               ; the game's screen line table (line 0 = bottom)
XMODE   EQU 58079               ; plotter 2's XOR C (0xA9) / LD A,C (0x79), set by the game

; ---- variables in the printer buffer (game RAM, slot 2) ----
V_SP    EQU 0x5B40              ; game SP at hook entry
V_CONV  EQU 0x5B42              ; current plotter-2 call converts (1) or stays on the ULA (0)
V_COL   EQU 0x5B43              ; default colour of the current plot
V_RES   EQU 0x5B44              ; result byte (A at the hook's exit)
V_G     EQU 0x5B45              ; graphics byte
V_T     EQU 0x5B46              ; 2 bytes scratch
V_FM    EQU 0x5B48              ; 1 = exit with the XOR's flags, 0 = keep the entry flags
V_R2    EQU 0x5B4A              ; plotter 2's caller (its return address, swapped for t_p2)
V_R1    EQU 0x5B4C              ; Dizzy plotter's caller (swapped for t_dz)
V_PIX   EQU 0x5B50              ; 8 colours of the byte being written (bit 0 = leftmost)
V_IM    EQU 0x5B58              ; its interior mask (enclosed paper bits)
V_CL    EQU 0x5B59              ; its transparent mask (painted transparent)
V_FX    EQU 0x5B5A              ; fill bits to XOR in setsh
V_NI    EQU 0x5B5B              ; new ink shadow byte (setsh)
V_NF    EQU 0x5B5C              ; new fill shadow byte (setsh)
V_HAS   EQU 0x5B5D              ; 1 = V_PIX holds painted colours, 0 = defaults (ink V_COL, fill black)
V_SF    EQU 0x5B5E              ; Dizzy sprite: frame, x, y of the image shown (the stamp)
V_SX    EQU 0x5B5F
V_SY    EQU 0x5B60
V_VIS   EQU 0x5B61              ; 1 = shown
V_PEND  EQU 0x5B62              ; 1 = erased, hide unless the next Dizzy draw comes first
V_YY    EQU 0x5B63              ; sprite Y (+32)
V_XX    EQU 0x5B64              ; sprite X (+32, 16 bits)
HSTK    EQU 0x5BC0              ; hook stack top (grows down; the variables end at 0x5B58)

SH      EQU 0x6000              ; shadow screen in PG (offset = screen address - 0x4000)
SA      EQU 0x7800              ; shadow attributes in PG

        ORG 0x2000

; ------------------------------------------------------------------------------------------
; plotter 2 entry: the caller decides convert / keep; B, C give the default colour
e_p2:   nextreg 0x07,3          ; the whole plot at 28 MHz (the game has no frame sync: hook time
        res 0,e                 ; would slow it down); t_p2 switches back at the plotter's RET
        ld (57709),a
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push hl
        push de
        ld a,(V_PEND)
        or a
        call nz,hidedz          ; Dizzy erased and something else drawn first: hide him now
        ld hl,(V_SP)
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; the caller's return address
        ld (V_R2),hl
        ld de,t_p2
        ld a,e
        ld hl,(V_SP)
        ld (hl),a
        inc hl
        ld (hl),d               ; the plotter returns to t_p2
        ld hl,(V_R2)
        ld de,keep
.k:     ld a,(de)
        inc de
        cp l
        ld a,(de)
        inc de
        jr nz,.n
        cp h
        jr z,.kept
.n:     or a                    ; end of the list: a zero high byte
        jr nz,.k
        ld a,1
        jr .s
.kept:  xor a
.s:     ld (V_CONV),a
        ld a,b
        and 3
        ld a,15                 ; no cell colour: bright white
        jr z,.w
        ld a,c
        xor 7
        and 7
        or 8                    ; bright ink of C ^ 7 (8 = black)
.w:     ld (V_COL),a
        pop de
        pop hl
        pop af
        ld sp,(V_SP)
        jp 57988

keep:   dw 58549, 62673, 62694, 62739, 60749   ; room renderer, score digits, lives, item name
        dw 0

; the plotters' RET lands here: put the caller's address back into the (now dead) stack slot, as
; the original leaves it, back to 3.5 MHz, return. No register or flag changes.
t_p2:   push hl                 ; SP = the slot
        ld hl,(V_R2)
        ex (sp),hl              ; slot = the caller's address, HL restored
        nextreg 0x07,0
        ret

t_dz:   push hl
        ld hl,(V_R1)
        ex (sp),hl
        nextreg 0x07,0
        ret

; Dizzy plotter entry 58113: LD (57709),A -> JP e_dz (same speed-up, return via t_dz)
e_dz:   nextreg 0x07,3
        ld (57709),a
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call dzspr              ; the sprite follows the XOR parity of Dizzy's draws
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld (V_T),hl
        ld (V_PIX),de           ; (scratch: V_PIX is refilled per byte)
        ld (V_SP),sp
        ld hl,(V_SP)
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (V_R1),de
        ld de,t_dz
        ld (hl),d
        dec hl
        ld (hl),e
        ld de,(V_PIX)
        ld a,15
        ld (V_COL),a
        ld a,(57709)            ; A as on entry (just stored there); flags untouched
        ld hl,(V_T)
        jp 58116

; ------------------------------------------------------------------------------------------
; plotter 2 screen write. Game: A = (HL) graphics, C = A, A = (DE) screen, then 58079 XOR C or
; LD A,C, 58080 LD (DE),A. Out: C = g, A = the original's result, flags as the original's.
e_p2w:  ld (V_SP),sp
        ld sp,HSTK
        push af                 ; the entry flags (LD A,C mode keeps them)
        ld a,d
        sub 0x40
        cp 0x18
        jr c,.scr
        pop af                  ; not the screen: the original instructions
        ld sp,(V_SP)
        ld a,(hl)
        ld c,a
        ld a,(de)
        jp 58079
.scr:   push hl                 ; (28 MHz since e_p2)
        push de
        push bc
        ld a,(hl)
        ld (V_G),a
        call fillpix            ; colours / interior / transparent bits of this graphics byte
        nextreg 0x53,PG
        ex de,hl                ; HL = screen
        ld a,h
        add a,0x20
        ld d,a
        ld e,l                  ; DE = its shadow byte
        ld a,(de)
        ld b,a                  ; B = objects' shadow
        nextreg 0x53,PG3
        ld a,(de)
        xor (hl)
        xor b
        ld c,a                  ; C = V = ULA ^ objects ^ Dizzy: the original's screen byte
        nextreg 0x53,PG
        ld a,(XMODE)            ; the game's instruction at 58079
        cp 0xA9
        jr nz,.m1
        ld a,(V_G)
        xor c                   ; XOR C
        jr .xf
.m1:    cp 0xB1
        jr nz,.m2
        ld a,(V_G)
        or c                    ; OR C (room renderer tiles)
        jr .xf
.m2:    ld a,(V_G)              ; LD A,C (room renderer; no other value is stored: verify checks)
        ld (V_RES),a
        xor a
        jr .fm
.xf:    ld (V_RES),a
        ld a,1
.fm:    ld (V_FM),a
        ld a,(V_RES)
        xor c                   ; D = what the original changes in this byte
        ld e,a
        ld a,(V_CONV)
        or a
        jr z,.ula
        ld a,(V_IM)
        ld (V_FX),a             ; the figure's interior toggles with it (fill shadow)
        ld a,e
        xor b
        call setsh              ; converted: the change goes to the shadow (Layer 2 follows)
        jr .out
.ula:   ld a,e
        xor (hl)
        ld (hl),a               ; kept: the change goes to the ULA, the shadow stays
.out:   nextreg 0x53,GPG
        pop bc
        ld a,(V_G)
        ld c,a
        pop de
        pop hl
        ld a,(V_FM)
        or a
        jr z,.kf
        pop af
        ld a,(V_RES)
        or a                    ; = the XOR's flags (S Z P, H N C 0, bits 3/5 of A)
        ld sp,(V_SP)
        jp 58081
.kf:    pop af
        ld a,(V_RES)
        ld sp,(V_SP)
        jp 58081

; ------------------------------------------------------------------------------------------
; Dizzy's screen write. Game: A = (DE) ^ (HL); (HL) = A. Every Dizzy write converts.
e_dw:   ld (V_SP),sp
        ld sp,HSTK
        push af
        ld a,h
        sub 0x40
        cp 0x18
        jr c,.scr
        pop af
        ld sp,(V_SP)
        ld a,(de)
        xor (hl)
        ld (hl),a
        jp 58185
.scr:   push hl                 ; (28 MHz since e_dz)
        push de
        push bc
        ld a,(de)               ; the graphics byte (slot 2/3: read before slot 3 changes)
        ld c,a
        ld b,(hl)               ; ULA
        ld a,h
        add a,0x20
        ld h,a                  ; offset in the shadow pages
        nextreg 0x53,PG
        ld a,(hl)
        xor b
        ld b,a                  ; ULA ^ objects
        nextreg 0x53,PG3
        ld a,(hl)
        ld d,a                  ; Dizzy's shadow
        xor b
        ld b,a                  ; V = the original's screen byte
        ld a,d
        xor c
        ld (hl),a               ; Dizzy's shadow ^= g (no Layer 2: he is the sprite)
        nextreg 0x53,GPG
        ld a,c
        xor b
        ld (V_RES),a            ; the original's A
        pop bc
        pop de
        pop hl
        pop af
        ld a,(V_RES)
        or a
        ld sp,(V_SP)
        jp 58185

; ------------------------------------------------------------------------------------------
; attribute routine 58702 (called from plotter 2's 57957): PUSH AF / CALL 58683 / POP AF /
; AND 127 / [58709] / LD (HL),A / RET, where the game sets 58709 = XOR (HL) (0xAE) or NOP (0x00,
; room renderer: absolute colours). Run here as a copy; the dead-stack words are the original's
; (AF at SP-2, the CALL's 58706 at SP-4); the change goes to the shadow attributes (converted) or
; the ULA (kept), so ULA ^ shadow == the original's attribute.
e_at:   ld (V_T),hl
        push af                 ; as the original's PUSH AF
        ld hl,58706
        push hl                 ; as the original's CALL 58683
        pop hl
        pop af
        ld hl,(V_T)
        ld (V_RES),a            ; A (restored by the original's POP AF)
        ld a,191                ; = 58683-58700
        sub l
        and 248
        ld h,0
        ld d,h
        ld l,a
        add hl,hl
        add hl,hl
        srl e
        add hl,de
        ld de,22528
        add hl,de
        ld a,(V_RES)
        and 127
        ld (V_G),a              ; c = the colour
        ld (V_SP),sp
        ld sp,HSTK
        push bc
        push hl
        ld a,h
        sub 0x58
        cp 3
        jr c,.att
        ld a,(58709)            ; not an attribute (never in the RZX): the original instructions
        or a
        ld a,(V_G)
        jr z,.n0
        xor (hl)
.n0:    ld (hl),a
        ld (V_RES),a
        jr .o
.att:   ld b,(hl)               ; ULA attribute
        nextreg 0x53,PG
        ld a,h
        add a,0x20
        ld h,a
        ld a,(hl)
        ld c,a                  ; shadow attribute
        xor b                   ; V = the original's attribute
        ld b,a
        ld a,(58709)
        or a
        ld a,(V_G)
        jr z,.n1                ; NOP: the original writes c
        xor b                   ; XOR (HL)
.n1:    ld (V_RES),a
        xor b                   ; the change
        ld b,a
        ld a,(V_CONV)
        or a
        jr z,.k
        ld a,c
        xor b
        ld (hl),a               ; converted: shadow attribute ^= change
        jr .u
.k:     ld a,h
        sub 0x20
        ld h,a
        ld a,b
        xor (hl)
        ld (hl),a               ; kept: ULA attribute ^= change
.u:     nextreg 0x53,GPG
.o:     pop hl
        pop bc
        ld sp,(V_SP)
        ld a,(58709)
        or a
        ld a,(V_RES)
        jr z,.fa
        or a                    ; XOR (HL): its flags
        jp 58711
.fa:    and 127                 ; NOP: the flags of the AND 127 (A < 128)
        jp 58711

; ------------------------------------------------------------------------------------------
; attribute read 58712: CALL 58683 (cell address from L = line, E = x), LD A,(HL), RET.
; The routine 58683 is run here as a copy (bytes checked); its dead-stack word is written as
; the original's CALL leaves it (58715); A = the original's attribute.
e_ar:   nextreg 0x07,3
        ld (V_T),hl
        ld hl,58715
        push hl
        pop hl
        ld hl,(V_T)
        ld a,191                ; = 58683-58700
        sub l
        and 248
        ld h,0
        ld d,h
        ld l,a
        add hl,hl
        add hl,hl
        srl e
        add hl,de
        ld de,22528
        add hl,de
        ld (V_SP),sp
        ld sp,HSTK
        push af                 ; the copy's flags
        push bc
        ld a,h
        sub 0x58
        cp 3
        jr nc,.raw
        ld b,(hl)
        nextreg 0x53,PG
        ld a,h
        add a,0x20
        ld h,a
        ld a,(hl)
        xor b
        ld b,a
        ld a,h
        sub 0x20
        ld h,a
        nextreg 0x53,GPG
        ld a,b
        jr .o
.raw:   ld a,(hl)
.o:     ld (V_T),a
        pop bc
        pop af
        ld a,(V_T)
        ld sp,(V_SP)
        nextreg 0x07,0
        ret

; ------------------------------------------------------------------------------------------
; collision reads 60244 / 60251: A = the original's screen byte, AND as the game
e_c1:   nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        call virt
        ld sp,(V_SP)
        and 240
        nextreg 0x07,0
        jp 60247

e_c2:   nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        call virt
        ld sp,(V_SP)
        and 15
        nextreg 0x07,0
        jp 60254

virt:   ld a,h                  ; HL -> A = ULA ^ objects ^ Dizzy (the screen) / (HL) (elsewhere)
        sub 0x40
        cp 0x18
        jr nc,.raw
        push bc
        ld b,(hl)
        ld a,h
        add a,0x20
        ld h,a
        nextreg 0x53,PG
        ld a,(hl)
        xor b
        ld b,a
        nextreg 0x53,PG3
        ld a,(hl)
        xor b
        ld b,a
        ld a,h
        sub 0x20
        ld h,a
        nextreg 0x53,GPG
        ld a,b
        pop bc
        ret
.raw:   ld a,(hl)
        ret

; ------------------------------------------------------------------------------------------
; room wipe 58634: lines 8-151 of the line table, columns 1-30 (the game zeroes them next)
e_wipe: nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        call hidedz             ; room wipe: Dizzy is redrawn afterwards
        ld hl,LTAB + 16
        ld b,144
        ld de,0x011E            ; D = first column 1, E = 30 columns
        call fold
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld ix,23766
        nextreg 0x07,0
        jp 58638

; room wipe 58666: attribute rows 5-22, columns 1-30 (the game overwrites them next)
e_wipea: nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        nextreg 0x53,PG
        ld hl,22688 + 1
        ld c,18
.r:     ld b,30
.c:     ld a,h
        add a,0x20
        ld d,a
        ld e,l
        ld a,(de)
        or a
        jr z,.z
        xor (hl)
        ld (hl),a               ; fold: ULA attribute ^= shadow attribute
        xor a
        ld (de),a
.z:     inc hl
        djnz .c
        inc hl
        inc hl
        dec c
        jr nz,.r
        nextreg 0x53,GPG
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld hl,22688
        nextreg 0x07,0
        jp 58669

; ------------------------------------------------------------------------------------------
; type-3 effect (55935): IX+11 = 0 scroll-copy 55955, 2 rotate right 56083, 3 rotate left 56169,
; all on line-table lines IX+9..IX+10 and columns IX+7..IX+8: fold that rectangle first.
e_f3:   nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld a,(ix+11)
        or a
        jr z,.go
        cp 2
        jr z,.go
        cp 3
        jr nz,.no
.go:    ld a,(ix+10)
        sub (ix+9)
        inc a
        ld b,a                  ; lines
        ld a,(ix+8)
        sub (ix+7)
        inc a
        ld e,a                  ; columns
        ld d,(ix+7)
        ld a,(ix+9)
        call lineptr
        call fold
.no:    pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld a,(ix+11)
        nextreg 0x07,0
        jp 55938

; type-7 rotator (57095): 8 lines from IX+11, IX+12 bytes from column IX+10
e_f7:   nextreg 0x07,3
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        ld b,8
        ld e,(ix+12)
        ld d,(ix+10)
        ld a,(ix+11)
        call lineptr
        call fold
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld c,(ix+11)
        nextreg 0x07,0
        jp 57098

lineptr: ld l,a                 ; A = line index -> HL = LTAB + 2A
        ld h,0
        add hl,hl
        push de
        ld de,LTAB
        add hl,de
        pop de
        ret

; fold B lines (line-table pointer HL), E columns from column D: wherever the shadow has bits,
; move them to the ULA (ULA ^= shadow, shadow = 0, Layer 2 cleared). Exact: ULA ^ shadow is kept.
fold:   nextreg 0x53,PG
        ld a,e
        or a
        jr z,.end
.line:  push bc
        push hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        add a,d
        ld l,a
        jr nc,.nc
        inc h
.nc:    ld b,e
.byte:  ld a,h                  ; (rows past line 191 read game data as addresses: checked)
        sub 0x40
        cp 0x18
        jr nc,.skip
        push bc
        push de
        add a,0x60
        ld d,a
        ld e,l                  ; DE = the byte's offset in the shadow pages
        nextreg 0x53,PG3
        ld a,(de)
        or a
        jr z,.nd
        ld b,a
        xor a
        ld (de),a               ; Dizzy's bits to the ULA, his shadow byte 0
        ld a,b
        xor (hl)
        ld (hl),a
.nd:    nextreg 0x53,PG2
        ld a,(de)
        ld (V_FX),a             ; fill bits (cleared by setsh)
        nextreg 0x53,PG
        ld a,(de)
        ld c,a                  ; ink bits
        ld a,(V_FX)
        or c
        jr z,.s2
        ld a,c
        xor (hl)
        ld (hl),a               ; the ULA takes the figure's ink bits
        xor a
        call setsh              ; ink and fill 0, Layer 2 cleared
.s2:    pop de
        pop bc
.skip:  inc hl
        djnz .byte
        pop hl
        inc hl
        inc hl
        pop bc
        djnz .line
.end:   nextreg 0x53,GPG
        ret

; ------------------------------------------------------------------------------------------
; setsh: PG mapped; HL = screen address, A = the new ink shadow byte, V_FX = fill bits to XOR.
; Redraws the Layer 2 pixels whose ink or (visible) fill changed: ink -> V_PIX[bit]; else fill ->
; V_PIX[bit] when it is this graphic's own interior, else black; else 0 (transparent); a bit in
; V_CL (painted transparent) -> 0. Keeps HL; PG mapped again at exit. Clobbers AF, BC, DE.
setsh:  push hl
        ld e,a                  ; new ink
        ld a,h
        add a,0x20
        ld h,a
        ld a,(hl)
        ld (hl),e
        xor e
        ld d,a                  ; ink changes
        ld a,e
        ld (V_NI),a
        nextreg 0x53,PG2
        ld a,(V_FX)
        ld c,a
        xor (hl)
        ld (hl),a               ; fill ^= V_FX
        ld (V_NF),a
        ld a,e
        cpl
        and c                   ; fill changes not covered by ink
        or d
        pop hl
        jr nz,.go
        nextreg 0x53,PG
        ret
.go:    ld d,a                  ; D = pixels to redraw
        push hl
        ld a,h                  ; H = 010 y7 y6 y2 y1 y0, L = y5 y4 y3 x4..x0
        and 0x18
        rrca
        rrca
        ld b,a                  ; (y >> 6) << 1
        ld a,l
        rlca                    ; carry = y5
        ld a,b
        adc a,L2PG
        nextreg 0x53,a          ; Layer 2 page of lines (y & ~31)
        ld a,l
        and 0x60
        rrca
        rrca
        ld b,a
        ld a,h
        and 7
        or b
        or 0x60
        ld b,a                  ; 0x60 + (y & 31)
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld c,a                  ; x of the byte's first pixel
        ld hl,V_PIX
        ld e,0x80
.bit:   ld a,d
        and e
        jr z,.next
        ld a,(V_NI)
        and e
        jr z,.nf
        ld a,(V_CL)             ; ink
        and e
        jr nz,.zero
        ld a,(V_HAS)
        or a
        ld a,(V_COL)            ; default: the plot's colour
        jr z,.w
        ld a,(hl)
        jr .w
.nf:    ld a,(V_NF)
        and e
        jr z,.zero
        ld a,(V_IM)             ; fill: this graphic's interior?
        and e
        jr z,.blk
        ld a,(V_CL)
        and e
        jr nz,.zero
        ld a,(V_HAS)
        or a
        jr z,.blk               ; default: black
        ld a,(hl)
        jr .w
.blk:   ld a,8                  ; another figure's interior: black
        jr .w
.zero:  xor a
.w:     ld (bc),a
.next:  inc hl
        inc c
        rrc e
        jr nc,.bit
        nextreg 0x53,PG
        pop hl
        ret

; fillpix: HL = graphics address -> V_PIX[0..7] = V_COL, or the painted colour of each bit
; (colour plane: 4 bytes per graphics byte, bit 0 in the high nibble of the first byte).
; Leaves a plane page at slot 3 when the map is on (the caller maps PG next). Keeps HL.
; fillpix: HL = graphics address, V_G = its byte, V_COL = the plot's ink default -> V_IM, V_CL and
; V_HAS from the plane (8 bytes per graphics byte; plotter-2 graphics first, then Dizzy's: 4 colour
; bytes, interior, transparent, has-colours); with colours V_PIX[0..7] (painted nibble, else V_COL
; for ink bits, black for the others). Leaves a plane page at slot 3 (the caller maps PG next).
fillpix: push hl
        push de
        push bc
        xor a
        ld (V_IM),a
        ld (V_CL),a
        ld (V_HAS),a
        ld de,P2BASE
        or a
        sbc hl,de
        jr c,.dz
        ld de,P2LEN
        or a
        sbc hl,de
        jr c,.p2
        jr .ret
.p2:    add hl,de               ; index = address - P2BASE
        jr .idx
.dz:    add hl,de               ; back to the address
        ld de,DZBASE
        or a
        sbc hl,de
        jr c,.ret
        ld de,DZLEN
        or a
        sbc hl,de
        jr nc,.ret
        ld de,DZLEN + P2LEN     ; index = P2LEN + address - DZBASE
        add hl,de
.idx:   ld a,h
        rrca
        rrca
        and 0x3F
        add a,PLPG
        nextreg 0x53,a          ; page = PLPG + index / 1024
        ld a,h
        and 3
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,h
        or 0x60
        ld h,a                  ; 0x6000 + (index % 1024) * 8
        push hl
        ld de,4
        add hl,de
        ld a,(hl)
        ld (V_IM),a
        inc hl
        ld a,(hl)
        ld (V_CL),a
        inc hl
        ld a,(hl)               ; 1 = painted colours in this entry
        pop hl
        or a
        jr z,.ret               ; none: setsh uses the defaults
        ld (V_HAS),a
        ld a,(V_G)
        ld c,a
        ld de,V_PIX
        ld b,8
.d:     ld a,8                  ; not ink: black (fill default)
        sla c
        jr nc,.d1
        ld a,(V_COL)
.d1:    ld (de),a
        inc de
        djnz .d
        ld de,V_PIX
        ld b,4
.e:     ld a,(hl)
        rrca
        rrca
        rrca
        rrca
        and 15
        jr z,.e1
        ld (de),a
.e1:    inc de
        ld a,(hl)
        and 15
        jr z,.e2
        ld (de),a
.e2:    inc de
        inc hl
        djnz .e
.ret:   pop bc
        pop de
        pop hl
        ret

; ------------------------------------------------------------------------------------------
; Dizzy sprite (entry of a Dizzy plot: A = frame 0-38, E = x in 4-pixel units, L = y from the
; bottom). The original draws nothing when y + rows >= 200 (no parity change). The same image as
; the one shown, shown and not pending = the erase: keep it on screen (the draw follows: no
; flicker), pending; anything else = a draw: show it there.
dzspr:  ld c,a                  ; frame
        ld b,l                  ; y
        ld d,e                  ; x
        ld h,0
        ld l,a
        push de
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,de               ; frame * 9
        ld de,dztab
        add hl,de
        pop de
        ld a,(hl)               ; rows
        add a,b                 ; (8 bits, carry ignored: as the plotter's ADD A,B / CP 200)
        cp 200
        ret nc
        ld a,(V_VIS)
        or a
        jr z,.draw
        ld a,(V_PEND)
        or a
        jr nz,.draw
        ld a,(V_SF)
        cp c
        jr nz,.draw
        ld a,(V_SX)
        cp d
        jr nz,.draw
        ld a,(V_SY)
        cp b
        jr nz,.draw
        ld a,1
        ld (V_PEND),a           ; the erase
        ret
.draw:  ld a,c
        ld (V_SF),a
        ld a,d
        ld (V_SX),a
        ld a,b
        ld (V_SY),a
        ld a,1
        ld (V_VIS),a
        xor a
        ld (V_PEND),a
        ld a,(hl)
        add a,b
        ld e,a
        ld a,224
        sub e
        ld (V_YY),a             ; 192 - y - rows + 32
        push hl
        ld h,0
        ld l,d
        add hl,hl
        add hl,hl
        ld de,32
        add hl,de
        ld (V_XX),hl            ; 4x + 32
        pop hl
        inc hl                  ; 4 x (attribute 3, attribute 4): TL, TR, BL, BR
        ld c,0
.q:     ld a,c
        nextreg 0x34,a
        push hl
        ld hl,(V_XX)
        bit 0,c
        jr z,.x0
        ld de,16
        add hl,de
.x0:    ld a,l
        nextreg 0x35,a
        ld a,h
        and 1
        nextreg 0x37,a          ; X bit 8, no mirror / rotation
        ld a,(V_YY)
        bit 1,c
        jr z,.y0
        add a,16
.y0:    nextreg 0x36,a
        pop hl
        ld a,(hl)
        inc hl
        nextreg 0x38,a          ; visible + pattern (0: an empty quarter, hidden)
        ld a,(hl)
        inc hl
        nextreg 0x39,a
        inc c
        ld a,c
        cp 4
        jr nz,.q
        ret

hidedz: push af                 ; hide Dizzy's sprites (keeps every register and flag)
        nextreg 0x34,0
        nextreg 0x38,0
        nextreg 0x34,1
        nextreg 0x38,0
        nextreg 0x34,2
        nextreg 0x38,0
        nextreg 0x34,3
        nextreg 0x38,0
        xor a
        ld (V_VIS),a
        ld (V_PEND),a
        pop af
        ret

dztab:  ds 39 * 9               ; per frame: rows, then 4 x (attr 3, attr 4) - filled by dizzy1.py
rom_end:

; ---- setup (stub bank, 0xD000): Layer 2 bank, palette, visible -----------------------------
        ORG 0xD000
setup:  nextreg 0x12,L2B        ; Layer 2 at banks 16-18 (zero in the .nex)
        nextreg 0x43,0x10       ; Layer 2 palette 0, auto-increment
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        ld bc,0x123B
        ld a,2                  ; Layer 2 visible, no write mapping
        out (c),a
        nextreg 0x43,0x20       ; sprite palette 0: the same 16 colours (index 0 transparent)
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.s:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .s
        nextreg 0x4B,0          ; sprite transparency index 0
        nextreg 0x54,SPP        ; patterns: pages 30-31 at slots 4-5 for the upload
        nextreg 0x55,SPP + 1
        ld bc,0x303B
        xor a
        out (c),a               ; pattern slot 0
        ld hl,0x8000
        ld c,0x5B
        ld d,64                 ; 64 x 256 bytes = 128 4-bit patterns
.u:     ld b,0
        otir
        dec d
        jr nz,.u
        nextreg 0x54,4          ; game pages back
        nextreg 0x55,5
        xor a
.h:     nextreg 0x34,a          ; every sprite hidden
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01       ; sprites on, order SLU: Dizzy over Layer 2 over the ULA
        ret
pal:                            ; 16 palette bytes appended by dizzy1.py (index 0 = 0xE3: Layer 2
                                ; transparent; as a sprite colour index 0 is transparent anyway)

        SAVEBIN "d1_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "d1_setup.bin",0xD000,pal-0xD000
