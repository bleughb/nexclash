; R-Type prototype step 2: figures as hardware sprites (included by l2scroll.asm).
;
; Every figure the game draws goes through one of four plotters (8CFD normal,
; 8D65 mirrored, 8DD3 upside down, 8E29 both) with HL = graphic, B/C = row/column,
; D/E = height/width in 8x8 cells. A graphic is a row-major stream of cells: one
; attribute byte then eight pixel bytes, or the single byte 36 for an empty cell.
; Each plot is recorded here; its graphic is converted once into 16x16 4bpp
; patterns (2x2 cells each, colour index = ink + 8*bright; black paper transparent,
; coloured paper drawn) and
; cached by graphic address and ink override (8EB1), with a checksum: the game
; rewrites some graphics in place and those are converted again into the same slots. The game's flips become the
; sprite mirror flags. The native plotter still runs for the owner/collision maps;
; the copier's figure copy to the ULA is skipped while sprites are on (8886).
; All sprites recorded since the previous copier call are published at 8842.
; A figure that does not fit (128 sprites, 128 patterns) is drawn natively on the
; ULA for that update. The cell hook flags only cells a sprite shows; the copier
; copies every other buffer cell natively, including cells produced outside the
; plotters (the level 3 battleship).
CELLW   EQU 17                  ; cells kept per row (16 + one empty)
CELLH   EQU 19                  ; plots are at most 18 cells high (spr_record), plus the row a tile reads below
MAXENT  EQU 44
MAXSPR  EQU 128
BEHIND_PG EQU 26               ; bank 13: the behind-scenery flags (behind_flags.asm)
FLAGMAP EQU 0x3B00              ; one byte per cell, same layout as the owner map 7E00 (to 3D80; 256-aligned)
TITLE_PACE EQU 4               ; frames per title update (16 / 4 = 4 pixels a frame)
BUDGET  EQU 24                  ; tiles converted per update
CACHE_LIM EQU 128               ; pattern slots for cached graphics
COL_DIR EQU 64                  ; colour pages (r_type_colour.py): directory
PRE_DIR EQU 48                  ; outlined graphics: directory page (bank 24)
PRE_PAT0 EQU 49                 ; outlined graphics: first pattern page (64 x 128 bytes each)
PRE_ENTRY EQU 12
ENT     EQU 20                  ; cache entry: 0-1 graphic, 2 ink, 3 first slot, 4 sprites,
                                ; 5-13 tile bitmap, 14-15 checksum, 16 outlined, 17-18 tiles x/y
COL_REC0 EQU 66                 ; first record page (the directory spans pages 64-65)
COL_REC EQU 40                  ; bytes per painted cell
COL_PER_PAGE EQU 8192/COL_REC

spr_setup:
        nextreg 0x43,0x20       ; edit the first sprite palette
        nextreg 0x40,0
        ld hl,col_tab
        ld b,16
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        ld hl,col_tab+1         ; flash colours: entry 16n+1 = colour n (palette offset n)
        ld bc,0x0F11
.q:     ld a,c
        nextreg 0x40,a
        ld a,(hl)
        nextreg 0x41,a
        inc hl
        ld a,c
        add a,16
        ld c,a
        djnz .q
        nextreg 0x43,0
        nextreg 0x4B,0          ; colour index 0 is transparent
        nextreg 0x1C,2          ; reset sprite clip index
        nextreg 0x19,8
        nextreg 0x19,247
        nextreg 0x19,0
        nextreg 0x19,159
        nextreg 0x15,LORDER     ; layer order (LORDER); sprite 0 on top; hidden
        ret

; A level (or life) has just been drawn: empty cache, sprites on.
spr_start:
        ld a,(run_fast)         ; conversion budget: unlimited outside play (see spr_publish)
        or a
        ld a,BUDGET
        jr nz,.bg
        ld a,250
.bg:    ld (budget),a
        xor a
        ld (cache_n),a
        ld (spr_n),a
        ld a,MAXSPR
        ld (spr_prev),a         ; the next publication hides every stale sprite
        ld a,1
        ld (spr_on),a
        IFDEF L2_SPR_HIDE
        nextreg 0x15,LORDER     ; debug: sprites hidden, only native (ULA) figures show
        ELSE
        nextreg 0x15,LORDER+1
        ENDIF
        ret

; ---- FDF8 replaces LD HL,4000: the game clears the screen (title -> high scores, game start).
; The last sprites must not stay over the next page: hidden until the next publish shows them.
spr_cls:
        nextreg 0x15,LORDER
        ld hl,0x4000
        jp 0xFDFB

; ---- plotter entries: record, then the displaced instructions -----------------
plot_n: xor a
        call spr_record
        call .body
        jp spr_after
.body:  push bc
        push de
        exx
        jp 0x8D00
plot_h: ld a,1
        call spr_record
        call .body
        jp spr_after
.body:  push bc
        push de
        ld b,0x5D
        jp 0x8D69
plot_v: ld a,2
        call spr_record
        call .body
        jp spr_after
.body:  push bc
        push de
        exx
        jp 0x8DD6
plot_hv:
        ld a,3
        call spr_record
        call .body
        jp spr_after
.body:  push bc
        push de
        ld b,0x5D
        jp 0x8E2D

; The native plot has finished. A figure keeps its sprites only if every cell the
; plotter tried was drawn (8EC2 candidates = 8EA2 writes); otherwise another
; figure or the scenery owns part of it and the native ULA cells show it exactly.
spr_after:
        push af
        push hl
        ld a,(cur_serial)
        or a
        jr z,.x
        ld a,(emitted)
        or a
        jr nz,.ok
        ld hl,stat_part         ; a plot left to the ULA (8x8 colour blocks)
        inc (hl)
        jr .x
        ; Every figure is whole: overlaps follow plot order, pixel by pixel (the old rule, partly
        ; hidden figures behind all others, was removed 2026-11-17).
