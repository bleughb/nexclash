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
; which put it back (the dead stack slot holds what the original leaves) and return at the caller's speed:
; the game has no frame sync, so the hooks must not add time (they make a plot slightly faster).
;   58076 7E 4F 1A        LD A,(HL)/LD C,A/LD A,(DE) -> JP e_p2w  plotter 2 screen write
;   58182 1A AE 77        LD A,(DE)/XOR (HL)/LD (HL),A -> JP e_dw Dizzy's screen write
;   58702 F5 CD 3B        PUSH AF / CALL 58683       -> JP e_at   attribute routine (58709 is the game's)
;   58712 CD 3B E5        CALL 58683                 -> JP e_ar   attribute read (+ LD A,(HL), RET)
;   60228 C5 E5 3A        PUSH BC / PUSH HL / LD A,  -> JP e_col  collision read (whole routine, 29 bytes checked)
;   58634 DD 21 D6 5C     LD IX,23766                -> JP e_wipe room wipe (pixels)
;   58666 21 A0 58        LD HL,22688                -> JP e_wipea room wipe (attributes)
;   55935 DD 7E 0B        LD A,(IX+11)               -> JP e_f3   type-3 effect dispatch
;   57095 DD 4E 0B        LD C,(IX+11)               -> JP e_f7   type-7 rotator

        DEVICE ZXSPECTRUMNEXT
        INCLUDE "lib/hlib_speed.asm"
        INCLUDE "lib/hlib_iff.asm"
        IFNDEF DZ_ENHANCED
        DEFINE HLIB_PACE_LEAN
        ENDIF
HLIB_V_PACE EQU 0x7B80          ; 26 zero-initialised bytes in shadow page PG
HLIB_PACE_NL EQU 312
V_F7_TARGET EQU 0x7B9A

; DZ_SPEED_IN: the caller's NR 7 into V_RAW, then 28 MHz, as the hook's FIRST instructions (1.0 switched
; there; lib/hlib_speed's HLIB_SPEED_IN needs the hook stack, so it ran after the stack switch and cost
; 97 T at 3.5 MHz: the game has no frame sync, so 1.1 played ~1.6% slower). 51 T at the incoming clock,
; no stack (the game's dead stack stays the original's), every register and flag kept (IN A,(n) keeps
; the flags). Port 0x243B selects NR 7 already: setup selects it, and spdfix selects it again whenever a
; read was not NR 7. spd_p / spd_d / spd_h then latch V_RAW on the hook stack, at 28 MHz.
        MACRO DZ_SPEED_IN
        ld (V_A),a
        ld a,0x25
        in a,(0x3B)             ; port 0x253B: NR 7 (bits 5-4 the actual speed, 1-0 the programmed one)
        nextreg 0x07,3
        ld (V_RAW),a
        ld a,(V_A)
        ENDM

PG      EQU 26                  ; shadow page (slot 3 during hooks): ink shadow + shadow attributes
PG2     EQU 27                  ; fill shadow (figures' enclosed paper, display only)
PG3     EQU 28                  ; Dizzy's shadow (his XOR bits; he is shown as hardware sprites 0-3)
SPP     EQU 30                  ; sprite patterns: pages 30-31 (uploaded once by setup)
GPG     EQU 11                  ; the game's page at slot 3 (48K: bank 5 upper half)
L2B     EQU 16                  ; Layer 2 16K bank -> 8K pages L2PG..L2PG+5
L2PG    EQU 32
PLPG    EQU 40                  ; plane pages 40-54: 8 bytes per graphics byte = 8 colour nibbles (0 =
                                ; default), interior mask (enclosed paper), transparent mask
BGFLAG  EQU 78                  ; dirty scenery bytes, bank 39
BGPG    EQU 80                  ; Enhanced scenery colours, six 8K pages (banks 40-42)
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
V_SPDP  EQU 0x5B66              ; the caller's CPU speed (lib/hlib_speed.asm latches): plotter 2 (e_p2 .. t_p2),
V_SPDD  EQU 0x5B67              ; the Dizzy plotter (e_dz .. t_dz),
V_SPDH  EQU 0x5B68              ; every other hook (entry to exit inside the hook)
V_A     EQU 0x5B69              ; A while an entry reads / an exit restores the speed (no flags)
V_RAW   EQU 0x5B6A              ; the NR 7 byte DZ_SPEED_IN read (spdfix latches it)
HLIB_V_R EQU 0x5B6B             ; refresh checkpoint / target / saved A (no nested window)
V_BGPIX EQU 0x5B6E
V_NB    EQU 0x5B6F
V_LPAGE EQU 0x5B70
V_COVER EQU 0x5B71
V_BG    EQU 0x5B72              ; one byte of scenery, eight palette indices
HSTK    EQU 0x5BC0              ; hook stack top (grows down; the variables end at 0x5B6A)

        MACRO DZ_R_BEGIN delta
        ; Rotate bit 7 into bit 0, add an even delta, rotate back: the low seven
        ; bits wrap while bit 7 survives. No BC save is needed on this byte path.
        push af
        ld a,r
        rlca
        add a,((delta)*2) & 255
        rrca
        ld (HLIB_V_R + 1),a
        pop af
        ENDM

        MACRO DZ_R_DIRTY_AF delta
        ; The displaced code overwrites AF. No redundant AF save on this byte path.
        ld a,r
        rlca
        add a,((delta+1)*2) & 255
        rrca
        ld (HLIB_V_R + 1),a
        ENDM

        MACRO DZ_R_KEEP_FLAGS delta
        ; Leave the original AF on the hook stack for the plot mode's epilogue.
        push af
        ld a,r
        rlca
        add a,((delta)*2) & 255
        rrca
        ld (HLIB_V_R + 1),a
        ENDM

        MACRO DZ_R_SPEED_OUT latch
        ; Set R while still fast. Only the shared speed restore and the final A load
        ; follow it: three more M1s than HLIB_R_OUT, accounted for by the entry delta.
        ld (V_A),a
        ld a,(HLIB_V_R + 1)
        ld r,a
        HLIB_SPEED_OUT_A latch
        ld a,(V_A)
        ENDM

SH      EQU 0x6000              ; shadow screen in PG (offset = screen address - 0x4000)
SA      EQU 0x7800              ; shadow attributes in PG

        ORG 0x2000
        INCLUDE "lib/hlib_r.asm"

; ------------------------------------------------------------------------------------------
; plotter 2 entry: the caller decides convert / keep; B, C give the default colour
e_p2:   DZ_SPEED_IN             ; the whole plot at 28 MHz (the game has no frame sync: hook time
        res 0,e                 ; would slow it down); t_p2 gives the caller's speed back at the plotter's RET
        ld (57709),a
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -16
        call spd_p
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
        HLIB_R_OUT
        jp 57988

keep:   dw 58549, 62673, 62694, 62739, 60749   ; room renderer, score digits, lives, item name
        dw 0

; the plotters' RET lands here: put the caller's address back into the (now dead) stack slot, as
; the original leaves it, back to 3.5 MHz, return. No register or flag changes.
t_p2:   ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -11
        ld sp,(V_SP)
        push hl                 ; SP = the slot
        ld hl,(V_R2)
        ex (sp),hl              ; slot = the caller's address, HL restored
        DZ_R_SPEED_OUT V_SPDP
        ret

t_dz:   ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -11
        ld sp,(V_SP)
        push hl
        ld hl,(V_R1)
        ex (sp),hl
        DZ_R_SPEED_OUT V_SPDD
        ret

; Dizzy plotter entry 58113: LD (57709),A -> JP e_dz (same speed-up, return via t_dz)
e_dz:   DZ_SPEED_IN
        ld (57709),a
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -16
        call spd_d
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
        HLIB_R_OUT
        jp 58116

; ------------------------------------------------------------------------------------------
; plotter 2 screen write. Game: A = (HL) graphics, C = A, A = (DE) screen, then 58079 XOR C or
; LD A,C, 58080 LD (DE),A. Out: C = g, A = the original's result, flags as the original's.
e_p2w:  ld (V_SP),sp
        ld sp,HSTK
        DZ_R_KEEP_FLAGS -4       ; original flags remain on the hook stack
        ld a,d
        sub 0x40
        cp 0x18
        jr c,.scr
        ld a,126                ; rare non-screen path displaces two fewer M1 cycles
        call hlib_r_add
        pop af                  ; not the screen: the original instructions
        ld sp,(V_SP)
        ld a,(hl)
        ld c,a
        ld a,(de)
        HLIB_R_OUT
        jp 58079
.scr:   push hl                 ; (28 MHz since e_p2)
        push de
        push bc
        ld a,(hl)
        ld (V_G),a
        IFDEF DZ_ENHANCED
        ld a,(V_CONV)
        or a
        jp nz,.normal
        ; A kept tile over no figure bits needs no virtual-screen reconstruction
        ; or interior masks. Check all three shadows before taking this route.
        push hl
        ld a,d
        add a,0x20
        ld h,a
        ld l,e
        nextreg 0x53,PG
        ld a,(hl)
        ld c,a
        nextreg 0x53,PG2
        ld a,(hl)
        or c
        ld c,a
        nextreg 0x53,PG3
        ld a,(hl)
        or c
        pop hl
        jp nz,.normal
        ; Empty kept pixels on an already empty background need no colour copy.
        ; Check the validity flag too: zero ULA ink can still have old overlay paint.
        ld a,(V_G)
        or a
        jr nz,.kept_colour
        ld a,(de)
        or a
        jr nz,.kept_colour
        push hl
        ld a,d
        add a,0x20
        ld h,a
        ld l,e
        nextreg 0x53,BGFLAG
        ld a,(hl)
        pop hl
        or a
        jr nz,.kept_colour
        ld (V_RES),a
        ld a,(XMODE)
        cp 0x79
        ld a,0
        jr z,.empty_flags
        inc a
.empty_flags:
        ld (V_FM),a
        jp .out
.kept_colour:
        call keptcolour
        jp nc,.normal           ; incomplete/unmapped colours use the general path
        ld a,(XMODE)
        cp 0x79
        jr z,.kept_ld
        cp 0xB1
        ld a,(de)
        ld c,a
        ld a,(V_G)
        jr z,.kept_or
        xor c
        jr .kept_result
.kept_or:
        or c
.kept_result:
        ld (V_RES),a
        ld (de),a
        ld (V_NB),a
        ld a,1
        jr .kept_draw
.kept_ld:
        ld a,(V_G)
        ld (V_RES),a
        ld (de),a
        ld (V_NB),a
        xor a
.kept_draw:
        ld (V_FM),a
        ex de,hl
        call bgpaint_fast
        jp .out
.normal:
        ENDIF
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
        IFDEF DZ_ENHANCED
        or e                    ; no ink or fill changes: all display/shadow bytes already agree
        jr z,.out
        ENDIF
        ld a,e
        xor b
        call setsh              ; converted: the change goes to the shadow (Layer 2 follows)
        jr .out
.ula:   ld a,e
        xor (hl)
        ld (hl),a               ; kept: the change goes to the ULA, the shadow stays
        IFDEF DZ_ENHANCED
        ld (V_NB),a
        call bgpaint
        ENDIF
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
        HLIB_R_OUT
        jp 58081
.kf:    pop af
        ld a,(V_RES)
        ld sp,(V_SP)
        HLIB_R_OUT
        jp 58081

; ------------------------------------------------------------------------------------------
; Dizzy's screen write. Game: A = (DE) ^ (HL); (HL) = A. Every Dizzy write converts.
e_dw:   ld (V_SP),sp
        ld sp,HSTK
        DZ_R_DIRTY_AF -6
        ld a,h
        sub 0x40
        cp 0x18
        jr c,.scr
        ld sp,(V_SP)
        ld a,(de)
        xor (hl)
        ld (hl),a
        HLIB_R_OUT
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
        push hl
        ld a,h
        sub 0x60
        ld l,a
        ld h,0x7B
        ld (hl),1
        pop hl
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
        pop bc
        pop de
        pop hl
        or a
        ld sp,(V_SP)
        HLIB_R_OUT
        jp 58185

; ------------------------------------------------------------------------------------------
; attribute routine 58702 (called from plotter 2's 57957): PUSH AF / CALL 58683 / POP AF /
; AND 127 / [58709] / LD (HL),A / RET, where the game sets 58709 = XOR (HL) (0xAE) or NOP (0x00,
; room renderer: absolute colours). Run here as a copy; the dead-stack words are the original's
; (AF at SP-2, the CALL's 58706 at SP-4); the change goes to the shadow attributes (converted) or
; the ULA (kept), so ULA ^ shadow == the original's attribute.
e_at:   ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN 11
        ld sp,(V_SP)
        ld (V_T),hl
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
        HLIB_R_OUT
        jp 58711
.fa:    and 127                 ; NOP: the flags of the AND 127 (A < 128)
        HLIB_R_OUT
        jp 58711

; ------------------------------------------------------------------------------------------
; attribute read 58712: CALL 58683 (cell address from L = line, E = x), LD A,(HL), RET.
; The routine 58683 is run here as a copy (bytes checked); its dead-stack word is written as
; the original's CALL leaves it (58715); A = the original's attribute.
e_ar:   DZ_SPEED_IN             ; the copy below runs at 28 MHz too
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_DIRTY_AF -2
        ld sp,(V_SP)
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
        call spd_h
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
        ld sp,(V_SP)
        ld a,(V_T)
        DZ_R_SPEED_OUT V_SPDH
        ret

; ------------------------------------------------------------------------------------------
; collision read 60228 (CALL from 56647 / 60037 / 60099): the whole routine as a copy (bytes checked),
; at 28 MHz: PUSH BC / PUSH HL (the dead-stack words, as the original leaves them), C = (59263), HL -= BC,
; SRL C, HL += BC, A = the original's screen byte (virtual: ULA ^ objects ^ Dizzy) AND 240 (carry clear)
; or AND 15 (carry set), POP HL / POP BC / RET (was a hook per read, 60244 / 60251: the routine at 3.5 MHz).
e_col:  DZ_SPEED_IN
        push bc                 ; the original's PUSH BC / PUSH HL (game stack)
        push hl
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_DIRTY_AF -4
        call spd_h
        ld a,(59263)
        ld c,a
        ld b,0
        and a
        sbc hl,bc
        srl c
        jr c,.lo
        add hl,bc
        call virt
        and 240
        jr .x
.lo:    add hl,bc
        call virt
        and 15
.x:     ld sp,(V_SP)
        pop hl
        pop bc
        DZ_R_SPEED_OUT V_SPDH
        ret

; the latch from V_RAW (DZ_SPEED_IN's read), on the hook stack at 28 MHz; every register and flag kept.
; A read without NR 7's layout (bits 7-6 and 3-2 zero) means the selection was moved (an NMI, say):
; the latch keeps its last speed and NR 7 is selected again for the next hook.
spd_p:  push hl
        ld hl,V_SPDP
        jr spdfix
spd_d:  push hl
        ld hl,V_SPDD
        jr spdfix
spd_h:  push hl
        ld hl,V_SPDH
spdfix: push af
        ld a,(V_RAW)
        and 0xCC
        jr nz,.sel
        ld a,(V_RAW)
        and 3
        ld (hl),a
        pop af
        pop hl
        ret
.sel:   push bc
        ld bc,0x243B
        ld a,7
        out (c),a
        pop bc
        pop af
        pop hl
        ret

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
e_wipe: DZ_SPEED_IN
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -14           ; the complete original wipe, not just its first LD IX
        call spd_h
        push af
        push bc
        push de
        push hl
        call hidedz             ; room wipe: Dizzy is redrawn afterwards
        nextreg 0x53,PG
        call hlib_pace_open
        nextreg 0x53,GPG
        call clearroom
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld ix,23766
        ; The original wipe's instructions, unchanged, at the drawing clock. Its
        ; PUSH BC uses the game stack and leaves the same dead stack bytes.
        ld b,144
        xor a
.row:   push bc
        ld l,(ix+0)
        ld h,(ix+1)
        ld bc,1
        add hl,bc
        ld b,30
.byte:  ld (hl),a
        inc hl
        djnz .byte
        inc ix
        inc ix
        pop bc
        djnz .row
        ld (V_SP),sp
        ld sp,HSTK
        push af
        push bc
        push de
        push hl
        nextreg 0x53,PG
        ld hl,9208              ; original 128,910 T / 14 T per sixteenth-line
        IFNDEF DZ_ENHANCED
        HLIB_SPEED_OUT_A V_SPDH
        call hlib_pace_wait
        nextreg 0x07,3
        ENDIF                   ; Enhanced repays its room painting from this drawing window
        nextreg 0x53,GPG
        ld bc,0x243B
        ld a,7
        out (c),a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        DZ_R_SPEED_OUT V_SPDH
        ret

; A room wipe will erase the original pixels too, so no XOR fold is needed.
; Clear the shadows and the visible overlay in rows. The scenery backing store
; is invalidated through BGFLAG; its old bytes are never read while invalid.
clearroom:
        ld hl,LTAB+16
        ld b,144
.row:   push bc
        push hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
        inc hl
        nextreg 0x53,PG
        call .shadow
        nextreg 0x53,PG2
        call .shadow
        nextreg 0x53,PG3
        call .shadow
        IFDEF DZ_ENHANCED
        nextreg 0x53,BGFLAG
        call .shadow
        ENDIF
        call pixelptr
        nextreg 0x53,a
        ld h,b
        ld l,c
        ld b,30
        xor a
.pixels:
        DUP 8
        ld (hl),a
        inc l
        EDUP
        djnz .pixels
        nextreg 0x53,GPG
        pop hl
        inc hl
        inc hl
        pop bc
        ld a,b
        and 15
        jr nz,.next
        push bc
        push hl
        nextreg 0x53,PG
        call hlib_pace_tick      ; a long room clear may span several display frames
        nextreg 0x53,GPG
        pop hl
        pop bc
.next:  djnz .row
        ret
.shadow:
        push hl
        ld a,h
        add a,0x20
        ld h,a
        ld b,30
        xor a
        IFDEF DZ_ENHANCED
        DUP 30
        ld (hl),a
        inc l
        EDUP
        ELSE
.zero:  ld (hl),a
        inc l
        djnz .zero
        ENDIF
        pop hl
        ret

; room wipe 58666: attribute rows 5-22, columns 1-30 (the game overwrites them next)
e_wipea: DZ_SPEED_IN
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -18
        call spd_h
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
        DZ_R_SPEED_OUT V_SPDH
        jp 58669

; ------------------------------------------------------------------------------------------
; type-3 effect (55935): IX+11 = 0 scroll-copy 55955, 2 rotate right 56083, 3 rotate left 56169,
; all on line-table lines IX+9..IX+10 and columns IX+7..IX+8: fold that rectangle first.
e_f3:   DZ_SPEED_IN
        ld (V_SP),sp
        ld sp,HSTK
        IFDEF DZ_ENHANCED
        DZ_R_BEGIN -14
        ELSE
        DZ_R_BEGIN -17
        ENDIF
        call spd_h
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
.no:
        IFDEF DZ_ENHANCED
        nextreg 0x53,PG
        call hlib_pace_open
        nextreg 0x53,GPG
        ENDIF
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        ld a,(ix+11)
        IFDEF DZ_ENHANCED
        HLIB_R_OUT              ; keep the original screen-copy/rotate loop at drawing speed
        ELSE
        DZ_R_SPEED_OUT V_SPDH
        ENDIF
        jp 55938

        IFDEF DZ_ENHANCED
; Every exit from the original type-3 drawing routine restores the incoming clock.
t_f3:   ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -11
        push af
        push bc
        push de
        push hl
        nextreg 0x53,PG
        call hlib_pace_tick
        ld hl,(HLIB_V_PACE+2)
        ld a,40                ; 5/16 of original drawing time; the rest repays colour work
        call hlib_mul8
        HLIB_SPEED_OUT_A V_SPDH
        call hlib_pace_wait
        nextreg 0x07,3
        nextreg 0x53,GPG
        ld bc,0x243B
        ld a,7
        out (c),a
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        DZ_R_SPEED_OUT V_SPDH
        jp 54710
        ENDIF

; type-7 rotator (57095): 8 lines from IX+11, IX+12 bytes from column IX+10
e_f7:   DZ_SPEED_IN
        ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -14
        call spd_h
        push af
        push bc
        push de
        push hl
        nextreg 0x53,PG
        call hlib_pace_open
        ; The original rotator costs 888*width+1083 T (minus up to 8 carry cycles).
        ; Repay the other drawing hooks' measured cost from this drawing window:
        ; default keeps 90%, Enhanced 70% (its extra scenery/colour work is outside).
        ; This is a minimum drawing window, not a change to movement or delays.
        ld e,(ix+12)
        IFDEF DZ_ENHANCED
        ld d,44
        ELSE
        ld d,57
        ENDIF
        mul d,e
        ex de,hl
        IFDEF DZ_ENHANCED
        ld de,54
        ELSE
        ld de,70
        ENDIF
        add hl,de
        ld a,(ix+12)
        cp 2
        jr nc,.target
        IFDEF DZ_ENHANCED
        ld de,11264
        ELSE
        ld de,14592
        ENDIF                   ; original DJNZ: widths 0/1 mean 256/257 here
        add hl,de
.target:
        ld (V_F7_TARGET),hl
        nextreg 0x53,GPG
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
        HLIB_R_OUT              ; original screen rotator stays at 28 MHz
        jp 57098

; The original routine's final JP is redirected here. Wait at the incoming clock so
; the ROM interrupt handler keeps its usual clock during the limiting interval.
t_f7:   ld (V_SP),sp
        ld sp,HSTK
        DZ_R_BEGIN -11
        push af
        push bc
        push de
        push hl
        nextreg 0x53,PG
        ld hl,(V_F7_TARGET)
        HLIB_SPEED_OUT_A V_SPDH
        call hlib_pace_wait
        nextreg 0x07,3
        nextreg 0x53,GPG
        ld bc,0x243B
        ld a,7
        out (c),a               ; keep the fast entry latch's selected-register invariant
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(V_SP)
        DZ_R_SPEED_OUT V_SPDH
        jp 54710

        INCLUDE "lib/hlib_pace.asm"

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
        IFDEF DZ_ENHANCED
        call bgrowclear         ; test the dirty flags with one mapping per row
        ENDIF
        ld a,h
        sub 0x40
        cp 0x18
        jr nc,.byte
        push hl
        ld l,a
        ld h,0x7B
        ld a,(hl)               ; conservative slab occupancy: never skip possible figure bits
        pop hl
        or a
        jr nz,.byte
        ld a,l
        add a,e
        jr c,.byte              ; a row crossing a 256-byte boundary needs individual checks
        jr .linedone
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
.linedone:
        pop hl
        inc hl
        inc hl
        pop bc
        djnz .line
.end:   nextreg 0x53,GPG
        ret

; Rebuild conservative slab occupancy after a room wipe. Title animation can have touched
; every slab; retaining those stale hints would disable the fast empty-scenery path in play.
recache:
        ld hl,0x6000
        ld c,24
.slab:  nextreg 0x53,PG
        call .scan
        or a
        jr nz,.mark
        nextreg 0x53,PG2
        call .scan
        or a
        jr nz,.mark
        nextreg 0x53,PG3
        call .scan
.mark:  nextreg 0x53,PG
        ld d,a
        ld a,h
        sub 0x60
        push hl
        ld l,a
        ld h,0x7B
        ld (hl),d
        pop hl
        inc h
        dec c
        jr nz,.slab
        nextreg 0x53,GPG
        ret
.scan:  push hl
        ld b,0
        xor a
.byte:  or (hl)
        inc hl
        djnz .byte
        pop hl
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
        push hl
        ld a,h
        sub 0x60
        ld l,a
        ld h,0x7B
        ld (hl),1               ; this 256-byte screen slab may contain figure bits
        pop hl
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
        IFDEF DZ_ENHANCED
        ld (V_LPAGE),a
        ENDIF
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
        IFDEF DZ_ENHANCED
        call bgcache
        ENDIF
        ld a,(V_NI)
        ld e,a
        ld a,(V_NF)
        or e
        jr nz,.maybe_draw
        ; Nothing remains in this byte: publish its scenery in one burst.
        ld d,b
        ld e,c
        IFDEF DZ_ENHANCED
        ld a,(V_BGPIX)
        or a
        jr z,.blank
        ld hl,V_BG
        DUP 8
        ldi
        EDUP
        jp .done
.blank:
        ENDIF
        xor a
        DUP 7
        ld (de),a
        inc de
        EDUP
        ld (de),a
        jp .done
.maybe_draw:
        IFDEF DZ_ENHANCED
        cp d                    ; all visible bits are newly changed (no older figure)
        jp nz,.generic
        ld a,(V_HAS)
        cp 2
        jp nz,.generic
        ld a,(V_CL)
        or a
        jp nz,.generic
        ld a,(V_G)
        cp e                    ; new ink is this graphic, not an XOR overlap
        jp nz,.generic
        ld a,(V_IM)
        ld e,a
        ld a,(V_NF)
        cp e
        jp nz,.generic
        ld d,b
        ld e,c
        ld hl,V_PIX
        ld a,(V_BGPIX)
        or a
        jr nz,.blend
        DUP 8
        ldi
        EDUP
        jp .done
.blend:
        push de
        ld hl,V_BG
        DUP 8
        ldi
        EDUP
        pop de
        ld hl,V_PIX
        xor a
        DUP 8
        ldix                    ; figure holes retain the freshly copied scenery
        EDUP
        jp .done
.generic:
        ; Complete palette bytes can resolve overlapping particles from three
        ; masks. Preserve every unchanged pixel; foreign interiors remain black.
        ld a,(V_HAS)
        cp 2
        jp nz,.complex
        ld a,(V_CL)
        or a
        jp nz,.complex
        ld a,(V_NI)
        ld e,a
        ld a,(V_NF)
        or e
        cpl
        ld (V_NB),a            ; pixels that expose the backing scenery
        ld a,(V_IM)
        or e
        cpl
        ld e,a
        ld a,(V_NF)
        and e
        ld e,a                 ; another figure's unpainted interior
        bit 7,d
        jr z,.mix0_next
        bit 7,e
        jr nz,.mix0_black
        ld a,(V_NB)
        and 128
        jr nz,.mix0_bg
        ld a,(V_PIX+0)
        jr .mix0_write
.mix0_black:
        ld a,8
        jr .mix0_write
.mix0_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix0_write
        ld a,(V_BG+0)
.mix0_write:
        ld (bc),a
.mix0_next:
        inc c
        bit 6,d
        jr z,.mix1_next
        bit 6,e
        jr nz,.mix1_black
        ld a,(V_NB)
        and 64
        jr nz,.mix1_bg
        ld a,(V_PIX+1)
        jr .mix1_write
.mix1_black:
        ld a,8
        jr .mix1_write
.mix1_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix1_write
        ld a,(V_BG+1)
.mix1_write:
        ld (bc),a
.mix1_next:
        inc c
        bit 5,d
        jr z,.mix2_next
        bit 5,e
        jr nz,.mix2_black
        ld a,(V_NB)
        and 32
        jr nz,.mix2_bg
        ld a,(V_PIX+2)
        jr .mix2_write
.mix2_black:
        ld a,8
        jr .mix2_write
.mix2_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix2_write
        ld a,(V_BG+2)
.mix2_write:
        ld (bc),a
.mix2_next:
        inc c
        bit 4,d
        jr z,.mix3_next
        bit 4,e
        jr nz,.mix3_black
        ld a,(V_NB)
        and 16
        jr nz,.mix3_bg
        ld a,(V_PIX+3)
        jr .mix3_write
.mix3_black:
        ld a,8
        jr .mix3_write
.mix3_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix3_write
        ld a,(V_BG+3)
.mix3_write:
        ld (bc),a
.mix3_next:
        inc c
        bit 3,d
        jr z,.mix4_next
        bit 3,e
        jr nz,.mix4_black
        ld a,(V_NB)
        and 8
        jr nz,.mix4_bg
        ld a,(V_PIX+4)
        jr .mix4_write
.mix4_black:
        ld a,8
        jr .mix4_write
.mix4_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix4_write
        ld a,(V_BG+4)
.mix4_write:
        ld (bc),a
.mix4_next:
        inc c
        bit 2,d
        jr z,.mix5_next
        bit 2,e
        jr nz,.mix5_black
        ld a,(V_NB)
        and 4
        jr nz,.mix5_bg
        ld a,(V_PIX+5)
        jr .mix5_write
.mix5_black:
        ld a,8
        jr .mix5_write
.mix5_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix5_write
        ld a,(V_BG+5)
.mix5_write:
        ld (bc),a
.mix5_next:
        inc c
        bit 1,d
        jr z,.mix6_next
        bit 1,e
        jr nz,.mix6_black
        ld a,(V_NB)
        and 2
        jr nz,.mix6_bg
        ld a,(V_PIX+6)
        jr .mix6_write
.mix6_black:
        ld a,8
        jr .mix6_write
.mix6_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix6_write
        ld a,(V_BG+6)
.mix6_write:
        ld (bc),a
.mix6_next:
        inc c
        bit 0,d
        jr z,.mix7_next
        bit 0,e
        jr nz,.mix7_black
        ld a,(V_NB)
        and 1
        jr nz,.mix7_bg
        ld a,(V_PIX+7)
        jr .mix7_write
.mix7_black:
        ld a,8
        jr .mix7_write
.mix7_bg:
        ld a,(V_BGPIX)
        or a
        jr z,.mix7_write
        ld a,(V_BG+7)
.mix7_write:
        ld (bc),a
.mix7_next:
        inc c
        jp .done
.complex:
        ENDIF
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
.zero:
        IFDEF DZ_ENHANCED
        ld a,(V_BGPIX)
        or a
        jr z,.w
        push hl                 ; one mapped read per byte, never per pixel
        ld a,l
        add a,V_BG-V_PIX
        ld l,a
        ld a,(hl)
        pop hl
        ELSE
        xor a
        ENDIF
.w:     ld (bc),a
.next:  inc hl
        inc c
        rrc e
        jr nc,.bit
.done:  nextreg 0x53,PG
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
        ; Caller already saved BC and immediately replaces it after this call.
        ; Valid plane entries supply all three metadata bytes; clear only on a miss.
        ld de,P2BASE
        or a
        sbc hl,de
        jr c,.dz
        ld de,P2LEN
        or a
        sbc hl,de
        jr c,.p2
        jp .empty
.p2:    add hl,de               ; index = address - P2BASE
        jr .idx
.dz:    add hl,de               ; back to the address
        IFDEF DZ_ENHANCED
        jp .empty               ; Dizzy has hardware patterns, not a second Layer 2 plane
        ENDIF
        ld de,DZBASE
        or a
        sbc hl,de
        jp c,.empty
        ld de,DZLEN
        or a
        sbc hl,de
        jp nc,.empty
        ld de,DZLEN + P2LEN     ; index = P2LEN + address - DZBASE
        add hl,de
.idx:   ld a,h
        IFNDEF DZ_ENHANCED
        rrca
        rrca
        and 0x3F
        ENDIF
        add a,PLPG
        nextreg 0x53,a          ; page = PLPG + index / 1024
        IFDEF DZ_ENHANCED
        ld (V_BG+2),a           ; source page for a kept plot's direct bulk copy
        ENDIF
        ld a,h
        IFDEF DZ_ENHANCED
        xor a
        ELSE
        and 3
        ENDIF
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        IFDEF DZ_ENHANCED
        add hl,hl
        add hl,hl
        ENDIF
        ld a,h
        or 0x60
        ld h,a                  ; 0x6000 + (index % 1024) * 8
        push hl
        IFDEF DZ_ENHANCED
        ld de,8
        ELSE
        ld de,4
        ENDIF
        add hl,de
        ld a,(hl)
        ld (V_IM),a
        inc hl
        ld a,(hl)
        ld (V_CL),a
        inc hl
        ld a,(hl)               ; 1 = painted colours in this entry
        pop hl
        ld (V_HAS),a
        or a
        IFNDEF DZ_ENHANCED
        jr z,.ret               ; none: setsh uses the defaults
        ENDIF
        IFDEF DZ_ENHANCED
        cp 2
        jr nz,.partial
        ld a,(V_CONV)
        or a
        jr nz,.figure
        ld a,h
        add a,0x20
        ld h,a
        ld (V_T),hl            ; read this entry directly through slot 4 in bgpaint
        jr .ret
.figure:
        ld de,V_PIX
        DUP 8
        ldi
        EDUP
        jr .ret
.partial:
        ENDIF
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
        IFDEF DZ_ENHANCED
        ld b,8
.wide:  ld a,(hl)
        or a
        jr z,.unpainted
        ld (de),a
.unpainted:
        inc hl
        inc de
        djnz .wide
        ELSE
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
        ENDIF
.ret:   pop de
        pop hl
        ret
.empty: xor a
        ld (V_IM),a
        ld (V_CL),a
        ld (V_HAS),a
        jr .ret

; A Spectrum byte's eight pixels: HL -> A = Layer 2 page, BC = slot-3 pixel address.
pixelptr:
        ld a,h
        and 0x18
        rrca
        rrca
        ld b,a
        ld a,l
        rlca
        ld a,b
        adc a,L2PG
        ld (V_LPAGE),a
        ld a,l
        and 0x60
        rrca
        rrca
        ld b,a
        ld a,h
        and 7
        or b
        or 0x60
        ld b,a
        ld a,l
        and 31
        add a,a
        add a,a
        add a,a
        ld c,a
        ld a,(V_LPAGE)
        ret

        IFDEF DZ_ENHANCED
; Complete kept colour bytes do not need figure interiors or a temporary pixel copy.
; Carry = ready; HL and DE are kept so a miss can use fillpix unchanged.
keptcolour:
        push hl
        push de
        ld de,P2BASE
        or a
        sbc hl,de
        jr c,.miss
        ld a,h
        cp P2LEN / 256
        jr c,.valid
        jr nz,.miss
        ld a,l
        cp P2LEN & 255
        jr nc,.miss
.valid: ld a,h
        add a,PLPG
        ld (V_BG+2),a
        nextreg 0x53,a
        ld d,32
        ld e,l
        mul d,e
        ex de,hl
        ld a,h
        or 0x60
        ld h,a
        ld de,10
        add hl,de
        ld a,(hl)
        cp 2
        jr nz,.miss
        ld (V_HAS),a
        ld a,l
        sub 10
        ld l,a
        ld a,h
        add a,0x20
        ld h,a
        ld (V_T),hl
        pop de
        pop hl
        scf
        ret
.miss:  pop de
        pop hl
        or a
        ret

; Cache the byte's scenery once. BC is the pixel address; DE kept, HL lost.
bgcache:
        push hl                 ; HL still holds the Spectrum screen address
        ld a,h
        add a,0x20
        ld h,a
        nextreg 0x53,BGFLAG
        ld a,(hl)
        ld (V_BGPIX),a
        cp 2
        jr nz,.saved
        ld (hl),1              ; first figure touching this byte saves the visible scenery
        pop hl
        call bgmaterialize
        jr .ready
.saved:
        pop hl
        or a
        jr nz,.copy
        ld a,(V_LPAGE)
        nextreg 0x53,a
        ret
.copy:  push bc
        push de
        ld h,b
        ld l,c
        ld a,(V_LPAGE)
        add a,BGPG-L2PG
        nextreg 0x53,a
        ld de,V_BG
        DUP 8
        ldi
        EDUP
        pop de
        pop bc
.ready:
        ld a,(V_LPAGE)
        nextreg 0x53,a
        ret

; BC = one displayed scenery byte's eight pixels. Save it only on first use.
; BC and DE kept; HL/AF lost. V_BG also supplies setsh's immediate restore colours.
bgmaterialize:
        push bc
        push de
        push bc
        ld h,b
        ld l,c
        ld a,(V_LPAGE)
        nextreg 0x53,a
        ld de,V_BG
        DUP 8
        ldi
        EDUP
        pop de
        ld hl,V_BG
        ld a,(V_LPAGE)
        add a,BGPG-L2PG
        nextreg 0x53,a
        DUP 8
        ldi
        EDUP
        pop de
        pop bc
        ret

; The kept plot's ULA byte is already updated. Record its source colours on set bits,
; clear erased bits, preserve old colours under OR holes, and don't overwrite foreground.
bgpaint:
        ld a,h
        add a,0x20
        ld d,a
        ld e,l
        nextreg 0x53,PG
        ld a,(de)
        ld b,a
        nextreg 0x53,PG2
        ld a,(de)
        or b
        ld (V_COVER),a
        jr bgpaint_flags
bgpaint_fast:
        xor a                   ; all shadows were checked before the kept ULA write
        ld (V_COVER),a
        ld a,h
        add a,0x20
        ld d,a
        ld e,l
bgpaint_flags:
        nextreg 0x53,BGFLAG
        call pixelptr
        ld a,(V_HAS)
        cp 2
        jp nz,.slow
        ld a,(V_BG+2)
        nextreg 0x54,a          ; source plane at 8000, destination page at 6000
        ld a,(V_COVER)
        or a
        jp nz,.slow
        ld a,(V_NB)
        ld d,a
        ld a,(V_G)
        cp d
        jr nz,.try_or
        ld a,h
        add a,0x20
        ld h,a
        ld (hl),2              ; valid scenery lives in Layer 2 until first covered
        ld d,b
        ld e,c
        ld hl,(V_T)
        set 4,l                 ; ink-only colours at byte 16 of this aligned entry
        ld a,(V_LPAGE)
        nextreg 0x53,a
        DUP 8
        ldi
        EDUP
        jp .done
.try_or:
        ld a,(XMODE)
        cp 0xB1
        jr nz,.slow
        ld a,h
        add a,0x20
        ld h,a
        ld (hl),2              ; no figure covers it, so the visible bytes are the backing
        ld d,b
        ld e,c
        ld hl,(V_T)
        set 4,l
        ld a,(V_LPAGE)
        nextreg 0x53,a
        xor a
        DUP 8
        ldix                    ; original OR holes keep the previously painted scenery
        EDUP
        jp .done
.slow:
        ; Only mixed/covered writes need the old backing validity. Fresh and OR
        ; copies publish flag 2 directly and need no intermediate flag-1 write.
        push hl
        ld a,h
        add a,0x20
        ld h,a
        nextreg 0x53,BGFLAG
        ld a,(hl)
        ld (V_FX),a
        ld (hl),1
        pop hl
        ld a,(V_FX)
        cp 2
        jr nz,.backed
        call bgmaterialize      ; mixed XOR/covered writes need the separate backing first
.backed:
        ld a,(V_HAS)
        cp 2
        jr nz,.ready
        push bc
        ld hl,(V_T)
        ld de,V_PIX
        DUP 8
        ldi
        EDUP
        pop bc
.ready:
        ld hl,V_PIX
        ld d,0x80
.bit:   ld a,(V_LPAGE)
        add a,BGPG-L2PG
        nextreg 0x53,a
        ld a,(V_NB)
        and d
        jr z,.zero
        ld a,(V_G)
        and d
        jr z,.old
        ld a,(V_HAS)
        or a
        ld a,(V_COL)
        jr z,.write
        ld a,(hl)
.write:
        ld (bc),a
        jr .show
.zero:  xor a
        ld (bc),a
        jr .show
.old:   ld a,(V_FX)
        or a
        jr z,.show              ; invalid backing pixels read as transparent
        ld a,(bc)
.show:  ld (V_BGPIX),a
        ld a,(V_COVER)
        and d
        jr nz,.next
        ld a,(V_LPAGE)
        nextreg 0x53,a
        ld a,(V_BGPIX)
        ld (bc),a
.next:  inc hl
        inc c
        srl d
        jr nz,.bit
.done:  nextreg 0x54,4
        ret                     ; e_p2w immediately restores the game's slot-3 page

; Clear a byte's background and displayed overlay before an original wipe/effect.
; Every register and flag is kept; PG is mapped on exit, as fold expects.
bgrowclear:
        push af
        push bc
        push de
        push hl
        nextreg 0x53,BGFLAG
.byte:  ld a,h
        sub 0x40
        cp 0x18
        jr nc,.next
        add a,0x60
        ld d,a
        ld e,l
        ld a,(de)
        or a
        jr z,.next
        call bgclear
        nextreg 0x53,BGFLAG
.next:  inc hl
        djnz .byte
        nextreg 0x53,PG
        pop hl
        pop de
        pop bc
        pop af
        ret

bgclear:
        push af
        push hl
        ld a,h
        add a,0x20
        ld h,a
        nextreg 0x53,BGFLAG
        ld a,(hl)
        or a
        jr nz,.dirty
        nextreg 0x53,PG
        pop hl
        pop af
        ret
.dirty: ld (hl),0
        pop hl
        push bc
        push de
        push hl
        call pixelptr
        ld h,b
        ld l,c
        nextreg 0x53,a
        push af
        push hl
        xor a
        DUP 7
        ld (hl),a
        inc hl
        EDUP
        ld (hl),a
        pop hl
        pop af
        nextreg 0x53,PG
        pop hl
        pop de
        pop bc
        pop af
        ret
        ENDIF

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
        IFDEF DZ_ENHANCED
        ld b,0
.p:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .p
        ELSE
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        ENDIF
        ld bc,0x123B
        ld a,2                  ; Layer 2 visible, no write mapping
        out (c),a
        nextreg 0x43,0x20       ; sprite palette 0: the same 16 colours (index 0 transparent)
        nextreg 0x40,0
        IFDEF DZ_ENHANCED
        ld hl,pal+512
        ld b,16
.s:     ld a,(hl)
        nextreg 0x44,a
        inc hl
        ld a,(hl)
        nextreg 0x44,a
        inc hl
        djnz .s
        ELSE
        ld hl,pal
        ld b,16
.s:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .s
        ENDIF
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
        ld bc,0x243B
        ld a,7
        out (c),a               ; 0x243B selects NR 7 for the hooks' DZ_SPEED_IN
        ret
pal:                            ; 16 palette bytes appended by dizzy1.py (index 0 = 0xE3: Layer 2
                                ; transparent; as a sprite colour index 0 is transparent anyway)

        IFNDEF DZ_NO_SAVE
        SAVEBIN "d1_rom.bin",0x2000,rom_end-0x2000
        SAVEBIN "d1_setup.bin",0xD000,pal-0xD000
        ENDIF
