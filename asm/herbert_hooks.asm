; Herbert's Dummy Run: Mikro-Gen buffer/plotter family, per-game implementation.
; No game logic or sound changes. Original plotters still execute.
 DEVICE ZXSPECTRUMNEXT
HPG EQU 26
LPG EQU 28
APG EQU 30
PPG EQU 31
STK EQU 0x1f00
V_SP EQU 0
V_R EQU 2
V_SPEED EQU 3
V_N EQU 4
V_PTR EQU 5
V_ROOM EQU 7
V_CPUR EQU 8
V_CPUS EQU 9
V_BACK EQU 10
V_PREV EQU 11
V_NS EQU 12
V_KIND EQU 13
V_G EQU 14
V_X EQU 16
V_Y EQU 17
V_H EQU 18
V_MASK EQU 19
V_COL EQU 20
V_SRC EQU 21
V_LEFT EQU 23
V_QTAIL EQU 24
V_HEAD EQU 26
V_ROW EQU 28
V_INK EQU 29
V_MSK EQU 44
V_CACHE EQU 46
V_RAWLEN EQU 48
V_KEY EQU 50
V_INDEX EQU 52
V_LIMIT EQU 54
V_ENH EQU 56
V_EBASE EQU 57
V_BGACTIVE EQU 59
V_BGCOUNT EQU 60
V_BGREAD EQU 62
V_BGKEY EQU 64
V_BGXY EQU 66
V_BGRAW EQU 68
V_BGOVER EQU 76
V_BGOBJ EQU 77
V_BGTEST EQU 78
V_BGCHAIN EQU 79
V_BGORG EQU 81
V_BGREL EQU 83
V_BGUS EQU 85
V_BGSP EQU 86
V_LINE EQU 32
V_EL EQU 34
V_DEBT EQU 36
V_LAST EQU 38
V_TARGET EQU 40
V_DROP EQU 42
V_COPYDELTA EQU 43
PAL EQU 0x1c00
PIX EQU 0x3400
QUEUE EQU 0x3500
PAT EQU 0x3600
ATT EQU 0x3700

 MACRO STUB dest
 nextreg 0x50,HPG
 jp dest
 ENDM
 ORG 0x386e
e_or: STUB h_or
e_m16: STUB h_m16
e_hero: STUB h_hero
e_a32: STUB h_a32
e_b32: STUB h_b32
e_reset: STUB h_reset
e_room: STUB h_room
e_clear: STUB h_clear
e_copy: STUB h_copy
e_copytest:
 jp pe,0x97ca
 STUB h_commit
e_paint: STUB h_paint
e_unpaint: STUB h_unpaint
e_effect: STUB h_effect
e_attrs: STUB h_attrs
e_bgclean: STUB h_bgclean
e_bgdisplay: STUB h_bgdisplay
e_bgobject: STUB h_bgobject
e_bgfinish: STUB h_bgfinish
e_bgdisplayfinish: STUB h_bgdisplayfinish
x_or:
 nextreg 0x50,0xff
 exx
 push af
 ld (0x9da9),sp
 jp 0x8ca9
x_m16:
 nextreg 0x50,0xff
 exx
 push af
 ld (0x9da9),sp
 jp 0x93c0
x_hero:
 nextreg 0x50,0xff
 exx
 ld hl,(0x9d69)
 jp 0x933a
x_a32:
 nextreg 0x50,0xff
 exx
 ld hl,(0x9d69)
 jp 0x9320
x_b32:
 nextreg 0x50,0xff
 ld (0x9da9),sp
 jp 0x9334
x_reset:
 nextreg 0x50,0xff
 ld hl,0x6d00
 jp 0x96bf
x_room:
 nextreg 0x50,0xff
 ld hl,0x4070
 jp 0xa29b
x_clear:
 nextreg 0x50,0xff
 ld hl,0x4000
 jp 0x943f
x_copy:
 nextreg 0x50,0xff
 ld ix,0xf390
 jp 0x97c4
x_commit:
 nextreg 0x50,0xff
 jp 0x97da
x_attr:
 nextreg 0x50,0xff
 ret
x_effect:
 nextreg 0x50,0xff
 ld hl,(0x9d5e)
 jp 0xc139
x_attrs:
 nextreg 0x50,0xff
 ld hl,0x9c23
 jp 0x9c81
x_bgclean:
 nextreg 0x50,0xff
 push af
 push hl
 push bc
 jp 0x9c8b
x_bgdisplay:
 nextreg 0x50,0xff
 push af
 push hl
 push bc
 jp 0x9c26
x_bgobject:
 nextreg 0x50,0xff
 push hl
 add a,a
 ld c,a
 jp 0xa327