.ok:    ld a,(cur_serial)
        ld hl,plot_ok
        add hl,a
        ld (hl),1
.x:     xor a
        ld (cur_serial),a
        pop hl
        pop af
        ret

; 8EC2 replaces LD A,B / RRCA / RRCA: the plotter is testing one cell.
cand_hook:
        push hl
        ld hl,cand
        inc (hl)
        pop hl
        ld a,b
        rrca
        rrca
        jp 0x8EC5

; 8886 replaces LD A,H / ADD A,20: skip the eight-byte figure copy to the ULA.
spr_gate:
        ld a,(spr_on)
        or a
        jr z,.native
        push hl
        ld a,d
        add a,high(FLAGMAP)-0x7E
        ld h,a
        ld l,e
        ld a,(hl)               ; serial of the plot that drew this cell, or 0
        ld (hl),0               ; one use: other producers of buffer cells never set it
        or a
        jr z,.nat
        ld hl,plot_ok
        add hl,a
        ld a,(hl)
        or a
        pop hl
        jr z,.native
.blank: xor a                   ; a sprite shows it: the ULA cell must be blank,
        ld (hl),a               ; or older pixels show in the figure's colours
        inc h
        ld (hl),a
        inc h
        ld (hl),a
        inc h
        ld (hl),a
        inc h
        ld (hl),a
        inc h
        ld (hl),a
        inc h
        ld (hl),a
        inc h
        ld (hl),a
        jp 0x88A9
.nat:   pop hl
        IFDEF L2_SHIP
        ld a,(ship_on)          ; the battleship's cells are on the tilemap (ship.asm)
        or a
        jr z,.native
        ld a,(de)
        cp 0x9C
        jr z,.blank
        ENDIF
.native:
        ld a,h
        add a,0x20
        jp 0x8889

; 8EA2 replaces LD A,(7A9C): a plotter is about to draw one cell (DE = its owner
; map byte). Remember whether that figure is shown by sprites or by the ULA.
cell_hook:
        push hl
        ld a,d
        add a,high(FLAGMAP)-0x7E
        ld h,a
        ld l,e
        ld a,(cur_serial)
        ld (hl),a
        ld hl,succ
        inc (hl)
        pop hl
        ld a,(0x7A9C)
        jp 0x8EA5

