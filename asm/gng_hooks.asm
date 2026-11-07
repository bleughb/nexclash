; Ghosts 'n Goblins (Elite 1986) - figures as hardware sprites. Hooks + state in RAM page PAGE at 0x2000-0x3FFF
; (MMU slot 1) for the whole game; the top of the page holds the ROM font, which the game prints with.
;
; Method (games/ghosts_n_goblins.md): each tick the game redraws the play area in bands, plotting figures straight on
; the screen. Three plot loops' stores become NOPs; each loop's LD (49060),SP becomes JP e_x: image, screen and rows
; give sprites. Interrupts are off at the three sites (the verifier counts IFF). Game memory is never written, but 49060.
;
; Cache: 32 groups of 4 patterns (4-bit), key = image address, kind + rows, and a checksum of the image: the game
; rewrites images at the same address (armour, levels), and one kind plots from a buffer.
; Colour plane (Next pages PLANE.., CHECK.., built by gng.py, also in recolour): for each graphics byte in
; 0xC000-0xFFFF 4 bytes of nibbles (0 = default) and a check byte: colours apply only if the byte holds that value.

        DEVICE ZXSPECTRUMNEXT

SPSAVE  EQU 49060
GB      EQU 0xC0
PLANE   EQU 26          ; 8 pages, offset 4 * (a - 0xC000)
CHECK   EQU 34          ; 2 pages, offset a - 0xC000
SLOT2   EQU 10          ; the game's page at slot 2
NMAX    EQU 124         ; sprites
NC      EQU 32          ; cache groups
ROWMAX  EQU 16          ; line pairs a group can hold
LBSIZE  EQU 32*12

KM3     EQU 0           ; masked, 3 columns: 10 bytes per 2 lines
KO3     EQU 1           ; OR, 3 columns: 6 bytes per 2 lines
KX2     EQU 2           ; XOR, 2 columns: 4 bytes per 2 lines

        INCLUDE "lib/hlib_speed.asm"
HLIB_V_R EQU rstate
        ORG 0x2000
        INCLUDE "lib/hlib_r.asm"