x_bgfinish:
 nextreg 0x50,0xff
 pop de
 pop bc
 pop hl
 jp 0x9cba
x_bgdisplayfinish:
 nextreg 0x50,0xff
 pop de
 pop bc
 pop hl
 jp 0x9c61
rom_end:
 ASSERT rom_end<0x3d00-20
 SAVEBIN "herbert_rom.bin",0x386e,rom_end-0x386e

 ORG 0x100
 MACRO ENTER
 ld (V_SP),sp
 ld sp,STK
 push af
 ld a,r
 ld (V_R),a
 push bc
 push de
 push hl
 push ix
 push iy
 ld bc,0x243b
 ld a,7
 out (c),a
 inc b
 in a,(c)
 and 3
 ld (V_SPEED),a
 nextreg 7,3
 ENDM
 MACRO SETR delta
 ld a,(V_R)
 ld b,a
 add a,delta
 and 127
 ld c,a
 ld a,b
 and 128
 or c
 ld r,a
 ENDM
 MACRO POPREG
 pop iy
 pop ix
 pop hl
 pop de
 pop bc
 pop af
 ld sp,(V_SP)
 ENDM
 MACRO EXIT dest
 ld a,(V_SPEED)
 nextreg 7,a
 SETR -24
 POPREG
 jp dest
 ENDM

h_or:
 ENTER
 ld a,0
 call log_plot
 EXIT x_or
h_m16:
 ENTER
 ld a,1
 call log_plot
 EXIT x_m16
h_hero:
 ENTER
 ld a,2
 call log_plot
 EXIT x_hero
h_a32:
 ENTER
 ld a,3
 call log_plot
 EXIT x_a32
h_b32:
 ENTER
 ld a,4
 call log_plot
 EXIT x_b32

; Entry image copied now: later in-place mirrors cannot alter an earlier logged pose.
log_plot:
 ld (V_KIND),a
 nextreg 0x51,LPG
 ld a,(V_N)
 cp 32
 jr c,.space
 ld hl,V_DROP
 inc (hl)
 jp .done
.space:
 ld a,(V_KIND)
 cp 2
 jr nc,.large
 ld hl,(0x9da4)
 ld (V_X),hl
 ld a,16
 ld (V_H),a
 ld a,(V_KIND)
 ld (V_MASK),a
 ld hl,(0x8cb2)
 ld a,(STK-1)
 ld e,a
 ld d,0
 REPT 5
 sla e
 rl d
 ENDR
 ld a,(V_MASK)
 or a
 jr z,.add
 sla e
 rl d
 jr .add
.large:
 ld hl,(0x9d69)
 ld a,(V_KIND)
 cp 4
 jr nz,.pos
 ld hl,(0x9e7a)
.pos:
 ld (V_X),hl
 ld a,32
 ld (V_H),a
 ld a,1
 ld (V_MASK),a
 ld hl,0xf4b0
 ld a,(V_KIND)
 cp 4
 jr nz,.base
 ld hl,(STK-6)
.base:
 cp 2
 ld a,(STK-1)
 jr nz,.frame
 ld a,(0xca93)
.frame:
 ld e,0
 ld d,a
 srl d
 rr e
.add:
 add hl,de
 ld (V_G),hl
 ; Fixed colour lookup by graphics address. Herbert is explicitly yellow in the game.
 ld a,h
 rrca
 rrca
 rrca
 rrca
 rrca
 and 7
 add a,36
 nextreg 0x51,a
 res 7,h
 res 6,h
 set 5,h
 ld a,(hl)
 ld (V_COL),a
 nextreg 0x51,LPG
 ld hl,(V_PTR)
 ld de,V_X
 ld a,(de)
 ld (hl),a
 inc hl
 inc de
 ld a,(de)
 ld (hl),a
 inc hl
 ld a,(V_H)
 ld (hl),a
 inc hl
 ld a,(V_MASK)
 ld (hl),a
 inc hl
 ld a,(V_COL)
 ld (hl),a
 inc hl
 ld de,(V_G)
 ld (hl),e
 inc hl
 ld (hl),d
 inc hl
 inc hl
 ex de,hl
 ld hl,(V_G)
 ld a,(V_H)
 add a,a
 ld c,a
 ld a,(V_MASK)
 or a
 jr z,.len
 sla c
.len:
 ld b,0
 ldir
 ld hl,(V_PTR)
 ld de,136
 add hl,de
 ld (V_PTR),hl
 ld hl,V_N
 inc (hl)
.done:
 nextreg 0x51,0xff
 ret

