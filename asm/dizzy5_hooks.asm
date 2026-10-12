; Dizzy V engine hooks (slot-1 hook page). Not in a profile: nexclash/dizzy5.py emits these bytes
; itself (hook_code, values derived per game). Values below are the Dizzy V profile's; the pinned
; sjasmplus output must equal hook_code() for it: `python selftest.py --tools` checks that.
        DEVICE NOSLOT64K
STATE   EQU 44749
FLAG    EQU 44772
FRAME   EQU 44767
DEFFR   EQU 36
NFR     EQU 37
XV      EQU 44737
YV      EQU 44736
FLIP    EQU 44739
PCONT   EQU 40068
ECONT   EQU 40395
        ORG 0x3800
T_PLOT: ld (STATE),a            ; original instruction
        ld a,(FLAG)
        and a
        ld a,(FRAME)
        jr nz,.fr
        ld a,DEFFR
.fr:    cp NFR
        jp nc,.hide
        ld l,a : ld h,0 : add hl,hl : add hl,hl : add hl,hl
        ld de,TABLE
        add hl,de               ; HL -> 8-byte frame entry (attr3/attr4 x 4)
        exx
        ld a,(XV)
        ld l,a : ld h,0 : add hl,hl : add hl,hl
        ld de,32 : add hl,de    ; HL' = x*4 + 32
        ld a,(FLIP)
        rlca
        jr nc,.mir
        ld c,0 : ld de,16 : jr .go
.mir:   ld c,8 : ld de,8 : add hl,de : ld de,-16
.go:    ex de,hl : add hl,de    ; DE' = left X, HL' = right X, C' = mirror bit
        MACRO SPR n, xr, xh, dy
        nextreg 0x34,n
        ld a,xr : nextreg 0x35,a
        ld a,(YV)
        IF dy
        add a,dy
        ENDIF
        nextreg 0x36,a
        ld a,xh : and 1 : or c : nextreg 0x37,a
        exx
        ld a,(hl) : inc hl : nextreg 0x38,a
        ld a,(hl) : inc hl : nextreg 0x39,a
        exx
        ENDM
        SPR 0, e, d, 0
        SPR 1, l, h, 0
        SPR 2, l, h, 16
        SPR 3, e, d, 16
        exx                     ; even EXX count: the ISR's register restore is unchanged
        nextreg 0x15,1
        jp PCONT
.hide:  nextreg 0x15,0
        jp PCONT
T_ERASE: ld (STATE),a           ; original instruction
        nextreg 0x15,0
        jp ECONT
TABLE:
        SAVEBIN "dizzy5_hooks.bin", T_PLOT, TABLE - T_PLOT