; --- the plot loops ------------------------------------------------------------------------------------
; masked: DE image, HL screen (rightmost byte of the first line), B + 4 * (C' - 1) + B' line pairs
e_m3:   ld (SPSAVE),sp
        ld sp,hstack
        push af
        HLIB_R_IN
        push bc
        push de
        push hl
        call m3_r_target
        pop hl
        pop de
        push de
        push hl
        exx
        ld a,c
        dec a
        add a,a
        add a,a
        add a,b
        exx
        add a,b
        ld (mrows),a
        ld b,a
        ld c,KM3
        ex de,hl
        call plot
; what the loop leaves in C, D, E: the last line pair's bytes 2, 8, 9
        ld a,(mrows)
        dec a
        ld d,a
        ld e,10
        mul d,e
        pop hl                  ; screen
        ld (mscr),hl
        pop hl                  ; image
        add hl,de
        inc hl
        inc hl
        ld a,(hl)
        ld (mc),a
        ld de,6
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop bc
        ld a,(mc)
        ld c,a
        pop af
        ld hl,(mscr)
; the loop without its plotting, faster than the original's: every register as it leaves them. H moves 2 per line pair.
        xor a
        ex af,af'
.a:     ld a,b
        add a,a
        add a,h
        ld h,a
        ld b,0
        ld a,l
        add a,32
        ld l,a
        jr c,.b
        ld a,h
        sub 8
        ld h,a
.b:     exx
        dec c
        exx
        jr z,.c
        ld b,4
        ex af,af'
        jp z,.d
        jr .e
.c:     exx
        ld a,b
        exx
        or a
        ld b,a
        jr nz,.d
.e:     HLIB_R_OUT
        ld sp,(SPSAVE)
        jp 36601
.d:     ex af,af'
        jr .a

; OR: HL image, D rightmost column, E y / 2, C line pairs
e_o3:   ld (SPSAVE),sp
        ld sp,hstack
        push af
        HLIB_R_IN
        ld a,-14
        call hlib_r_set
        push bc
        push de
        push hl
        ld a,e
        add a,a
        ld l,a
        ld h,0xBE
        ld a,(hl)
        add a,d
        ld e,a
        inc l
        ld d,(hl)
        pop hl
        push hl
        ld b,c
        ld c,KO3
        call plot
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(SPSAVE)
        jp 37114

; XOR: HL image, DE screen (right byte of the first line), 4 line pairs
e_x2:   ld (SPSAVE),sp
        ld sp,hstack
        push af
        HLIB_R_IN
        ld a,-14
        call hlib_r_set
        push bc
        push de
        push hl
        ld b,4
        ld c,KX2
        call plot
        HLIB_R_OUT
        pop hl
        pop de
        pop bc
        pop af
        ld sp,(SPSAVE)
        jp 37007

; the weapon in the score bar stays on the ULA: the masked loop as the original, with its stores
e_hud:  nop                     ; replaces the second original JP, keeping R exact
        ld (SPSAVE),sp
        ex de,hl
        ld sp,hl
        ex de,hl
        xor a
.again: ex af,af'
.a:     pop de
        ld a,(hl)
        and e
        or d
        ld (hl),a
        dec l
        pop de
        ld a,(hl)
        and e
        or d
        ld (hl),a
        dec l
        ld c,e
        pop de
        ld a,(hl)
        and e
        or d
        ld (hl),a
        inc h
        ld a,e
        pop de
        and (hl)
        or e
        ld (hl),a
        inc l
        ld a,(hl)
        and c
        or d
        ld (hl),a
        pop de
        inc l
        ld a,(hl)
        and e
        or d
        ld (hl),a
        inc h
        djnz .a
        ld a,l
        add a,32
        ld l,a
        jr c,.b
        ld a,h
        sub 8
        ld h,a
.b:     exx
        dec c
        exx
        jr z,.c
        ld b,4
        ex af,af'
        jp z,.again
        jr .e
.c:     exx
        ld a,b
        exx
        or a
        ld b,a
        jr nz,.again
.e:     ld sp,(SPSAVE)
        ret

; --- the end of a draw pass: sprites the pass did not use go ---------------------------------------------
e_tick: ld (hsp),sp
        ld sp,hstack
        push af
        HLIB_R_IN
        ld a,-15
        call hlib_r_set
        push bc
        push hl
        ld a,(nsp)
        ld c,a
        call hide
        HLIB_SPEED_IN speed
        call sm_end
        HLIB_SPEED_OUT speed
        ld a,c
        ld (shown),a
        xor a
        ld (nsp),a
        ld hl,tick
        inc (hl)
        HLIB_R_OUT
        pop hl
        pop bc
        pop af
        ld sp,(hsp)
        ld iy,49008
        jp 36419

; --- screens with no pass: all sprites go ---------------------------------------------------------------
e_cls: ld (hsp),sp
        ld sp,hstack
        push af
        ld a,i
        di                      ; bounded reset-only critical section; IFF is restored below
        jp po,.off
        ld a,1
        jr .saved
.off:   xor a
        nop
.saved: ld (irq_restore),a
        HLIB_R_IN
        push bc
        push hl
        ld a,-26
        call hlib_r_set
        HLIB_SPEED_IN speed
        call hideall
        HLIB_SPEED_OUT speed
        HLIB_R_OUT
        pop hl
        pop bc
        ld a,(irq_restore)
        or a
        jr z,.return_off
        pop af
        ld sp,(hsp)
        ld hl,16384
        ei
        jp 36064
.return_off:
        pop af
        ld sp,(hsp)
        ld hl,16384
        nop
        jp 36064

e_cls2: ld (hsp),sp
        ld sp,hstack
        push af
        ld a,i
        di                      ; bounded reset-only critical section; IFF is restored below
        jp po,.off
        ld a,1
        jr .saved
.off:   xor a
        nop
.saved: ld (irq_restore),a
        HLIB_R_IN
        push bc
        push hl
        ld a,-26
        call hlib_r_set
        HLIB_SPEED_IN speed
        call hideall
        HLIB_SPEED_OUT speed
        HLIB_R_OUT
        pop hl
        pop bc
        ld a,(irq_restore)
        or a
        jr z,.return_off
        pop af
        ld sp,(hsp)
        ld hl,16384
        ei
        jp 23966
.return_off:
        pop af
        ld sp,(hsp)
        ld hl,16384
        nop
        jp 23966

e_init: ld (hsp),sp
        ld sp,hstack
        push af
        ld a,i
        di                      ; bounded reset-only critical section; IFF is restored below
        jp po,.off
        ld a,1
        jr .saved
.off:   xor a
        nop
.saved: ld (irq_restore),a
        HLIB_R_IN
        push bc
        push hl
        ld a,-25
        call hlib_r_set
        HLIB_SPEED_IN speed
        call hideall
        HLIB_SPEED_OUT speed
        HLIB_R_OUT
        pop hl
        pop bc
        ld a,(irq_restore)
        or a
        jr z,.return_off
        pop af
        ld sp,(hsp)
        ei
        jp 25202
.return_off:
        pop af
        ld sp,(hsp)
        nop
        jp 25202


hideall: push af
        push bc
        call sm_reset
        xor a
        ld c,a
        call hide
        xor a
        ld (nsp),a
        ld (shown),a
        pop bc
        pop af
        ret

; A = first slot to hide, up to (shown) or (nsp), whichever is more. Keeps C.
hide:   ld b,a
        ld a,(nsp)
        ld l,a
        ld a,(shown)
        cp l
        jr nc,.m
        ld a,l
.m:     sub b
        ret z
        ret c
        ld l,a
        ld a,b
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        dec l
        jr nz,.h
        ret

; --- one plot: B line pairs, C kind, HL image, DE screen (rightmost byte of the first line) --------------
plot:   ld a,b
        dec a
        cp ROWMAX
        ret nc                  ; the verifier counts a figure with no sprite
        ld a,(nsp)
        cp NMAX-3
        ret nc
        HLIB_SPEED_IN speed
        call sm_begin
        call gc_prepare
        ld (gfx),hl
        ld (scr),de
        ld a,b
        ld (rows),a
        ld a,c
        ld (kind),a
        ld a,(attrs.gc_visibility_mask+1)
        and 0x80
        jr nz,.visible
        call attrs
        HLIB_SPEED_OUT speed
        ret
.visible:
; length of the image, and its checksum (Fletcher)
        ld a,c
        add a,low rowsz
        ld e,a
        ld a,high rowsz
        adc a,0
        ld d,a
        ld a,(de)
        ld d,b
        ld e,a
        mul d,e
        ld a,e
        ld (rawlen),a
        ld b,a                  ; all bytes, including masks and even graphics bytes
        ld de,0
.ck:    ld a,(hl)
        inc hl
        add a,e
        ld e,a
        add a,d
        ld d,a
        djnz .ck
        ld (sum),de
        ld a,(kind)
        rrca
        rrca
        rrca
        ld c,a
        ld a,(rows)
        or c
        ld (shape),a
; find the image
        ld hl,keys
        ld b,NC
.s:     push hl
        ld a,(gfx)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(gfx+1)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(shape)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(sum)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(sum+1)
        cp (hl)
        jr nz,.n
        push bc
        ld a,NC
        sub b
        ld (grp),a
        call cached_match
        pop bc
        jr c,.hit
.n:     pop hl
        ld de,5
        add hl,de
        djnz .s
; miss: the next group in rotation not on show: not used this tick or the last, whose sprites stay up until this
; tick replaces them. After NC tries the group is taken anyway.
        ld a,(rr)
        ld e,a
        ld d,0
        ld b,NC
.try:   ld hl,used
        add hl,de
        ld a,(tick)
        sub (hl)
        cp 2
        jr nc,.free
        ld a,e
        inc a
        and NC-1
        ld e,a
        djnz .try
.free:  ld a,e
        ld (grp),a
        inc a
        and NC-1
        ld (rr),a
        ld a,(grp)
        ld d,a
        ld e,5
        mul d,e
        ld hl,keys
        add hl,de
        ld a,(gfx)
        ld (hl),a
        inc hl
        ld a,(gfx+1)
        ld (hl),a
        inc hl
        ld a,(shape)
        ld (hl),a
        inc hl
        ld a,(sum)
        ld (hl),a
        inc hl
        ld a,(sum+1)
        ld (hl),a
        call upload
        jr .mark
.hit:   pop hl
        ld a,NC
        sub b
        ld (grp),a
.mark:  ld a,(grp)
        ld e,a
        ld d,0
        ld hl,used
        add hl,de
        ld a,(tick)
        ld (hl),a
        call attrs
        HLIB_SPEED_OUT speed
        ret

; --- the sprites: 16 x 16 cells, in plot order, so later is in front, as the game ---------------------------
attrs:  call sm_calc
        call gc_motion
        ld hl,(scr)
        ld a,h                  ; screen address -> y
        and 7
        ld e,a
        ld a,h
        and 0x18
        add a,a
        add a,a
        add a,a
        or e
        ld e,a
        ld a,l
        and 0xE0
        rrca
        rrca
        or e
        add a,32
        ld (ybase),a
        ld a,l                  ; rightmost column -> first column: may be below 0 at the left edge
        and 31
        ld d,a
        ld a,(kind)
        cp KX2
        ld a,d
        ld c,1
        jr z,.k2
        dec a
        ld c,2
.k2:    dec a
        add a,4                 ; column + 4 >= 2
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl               ; (column + 4) * 8 = x + 32
        ld (xbase),hl
        ld a,c
        ld (ncols),a
        ld a,(rows)
        cp 9
        ld a,1
        jr c,.r1
        inc a
.r1:    ld (nrows),a
        ld a,(grp)
        add a,a
        add a,a
        ld (pat),a
        xor a
        ld (rown),a
.row:   ld a,(ncols)
        ld b,a
        ld hl,(xbase)
.col:   ld a,(nsp)
        call sm_emit_full
        nextreg 0x34,a
        inc a
        ld (nsp),a
        push hl
        ld a,(sm_dx)
        ld e,a
        add a,a
        sbc a,a
        ld d,a
        add hl,de
        ld a,l
        nextreg 0x35,a
        ld a,(sm_dy)
        ld e,a
        ld a,(ybase)
        add a,e
        nextreg 0x36,a
        ld a,h
        and 1
        nextreg 0x37,a
        pop hl
        ld a,(ncols)
        sub b                   ; column in the group
        ld c,a
        ld a,(pat)
        add a,c
        ld c,a
        srl a
.gc_visibility_mask: or 0xC0
        nextreg 0x38,a
        ld a,c
        and 1
        rrca
        rrca
        or 0x80
        nextreg 0x39,a
        ld de,16
        add hl,de
        djnz .col
        ld a,(ybase)
        add a,16
        ld (ybase),a
        ld a,(pat)
        add a,2
        ld (pat),a
        ld a,(rown)
        inc a
        ld (rown),a
        ld c,a
        ld a,(nrows)
        cp c
        jr nz,.row
        ret

; --- the group's four patterns, from the image ------------------------------------------------------------
upload: call atlas_upload
        ret c
        call parent_find
        ld hl,lb
        ld de,lb+1
        ld bc,16*12-1
        ld a,(rows)
        cp 9
        jr c,.cl
        ld bc,LBSIZE-1
.cl:    ld (hl),0
        ldir
        ld hl,(gfx)
        ld (cur),hl
        ld hl,lb
        ld (dest),hl
        ld a,(rows)
        ld (cnt),a
.row:   ld a,(kind)
        add a,a
        add a,low tabs
        ld l,a
        ld a,high tabs
        adc a,0
        ld h,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (tp),hl
        ld a,6
        ld (cc),a
.ent:   ld hl,(tp)
        ld a,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld (tp),hl
        cp 255
        jr nz,.has
        ld hl,(dest)
        ld de,4
        add hl,de
        ld (dest),hl
        jr .nxt
.has:   ld hl,(cur)
        add hl,a                ; graphics address
        ld d,(hl)
        ld (ga),hl
        ld e,255
        ld a,c
        cp 255
        jr z,.nm
        ld hl,(cur)
        add hl,a
        ld e,(hl)
.nm:    ld hl,(ga)
        call emit
.nxt:   ld a,(cc)
        dec a
        ld (cc),a
        jr nz,.ent
; next line pair
        ld a,(kind)
        add a,low rowsz
        ld l,a
        ld a,high rowsz
        adc a,0
        ld h,a
        ld a,(hl)
        ld hl,(cur)
        add hl,a
        ld (cur),hl
        ld a,(cnt)
        dec a
        ld (cnt),a
        jr nz,.row
        nextreg 0x52,SLOT2
; out: pattern select, then top left, top right, bottom left, bottom right
        ld a,(grp)
        add a,a
        and 0x3F
        ld bc,0x303B
        out (c),a
        ld hl,lb
        call pats
        ld hl,lb+16*12
        call pats
        ret

; 16 lines at HL: the left pattern (8 bytes a line), then the right (4 bytes and 4 empty)
pats:   push hl
        ld d,16
.l:     ld bc,0x085B
        otir
        inc hl
        inc hl
        inc hl
        inc hl
        dec d
        jr nz,.l
        pop hl
        ld de,8
        add hl,de
        ld d,16
.r:     ld bc,0x045B
        otir
        xor a
        ld bc,0x045B
.z:     out (c),a
        djnz .z
        ld a,d
        ld de,8
        add hl,de
        ld d,a
        dec d
        jr nz,.r
        ret

; HL graphics address, D data, E mask (255: none). 4 bytes at (dest): 1 ink, 2 body, 0 see-through, or the map's colour.
emit:   xor a
        ld (usenb),a
        ld a,(parent_page)
        or a
        jr z,.legacy
        push de
        ld de,(parent_addr)
        or a
        sbc hl,de
        add hl,hl
        add hl,hl
        ld de,(parent_paint)
        add hl,de
        ld a,(parent_page)
        nextreg 0x52,a
        ld de,(dest)
        ld bc,4
        ldir
        ld (dest),de
        nextreg 0x52,SLOT2
        pop de
        ret                     ; complete parent pixels, including explicit clear mask
.legacy:
        ld a,h
        cp GB
        jr c,.def
        ld (ga),hl
        and 0x3F
        ld h,a
        add hl,hl
        add hl,hl
        ld a,h
        rlca
        rlca
        rlca
        and 7
        add a,PLANE
        nextreg 0x52,a
        ld a,h
        and 0x1F
        or 0x40
        ld h,a
        ld a,(hl)
        inc hl
        or (hl)
        inc hl
        or (hl)
        inc hl
        or (hl)
        jr z,.def
        call colour
.def:   ld hl,(dest)
        ex de,hl                ; DE dest, H data, L mask
        ld a,h
        and 0xF0
        ld b,a
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 0x0F
        or b
        ld b,h
        ld c,l
        call nibs
        ld a,b
        rlca
        rlca
        rlca
        rlca
        and 0xF0
        ld l,a
        ld a,c
        and 0x0F
        or l
        call nibs
        ld (dest),de
        ld a,(usenb)
        or a
        ret z
; the map's nibbles over the bytes just made
        ld hl,(dest)
        ld de,-4
        add hl,de
        ld de,nb
        ld c,4
.m:     ld a,(de)
        ld b,a
        and 0xF0
        jr nz,.hi
        ld a,(hl)
        and 0xF0
.hi:    ld (hv),a
        ld a,b
        and 0x0F
        jr nz,.lo
        ld a,(hl)
        and 0x0F
.lo:    ld b,a
        ld a,(hv)
        or b
        ld (hl),a
        inc hl
        inc de
        dec c
        jr nz,.m
        ret

; A = data nibble << 4 | mask nibble: 2 bytes from the table to (DE)
nibs:   add a,a
        ld l,a
        ld a,high ntab
        adc a,0
        ld h,a
        ld a,(hl)
        ld (de),a
        inc hl
        inc de
        ld a,(hl)
        ld (de),a
        inc de
        ret

; a byte with a colour in the map: keep the nibbles if the check byte matches. HL at the plane's 4th byte, (ga) the address, D the data.
colour: dec hl
        dec hl
        dec hl
        push de
        ld de,nb
        ld bc,4
        ldir
        pop de
        ld hl,(ga)
        ld a,h
        and 0x3F
        ld h,a
        rlca
        rlca
        rlca
        and 1
        add a,CHECK
        nextreg 0x52,a
        ld a,h
        and 0x1F
        or 0x40
        ld h,a
        ld a,(hl)
        cp d
        ret nz
        ld a,1
        ld (usenb),a
        ret

; Compute the original whole masked loop's M1 count before any input registers change.
; The table covers every legitimate first-row count, band count, tail and vertical wrap.
m3_r_target:
        ld a,l
        rlca
        rlca
        rlca
        and 7
        ld (rphase),a
        ld a,b
        dec a
        cp 4
        jr nc,.invalid
        ld d,a
        ld e,20
        mul d,e
        exx
        ld a,c
        dec a
        add a,a
        add a,a
        add a,b
        exx
        add a,e
        ld e,a
        ld d,0
        sla e
        rl d
        sla e
        rl d
        sla e
        rl d
        ld a,(rphase)
        or e
        ld e,a
        ld hl,rtable
        add hl,de
        ld a,(hl)
        sub 12                  ; JP + capture prefix + exit suffix
        jp hlib_r_set
.invalid:
        xor a
        jp hlib_r_set
rphase: db 0
rstate: ds 3
speed: db 0
irq_restore: db 0
rtable:
        INCLUDE "gng_r_table.inc"

; Content check on every cache hit. Unknown graphics are rendered by the fallback
; and never cached, so a Fletcher collision cannot reuse a different image.
cached_match:
        ld a,(grp)
        add a,a
        ld hl,atlas_keys
        add hl,a
        ld a,(hl)
        or a
        jp z,parent_cached_match
        inc hl
        ld h,(hl)
        ld l,0
        call atlas_compare
        ret

; A page, H offset high. Compare the entire current source image against the
; atlas's source bytes. Carry means exact identity; all exits restore slot 2.
atlas_compare:
        nextreg 0x52,a
        ld a,h
        or 0x40
        ld h,a
        ld de,(gfx)
        ld a,(rawlen)
        ld b,a
.c:     ld a,(de)
        cp (hl)
        jr nz,.no
        inc de
        inc hl
        djnz .c
        nextreg 0x52,SLOT2
        scf
        ret
.no:    nextreg 0x52,SLOT2
        or a
        ret

atlas_upload:
        call parent_key
        ld (hl),0
        ld a,(grp)
        add a,a
        ld hl,atlas_keys
        add hl,a
        ld (atlas_key),hl
        ld (hl),0               ; fallback has no cache identity
        call gc_atlas
        jp c,.found
        ld hl,0x4000
.find:  nextreg 0x52,36
        ld a,(hl)
        or a
        jr z,.none
        ld a,(shape)
        cp (hl)
        jr nz,.next0
        inc hl
        ld a,(sum)
        cp (hl)
        jr nz,.next1
        inc hl
        ld a,(sum+1)
        cp (hl)
        jr nz,.next2
        inc hl
        ld a,(hl)
        ld (atlas_page),a
        inc hl
        ld a,(hl)
        ld (atlas_off),a
        inc hl
        ld (atlas_next),hl
        ld h,a
        ld l,0
        ld a,(atlas_page)
        call atlas_compare
        jr c,.found
        ld hl,(atlas_next)
        jr .find
.next0: inc hl
.next1: inc hl
.next2: inc hl
        inc hl
        inc hl
        jr .find
.none:  nextreg 0x52,SLOT2
        or a
        ret
.found: ld hl,(atlas_key)
        ld a,(atlas_page)
        ld (hl),a
        inc hl
        ld a,(atlas_off)
        ld (hl),a
        ld a,(grp)
        add a,a
        ld bc,0x303B
        out (c),a
        ld a,(atlas_page)
        nextreg 0x52,a
        ld a,(atlas_off)
        or 0x40
        inc a                   ; patterns begin 256 bytes after raw data
        ld h,a
        ld l,0
        ld bc,0x005B
        otir
        ld bc,0x005B
        otir
        nextreg 0x52,SLOT2
        scf
        ret
; Parent fallback: full original bytes identify artwork even for a clipped height
; absent from the fast atlas. Its compact per-byte ink plane then drives the normal
; converter. Complete parent pixels preserve black detail and explicit exterior-mask clearing.
parent_key:
        ld a,(grp)
        ld d,a
        ld e,6
        mul d,e
        ld hl,parent_keys
        add hl,de
        ret
parent_cached_match:
        call parent_key
        ld a,(hl)
        or a
        ret z
        push af
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld a,(hl)
        ld (parent_length),a
        ex de,hl
        push bc
        pop de
        ld b,a
        pop af
        jp parent_compare
; A page, HL raw offset, DE original address, B bytes. Carry means exact.
parent_compare:
        nextreg 0x52,a
        ld a,h
        or 0x40
        ld h,a
.c:     ld a,(de)
        cp (hl)
        jr nz,.no
        inc de
        inc hl
        djnz .c
        nextreg 0x52,SLOT2
        scf
        ret
.no:    nextreg 0x52,SLOT2
        or a
        ret
parent_find:
        xor a
        ld (parent_page),a
        ld hl,0x4000
.scan:  nextreg 0x52,77
        ld a,(hl)
        cp 255
        jp z,.none
        ld de,7
        push hl
        add hl,de
        ld (parent_next),hl
        pop hl
        ld a,(kind)
        cp (hl)
        jp nz,.next
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (parent_addr),de
        inc hl
        ld a,(hl)
        ld (parent_length),a
        inc hl
        ld a,(hl)
        ld (parent_candidate),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (parent_raw),de
; The complete visible fragment must be contained in this original parent.
        ld hl,(gfx)
        ld de,(parent_addr)
        or a
        sbc hl,de
        jp c,.next
        ld a,h
        or a
        jp nz,.next
        ld (parent_offset),hl
        ld a,(kind)
        add a,low rowsz
        ld l,a
        ld a,high rowsz
        adc a,0
        ld h,a
        ld b,(hl)
        ld a,(parent_offset)
        or a
        jr z,.aligned
.mod:   sub b
        jp c,.next
        jr nz,.mod
.aligned:
        ld hl,(parent_offset)
        ld a,(rawlen)
        add a,l
        jp c,.next
        ld e,a
        ld a,(parent_length)
        cp e
        jp c,.next
        ld b,a
        ld hl,(parent_raw)
        ld de,(parent_addr)
        ld a,(parent_candidate)
        call parent_compare
        jp nc,.next
        ld a,(parent_candidate)
        ld (parent_page),a
        ld hl,(parent_raw)
        ld a,(parent_length)
        add hl,a
        ld a,h
        or 0x40
        ld h,a
        ld (parent_paint),hl
; Cache the parent identity, not just the visible fragment. A later rewrite of a
; hidden part can therefore never reuse the wrong material colours.
        call parent_key
        ld a,(parent_page)
        ld (hl),a
        inc hl
        ld de,(parent_raw)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld de,(parent_addr)
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld a,(parent_length)
        ld (hl),a
        ret
.next:  ld hl,(parent_next)
        jp .scan
.none:  nextreg 0x52,SLOT2
        ret
parent_offset: dw 0
parent_page: db 0
parent_candidate: db 0
parent_length: db 0
parent_addr: dw 0
parent_raw: dw 0
parent_paint: dw 0
parent_next: dw 0
parent_keys: ds NC*6

atlas_key: dw 0
atlas_next: dw 0
atlas_page: db 0
atlas_off: db 0
rawlen: db 0
atlas_keys: ds NC*2

; --- tables: per kind, for line 0 columns 0-2 then line 1 columns 0-2: (graphics offset, mask offset), 255 = none
rowsz:  db 10,6,4
tabs:   dw tm3,to3,tx2
tm3:    db 5,4, 3,2, 1,0,  6,4, 7,2, 9,8
to3:    db 2,255, 1,255, 0,255,  3,255, 4,255, 5,255
tx2:    db 0,255, 1,255, 255,255,  2,255, 3,255, 255,255

mrows:  db 0
mc:     db 0
mscr:   dw 0
gfx:    dw 0
scr:    dw 0
sum:    dw 0
cur:    dw 0
dest:   dw 0
tp:     dw 0
ga:     dw 0
hsp:    dw 0
xbase:  dw 0
rows:   db 0
kind:   db 0
shape:  db 0
grp:    db 0
rr:     db 0
tick:   db 2
nsp:    db 0
shown:  db 0
ybase:  db 0
ncols:  db 0
nrows:  db 0
rown:   db 0
pat:    db 0
cnt:    db 0
cc:     db 0
usenb:  db 0
hv:     db 0
nb:     ds 4
regs:   ds 20               ; register block for the start-up tail
keys:   ds NC*5
used:   ds NC
lb:     ds LBSIZE
        ds 64
hstack:
; data nibble, mask nibble -> 2 bytes of pattern nibbles: 1 ink, 2 body (mask 0), 0 see-through
        ALIGN 256
ntab:
idx = 0
        DUP 256
dn = idx >> 4
mn = idx & 15
d3 = (dn >> 3) & 1
d2 = (dn >> 2) & 1
d1 = (dn >> 1) & 1
d0 = dn & 1
m3 = (mn >> 3) & 1
m2 = (mn >> 2) & 1
m1 = (mn >> 1) & 1
m0 = mn & 1
        db ((d3 + (1 - d3) * (1 - m3) * 2) << 4) | (d2 + (1 - d2) * (1 - m2) * 2)
        db ((d1 + (1 - d1) * (1 - m1) * 2) << 4) | (d0 + (1 - d0) * (1 - m0) * 2)
idx = idx + 1
        EDUP
; Experimental display interpolation. No game position or update-rate writes.
; The object dispatcher supplies an exact identity before its drawing routines.
e_object:
        ld (49028),a            ; replaced original instruction
        ld (sm_obj),hl          ; save dispatcher pointer (object minus one)
        ld (hsp),sp
        ld sp,hstack
        push af
        push hl
        ld a,r                  ; 10 M1 including patched JP through here
        ld l,a
        ld h,HIGH sm_object_r
        ld a,(hl)
        ld r,a                  ; 5 M1 from here through return
        pop hl
        pop af
        ld sp,(hsp)
        jp 35899                ; original effect: one M1, delta 1-10-5 = -14

; First plot of a pass stops the previous list before any sprite-port access.
sm_begin:
        ld a,(nsp)
        or a
        ret nz
        nextreg 0x62,0
        nextreg 0x61,0
        nextreg 0x60,0x80        ; WAIT active line 0 of the next frame
        nextreg 0x60,0
        push hl
        push de
        ld hl,(49026)           ; game's coarse/fine camera state
        ld de,(sm_camera)
        ld (sm_camera),hl
        or a
        sbc hl,de
        ld a,h
        or l
        ld (sm_scroll),a        ; snap while scenery scrolls
        pop de
        pop hl
        ret

sm_end:
        call sm_prune
        ld a,(nsp)
        or a
        jr z,.off
        nextreg 0x60,0xFF        ; HALT after the full positions
        nextreg 0x60,0xFF
        nextreg 0x62,0x40        ; run once, then remain at HALT
        jr .done
.off:   nextreg 0x62,0
.done:  xor a
        ld (sm_obj),a
        ld (sm_obj+1),a
        ret

; Discard objects absent from this pass. Otherwise an eight-bit tick wrap could
; mistake an old occupant of a reused object slot for a current neighbour.
sm_prune:
        push bc
        push de
        push hl
        ld a,(tick)
        ld c,a
        ld hl,sm_hist
        ld b,16
.row:   ld a,(hl)
        cp c
        jr z,.keep
        push hl
        ld de,6
        add hl,de
        ld (hl),0
        pop hl
.keep:  ld de,8
        add hl,de
        djnz .row
        pop hl
        pop de
        pop bc
        ret

sm_reset:
        nextreg 0x62,0
        xor a
        ld (sm_obj),a
        ld (sm_obj+1),a
        push hl
        push bc
        ld hl,sm_hist
        ld b,128
.clear: ld (hl),0
        inc hl
        djnz .clear
        pop bc
        pop hl
        ret

; Exact object positions are in two-pixel units. Their previous-minus-current
; difference is therefore the midpoint displacement in individual pixels.
sm_calc:
        push bc
        push de
        push hl
        push ix
        xor a
        ld (sm_dx),a
        ld (sm_dy),a
        ld hl,(sm_obj)
        inc l                   ; dispatcher supplied object minus one
        ld a,h
        cp 0xDF
        jp nz,.done
        ld a,l
        and 15
        cp 2
        jp nz,.done
        ld a,l
        cp 18
        jp c,.done
        and 0xF0
        rrca
        ld e,a
        ld d,0
        push hl
        ld hl,sm_hist
        add hl,de
        push hl
        pop ix
        pop hl
        inc l
        ld a,(hl)
        ld (sm_type),a
        inc l
        inc l
        ld e,(hl)              ; pixel-shift phase 0..3
        inc l
        ld a,(hl)              ; character column
        add a,a
        add a,a
        add a,e
        ld (sm_x),a
        inc l
        ld a,(hl)
        ld (sm_y),a
        ld a,(ix+6)
        or a
        jr z,.new
        ld a,(sm_type)
        cp (ix+1)
        jr nz,.new
        ld a,(tick)
        cp (ix+0)
        jr z,.reuse
        dec a
        cp (ix+0)
        jr nz,.new
        ld a,(sm_scroll)
        or a
        jr nz,.new
        ld a,(sm_x)
        ld e,a
        ld a,(ix+2)
        sub e
        call sm_limit
        ld (sm_dx),a
        ld a,(sm_y)
        ld e,a
        ld a,(ix+3)
        sub e
        call sm_limit
        ld (sm_dy),a
.new:   ld a,(tick)
        ld (ix+0),a
        ld a,(sm_type)
        ld (ix+1),a
        ld a,(sm_x)
        ld (ix+2),a
        ld a,(sm_y)
        ld (ix+3),a
        ld a,(sm_dx)
        ld (ix+4),a
        ld a,(sm_dy)
        ld (ix+5),a
        ld (ix+6),1
        jr .done
.reuse: ld a,(ix+4)
        ld (sm_dx),a
        ld a,(ix+5)
        ld (sm_dy),a
.done:  pop ix
        pop hl
        pop de
        pop bc
        ret

sm_limit:
        cp 9
        ret c
        cp 248
        ret nc
        xor a                   ; births, teleports and discontinuities snap
        ret

; A slot, HL exact X, ybase exact Y. Append the original/full coordinates.
; This list runs at line 0, while the game is outside its drawing hooks.
sm_emit_full:
        push af
        push bc
        ld c,a
        nextreg 0x60,0x34
        ld a,c
        nextreg 0x60,a
        nextreg 0x60,0x35
        ld a,l
        nextreg 0x60,a
        nextreg 0x60,0x36
        ld a,(ybase)
        nextreg 0x60,a
        nextreg 0x60,0x37
        ld a,h
        and 1
        nextreg 0x60,a
        pop bc
        pop af
        ret

sm_obj:    dw 0
sm_camera: dw 0
sm_scroll: db 0
sm_dx:     db 0
sm_dy:     db 0
sm_type:   db 0
sm_x:      db 0
sm_y:      db 0
sm_hist:   ds 128

; Exact R effect at any incoming clock; the tiny dispatcher never changes speed.
        ALIGN 256
sm_object_r:
        db 114,115,116,117,118,119,120,121,122,123,124,125,126,127,0,1
        db 2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17
        db 18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33
        db 34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49
        db 50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65
        db 66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81
        db 82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97
        db 98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113
        db 242,243,244,245,246,247,248,249,250,251,252,253,254,255,128,129
        db 130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145
        db 146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161
        db 162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177
        db 178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193
        db 194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209
        db 210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225
        db 226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241

; Display-only clipping for the attached pot, using its live zombie's foot line.
; The original attachment update at 34742 dereferences item+2 = parent+3.
; Its bit 3 at item+9 marks a released/falling item and must bypass this rule.
gc_prepare:
        ld a,b
        ld (gc_rows),a
        ld a,0xC0
        ld (attrs.gc_visibility_mask+1),a
        xor a
        ld (gc_grounded),a
        ld a,c
        or a
        ret nz                 ; masked figures only
        push bc
        push de
        push hl
        ld hl,(sm_obj)         ; dispatcher pointer = object minus one
        inc l
        ld a,h
        cp 0xDF
        jp nz,.done
        ld a,l
        and 15
        cp 2
        jp nz,.done
        ld a,l
        cp 18
        jp c,.done
        inc l
        ld a,(hl)
        cp 76                  ; the body already has its original height clip
        jr z,.grounded
        cp 62                  ; attached pot; weapons on the floor use type 64
        jp nz,.done
        inc l
        ld c,(hl)              ; pointer to parent's phase byte (parent+3)
        ld a,l
        add a,7
        ld l,a
        bit 3,(hl)             ; released, falling or turning into a pickup
        jp nz,.done
        ld a,c
        and 15
        cp 5
        jp nz,.done
        ld a,c
        sub 3
        cp 18
        jp c,.done
        ld l,a
        inc l
        ld a,(hl)
        cp 76
        jp nz,.done
        ld a,1
        ld (gc_grounded),a
        ld a,l
        add a,4
        ld l,a                 ; parent+5, top in line-pair units
        ld c,(hl)
        ld a,l
        add a,6
        ld l,a                 ; parent+11, visible line-pair count
        ld a,(hl)
        add a,c
        ld (gc_floor),a
        ; DE is the actual plot address, including the game's top clipping.
        ld a,d
        and 0x18
        add a,a
        add a,a
        add a,a
        ld h,a
        ld a,d
        and 7
        or h
        ld h,a
        ld a,e
        and 0xE0
        rrca
        rrca
        or h
        srl a
        ld l,a                 ; first displayed source row in line-pair units
        ld a,(gc_floor)
        sub l
        jr c,.hidden
        jr z,.hidden
        cp b
        jr nc,.done
        ld (gc_rows),a
        jr .done
.hidden:
        ld a,0x40
        ld (attrs.gc_visibility_mask+1),a ; retain extended attributes, visibility off
        jr .done               ; their unmodified source pattern stays cached
.grounded:
        ld a,1
        ld (gc_grounded),a
.done:  pop hl
        pop de
        pop bc
        ld a,(gc_rows)
        ld b,a                 ; display height only; mrows retains original CPU loop
        ret

gc_motion:
        ld a,(gc_grounded)
        or a
        ret z
        xor a
        ld (sm_dy),a           ; never push the clipped bottom below the ground
        ret                    ; horizontal midpoint movement is retained

; Direct lookup of the 28 prepainted partial pot images. Every candidate still
; compares its complete live source bytes before it can supply cached pixels.
gc_atlas:
        ld a,(shape)
        dec a
        cp 7
        ret nc
        ld e,a
        ld a,(gfx)
        cp 0xAA
        jr nz,.no
        ld a,(gfx+1)
        sub 0xC8
        cp 4
        jr nc,.no
        ld d,a
        add a,a
        add a,a
        add a,a
        sub d
        add a,e                ; phase * 7 + partial height - 1
        ld e,a
        and 7
        add a,a
        add a,a
        ld (atlas_off),a
        ld h,a
        ld l,0
        ld a,e
        srl a
        srl a
        srl a
        add a,96
        ld (atlas_page),a
        jp atlas_compare
.no:    or a
        ret

gc_rows:     db 0
gc_grounded: db 0
gc_floor:    db 0

hook_end:
        ASSERT hook_end <= 0x3828
page_end:

; --- setup routine (stub bank, 0xD000): palette, hide all, clip, sprites on -----------------------------------
        ORG 0xD000
setup:  nextreg 0x62,0
        nextreg 0x4B,0
        nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,16
.c:     ld a,(hl)
        inc hl
        nextreg 0x41,a
        djnz .c
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x1C,2
        nextreg 0x19,0
        nextreg 0x19,255
        nextreg 0x19,0
        nextreg 0x19,191
        nextreg 0x15,0x01
        ret
; 0 transparent, 1 cyan (the game's ink: attribute 5 where figures are, every level), 2 black (paper: bodies), then the
; Spectrum's others
pal:    db 0x00,0x16,0x00,0x02,0xA0,0xA2,0x14,0xFC,0xB4,0xB6,0x03,0xE0,0xE7,0x1C,0x1F,0xFF
setup_end:

        SAVEBIN "gng_page.bin",0x2000,page_end-0x2000
        SAVEBIN "gng_setup.bin",0xD000,setup_end-0xD000