h_reset:
 ENTER
 ; Freeze the clean image at reset; later room edits belong to the next update.
 nextreg 0x51,34
 ld hl,0x6d00
 ld de,0x2000
 ld bc,4608
 ldir
 nextreg 0x51,0xff
 xor a
 ld (V_N),a
 ld hl,0x2000
 ld (V_PTR),hl
 ld a,(V_ROOM)
 or a
 jr z,.end
 nextreg 0x51,APG
 ld hl,0x5800
 ld de,0x3800
 ld bc,768
 ldir
 nextreg 0x51,0xff
 xor a
 ld (V_ROOM),a
.end:
 EXIT x_reset
h_room:
 ENTER
 call hide
 call bg_clear
 ld a,1
 ld (V_BGACTIVE),a
 ld a,1
 ld (V_ROOM),a
 EXIT x_room
h_clear:
 ENTER
 call hide
 call bg_clear
 xor a
 ld (V_BGACTIVE),a
 ld a,1
 ld (V_ROOM),a
 EXIT x_clear
hide:
 xor a
.loop:
 nextreg 0x34,a
 nextreg 0x38,0
 inc a
 cp 128
 jr nz,.loop
 xor a
 ld (V_N),a
 ld (V_PREV),a
 ret

; The room's animated four-cell colour effect also belongs in the logical shadow.
h_effect:
 ENTER
 nextreg 0x51,APG
 ld hl,(STK-6)
 ld de,-34
 add hl,de
 ld e,l
 ld a,h
 sub 0x20
 ld d,a
 ld bc,2
 ldir
 ld bc,30
 add hl,bc
 ex de,hl
 add hl,bc
 ex de,hl
 ld c,2
 ldir
 nextreg 0x51,0xff
 EXIT x_effect
h_attrs:
 ENTER
 ld a,255
 ld (V_BGOBJ),a
 nextreg 0x51,APG
 ld hl,0x5800
 ld de,0x3800
 ld bc,768
 ldir
 nextreg 0x51,0xff
 EXIT x_attrs

; Original attribute code runs against a shadow; its outputs, including R, are retained.
h_paint:
 ENTER
 nextreg 0x52,APG
 ld a,(V_SPEED)
 nextreg 7,a
 SETR -21
 POPREG
 jp original_paint
h_unpaint:
 ENTER
 nextreg 0x52,APG
 ld a,(V_SPEED)
 nextreg 7,a
 SETR -21
 POPREG
 jp original_unpaint
attr_done:
 ENTER
 ld a,(V_R)
 ld b,a
 add a,4
 and 127
 ld c,a
 ld a,b
 and 128
 or c
 ld (V_R),a
 nextreg 0x52,10
 EXIT x_attr

; Hidden copy preserves the original copy's register/flag result and R count.
h_copy:
 ENTER
 ld a,(V_R)
 ld (V_CPUR),a
 ld a,(V_SPEED)
 ld (V_CPUS),a
 call line
 ld (V_LAST),hl
 xor a
 ld (V_EL),a
 ld (V_EL+1),a
 nextreg 0x51,PPG
 ld hl,0x5b00
 ld de,0x3b00
 ld bc,0x500
 ldir
 nextreg 0x51,0xff
 nextreg 0x52,PPG
 ld a,3
 ld (V_SPEED),a
 EXIT x_copy
h_commit:
 ENTER
 nextreg 0x52,10
 ld a,(V_CPUR)
 ld b,a
 ld a,(V_COPYDELTA)
 add a,b
 and 127
 ld c,a
 ld a,b
 and 128
 or c
 ld (V_R),a
 call tick
 nextreg 0x51,LPG
 call render
 call bg_flush
 ; Plot logging runs outside this copy window: repay one video line per plot.
 ld hl,(V_TARGET)
 ld a,(V_N)
 ld e,a
 ld d,0
 or a
 sbc hl,de
 ld (V_LIMIT),hl
 ; Publish only in the border: old pattern halves stay displayed until this point.
.beam:
 call line
 ld a,h
 or a
 jr nz,.publish
 ld a,l
 cp 32
 jr c,.publish
 cp 240
 jr nc,.publish
 call tick
 jr .beam
.publish:
 call clean_copy
 call commit_attrs
 ld a,(V_ENH)
 or a
 jr z,.bg_off
 ld a,(V_BGACTIVE)
 or a
 jr z,.bg_off
 nextreg 0x69,128
.bg_off:
 nextreg 0x51,0xff
 call tick
 ; Initial target calibrated from native measurements, not an unconditional frame cap.
.wait:
 ld hl,(V_EL)
 ld de,(V_LIMIT)
 or a
 sbc hl,de
 jr nc,.ready
 call tick
 jr .wait