; ---- record one plot: A = flip, HL/BC/DE as the plotter receives them ---------
; Runs at 28MHz even outside play (title: the game's own 3.5MHz timing must not pay for it).
spr_record:
        nextreg 7,3
        call spr_rec_body
        push af
        ld a,(run_fast)
        nextreg 7,a
        pop af
        ret
spr_rec_body:
        ld (r_flip),a
        xor a
        ld (cur_serial),a
        ld (emitted),a
        ld (cand),a
        ld (succ),a
        ld a,(spr_on)
        or a
        ret z
        ld a,(0x8EBF)
        cp 0x60
        ret nz                  ; the plotter is drawing scenery straight to the ULA
        IFDEF L2_SHIP
        ld a,d                  ; level 3 battleship hull strip (1x13, object 85D9): tilemap
        cp 13
        jr nz,.nsh
        ld a,(0x719C)
        cp '3'
        jr nz,.nsh
        push hl
        push iy
        pop hl
        ld a,l
        cp 0xD9
        jr nz,.nsp
        ld a,h
        cp 0x85
.nsp:   pop hl
        jr nz,.nsh
        push bc
        push de
        push hl
        xor a
        call s_call
        pop hl
        pop de
        pop bc
        or a
        ret z                   ; ship.asm shows it; the copier gate blanks its ULA cells
.nsh:
        ENDIF
        IFDEF L2_BEHIND_FLAGS
        call behind_chk
        ret z                   ; flagged (behind_flags.asm): the game draws it, behind Layer 2
        ENDIF
        push hl
        push de
        push bc
        push ix
        ld (r_src),hl
        ld (r_w),de             ; r_w = E, r_h = D
        ld (r_col),bc           ; r_col = C, r_row = B
        ld a,(0x8EB1)           ; colour override (flashing): convert once in colour 1 and pick
        or a                    ; the colour with the sprite palette offset, so the flash colours
        jr z,.ink               ; share one cache entry (spr_setup: entry 16n+1 = colour n)
        ld b,a
        and 7
        bit 6,b
        jr z,.nb
        add a,8
.nb:    rlca
        rlca
        rlca
        rlca
        ld (r_pal),a
        ld a,1
        jr .ik
.ink:   ld (r_pal),a
.ik:    ld (r_ink),a
        ld a,(need_reset)
        or a
        jr z,.nr
        push de
        ld hl,plot_ok
        ld de,plot_ok+1
        ld bc,255
        ld (hl),0
        ldir
        pop de
        xor a
        ld (need_reset),a
        ld (serial),a
.nr:    ld a,(serial)
        inc a
        jp z,.out               ; more than 255 plots in one update: native
        ld (serial),a
        ld (cur_serial),a
        ld a,(spr_n)
        ld (save_n),a
        ld a,e
        dec a
        cp 16
        jp nc,.out
        ld a,d
        dec a
        cp 18                   ; at most 8 x 9 sprites: the entry bitmap is 72 bits
        jr nc,.out
        ld a,e
        inc a
        srl a
        ld (nx),a
        ld a,d
        inc a
        srl a
        ld (ny),a
        call stream_sum
        call cache_find
        jr z,.hit
        call convert
        jr c,.out
        jr .have
.hit:   ld hl,(r_sum)
        ld a,(ix+14)
        cp l
        jr nz,.stale
        ld a,(ix+15)
        cp h
        jr z,.have
.stale: call reconvert          ; the game rewrote this graphic in place
        jr c,.out
.have:  ld a,(upd)               ; shown this update: not evicted (c_evict)
        ld (ix+19),a
        ld a,(spr_n)
        add a,(ix+4)
        jr c,.out
        cp MAXSPR+1
        jp nc,.out              ; no sprites left: the whole figure stays on the ULA
        ld a,(ix+16)
        or a
        jr z,.em
        ld a,(ix+17)
        ld (nx),a
        ld a,(ix+18)
        ld (ny),a
        call emit_pre
        jr .emd
.em:    call emit
.emd:   ld a,1
        ld (emitted),a
        IFDEF L2_GLIDE
        xor a
        call g_call             ; glide.asm: record this figure and its object
        ld a,1                  ; as before: the native plotter runs next
        ENDIF
.out:   pop ix
        pop bc
        pop de
        pop hl
        ret

; Z and IX = entry when cached; NZ and IX = first free entry otherwise.
cache_find:
        ld ix,cache
        ld a,(cache_n)
        or a
        jr z,.miss
        ld b,a
        ld hl,(r_src)
        ld a,(r_ink)
        ld c,a
        ld de,ENT
.l:     ld a,(ix+0)
        cp l
        jr nz,.n
        ld a,(ix+1)
        cp h
        jr nz,.n
        ld a,(ix+2)
        cp c
        ret z
.n:     add ix,de
        djnz .l
.miss:  or 1
        ret

; ---- convert the graphic at r_src into patterns; carry = no room --------------
convert:
        call pre_find           ; an outlined graphic: copy its pre-rendered patterns
        jp z,conv_pre
        ld a,(ny)               ; spread conversion work: at most BUDGET tiles an
        ld d,a                  ; update, or one figure of any size
        ld a,(nx)
        ld e,a
        mul d,e
        ld c,e                  ; tiles this figure may need
        ld a,(budget)           ; fits: spend it; too big: only as the update's first
        cp c
        jr nc,.sub
        cp BUDGET
        jp nz,conv_later
        xor a
        jr .spend
.sub:   sub c
.spend: ld (budget),a
        call build_cells        ; c_alloc reserves only the tiles that are not empty
        ld a,0xFF
        call alloc              ; IX = entry, A = first slot
        jp c,conv_fail
        ld (c_slot),a
        ld hl,ca_n
        add a,(hl)
        ld (slot_lim),a
        ld hl,(r_src)
        ld (ix+0),l
        ld (ix+1),h
        ld a,(r_ink)
        ld (ix+2),a
        ld (ix+16),0
        call conv_core
        jp c,conv_fail
        ld a,(c_slot)
        sub (ix+3)
        ld (ix+4),a             ; sprites this figure needs (the rest of its slots free again)
        or a
        ret
; A = slots wanted: glide.asm c_alloc. IX = entry, A = first slot; carry = no room. Keeps BC, DE, HL.
alloc:  push bc
        push de
        push hl
        ld (ca_n),a
        ld a,0x0F
        call g_call
        pop hl
        pop de
        pop bc
        ld ix,(ca_ent)
        ld a,(ca_slot)
        add a,1                 ; carry when FF
        dec a
        ret
; Same entry, same pattern slots, new pixels. Carry = it no longer fits.
reconvert:
        ld hl,stat_re
        inc (hl)
        ld (ix+16),0            ; converted normally from now on
        ld a,(ix+3)
        ld (c_slot),a
        add a,(ix+4)
        ld (slot_lim),a
        call conv_core
        ret nc
        ld (ix+0),0xFF          ; grew: forget it, a later plot converts it afresh
        ld (ix+1),0xFF
        scf
        ret
conv_fail:                      ; the figures shown this update need more than 128 patterns
conv_keep:
        ld hl,stat_drop
        inc (hl)
        scf
        ret
conv_later:
        scf                     ; the figure is drawn natively this update
        ret

; Upload the graphic r_src into slots c_slot.. below slot_lim; bitmap and
; checksum into entry IX. Carry = out of slots.
conv_core:
        ld hl,(r_sum)
        ld (ix+14),l
        ld (ix+15),h
        call build_cells
        push ix
        pop hl
        ld a,5
        add hl,a
        ld b,9
        xor a
.clr:   ld (hl),a
        inc hl
        djnz .clr
        ld (t_idx),a
        ld hl,celltab
        ld (rowbase),hl
        ld a,(ny)
        ld b,a
.ty:    push bc
        ld hl,(rowbase)
        ld (tp),hl
        ld a,(nx)
        ld b,a
.tx:    push bc
        ld hl,(tp)
        call do_tile
        jr c,.full
        call nz,set_bit
        ld hl,(tp)
        ld a,4
        add hl,a
        ld (tp),hl
        ld hl,t_idx
        inc (hl)
        pop bc
        djnz .tx
        ld hl,(rowbase)
        ld a,CELLW*4
        add hl,a
        ld (rowbase),hl
        pop bc
        djnz .ty
        or a
        ret
.full:  pop bc
        pop bc
        scf
        ret

; celltab = pointers to the cells of the graphic r_src (0 = empty or absent).
build_cells:
        ld a,(r_h)              ; clear only the rows a tile can read: h+1
        inc a
        ld d,a
        ld e,CELLW*2
        mul d,e
        dec de
        ld b,d
        ld c,e
        ld hl,celltab
        ld de,celltab+1
        ld (hl),0
        ldir
        ld hl,(r_src)
        ld a,(r_h)
        ld b,a
        ld de,celltab
.r:   push bc
        push de
        ld a,(r_w)
        ld b,a
.c:   ld a,(hl)
        cp 0x36
        jr z,.k
        ld a,l
        ld (de),a
        inc de
        ld a,h
        ld (de),a
        inc de
        ld a,9
        add hl,a
        jr .n
.k:  inc de
        inc de
        inc hl
.n:  djnz .c
        pop de
        ld a,CELLW*2
        add de,a
        pop bc
        djnz .r
        ret

; DE and r_sum = sum of every byte of the graphic stream at r_src.
stream_sum:
        ld hl,(r_src)
        ld de,0
        ld a,(r_h)
        ld b,a
.row:   push bc
        ld a,(r_w)
        ld b,a
.col:   ld a,(hl)
        cp 0x36
        jr z,.one
        ld c,9
.s:     ld a,(hl)
        add de,a
        inc hl
        dec c
        jr nz,.s
        jr .next
.one:   add de,a
        inc hl
.next:  djnz .col
        pop bc
        djnz .row
        ld (r_sum),de
        ret

; HL = cell-pointer pair of the tile's top row. Z = empty; NZ = uploaded; C = full.
do_tile:
        ld de,tl
        ld bc,4
        ldir
        ld a,CELLW*2-4
        add hl,a
        ld bc,4
        ldir
        ld hl,tl
        ld b,8
        xor a
.z:     or (hl)
        inc hl
        djnz .z
        ret z
        ld a,(c_slot)
        ld hl,slot_lim
        cp (hl)
        jr nc,.ovf
        IFDEF L2_GLIDE
        call g_hold             ; the glide interrupt also selects port 303B: off while uploading
        ENDIF
        ld bc,0x303B
        ld e,a
        srl a
        bit 0,e
        jr z,.s
        or 0x80
.s:     out (c),a               ; pattern, upper or lower 128 bytes
        ld hl,(tl)
        ld (ea),hl
        ld hl,(tr)
        ld (eb),hl
        call half
        ld hl,(bl)
        ld (ea),hl
        ld hl,(br)
        ld (eb),hl
        call half
        ld hl,c_slot
        inc (hl)
        IFDEF L2_GLIDE
        call g_release
        ENDIF
        or 1
        ret
.ovf:   xor a
        inc a
        scf
        ret

; Two cells of one tile half, line-major. Colours are worked out once per cell
; into four-byte tables (entry = pixel pair, bit 1 = left pixel).
half:   ld de,(ea)
        ld hl,tab_l
        call cell_tab
        ld de,(eb)
        ld hl,tab_r
        call cell_tab
        ld de,(ea)
        call col_lookup
        ld (ov_pa),a
        ld (ov_oa),hl
        ld de,(eb)
        call col_lookup
        ld (ov_pb),a
        ld (ov_ob),hl
        xor a
.l:     ld (e_line),a
        ld de,(ea)
        ld hl,tab_l
        call emit_line
        ld a,(ov_pa)
        ld hl,(ov_oa)
        call col_apply
        call line_out
        ld de,(eb)
        ld hl,tab_r
        call emit_line
        ld a,(ov_pb)
        ld hl,(ov_ob)
        call col_apply
        call line_out
        ld a,(e_line)
        inc a
        cp 8
        jr nz,.l
        ret

line_out:
        ld hl,lbuf
        ld bc,0x045B
        otir
        ret

; ---- painted colours (r_type_colour.py) -------------------------------------
; DE = cell (attribute byte address) or 0 -> A = colour page of its record (0 =
; unpainted) and HL = the record's offset in slot 0. Flash draws (8EB1 ink
; override) keep the forced colour.
col_lookup:
        ld a,d
        or e
        ret z
        ld a,(r_ink)
        or a
        jp nz,.none
        ld a,(0x719C)
        sub 0x30
        cp 16
        jp nc,.none
        add a,a
        add a,a
        ld l,a
        ld h,0
        ld a,COL_DIR
        call col_map
        ld c,(hl)
        inc hl
        ld b,(hl)
        inc hl
        ld (cl_count),bc
        ld a,b
        or c
        jp z,.unmap
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld (cl_first),hl
        ld hl,0
        ld (cl_lo),hl
