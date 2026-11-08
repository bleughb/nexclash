; Lunar Jetman (Ultimate, 1983, 48K) - every object the two XOR plotters draw becomes hardware
; sprites; the plotters' screen stores and the object colour painters are NOPs (lunar_jetman.py).
; Hooks in alt ROM image 1 at 0x386E (read-only). Interrupts stay on: the ROM IM 1 handler uses
; slots 0 and 2 only (the game's stack is at 0x5Exx), so slot 4 may hold a Next page while a hook
; runs, and slot 5 an image page during an upload (restored to pages 4 / 5 before any return). Hooks never touch IX, IY, I, IFF or the alternate registers (the plotter keeps the
; old image in them).
;
; Sites (original bytes checked by lunar_jetman.py):
;   34558  0E 00 C9  LD C,0 / RET  end of the figure plotter's new-image setup     -> JP h_new
;   34431  AF DD 77 09  XOR A / LD (IX+9),A  object outside the window: state clear  -> JP h_clr
;                    (every update for every such object: only an object with something drawn, IX+10 > 0,
;                    can have sprites showing; the rest pass at 3.5 MHz in 43 T more than the original)
;   34368  AF 32 59 5E  XOR A / LD (24153),A  erase-only entry                       -> JP h_eo
;   34383  AF 32 59 5E  XOR A / LD (24153),A  truck erase-only entry                 -> JP h_teo
;   34958  0E 00 C9  LD C,0 / RET  end of the truck plotter's setup                -> JP h_tnew
;   35749  21 BF 57  LD HL,22463 (entry of the play-area clear 35749: the missile warning,
;                    new screens; callers 41670, 45992, 46424, 46476)               -> JP h_msg
;   34011  CD AD 84  CALL 33965 (pixel clear of the whole screen, routine 34008)     -> CALL h_cls
; Sprites: trucks 0x6090 -> 0-9, 0x6180 -> 10-19 (5 x 2 tiles); object n (IX = 0x6078 + 24n,
; n 0-26) -> 20 + 4n .. 23 + 4n (2 x 2 tiles). Truck lowest, so figures go in front. Patterns: a
; pool of all 128 shared by tile content (acq), so a tile any pattern already holds is not uploaded.

        DEVICE ZXSPECTRUMNEXT

OBJ0    EQU 0x6078
NOBJ    EQU 27
STATE   EQU 26
IDXP    EQU 27
TP0     EQU 28
FP0     EQU 36
PCACHE  EQU 0x0800              ; state page offsets (lunar_jetman.py): the tile id each pattern holds
FTID    EQU 0x1000              ; figure graphic k's four tile ids at +8k
TTID    EQU 0x1800              ; truck graphic k's ten tile ids at +20k
OBJP    EQU 0x0600              ; object n's four patterns at +4n
REFS    EQU 0x0700              ; pattern p's holders at +p
WHERE   EQU 0x0C00              ; tile id -> the pattern holding it (0 = none)
OTAB    EQU 0x1C00              ; 0x6000-0x63FF -> object number or 0xFF (objn)
; R (card patch.preserve-r): each hook reads R at a fixed count of M1 cycles from its site and sets it at a fixed count
; before its return point, so R there is the original's: K = (the original's M1s, site to return) - (the hook's, site to
; and including its LD A,R) - (the hook's after its LD R,A), mod 128. Measured by the verifier (R compared), and so by count:
R_NEW   EQU 98                  ; 2 - 20 - 12
R_TNEW  EQU 102                 ; 2 - 18 - 10
R_CLR   EQU 120                 ; 3 - 7 - 4 (h_clr, nothing drawn: inline)
R_CLRH  EQU 117                 ; 3 - 8 - 6 (h_clr, something drawn)
R_EO    EQU 121                 ; 2 - 4 - 5
R_TEO   EQU 121                 ; 2 - 4 - 5
R_MSG   EQU 119                 ; 1 - 5 - 5
R_CLS   EQU 120                 ; 1 - 5 - 4
TOBJP   EQU 108                 ; the trucks' OBJP entries (27 x 4 for the objects first)
V_RR    EQU 0x8026              ; state page variables (slot 4): the pool's round robin (0-127)
V_WH    EQU 0x8038              ; the truck graphic's W, H
V_SRC   EQU 0x8030              ; (0x8028-0x802F: the trucks' placement memos, tmemo)
V_TID   EQU 0x8032
V_LST   EQU 0x8034
V_P     EQU 0x8036
SCROLL  EQU 24698
GLOOK   EQU 34175               ; the game's own graphic lookup (IX+0 -> DE), reads only
FLIST   EQU 0x8040
TLIST   EQU 0x8400

        ORG 0x386E
; ---- figure: new image set up (IX+9..15 = what is drawn) ----
h_new:  push af
        push bc
        ld bc,0x243B            ; the caller's CPU speed (NR 7 bits 1:0, card patch.restore-speed), kept on the
        ld a,7                  ; stack: these hooks live in the alt ROM (no RAM for a latch)
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        push de                 ; DE / HL saved at 28 MHz
        push hl
        nextreg 0x54,STATE      ; the state page at slot 4 for the whole hook (back to page 4 at .out)
        ld a,r                  ; R at a fixed count of M1 cycles from the site (card patch.preserve-r)
        push af
        call objn               ; A = n, carry = not an object
        jp c,.out
        ld c,a                  ; C = n
        add a,a
        add a,a
        add a,20
        ld b,a                  ; B = first sprite
        ld a,(ix+10)
        or a
        jp z,.hid
        dec de                  ; DE = graphic (height byte)
        call ffind              ; A = id, carry = none; slot 4 = state page
        jp c,.hid
        ld e,a                  ; E = id
        ld h,0x80
        ld l,c                  ; HL = cache[n]
        inc a
        cp (hl)
        jr z,.cached
        ld (hl),a               ; cache[n] = id + 1
        push bc                 ; B = first sprite, C = n, kept across the upload
        ld a,e
        rrca
        rrca
        rrca
        rrca
        and 15
        add a,FP0
        nextreg 0x55,a          ; the images at slot 5, the state page stays at slot 4
        ld a,e
        and 15
        add a,a
        add a,0xA0
        ld h,a
        ld l,0
        ld (V_SRC),hl           ; 0xA000 + (id & 15) * 512
        ld l,e
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,0x8000 + FTID
        add hl,de
        ld (V_TID),hl           ; the graphic's four tile ids
        ld a,c
        add a,a
        add a,a
        ld (V_LST),a            ; OBJP + 4n
        ld b,4
        call rel                ; the patterns it held, released
        ld de,(V_TID)
        ld a,(V_LST)
        ld c,a
        ld b,4
        call acq                ; four patterns holding its tiles (uploaded only when no pattern holds one)
        nextreg 0x55,5
        pop bc
.cached:                        ; the state page stays at slot 4 (the object's patterns at OBJP + 4n)
        ld d,b                  ; D = first sprite
        ld a,c
        add a,a
        add a,a
        ld b,a                  ; B = 4n
        ; y = (IX+4) - (IX+10) + 32, x = (IX+1) + 31
        ld a,(ix+4)
        sub (ix+10)
        add a,32
        ld e,a                  ; E = Y
        ld a,(ix+7)
        call paloff             ; A = palette offset << 4
        ld c,a
        ld l,(ix+1)
        ld h,0
        ld a,l
        add a,31
        ld l,a
        jr nc,.n9
        inc h
.n9:    ; HL = X, D = first sprite, B = its patterns' OBJP index, C = palette, E = Y; four tiles
        call plsel
        push hl
        call pl1
        call pl1
        pop hl
        ld a,e
        add a,16
        ld e,a
        call pl1
        call pl1
        jr .out
.hid:   ld a,b
        ld b,4
        call hide
.out:   pop af
        ld c,R_NEW
        call rfix               ; R as the original leaves it at the return
        nextreg 0x54,4
        pop hl
        pop de
        pop af
        pop bc
        ld c,0
        nextreg 0x07,a          ; the caller's speed back (never a fixed 3.5 MHz)
        pop af
        ret

; ---- figure outside the window (the state clear 34431) / erase only: hide its sprites ----
h_clr:  ld a,(ix+10)            ; the drawn image's height: 0 = nothing drawn, its sprites already hidden
        or a                    ; (h_new hides them whenever it sees IX+10 = 0)
        jr nz,.h
        ld a,r                  ; R as the original's 3 M1 cycles leave it (inline: about 10 calls an update);
        ld c,a                  ; C is set by the clear's own LD C,0 before it returns
        add a,R_CLR
        xor c
        and 0x7F
        xor c
        ld r,a
        xor a                   ; the original's XOR A / LD (IX+9),A (its flags)
        ld (ix+9),a
        jp 34435
.h:     push bc
        ld a,r
        push af
        call hidefig
        pop af
        ld c,R_CLRH
        call rfix
        pop bc
        xor a
        ld (ix+9),a
        jp 34435
h_eo:   push bc
        ld a,r
        push af
        call hidefig
        pop af
        ld c,R_EO
        call rfix
        pop bc
        xor a
        ld (24153),a
        jp 34372
h_teo:  push bc
        ld a,r
        push af
        call hidetruck
        pop af
        ld c,R_TEO
        call rfix
        pop bc
        xor a
        ld (24153),a
        jp 34387

; rfix: A = R as read, C = M1 cycles to add -> R = A's bit 7 | (A + C) bits 6:0 (card patch.preserve-r). AF, B lost.
rfix:   ld b,a
        add a,c
        xor b
        and 0x7F
        xor b
        ld r,a
        ret

hidefig:
        push af
        push bc
        ld bc,0x243B            ; the caller's CPU speed, kept on the stack, then 28 MHz (as h_new)
        ld a,7
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        nextreg 0x54,STATE
        call objn
        jr c,.x
        add a,a
        add a,a
        add a,20
        ld b,4
        call hide
.x:     nextreg 0x54,4
        pop af
        nextreg 0x07,a          ; the caller's speed back
        pop bc
        pop af
        ret

hidetruck:
        push af
        push bc
        call trk
        jr c,.x
        ld b,a
        call tinv
        ld a,b
        ld b,10
        call hide
.x:     pop bc
        pop af
        ret

; ---- truck: new image set up ----
h_tnew: push af
        push bc
        ld bc,0x243B            ; the caller's CPU speed (NR 7 bits 1:0, card patch.restore-speed), kept on the
        ld a,7                  ; stack: these hooks live in the alt ROM (no RAM for a latch)
        out (c),a
        inc b
        in a,(c)
        and 3
        push af
        nextreg 0x07,3
        push de                 ; DE / HL saved at 28 MHz
        push hl
        ld a,r                  ; R at a fixed count of M1 cycles from the site (card patch.preserve-r)
        push af
        call trk                ; A = first sprite (0 / 10), carry = not a truck
        jp c,.out
        ld b,a
        ld a,(ix+10)
        or a
        jp z,.hid
        push bc
        call GLOOK              ; DE = graphic [W, H, data]
        pop bc
        ld a,(de)
        ld l,a                  ; L = W
        inc de
        ld a,(de)
        ld h,a                  ; H = H (read while the game's page is at slot 4)
        dec de
        nextreg 0x54,STATE
        ld (V_WH),hl
        ld hl,0x8022            ; the graphic last uploaded: 0x8022 (truck sprites 0), 0x8024 (10)
        ld a,b
        or a
        jr z,.c0
        ld l,0x24
.c0:    ld a,(hl)
        cp e
        jr nz,.new
        inc l
        ld a,(hl)
        cp d
        jr z,.hit               ; the same graphic: its patterns are in place (no list search)
        dec l
.new:   push hl
        ld hl,TLIST
        call find               ; A = id
        pop hl
        jp c,.unm
        ld (hl),e
        inc l
        ld (hl),d
        push de                 ; the graphic, kept across the upload
        push bc                 ; B = first sprite (0 / 10)
        ld e,a                  ; E = id
        ld l,e
        ld h,0
        add hl,hl
        add hl,hl
        ld c,l
        ld b,h                  ; BC = 4 * id
        add hl,hl
        add hl,hl
        add hl,bc
        ld bc,0x8000 + TTID
        add hl,bc
        ld (V_TID),hl           ; the graphic's ten tile ids: TTID + 20 * id
        ; page TP0 + id / 6 at slot 5, offset (id % 6) * 1280
        ld a,e
        ld d,TP0
.dv:    cp 6
        jr c,.dd
        sub 6
        inc d
        jr .dv
.dd:    push af
        ld a,d
        nextreg 0x55,a
        pop af
        ld d,a
        add a,a
        add a,a
        add a,d                 ; 5 * (id % 6)
        add a,0xA0
        ld h,a
        ld l,0
        ld (V_SRC),hl           ; 0xA000 + (id % 6) * 1280
        pop bc
        push bc
        ld a,b
        add a,TOBJP
        ld (V_LST),a            ; OBJP + 108 (truck sprites 0) / + 118 (10)
        ld b,10
        call rel                ; the patterns it held, released
        ld de,(V_TID)
        ld a,(V_LST)
        ld c,a
        ld b,10
        call acq                ; ten patterns holding its tiles (uploaded only when no pattern holds one)
        nextreg 0x55,5
        pop bc
        pop de
.hit:   call tmemo              ; placed last time at the same x, y and columns, not hidden since: nothing to do
        ld a,(ix+1)             ; (2 in 3 calls on p2)
        cp (hl)
        jr nz,.cached
        inc l
        ld a,(ix+4)
        cp (hl)
        jr nz,.cached
        inc l
        ld a,(ix+11)
        cp (hl)
        jr nz,.cached
        inc l
        ld a,(hl)
        or a
        jr z,.cached
        nextreg 0x54,4
        jp .out
.cached:                        ; the state page stays at slot 4 (the truck's patterns at OBJP + TOBJP + B)
        call tmemo
        ld a,(ix+1)
        ld (hl),a
        inc l
        ld a,(ix+4)
        ld (hl),a
        inc l
        ld a,(ix+11)
        ld (hl),a
        inc l
        ld (hl),1               ; placed
        ; x: (IX+1) & 0xF8, or -8 * (W - (IX+11)) when cut on the left ((IX+1) = 0)
        ld a,(V_WH)             ; W
        sub (ix+11)
        ld c,a                  ; C = columns cut
        ld a,(ix+1)
        or a
        jr nz,.right
        ld a,c
        or a
        jr z,.right
        ld a,c
        add a,a
        add a,a
        add a,a
        neg
        ld l,a
        ld h,0xFF               ; HL = -8k
        jr .xx
.right: ld a,(ix+1)
        and 0xF8
        ld l,a
        ld h,0
.xx:    ld a,l
        add a,31
        ld l,a
        ld a,h
        adc a,0
        ld h,a                  ; HL = X (signed)
        ld a,(V_WH + 1)         ; H
        ld c,a
        ld a,(ix+4)
        sub c
        add a,32
        ld e,a                  ; E = Y
        ld c,0                  ; palette 0
        ld d,b                  ; D = first sprite
        ld a,b
        add a,TOBJP
        ld b,a                  ; B = its patterns' OBJP index
        call plsel
        push hl
        call row5
        pop hl
        ld a,e
        add a,16
        ld e,a
        call row5
        nextreg 0x54,4
        jr .out
.unm:
.hid:   call tinv               ; (slot 4 back on page 4)
        ld a,b
        ld b,10
        call hide
.out:   pop af
        ld c,R_TNEW
        call rfix               ; R as the original leaves it at the return
        pop hl
        pop de
        pop af
        pop bc
        ld c,0
        nextreg 0x07,a          ; the caller's speed back (never a fixed 3.5 MHz)
        pop af
        ret

; tinv: B = first truck sprite -> its memo says not placed (the sprites are being hidden); slot 4 = page 4 after. AF lost.
tinv:   push hl
        nextreg 0x54,STATE
        call tmemo
        inc l
        inc l
        inc l
        ld (hl),0
        nextreg 0x54,4
        pop hl
        ret

row5:   call pl1
        call pl1
        call pl1
        call pl1
        jp pl1

; ---- the play-area clear (missile warning, new screens): every sprite off (objects are reset after it) ----
h_msg:  push af
        push bc
        ld a,r
        ld c,a
        call allhide
        ld a,c
        ld c,R_MSG
        call rfix
        pop bc
        pop af
        ld hl,22463
        jp 35752

; ---- whole-screen clear (new game, new life): every sprite off, caches empty ----
h_cls:  push af
        push bc
        ld a,r
        ld c,a
        call allhide
        ld a,c
        ld c,R_CLS
        call rfix
        pop bc
        pop af
        jp 33965

allhide:
        push af
        push hl
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x54,STATE
        ld hl,0x8000
.c:     ld (hl),0
        inc l
        ld a,l
        cp 0x30                 ; figure caches, truck graphics last uploaded (0x22-0x25), V_RR, truck memos (0x28-0x2F)
        jr nz,.c
        nextreg 0x54,4
        pop hl
        pop af
        ret

; trk: A = first truck sprite (0 for 0x6090, 10 for 0x6180), carry if neither
trk:    ld a,ixh
        cp 0x60
        jr z,.a
        cp 0x61
        jr nz,.no
        ld a,ixl
        cp 0x80
        jr nz,.no
        ld a,10
        or a
        ret
.a:     ld a,ixl
        cp 0x90
        jr nz,.no
        xor a
        ret
.no:    scf
        ret

; ffind: figure graphic DE -> A = id (carry if absent), by the index page (DE & 0x1FFF -> id + 1),
; checked against the state page's list; leaves the state page in slot 4
ffind:  push bc
        push hl
        nextreg 0x54,IDXP
        ld a,d
        and 0x1F
        or 0x80
        ld h,a
        ld l,e
        ld c,(hl)
        nextreg 0x54,STATE
        ld a,c
        sub 1
        jr c,.x
        ld l,a
        ld h,0
        add hl,hl
        ld bc,FLIST
        add hl,bc
        ld c,a
        ld a,(hl)
        cp e
        jr nz,.no
        inc hl
        ld a,(hl)
        cp d
        jr nz,.no
        ld a,c
        or a
        jr .x
.no:    scf
.x:     pop hl
        pop bc
        ret

; hide: B sprites from A
hide:   nextreg 0x34,a
        nextreg 0x38,0
        inc a
        djnz hide
        ret

rom_end:


; ---------------------------------------------------------------------------------------------------
; Code in the state page (page 26 at 0x0900, put in by LunarJetmanPatch.apply): callable only while
; the state page is at slot 4 (the alt ROM hook space ends at 0x3D00).
        ORG 0x8900
stcode:

; ---- the pattern pool: all 128 patterns hold tiles for any figure or truck (a content cache) ----
; OBJP + 4n: object n's four patterns, OBJP + 108 / 118: the trucks' ten; REFS + p: how many of those 128 entries
; name pattern p (held until that object's next upload, hidden or not; the build counts the 128 initial entries,
; all 0, on pattern 0), so while one object takes new patterns a pattern no entry names always exists; PCACHE + 2p:
; the tile p holds; WHERE + id: the pattern holding tile id (0 = none). A hit costs no upload; a pattern is
; overwritten only when no object holds it (never one another object shows).

; rel: A = OBJP index, B = count -> those patterns held once less. AF, B, E, HL lost.
rel:    ld h,high (0x8000 + OBJP)
        ld l,a
.r:     ld e,(hl)
        push hl
        ld h,high (0x8000 + REFS)
        ld l,e
        dec (hl)
        pop hl
        inc l
        djnz .r
        ret

; acq: B tiles, ids from DE (state page), bytes from V_SRC (slot 5, low byte 0), into the patterns at OBJP + C
; (= V_LST on entry). AF, BC, DE, HL lost.
acq:    ld a,(de)
        ld l,a
        inc de
        ld a,(de)
        inc de
        ld h,a                  ; HL = tile id
        push de
        ld de,0x8000 + WHERE
        add hl,de
        ld a,(hl)
        or a
        jr z,.miss              ; no pattern holds it
.have:  ld e,a                  ; E = p
        ld h,high (0x8000 + REFS)
        ld l,a
        inc (hl)
        ld h,high (0x8000 + OBJP)
        ld l,c
        ld (hl),e               ; OBJP: p
        set 7,l
        dec h
        rrca                    ; carry = p & 1
        ld a,0x80
        jr nc,.n6
        ld a,0xC0
.n6:    ld (hl),a               ; A4 (OBJP - 0x80): 4-bit, N6 = p & 1
        inc h
        ld a,e
        srl a
        or 0xC0
        ld (hl),a               ; A3 (OBJP + 0x80): visible, 5-byte form, p >> 1
        pop de
        inc c
        djnz acq
        ret
.miss:  push hl
        call victim             ; A = a pattern no object holds (BC, DE kept)
        pop hl
        ld (hl),a               ; WHERE[id] = p
        ld (V_P),a
        ld de,-(0x8000 + WHERE)
        add hl,de
        ex de,hl                ; DE = tile id
        add a,a
        ld l,a
        ld h,high (0x8000 + PCACHE)
        ld a,(hl)
        ld (hl),e
        ld e,a
        inc l
        ld a,(hl)
        ld (hl),d
        ld d,a                  ; DE = the tile p held before
        or e
        jr z,.up
        ld hl,0x8000 + WHERE
        add hl,de
        ld (hl),0               ; held nowhere now
.up:    ld a,(V_P)
        call patsel
        ld hl,V_LST
        ld a,c
        sub (hl)                ; A = tile number k, carry clear
        ld hl,(V_SRC)
        rra                     ; HL += 128 * k
        jr nc,.ev
        ld l,0x80
.ev:    add a,h
        ld h,a
        push bc
        ld bc,0x805B
        call up256              ; 128 bytes
        pop bc
        ld a,(V_P)
        jr .have

; victim: A = the next pattern after V_RR (0-127, round robin) that no object holds; V_RR = it. DE kept.
victim: ld a,(V_RR)
        ld l,a
        ld h,high (0x8000 + REFS)
.v:     inc l
        res 7,l
        ld a,(hl)
        or a
        jr nz,.v
        ld a,l
        ld (V_RR),a
        ret

; pl1: one sprite's five attributes by port 0x57 (C): X = HL (9 bits), Y = E, palette B, pattern bytes A3 / A4 at
; OBJP + 0x80 + D / OBJP - 0x80 + D (state page, set by acq); D += 1, HL += 16 (the next tile's X). AF lost.
pl1:    out (c),l
        out (c),e
        ld a,h
        and 1
        or b
        out (c),a
        push hl
        ld h,high (0x8000 + OBJP)
        ld a,d
        or 0x80
        ld l,a
        ld a,(hl)               ; visible, 5-byte form, pattern bits 6:1
        out (c),a
        dec h
        ld a,(hl)               ; 4-bit, pattern bit 0 (N6)
        out (c),a
        pop hl
        inc d
        ld a,l
        add a,16
        ld l,a
        ret nc
        inc h
        ret

; plsel: D = first sprite, B = OBJP index, C = palette -> port 0x57 writes go to sprite D on (0x303B; its
; index moves on after each 5-byte sprite); D = OBJP index, B = palette, C = 0x57. AF lost.
plsel:  ld a,d
        ld d,b
        ld b,c
        push bc
        ld bc,0x303B
        out (c),a
        pop bc
        ld c,0x57
        ret

; paloff: attribute A -> (ink + 8 * bright, 0 -> 8) << 4
paloff: push bc
        ld b,a
        and 7
        bit 6,b
        jr z,.d
        or 8
.d:     or a
        jr nz,.z
        ld a,8
.z:     rlca
        rlca
        rlca
        rlca
        pop bc
        ret

; patsel: select 4-bit pattern A for upload
patsel: push bc
        srl a
        jr nc,.e
        or 0x80
.e:     ld bc,0x303B
        out (c),a
        pop bc
        ret

; up256: 256 bytes (B = 0; 128 with B = 128) from HL to port C, B = 0 on exit; 16.6 T a byte against OTIR's 21
up256:  outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        outi
        jp nz,up256
        ret

; find: HL = list of graphic addresses (0-terminated), DE = address -> A = index, carry if absent
find:   push bc
        ld b,0
.l:     ld a,(hl)
        inc hl
        ld c,(hl)
        inc hl
        cp e
        jr nz,.n
        ld a,c
        cp d
        jr z,.f
.n:     dec hl
        dec hl
        ld a,(hl)
        inc hl
        or (hl)
        inc hl
        jr z,.no
        inc b
        jr .l
.f:     ld a,b
        or a
        pop bc
        ret
.no:    scf
        pop bc
        ret

; ---- helpers ----
; objn: A = (IX - OBJ0) / 24, carry if IX is not an object record start; the state page at slot 4 (OTAB:
; 0x6000-0x63FF -> n or 0xFF, built by lunar_jetman.tile_ids). HL kept.
objn:   ld a,ixh
        sub 0x60
        cp 4
        ccf
        ret c
        push hl
        add a,high (0x8000 + OTAB)
        ld h,a
        ld a,ixl
        ld l,a
        ld a,(hl)
        pop hl
        cp NOBJ
        ccf
        ret

; tmemo: B = first truck sprite (0 / 10) -> HL = its placement memo (state page: x, y, columns, 1 = placed). AF lost.
tmemo:  ld hl,0x8028
        ld a,b
        or a
        ret z
        ld l,0x2C
        ret
stcode_end:
        ASSERT stcode_end <= 0x8C00

; --- setup (stub bank, 0xD000): sprite palette, transparency, every sprite hidden, sprites on ---
        ORG 0xD000
setup:  nextreg 0x43,0x20
        nextreg 0x40,0
        ld hl,pal
        ld b,0
.p:     ld a,(hl)
        nextreg 0x41,a
        inc hl
        djnz .p
        nextreg 0x4B,0
        xor a
.h:     nextreg 0x34,a
        nextreg 0x38,0
        inc a
        cp 128
        jr nz,.h
        nextreg 0x15,0x01
        ret
pal:    INCLUDE "lunar_jetman_palette.asm"
setup_end:

        SAVEBIN "lj_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "lj_stcode.bin",0x8900,stcode_end-0x8900
        SAVEBIN "lj_setup.bin",0xD000,setup_end-0xD000

; ---------------------------------------------------------------------------------------------------
; Loading screen hold (the approved .nxc's builds lunar_jetman_sprites_loading / _enhanced_loading;
; imported 2026-11-04 from the pilot's loading/work/stub.asm, unchanged but for the picture: the build
; puts bank 5's own screen at loading.picture, lunar_jetman.loading_nex). The .nex's bank 5 screen area
; holds the tape's loading screen; this is bank 34 (pages 68, 69), the entry bank, PC $C000: it shows
; the picture until a key or 5 s, waits for the key to go, puts bank 5's screen back and falls through
; to $C000, page 20 (the converter's own stub). Assembled after the hook SAVEBINs (device 0xC000-0xFFFF).
        MODULE loading
SCREEN  equ     $4000
SCRLEN  equ     6912
REGS    equ     $FE00           ; register stack, page 69; below it the stub's call stack
SEL     equ     $FE02           ; port $243B as found
TIMEOUT equ     250             ; frames: 5 s at 50 Hz
CAP     equ     250             ; most frames to wait for a held key to go
CLEAR   equ     3               ; frames with no key before leaving
LINE    equ     192             ; first line below the picture

        org     $C000
start:  di
        ld      sp,REGS
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      bc,$243B
        in      a,(c)
        ld      (SEL),a
        xor     a
        out     ($fe),a
; Show: a key counts only after the keyboard has been seen clear, so one held at the start doesn't.
        ld      hl,TIMEOUT
        ld      d,0             ; 1 = armed
show:   push    de
        call    frame           ; E = keys seen in that frame
        ld      a,e
        pop     de
        or      a
        jr      nz,.key
        ld      d,1
        jr      .tick
.key:   bit     0,d
        jr      nz,leave
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,show
; Leave only after the keyboard has been clear for a few frames, so the menu doesn't see the key.
leave:  ld      hl,CAP
        ld      d,0
.wait:  push    de
        call    frame
        ld      a,e
        pop     de
        or      a
        jr      z,.clr
        ld      d,0
        jr      .tick
.clr:   inc     d
        ld      a,d
        cp      CLEAR
        jr      nc,.go
.tick:  dec     hl
        ld      a,h
        or      l
        jr      nz,.wait
.go:    call    frame
        ld      hl,picture
        ld      de,SCREEN
        ld      bc,SCRLEN
        ldir
        xor     a
        out     ($fe),a
        ld      bc,$243B
        ld      a,(SEL)
        out     (c),a
        nextreg $55,69
        jp      final

; One frame, to just past line LINE, with interrupts off. Returns E = keyboard bits seen meanwhile.
frame:  ld      e,0
.a:     call    poll
        cp      LINE
        jr      nz,.a
.b:     call    poll
        cp      LINE
        jr      z,.b
        ret
poll:   ld      bc,$243B
        ld      a,$1F
        out     (c),a
        inc     b
        in      d,(c)
        xor     a
        in      a,($fe)
        cpl
        and     $1f
        or      e
        ld      e,a
        ld      a,d
        ret

        ds      $C200-$
picture:
        ds      6912            ; bank 5's own screen, put in by the build (the file has the loading screen there)
        assert  $ <= $DF00      ; $DFxx: the loader's stack
        ds      $FFD0-$         ; REGS is written at run time; zero in the file
        disp    $-$4000
; Runs from page 69 at slot 5. Bank 10's top bytes get what the loader's stack left there.
final:  nextreg $56,20
        nextreg $57,21
        ld      hl,$C000
        ld      ($DFFC),hl
        ld      sp,REGS-$4000-12
        pop     iy
        pop     ix
        ld      hl,($BFFF)      ; MEMPTR = $C000, as the loader's RET left it
        pop     hl
        pop     de
        pop     bc
        pop     af
        ld      sp,$DFFE
        ds      $BFFC-$
        nextreg $55,5           ; falls through to $C000, page 20
        assert  $ == $C000
        ent
        ENDMODULE
        SAVEBIN "lj_loading.bin",0xC000,0x0200          ; code before loading.picture
        SAVEBIN "lj_loadend.bin",0xFFD0,0x0030          ; loading.final (the rest of the bank is zero)