.ready:
 ld a,(V_CPUS)
 ld (V_SPEED),a
 EXIT x_commit

line:
 ld bc,0x243b
.retry:
 ld a,0x1e
 out (c),a
 inc b
 in d,(c)
 dec b
 ld a,0x1f
 out (c),a
 inc b
 in l,(c)
 dec b
 ld a,0x1e
 out (c),a
 inc b
 in a,(c)
 dec b
 xor d
 and 1
 jr nz,.retry
 ld a,d
 and 1
 ld h,a
 ret
tick:
 call line
 ld de,(V_LAST)
 ld (V_LAST),hl
 or a
 sbc hl,de
 jr nc,.ok
 ld de,312
 add hl,de
.ok:
 ld de,(V_EL)
 add hl,de
 ld (V_EL),hl
 ret

clean_copy:
 nextreg 0x51,34
 ld ix,0xf390
 ld hl,0x2000
 ld a,144
.row:
 push af
 ld e,(ix+0)
 ld d,(ix+1)
 inc ix
 inc ix
 REPT 32
 ldi
 ENDR
 pop af
 dec a
 jr nz,.row
 nextreg 0x51,LPG
 ret

render:
 ld a,(V_BACK)
 xor 64
 ld (V_BACK),a
 xor a
 ld (V_NS),a
 ld a,(V_N)
 ld (V_LEFT),a
 ld ix,0x2000
.figure:
 ld a,(V_LEFT)
 or a
 ret z
 ld a,(ix+1)
 cp 48
 jr c,.next
 cp 192
 jr nc,.next
 ld (V_Y),a
 ld a,(ix+0)
 ld (V_X),a
 ld a,(ix+4)
 ld (V_COL),a
 ld a,(ix+3)
 ld (V_MASK),a
 ld l,(ix+5)
 ld h,(ix+6)
 ld (V_KEY),hl
 push ix
 pop hl
 ld de,8
 add hl,de
 ld (V_SRC),hl
 call make_pattern
 ld a,(V_NS)
 cp 64
 jp nc,.next
 call upload
 call stage
 ld a,(ix+2)
 cp 32
 jr nz,.next
 ld a,(V_Y)
 add a,16
 ld (V_Y),a
 ld hl,(V_KEY)
 ld de,64
 add hl,de
 ld (V_KEY),hl
 call make_pattern
 ld a,(V_NS)
 cp 64
 jp nc,.next
 call upload
 call stage
.next:
 ld de,136
 add ix,de
 ld hl,V_LEFT
 dec (hl)
 call tick
 jp .figure

make_pattern:
 ; Source-address-indexed cache shared across figures and animation poses.
 ; Full raw-byte comparison remains authoritative, including mirrored graphics.
 ld hl,(V_KEY)
 ld a,h
 rrca
 rrca
 rrca
 rrca
 rrca
 and 7
 add a,40
 nextreg 0x52,a
 ld a,h
 and 31
 or 64
 ld h,a
 ld a,(hl)
 ld (V_INDEX),a
 and 32
 rrca
 rrca
 rrca
 rrca
 rrca
 add a,32
 nextreg 0x52,a
 ld a,(V_INDEX)
 and 31
 add a,0x40
 ld d,a
 ld e,0
 ld (V_CACHE),de
 ; Painted images at distinct source addresses may have identical raw bytes.
 ld a,(V_ENH)
 or a
 jr z,.kind
 ld hl,193
 add hl,de
 ld a,(V_KEY)
 cp (hl)
 jr nz,.miss
 inc hl
 ld a,(V_KEY+1)
 cp (hl)
 jr nz,.miss
.kind:
 ld a,(V_MASK)
 inc a
 ld c,a
 ld a,(de)
 cp c
 jr nz,.miss
 inc de
 ld hl,(V_SRC)
 ld a,(V_MASK)
 or a
 ld b,32
 jr z,.compare
 ld b,64
.compare:
 ld a,(de)
 cp (hl)
 jr nz,.miss
 inc hl
 inc de
 djnz .compare
 ld (V_SRC),hl
 ld hl,(V_CACHE)
 ld de,65
 add hl,de
 ld de,PAT
 ld bc,128
 ldir
 nextreg 0x52,10
 ret
.miss:
 ld de,(V_CACHE)
 ld a,(V_MASK)
 inc a
 ld (de),a
 inc de
 ld hl,(V_SRC)
 ld bc,32
 cp 1
 jr z,.copy
 ld c,64
.copy:
 ldir
 ld a,(V_ENH)
 or a
 jr z,.ordinary
 call enhanced_pattern
 jr c,.built