.bs:    ld a,b                  ; BC = items left; lo = first candidate
        or c
        jr z,.end
        ld (cl_n),bc
        srl b
        rr c                    ; half
        ld (cl_half),bc
        ld hl,(cl_lo)
        add hl,bc
        ld (cl_mid),hl
        call cl_addr
        or a
        sbc hl,de               ; carry: entry < cell
        jr nc,.left
        ld hl,(cl_mid)
        inc hl
        ld (cl_lo),hl
        ld hl,(cl_n)
        ld bc,(cl_half)
        or a
        sbc hl,bc
        dec hl                  ; n - half - 1
        ld b,h
        ld c,l
        jr .bs
.left:  ld bc,(cl_half)
        jr .bs
.end:   ld hl,(cl_lo)
        ld bc,(cl_count)
        or a
        sbc hl,bc
        jp nc,.unmap            ; past the end: not painted
        ld hl,(cl_lo)
        call cl_addr
        or a
        sbc hl,de
        jp nz,.unmap
        ld hl,(cl_lo)
        ld bc,(cl_first)
        add hl,bc               ; record number
        ld a,COL_REC0
        ld bc,COL_PER_PAGE
.pg:    or a
        sbc hl,bc
        jr c,.inpg
        inc a
        jr .pg
.inpg:  add hl,bc               ; L = record within its page
        ld d,l
        ld e,COL_REC
        mul d,e
        ex de,hl                ; HL = offset in the page
        ld (cl_page),a
        call col_unmap
        ld a,(cl_page)
        ret
.unmap: call col_unmap
.none:  xor a
        ret

; HL = index into this level's sorted addresses -> HL = the cell address there.
cl_addr:
        ld bc,(cl_first)
        add hl,bc
        add hl,hl
        ld bc,64
        add hl,bc
        ld a,COL_DIR            ; the sorted addresses run on into the next page
        bit 5,h
        jr z,.p
        inc a
        res 5,h