.ordinary:
 call build_pattern
.built:
 ld a,(V_INDEX)
 and 32
 rrca
 rrca
 rrca
 rrca
 rrca
 add a,32
 nextreg 0x52,a
 ld hl,(V_CACHE)
 ld de,193
 add hl,de
 ld de,(V_KEY)
 ld (hl),e
 inc hl
 ld (hl),d
 ld hl,(V_CACHE)
 ld de,65
 add hl,de
 ex de,hl
 ld hl,PAT
 ld bc,128
 ldir
 nextreg 0x52,10
 ret

; Address lookup followed by complete live-image comparison, including mirrors.
; Unknown or modified art retains its original pattern. Tables cannot add pixels.
enhanced_pattern:
 ld hl,(V_KEY)
 ld a,h
 rrca
 rrca
 rrca
 rrca
 and 7
 add a,48
 nextreg 0x52,a
 ld a,h
 and 15
 ld h,a
 add hl,hl
 set 6,h
 ld a,(hl)
 inc hl
 ld h,(hl)
 ld l,0
.entry:
 or a
 ret z
 nextreg 0x52,a
 ld (V_EBASE),hl
 ld de,194
 add hl,de
 ld a,(V_MASK)
 or a
 ld b,32
 jr z,.length
 ld b,64
.length:
 ld a,(hl)
 cp b
 jr nz,.next
 ld hl,(V_SRC)
 ld de,(V_EBASE)
.compare:
 ld a,(de)
 cp (hl)
 jr nz,.next
 inc de
 inc hl
 djnz .compare
 ld (V_SRC),hl
 ld hl,(V_EBASE)
 ld de,64
 add hl,de
 ld de,PAT
 ld bc,128
 ldir
 scf
 ret
.next:
 ld hl,(V_EBASE)
 ld de,192
 add hl,de
 ld a,(hl)
 inc hl
 ld h,(hl)
 ld l,0
 jr .entry
build_pattern:
 ld a,(V_MASK)
 or a
 jp nz,masked_fast
 ld hl,(V_SRC)
 ld de,PIX
 ld a,16
 ld (V_ROW),a
.row:
 ld a,(V_MASK)
 or a
 jr z,.or
 ld c,(hl)
 inc hl
 ld b,(hl)
 inc hl
 jr .inks
.or:
 ld bc,0xffff
.inks:
 ld a,(hl)
 inc hl
 ld (V_INK),a
 ld a,(hl)
 inc hl
 ld (V_INK+1),a
 push hl
 ld a,c
 ld (V_MSK),a
 ld a,b
 ld (V_MSK+1),a
 ld hl,V_INK
 ld c,2
.byte:
 ld b,8
 ld a,(hl)
 ld (V_G),a
 ld a,(hl)
 inc hl
 push hl
 ld hl,V_MSK
 ld a,c
 cp 1
 jr nz,.left
 inc hl
.left:
 ld a,(hl)
 ld (V_G+1),a
.bit:
 ld a,(V_G+1)
 add a,a
 ld (V_G+1),a
 ld a,0
 jr c,.transparent
 ld a,8
.transparent:
 ld (de),a
 ld a,(V_G)
 add a,a
 ld (V_G),a
 jr nc,.empty
 ld a,1
 ld (de),a
.empty:
 inc de
 djnz .bit
 pop hl
 dec c
 jr nz,.byte
 pop hl
 ld a,(V_ROW)
 dec a
 ld (V_ROW),a
 jr nz,.row
 ld (V_SRC),hl
 ld a,(V_MASK)
 or a
 call z,flood
 ld hl,PIX
 ld de,PAT
 ld b,128
.pack:
 ld a,(hl)
 inc hl
 rlca
 rlca
 rlca
 rlca
 or (hl)
 inc hl
 ld (de),a
 inc de
 djnz .pack
 ret

; Four pixels per table lookup. The table covers every mask/ink combination.
masked_fast:
 ld hl,(V_SRC)
 ld de,PAT
 ld a,16
 ld (V_ROW),a
.row:
 ld c,(hl)
 inc hl
 ld b,(hl)
 inc hl
 ld a,(hl)
 inc hl
 push bc
 call masked_byte
 pop bc
 ld c,b
 ld a,(hl)
 inc hl
 call masked_byte
 ld a,(V_ROW)
 dec a
 ld (V_ROW),a
 jr nz,.row
 ld (V_SRC),hl
 ret
masked_byte:
 push hl
 ld b,a
 rrca
 rrca
 rrca
 rrca
 and 15
 ld l,a
 ld a,c
 and 240
 or l
 call nibble
 ld a,c
 rlca
 rlca
 rlca
 rlca
 and 240
 ld l,a
 ld a,b
 and 15
 or l
 call nibble
 pop hl
 ret