.p:     push hl
        call col_map
        pop hl
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ret

        IFDEF L2_BEHIND_FLAGS
; HL = graphic. Z if behind_flags.asm lists it for this level (0x719C): such a figure stays in the
; ULA, under Layer 2, so the scenery hides it as in the original. Table: page BEHIND_PG, entries
; level, graphic low, graphic high; level 0 ends it.
behind_chk:
        push bc
        push de
        push hl
        ex de,hl
        ld a,BEHIND_PG
        call col_map
        ld a,(0x719C)
        ld c,a
        ld hl,0
.l:     ld a,(hl)
        or a
        jr z,.no
        inc hl
        cp c
        ld a,(hl)
        inc hl
        jr nz,.n
        cp e
        jr nz,.n
        ld a,(hl)
        cp d
        jr z,.yes
.n:     inc hl
        jr .l
.no:    ld a,1
        jr .r
.yes:   xor a                   ; listed
.r:     ld b,a
        call col_unmap
        ld a,b
        or a
        pop hl
        pop de
        pop bc
        ret

        ENDIF                   ; L2_BEHIND_FLAGS

        IFDEF L2_GLIDE
GLIDE_PG EQU 27                 ; bank 13 high half: glide.asm
; A = glide.asm entry (0 record, 3 publish): call it with its page in slot 0.
g_call: push hl
        ld l,a
        ld h,1                  ; glide.asm entries at 0100
        ld (.j+1),hl
        ld a,GLIDE_PG
        ld (cur_mmu0),a
        nextreg 0x50,a
        pop hl
.j:     call 0
.mu:    ld a,(g_miss)           ; steps the interrupt skipped meanwhile
        or a
        jp z,col_unmap
        dec a
        ld (g_miss),a
        call 0x0106
        jr .mu
g_busy: db 0
g_miss: db 0
; Around a pattern upload: the glide interrupt counts the steps it skips (g_busy 2); afterwards
; they are made up at once (the upload takes a fraction of a frame). Preserve all registers.
g_hold: push af
        ld a,2
        ld (g_busy),a
        pop af
        ret
g_release:
        push af
        push bc
        push hl
        xor a
        ld (g_busy),a
.mu:    ld a,(g_miss)
        or a
        jr z,.md
        dec a
        ld (g_miss),a
        ld a,(cur_mmu0)         ; the caller's slot 0 (a colour page) comes back after
        push af
        ld a,6
        call g_call
        pop af
        ld (cur_mmu0),a
        nextreg 0x50,a
        jr .mu
.md:    pop hl
        pop bc
        pop af
        ret
hk_fr:  db 0                    ; frames since the last publish (irq_out)
hk_last: db 0
; 8842: publish with the glide start positions; the interrupt keeps off the sprite port meanwhile.
glide_publish:
        ld a,(run_fast)         ; outside play (title) the game's updates alternate 2 and 3 frames;
        or a                    ; hold each at TITLE_PACE frames: the logo letters move 16 pixels
        jr nz,.go               ; an update, so 4 gives exactly 4 pixels every frame (owner, 2026-11-17)
.w:     ld a,(hk_fr)
        cp TITLE_PACE
        jr c,.w
.go:
        IFDEF L2_SHIP
        call ship_tick_h
        ENDIF
        ld a,(hk_fr)            ; the update's length for glide (counted on every interrupt)
        ld (hk_last),a
        xor a
        ld (hk_fr),a
        ld a,1
        ld (g_busy),a
        ld a,3
        call g_call
        call spr_publish
        xor a
        ld (g_busy),a
        ret
; From the interrupt: step the gliding sprites (not while the main code is in glide or publishing).
glide_irq:
        IFDEF L2_GLIDE_NOIRQ
        ret
        ENDIF
        ld a,(g_busy)
        cp 2
        jr z,.miss              ; recording a plot: make the step up afterwards
        or a
        ret nz                  ; publishing
        ld a,(cur_mmu0)
        cp GLIDE_PG
        jr z,.miss              ; the main code is in glide: g_call makes the step up
        nextreg 0x50,GLIDE_PG   ; irq_out maps cur_mmu0 back
        jp 0x0106
.miss:  ld hl,g_miss
        inc (hl)
        ret
        ENDIF

        IFDEF L2_SHIP
SHIP_PG EQU 127                 ; bank 63 high half: ship.asm (level 3 battleship tilemap)
; A = ship.asm entry (0 plot, 3 off, 6 tick): call it with its page in slot 0; A comes back.
s_call: push hl
        ld l,a
        ld h,1
        ld (.j+1),hl
        ld a,SHIP_PG
        ld (cur_mmu0),a
        nextreg 0x50,a
        pop hl
.j:     call 0
        push af
        call col_unmap
        pop af
        ret
ship_stop:
        ld a,(ship_on)
        or a
        ret z
        ld a,3
        jr s_call
ship_tick_h:
        ld a,(ship_on)
        or a
        ret z
        ld a,6
        jr s_call
ship_on: db 0                   ; ship.asm holds page 14 (set by its build, cleared by ship_off)
        ENDIF

col_map:
        ld (cur_mmu0),a         ; variable first: the ISR restores slot 0 from it
        nextreg 0x50,a
        ret
col_unmap:
        ld a,0xFF
        ld (cur_mmu0),a
        nextreg 0x50,0xFF
        ret

; A = record page (0 = none), HL = record offset: paint line e_line of lbuf.
; byte = (default AND keep) OR painted nibbles, then transparent pixels cleared.
col_apply:
        or a
        ret z
        call col_map
        push hl
        ld a,(e_line)
        add a,a
        add a,a
        add hl,a
        ld de,lbuf
        ld b,4
.c:     ld a,(hl)
        or a
        jr z,.k
        ld c,a
        ld a,0xFF
        bit 7,c
        jr nz,.h0
        bit 6,c
        jr nz,.h0
        bit 5,c
        jr nz,.h0
        bit 4,c
        jr z,.h1
.h0:    and 0x0F                ; high nibble painted
.h1:    ld (.km+1),a
        ld a,c
        and 0x0F
        ld a,(.km+1)
        jr z,.l1
        and 0xF0                ; low nibble painted
.l1:    ld (.km+1),a
        ld a,(de)
.km:    and 0
        or c
        ld (de),a
.k:     inc hl
        inc de
        djnz .c
        pop hl
        ld a,(e_line)
        add a,32
        add hl,a
        ld c,(hl)               ; transparent mask, bit 7 = leftmost
        ld a,c
        or a
        jr z,.done
        ld de,lbuf
        ld b,4
.t:     ld a,0xFF
        sla c
        jr nc,.t1
        and 0x0F
.t1:    sla c
        jr nc,.t2
        and 0xF0
.t2:    ld (.tm+1),a
        ld a,(de)
.tm:    and 0
        ld (de),a
        inc de
        djnz .t
.done:  jp col_unmap

; HL = table for the cell DE (0 = blank). Index = ink + 8*bright; black paper is
; transparent, coloured paper drawn, black ink on coloured paper opaque black.
cell_tab:
        push hl
        ld bc,0                 ; B paper, C ink
        ld a,d
        or e
        jr z,.fill
        ld a,(r_ink)
        or a
        jr nz,.at
        ld a,(de)
.at:    ld l,a
        rrca
        rrca
        rrca
        ld h,a                  ; bits 0..2 paper, bit 3 bright
        and 7
        jr z,.pz
        ld a,h
        and 15
.pz:    ld b,a
        ld a,l
        and 7
        jr nz,.ic
        ld a,b
        or a
        jr z,.fill              ; black on black: nothing to show
        ld c,8
        jr .fill
.ic:    ld c,a
        ld a,h
        and 8
        or c
        ld c,a
.fill:  pop hl
        ld a,b
        rlca
        rlca
        rlca
        rlca
        ld e,a
        or b
        ld (hl),a               ; paper, paper
        inc hl
        ld a,e
        or c
        ld (hl),a               ; paper, ink
        inc hl
        ld a,c
        rlca
        rlca
        rlca
        rlca
        ld d,a
        or b
        ld (hl),a               ; ink, paper
        inc hl
        ld a,d
        or c
        ld (hl),a               ; ink, ink
        ret

; Four pattern bytes of line e_line of cell DE (or 0), table HL -> lbuf.
emit_line:
        ld a,d
        or e
        jr z,.blank
        push hl
        ld a,(e_line)
        inc a
        ex de,hl
        add hl,a
        ld c,(hl)
        pop hl
        ld de,lbuf
        ld b,4
.p:     xor a
        sla c
        rla
        sla c
        rla
        push hl
        add hl,a
        ld a,(hl)
        pop hl
        ld (de),a
        inc de
        djnz .p
        ret
.blank: ld hl,0
        ld (lbuf),hl
        ld (lbuf+2),hl
        ret

; HL = bitmap byte, A = mask for tile t_idx of entry IX.
bit_addr:
        ld a,(t_idx)
        ld c,a
        rrca
        rrca
        rrca
        and 0x1F
        add a,5
        push ix
        pop hl
        add hl,a
        ld a,c
        and 7
        ld b,a
        inc b
        ld a,0x80
.r:     rlca
        djnz .r
        ret
set_bit:
        call bit_addr
        or (hl)
        ld (hl),a
        ret

; ---- sprite attributes for the cached entry IX at r_row/r_col -----------------
emit:   ld a,(ix+3)
        ld (c_slot),a
        xor a
        ld (t_idx),a
        ld c,a                  ; tile row
.ty:    ld b,0                  ; tile column
.tx:    push bc
        call bit_addr
        and (hl)
        jp z,.next
        pop bc
        push bc
        ld a,b
        add a,a
        ld d,a
        ld a,(r_flip)
        and 1
        ld a,d
        jr z,.nh
        ld a,(r_w)
        sub 2
        sub d
.nh:    ld hl,r_col
        add a,(hl)
        inc a                   ; column + 1: 0..31 are on or beside the screen
        cp 32
        jp nc,.adv
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,24
        add hl,de
        ld (e_x),hl
        ld a,c
        add a,a
        ld d,a
        ld a,(r_flip)
        and 2
        ld a,d
        jr z,.nv
        ld a,(r_h)
        sub 2
        sub d
.nv:    ld hl,r_row
        add a,(hl)
        inc a
        cp 21
        jp nc,.adv
        add a,a
        add a,a
        add a,a
        add a,24
        ld (e_y),a
        ld a,(spr_n)
        cp MAXSPR
        jp nc,.adv
        ld l,a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,hl
        add hl,de
        ld de,spr_list
        add hl,de
        ld a,(e_x)
        ld (hl),a
        inc hl
        ld a,(e_y)
        ld (hl),a
        inc hl
        ld a,(r_flip)
        ld d,a
        and 1
        rlca
        rlca
        rlca
        ld e,a                  ; X mirror
        ld a,d
        and 2
        add a,a
        or e                    ; Y mirror
        ld d,a
        ld a,(r_pal)            ; flash colour (palette offset)
        or d
        ld d,a
        ld a,(e_x+1)
        and 1
        or d
        ld (hl),a
        inc hl
        ld a,(c_slot)
        ld d,a
        srl a
        or 0xC0                 ; visible, fifth byte follows
        ld (hl),a
        inc hl
        ld a,d
        rrca
        rrca
        and 0x40
        or 0x80                 ; 4bpp, pattern half
        ld (hl),a
        ld hl,spr_n
        inc (hl)