nibble:
 add a,a
 ld l,a
 ld a,0x18
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

; Flood-fill exterior zero pixels; enclosed regions become black, with no outside rim.
flood:
 ld hl,QUEUE
 ld (V_QTAIL),hl
 ld (V_HEAD),hl
 ld c,0
.seed:
 ld a,c
 and 0xf0
 jr z,.edge
 cp 0xf0
 jr z,.edge
 ld a,c
 and 15
 jr z,.edge
 cp 15
 jr nz,.seednext
.edge:
 call mark
.seednext:
 inc c
 jr nz,.seed
.take:
 ld hl,(V_HEAD)
 ld de,(V_QTAIL)
 or a
 sbc hl,de
 jr z,.finish
 ld hl,(V_HEAD)
 ld c,(hl)
 inc hl
 ld (V_HEAD),hl
 ld a,c
 and 15
 jr z,.right
 dec c
 call mark
 inc c
.right:
 ld a,c
 and 15
 cp 15
 jr z,.up
 inc c
 call mark
 dec c
.up:
 ld a,c
 cp 16
 jr c,.down
 sub 16
 push bc
 ld c,a
 call mark
 pop bc
.down:
 ld a,c
 cp 240
 jr nc,.take
 add a,16
 ld c,a
 call mark
 jr .take
.finish:
 ld hl,PIX
 ld b,0
.fix:
 ld a,(hl)
 cp 15
 jr nz,.inside
 ld (hl),0
 jr .advance
.inside:
 or a
 jr nz,.advance
 ld (hl),8
.advance:
 inc hl
 djnz .fix
 ret
mark:
 ld h,PIX>>8
 ld l,c
 ld a,(hl)
 or a
 ret nz
 ld (hl),15
 ld hl,(V_QTAIL)
 ld (hl),c
 inc hl
 ld (V_QTAIL),hl
 ret

upload:
 ld a,(V_NS)
 ld b,a
 ld a,(V_BACK)
 add a,b
 ld b,a
 srl a
 bit 0,b
 jr z,.sel
 or 128
.sel:
 ld bc,0x303b
 out (c),a
 ld hl,PAT
 ld bc,0x805b
 REPT 128
 outi
 ENDR
 ret
stage:
 ld a,(V_NS)
 cp 64
 ret nc
 ld e,a
 ld d,0
 ld hl,ATT
 add hl,de
 add hl,de
 add hl,de
 add hl,de
 add hl,de
 ld a,(V_X)
 add a,32
 ld (hl),a
 inc hl
 ld b,0
 rl b
 ld a,(V_Y)
 add a,32
 ld (hl),a
 inc hl
 ld c,0
 rl c
 ld a,(V_COL)
 rlca
 rlca
 rlca
 rlca
 or b
 ld (hl),a
 inc hl
 ld a,(V_BACK)
 add a,e
 ld b,a
 srl a
 or 0xc0
 ld (hl),a
 inc hl
 ld a,b
 and 1
 rrca
 rrca
 or 128
 or c
 ld (hl),a
 ld hl,V_NS
 inc (hl)
 ret
commit_attrs:
 ld a,(V_NS)
 or a
 jr z,.hide
 ld b,a
 ld hl,ATT
 xor a
 push bc
 ld bc,0x303b
 out (c),a
 pop bc
.show:
 push bc
 ld bc,0x0557
 outi
 outi
 outi
 outi
 outi
 pop bc
 djnz .show
.hide:
 ld a,(V_NS)
 ld b,a
 ld a,(V_PREV)
 sub b
 jr c,.done
 jr z,.done
 ld c,a
 ld a,b
.hidden:
 nextreg 0x34,a
 nextreg 0x38,0
 inc a
 dec c
 jr nz,.hidden
.done:
 ld a,(V_NS)
 ld (V_PREV),a
 nextreg 0x15,1
 ret

; Stage complete glyphs, then publish their colours with the clean image.
; Unknown/modified glyphs erase their overlay cell and fall back to the ULA.
h_bgobject:
 ENTER
 ld a,(STK-1)
 ld (V_BGOBJ),a
 ld de,(STK-6)
 ld (V_BGORG),de
 EXIT x_bgobject
h_bgclean:
 ENTER
 ld a,(V_SPEED)
 ld (V_BGUS),a
 call bg_capture
 ; The original clean-glyph copy is display work, with no game timing or sound.
 ; Run those same instructions fast; the paired tail restores its incoming speed.
 ld a,(V_ENH)
 or a
 jr z,.original_speed
 ld a,3
 ld (V_SPEED),a