.adv:   ld hl,c_slot
        inc (hl)
.next:  ld hl,t_idx
        inc (hl)
        pop bc
        inc b
        ld a,(nx)
        cp b
        jp nz,.tx
        inc c
        ld a,(ny)
        cp c
        jp nz,.ty
        ret

; Outlined graphic (conv_pre): tiles of the pre-rendered canvas, which starts one pixel up and
; left of the plot and is r_w*8+2 by r_h*8+2 pixels; a mirrored tile mirrors around that canvas.
emit_pre:
        ld a,(ix+3)
        ld (c_slot),a
        xor a
        ld (t_idx),a
        ld c,a                  ; tile row
.ty:    ld b,0                  ; tile column
.tx:    push bc
        call bit_addr
        and (hl)
        jp z,.next
        pop bc
        push bc
        ld d,b
        ld e,16
        mul d,e                 ; 16 * column
        ld a,(r_flip)
        and 1
        jr z,.xh
        ld a,(r_w)
        call canvas_size        ; HL = r_w * 8 + 2
        or a
        sbc hl,de
        ld de,16
        or a
        sbc hl,de               ; width - 16 * (column + 1)
        ex de,hl
.xh:    ld a,(r_col)
        call cell_px            ; HL = signed cell * 8 + 31 (sprite X of pixel -1)
        add hl,de
        bit 7,h
        jp nz,.adv
        push hl
        ld de,320
        or a
        sbc hl,de
        pop hl
        jp nc,.adv
        ld (e_x),hl
        pop bc
        push bc
        ld d,c
        ld e,16
        mul d,e
        ld a,(r_flip)
        and 2
        jr z,.yh
        ld a,(r_h)
        call canvas_size
        or a
        sbc hl,de
        ld de,16
        or a
        sbc hl,de
        ex de,hl
.yh:    ld a,(r_row)
        call cell_px
        add hl,de
        ld a,h
        or a
        jp nz,.adv
        ld a,l
        ld (e_y),a
        ld a,(spr_n)
        cp MAXSPR
        jp nc,.adv
        ld l,a
        ld h,0
        ld e,l
        ld d,h
        add hl,hl
        add hl,hl
        add hl,de
        ld de,spr_list
        add hl,de
        ld a,(e_x)
        ld (hl),a
        inc hl
        ld a,(e_y)
        ld (hl),a
        inc hl
        ld a,(r_flip)
        ld d,a
        and 1
        rlca
        rlca
        rlca
        ld e,a                  ; X mirror
        ld a,d
        and 2
        add a,a
        or e                    ; Y mirror
        ld d,a
        ld a,(r_pal)            ; flash colour (palette offset)
        or d
        ld d,a
        ld a,(e_x+1)
        and 1
        or d
        ld (hl),a
        inc hl
        ld a,(c_slot)
        ld d,a
        srl a
        or 0xC0                 ; visible, fifth byte follows
        ld (hl),a
        inc hl
        ld a,d
        rrca
        rrca
        and 0x40
        or 0x80                 ; 4bpp, pattern half
        ld (hl),a
        ld hl,spr_n
        inc (hl)
.adv:   ld hl,c_slot
        inc (hl)
.next:  ld hl,t_idx
        inc (hl)
        pop bc
        inc b
        ld a,(nx)
        cp b
        jp nz,.tx
        inc c
        ld a,(ny)
        cp c
        jp nz,.ty
        ret


canvas_size:                    ; A = cells -> HL = A * 8 + 2
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        inc hl
        inc hl
        ret
cell_px:                        ; A = signed cell -> HL = A * 8 + 31
        ld l,a
        rla
        sbc a,a
        ld h,a
        add hl,hl
        add hl,hl
        add hl,hl
        push de
        ld de,31
        add hl,de
        pop de
        ret

; Z: the graphic being converted (level, r_src, r_w, r_h; plain ink) has pre-rendered outline
; patterns; HL = its directory entry, PRE_DIR mapped in slot 0. NZ: none (slot 0 unmapped).
pre_find:
        ld a,(r_ink)
        or a
        jr nz,.no
        ld a,PRE_DIR
        call col_map
        ld bc,(0)
        ld a,b
        or c
        jr z,.un
        ld hl,2
.l:     push hl
        ld a,(0x719C)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(r_src)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(r_src+1)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(r_w)
        cp (hl)
        jr nz,.n
        inc hl
        ld a,(r_h)
        cp (hl)
        jr nz,.n
        pop hl
        xor a
        ret
.n:     pop hl
        ld de,PRE_ENTRY
        add hl,de
        dec bc
        ld a,b
        or c
        jr nz,.l
.un:    call col_unmap
.no:    or 1
        ret

; HL = directory entry (PRE_DIR in slot 0): claim slots, copy the patterns, fill cache entry IX.
conv_pre:
        ld de,5
        add hl,de
        ld a,(hl)
        ld (p_nx),a
        inc hl
        ld a,(hl)
        ld (p_ny),a
        inc hl
        ld a,(hl)
        ld (p_nt),a
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld (p_pat),de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld (p_map),de
        ld a,(p_nt)
        ld c,a
        ld a,(budget)           ; fits: spend it; too big: only as the update's first
        cp c
        jr nc,.sub
        cp BUDGET
        jp nz,.later
        xor a
        jr .spend
.sub:   sub c
.spend: ld (budget),a
        ld a,(p_nt)
        call alloc              ; unmaps the directory: p_* are already read
        jp c,conv_fail
        ld (c_slot),a
        ld hl,(r_src)
        ld (ix+0),l
        ld (ix+1),h
        ld (ix+2),0
        ld a,(p_nt)
        ld (ix+4),a
        ld hl,(r_sum)
        ld (ix+14),l
        ld (ix+15),h
        ld (ix+16),1
        ld a,(p_nx)
        ld (ix+17),a
        ld a,(p_ny)
        ld (ix+18),a
        push ix
        pop hl
        ld a,5
        add hl,a
        ld b,9
        xor a
.c:     ld (hl),a
        inc hl
        djnz .c
        ld (t_idx),a
        ld a,(p_nx)
        ld d,a
        ld a,(p_ny)
        ld e,a
        mul d,e
        ld b,e                  ; tiles (at most 72)
        ld hl,(p_map)
.m:     ld a,(hl)
        or a
        jr z,.m0
        push hl
        push bc
        call set_bit
        pop bc
        pop hl
.m0:    inc hl
        ld a,(t_idx)
        inc a
        ld (t_idx),a
        djnz .m
        ld a,(p_nt)
        ld b,a
        ld hl,(p_pat)
.u:     push bc
        push hl
        ld a,l
        and 63
        ld d,a
        ld e,128
        mul d,e                 ; offset of the pattern in its page
        ld a,l
        rlca
        rlca
        and 3
        ld c,a
        ld a,h
        add a,a
        add a,a
        or c                    ; pattern / 64
        add a,PRE_PAT0
        call col_map
        ld a,(c_slot)
        ld c,a
        srl a
        bit 0,c
        jr z,.s
        or 0x80                 ; upper 128 bytes of the 8-bit pattern
.s:     IFDEF L2_GLIDE
        call g_hold
        ENDIF
        ld bc,0x303B
        out (c),a
        ex de,hl
        ld bc,0x805B            ; 128 bytes to the pattern port
        otir
        IFDEF L2_GLIDE
        call g_release
        ENDIF
        ld hl,c_slot
        inc (hl)
        pop hl
        inc hl
        pop bc
        djnz .u
        call col_unmap
        or a
        ret
.later: call col_unmap
        jp conv_later

; ---- 8842: show everything recorded since the previous copier call ------------
spr_publish:
        nextreg 7,3
        call spr_pub_body
        ld a,(run_fast)
        nextreg 7,a
        ret
spr_pub_body:
        ld a,(spr_on)
        or a
        jr z,.vis
        IFNDEF L2_SPR_HIDE
        nextreg 0x15,LORDER+1   ; shown again after a screen clear (spr_cls)
        ENDIF
.vis:
        ld a,(spr_on)
        or a
        ret z
        ld bc,0x303B
        xor a
        out (c),a               ; from sprite 0
        ld c,0x57
        ld a,(spr_n)            ; in plot order: sprite 0 (first plotted) on top
        or a
        jr z,.hide
        ld d,a
        ld hl,spr_list
.s:     outinb
        outinb
        outinb
        outinb
        outinb
        dec d
        jr nz,.s
.hide:  ld a,(spr_n)
        ld e,a
        ld a,(spr_prev)
        sub e
        jr c,.done
        jr z,.done
        ld d,a
        xor a
.h:     out (c),a
        out (c),a
        out (c),a
        out (c),a               ; invisible: four bytes only
        dec d
        jr nz,.h
.done:  ld a,(spr_n)
        ld (spr_prev),a
        ld hl,stat_max
        cp (hl)
        jr c,.nm
        ld (hl),a
.nm:    ld hl,upd
        inc (hl)
        ld a,(run_fast)        ; outside play (title) convert everything at once: no scroll to
        or a                    ; protect, and a figure waiting for conversion steps natively
        ld a,BUDGET
        jr nz,.bg
        ld a,250
.bg:    ld (budget),a
        ld a,1
        ld (need_reset),a
        xor a
        ld (spr_n),a
        ret

spr_on:   db 0
spr_n:    db 0
spr_prev: db 0
budget:   db BUDGET
tab_l:    ds 4
lbuf:     ds 4
ov_pa:    db 0
ov_pb:    db 0
ov_oa:    dw 0
ov_ob:    dw 0
cl_count: dw 0
cl_first: dw 0
cl_lo:    dw 0
cl_n:     dw 0
cl_half:  dw 0
cl_mid:   dw 0
cl_page:  db 0
p_nx:     db 0
p_ny:     db 0
p_nt:     db 0
p_pat:    dw 0
p_map:    dw 0
tab_r:    ds 4
cur_serial: db 0
serial:   db 0
need_reset: db 1
emitted:  db 0
cand:     db 0
succ:     db 0
save_n:   db 0
stat_part: db 0
stat_re:  db 0
slot_lim: db 128
r_sum:    dw 0
cache_n:  db 0
upd:      db 0                  ; publications so far (wraps): cache entry stamps
ca_n:     db 0                  ; alloc / c_alloc
ca_slot:  db 0
ca_ent:   dw 0
stat_flush: db 0
stat_drop: db 0
stat_max: db 0
r_src:    dw 0
r_w:      db 0
r_h:      db 0
r_col:    db 0
r_row:    db 0
r_flip:   db 0
r_ink:    db 0
r_pal:    db 0
nx:       db 0
ny:       db 0
c_slot:   db 0
t_idx:    db 0
e_line:   db 0
e_x:      dw 0
e_y:      db 0
rowbase:  dw 0
tp:       dw 0
tl:       dw 0
tr:       dw 0
bl:       dw 0
br:       dw 0
ea:       dw 0
eb:       dw 0
spr_list: ds MAXSPR*5
cache:    ds MAXENT*ENT
celltab:  ds CELLW*CELLH*2
plot_ok:  ds 256
        DISPLAY "hook page end ",$," FLAGMAP ",FLAGMAP
        ASSERT $ <= FLAGMAP