.original_speed:
 EXIT x_bgclean
h_bgfinish:
 ENTER
 ld a,(V_BGUS)
 ld (V_SPEED),a
 EXIT x_bgfinish
h_bgdisplay:
 ENTER
 ld a,(V_SPEED)
 ld (V_BGUS),a
 call bg_capture
 ; Accelerate only playfield glyph display work; keep HUD drawing at its
 ; incoming speed. The paired tail restores speed before returning to the game.
 ld a,(V_ENH)
 or a
 jr z,.original_speed
 ld de,(STK-6)
 ld a,d
 cp 6
 jr c,.original_speed
 cp 24
 jr nc,.original_speed
 ld a,3
 ld (V_SPEED),a
.original_speed:
 EXIT x_bgdisplay
h_bgdisplayfinish:
 ENTER
 ld a,(V_BGUS)
 ld (V_SPEED),a
 EXIT x_bgdisplayfinish
bg_capture:
 ld a,(V_ENH)
 or a
 ret z
 ld a,(V_BGACTIVE)
 or a
 ret z
 ld de,(STK-6)
 ld a,d
 cp 6
 ret c
 cp 24
 ret nc
 ld a,e
 cp 32
 ret nc
 ld (V_BGXY),de
 ld hl,(V_BGCOUNT)
 ld a,h
 cp 4
 jr c,.space
 ld a,1
 ld (V_BGOVER),a
 xor a
 ld (V_BGACTIVE),a
 nextreg 0x69,0
 ret
.space:
 push hl
 inc hl
 ld (V_BGCOUNT),hl
 pop hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 ld a,h
 and 0x20
 rlca
 rlca
 rlca
 add a,86
 nextreg 0x51,a
 ld a,h
 and 31
 or 0x20
 ld h,a
 ld (hl),e
 inc hl
 ld (hl),d
 inc hl
 ex de,hl
 ld a,(STK-1)
 ld l,a
 ld h,0
 add hl,hl
 add hl,hl
 add hl,hl
 ld bc,(0x9c52)
 add hl,bc
 ld a,l
 ld (de),a
 inc de
 ld a,h
 ld (de),a
 inc de
 ld a,(V_BGOBJ)
 ld (de),a
 inc de
 push hl
 ld hl,(V_BGORG)
 ld a,(V_BGXY)
 sub l
 ld (de),a
 inc de
 ld a,(V_BGXY+1)
 sub h
 ld (de),a
 inc de
 pop hl
 ld bc,8
 ldir
 nextreg 0x51,0xff
 ret
bg_clear:
 nextreg 0x69,0
 xor a
 ld (V_BGCOUNT),a
 ld (V_BGCOUNT+1),a
 ld (V_BGOVER),a
 ld a,(V_ENH)
 or a
 ret z
 ld a,255
 ld (V_BGOBJ),a
 ; The original game and start-up are DI here. Use its existing interrupt
 ; state; clear the overlay with word stores, then restore our private stack.
 ld (V_BGSP),sp
 ld a,88
 ld hl,0
.page:
 nextreg 0x51,a
 ld sp,0x4000
 ld b,64
.zero:
 REPT 64
 push hl
 ENDR
 djnz .zero
 inc a
 cp 94
 jr nz,.page
 ld sp,(V_BGSP)
 nextreg 0x51,0xff
 ret
bg_flush:
 ld a,(V_ENH)
 or a
 ret z
 ld a,(V_BGACTIVE)
 or a
 ret z
 ld hl,(V_BGCOUNT)
 ld a,h
 or l
 ret z
.border:
 call line
 ld a,h
 or a
 jr nz,.paint
 ld a,l
 cp 32
 jr c,.paint
 cp 240
 jr c,.border
.paint:
 ld hl,0
 ld (V_BGREAD),hl
.next:
 ld hl,(V_BGREAD)
 ld de,(V_BGCOUNT)
 or a
 sbc hl,de
 jp z,.done
 ld hl,(V_BGREAD)
 push hl
 inc hl
 ld (V_BGREAD),hl
 pop hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 ld a,h
 and 0x20
 rlca
 rlca
 rlca
 add a,86
 nextreg 0x51,a
 ld a,h
 and 31
 or 0x20
 ld h,a
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc hl
 ld (V_BGXY),de
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc hl
 ld (V_BGKEY),de
 ld a,(hl)
 ld (V_BGTEST),a
 inc hl
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc hl
 ld (V_BGREL),de
 ld de,V_BGRAW
 ld bc,8
 ldir
 ; Sparse hash by object and placement: shared blank/fill glyphs no longer
 ; require a walk through hundreds of unrelated paint records.
 ld a,(V_BGTEST)
 ld d,a
 ld e,a
 ld a,(V_BGREL+1)
 and 31
 ld l,a
 ld h,0
 REPT 5
 add hl,hl
 ENDR
 ld a,(V_BGREL)
 and 31
 ld c,a
 ld b,0
 add hl,bc
 add hl,de
 ld a,h
 and 31
 ld h,a
 add hl,hl
 ld a,h
 and 0x20
 rlca
 rlca
 rlca
 add a,36
 nextreg 0x52,a
 ld a,h
 and 31
 or 0x40
 ld h,a
 ld a,(hl)
 or a
 jr z,.blank
 inc hl
 ld l,(hl)
.record:
 ld h,0
 REPT 6
 add hl,hl
 ENDR
 set 6,h
 nextreg 0x52,a
 push hl
 ld de,5
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 ld (V_BGCHAIN),de
 pop hl
 ld de,(V_BGKEY)
 ld a,(hl)
 cp e
 jr nz,.chain
 inc hl
 ld a,(hl)
 cp d
 jr nz,.chain
 inc hl
 ld a,(V_BGTEST)
 cp (hl)
 jr nz,.chain
 inc hl
 ld a,(V_BGREL)
 cp (hl)
 jr nz,.chain
 inc hl
 ld a,(V_BGREL+1)
 cp (hl)
 jr nz,.chain
 inc hl
 inc hl
 inc hl
 ld de,V_BGRAW
 ld b,8
.validate:
 ld a,(de)
 cp (hl)
 jr nz,.blank
 inc hl
 inc de
 djnz .validate
 jr .draw
.chain:
 ld hl,(V_BGCHAIN)
 ld a,l
 or a
 jr z,.blank
 ld l,h
 jr .record
.blank:
 ld hl,bg_empty
.draw:
 ld de,(V_BGXY)
 ld a,d
 srl a
 srl a
 add a,88
 nextreg 0x51,a
 ld a,d
 and 3
 rlca
 rlca
 rlca
 or 0x20
 ld d,a
 sla e
 sla e
 sla e
 ld b,8
.row:
 push bc
 push de
 REPT 4
 ld a,(hl)
 rrca
 rrca
 rrca
 rrca
 and 15
 ld (de),a
 inc e
 ld a,(hl)
 and 15
 ld (de),a
 inc e
 inc hl
 ENDR
 pop de
 inc d
 pop bc
 djnz .row
 jp .next
.done:
 xor a
 ld (V_BGCOUNT),a
 ld (V_BGCOUNT+1),a
 nextreg 0x52,10
 nextreg 0x51,LPG
 ret
bg_empty:
 DS 64,0

original_paint:
 INCBIN "paint.bin"
 jp attr_done
original_unpaint:
 INCBIN "unpaint.bin"
 jp attr_done
h_end:
 ASSERT h_end<0x1800
 SAVEBIN "herbert_hook.bin",0x100,h_end-0x100

 ORG 0xd000
setup:
 nextreg 0x50,HPG
 ld bc,0x243b
 ld a,7
 out (c),a
 inc b
 in a,(c)
 and 3
 ld (V_SPEED),a
 nextreg 7,3
 ld a,1
 ld (V_ROOM),a
 ld hl,0x2000
 ld (V_PTR),hl
 nextreg 0x43,0x20
 nextreg 0x40,0
 ld hl,PAL
 ld b,0
.palette:
 ld a,(hl)
 nextreg 0x41,a
 inc hl
 djnz .palette
 call hide
 call bg_clear
 nextreg 0x12,44
 nextreg 0x14,0xe3
 nextreg 0x70,0
 nextreg 0x43,0x10
 nextreg 0x40,0
 ld hl,PAL
 ld b,0
.bgpalette:
 ld a,(hl)
 nextreg 0x41,a
 inc hl
 djnz .bgpalette
 nextreg 0x40,0
 nextreg 0x41,0xe3
 nextreg 0x43,0x20
 nextreg 0x1c,1
 nextreg 0x18,0
 nextreg 0x18,255
 nextreg 0x18,48
 nextreg 0x18,191
 nextreg 0x4b,0
 nextreg 0x1c,2
 nextreg 0x19,0
 nextreg 0x19,255
 nextreg 0x19,48
 nextreg 0x19,191
 nextreg 0x15,1
 ld a,(V_SPEED)
 nextreg 7,a
 nextreg 0x50,0xff
 ret
 SAVEBIN "herbert_setup.bin",0xd000,$-0xd000
