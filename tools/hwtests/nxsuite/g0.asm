; nxsuite/g0.asm - G0 SYS: identity, launch state, the file itself (spec section 3 G0). GPL-3.0-or-later.

; S00 scan, run at entry before anything else touches bank 5: $5B00-$5BFF against i*7+$11
s00_scan:
        ld hl,$5B00 : ld c,0 : ld de,0              ; C = i, DE = changed count
        ld a,$FF : ld (s00_first),a : xor a : ld (s00_last),a
.l:     ld a,c : add a,a : add a,a : add a,a : sub c : add a,$11   ; i*7 + $11
        cp (hl) : jr z,.n
        inc de
        ld a,(s00_first) : cp $FF : jr nz,.f
        ld a,c : ld (s00_first),a
.f:     ld a,c : ld (s00_last),a
.n:     inc hl : inc c : jr nz,.l
        ld (s00_cnt),de
        ret
s00_cnt: dw 0
s00_first: db 0
s00_last: db 0

t_s00:  ld hl,(s00_cnt) : call res_int
        ld hl,u_bytes : call res_unit
        ld hl,(s00_cnt) : ld a,h : or l : ret z
        ld hl,k_first : ld a,(s00_first) : call ex_kh
        ld hl,k_last : ld a,(s00_last) : jp ex_kh
k_first: db "first",0
k_last: db "last",0
u_bytes: db "bytes",0
u_t:    db "T",0
u_clocks: db "clocks",0
u_lines: db "lines",0
u_count: db "count",0

; S01: the snapshot is taken at entry and written as R lines; here the values the claims name
t_s01:  ld a,(NRSNAP+$08) : call res_hex
        ld hl,s01regs
.l:     ld a,(hl) : or a : jr z,.p
        push hl
        ld (k_nr+2),a : call .hx
        ld hl,k_nr : call ex_k
        pop hl : push hl
        ld l,(hl) : ld h,NRSNAP>>8 : ld a,(hl) : call wdhex2
        pop hl : inc hl : jr .l
.p:     ld hl,k_7ffd : call ex_k
        ld hl,st1 : ld a,(NRSNAP+$08) : bit 7,a : jr nz,.w
        ld hl,st2
.w:     jp wstr
.hx:    ; A = register -> its two hex digits into k_nr+2
        push af : rrca : rrca : rrca : rrca : call .d : ld (k_nr+2),a : pop af
        call .d : ld (k_nr+3),a : ret
.d:     and 15 : add a,'0' : cp '9'+1 : ret c
        add a,'a'-'9'-1 : ret
s01regs: db $0A,$B8,$B9,$BA,$BB,$8C,$12,$13,$6E,$6F,$05,$07,$C0,$C4,0
k_nr:   db "nrxx",0
k_7ffd: db "p7ffd",0

; S02: core version a.b.cc, machine id ($00), board id ($0F); the core>=3.03 flag for later SKIPs
t_s02:  ld hl,WORK+256 : ld (wp),hl
        call wcore : xor a : call wchr
        ld hl,EXB : ld (wp),hl
        ld hl,WORK+256 : call res_word
        ld hl,k_nr00 : ld a,(NRSNAP+$00) : call ex_kh
        ld hl,k_nr0f : ld a,(NRSNAP+$0F) : call ex_kh
        ld hl,k_c303 : call ex_k
        ld a,(core303) : add a,'0' : jp wchr
k_nr00: db "nr00",0
k_nr0f: db "nr0f",0
k_c303: db "core303",0
; core >= 3.03.00 -> 1 (set by the preamble's caller; used by stage 2 groups)
core303: db 0
set_core303:
        ld a,(NRSNAP+$01) : cp $33 : ld a,0 : jr c,.s
        inc a
.s:     ld (core303),a : ret

; S03: RAM size choice (preamble measured it: s03_ram in core.asm)
t_s03:  ld a,(ramchoice) : add a,a : ld l,a : ld h,0 : ld de,ramw : add hl,de
        ld a,(hl) : inc hl : ld h,(hl) : ld l,a : call res_word
        ld hl,k_c96 : call ex_k : ld a,'$' : call wchr : ld hl,(s03c96) : call whex4
        ld hl,k_c0 : call ex_k : ld a,'$' : call wchr : ld hl,(s03c0) : call whex4
        ld hl,k_crom : call ex_k : ld a,'$' : call wchr : ld hl,(s03crom) : jp whex4
k_c96:  db "crc96",0
k_c0:   db "crc0",0
k_crom: db "crcrom0",0

; S04: ROM 3 (selected at start) CRCs and bytes
s04_crc:
        ld hl,$0000 : ld bc,$4000 : call crc_mem : ld (s04c),hl
        ld hl,$386E : ld bc,$3D00-$386E : call crc_mem : ld (s04c2),hl
        ret
s04c:   dw 0
s04c2:  dw 0
t_s04:  ld hl,(s04c) : call res_hex16
        ld hl,k_c386 : call ex_k : ld a,'$' : call wchr : ld hl,(s04c2) : call whex4
        ld hl,k_b38 : call ex_k : ld hl,$0038 : ld b,$51-$38 : call .bytes
        ld hl,k_b386 : call ex_k : ld hl,$386E : ld b,$3881-$386E
.bytes: ld a,(hl) : call whex2 : inc hl : djnz .bytes
        ret
k_c386: db "crc386e",0
k_b38:  db "b0038",0
k_b386: db "b386e",0

; S05: NEXTREG keeps the 0x243B selection (NEXTREG n,v and NEXTREG n,A forms) at 3.5 and 28 MHz
t_s05:  call .one : ld (.r),a : ld a,c : ld (.r+1),a
        nextreg $07,3
        call .one : ld (.r+2),a : ld a,c : ld (.r+3),a
        ld a,(spd0) : nextreg $07,a
        ld hl,.r : ld b,4 : ld c,0
.c:     ld a,(hl) : cp $5A : jr z,.ok
        inc c
.ok:    inc hl : djnz .c
        ld a,c : or a : ld a,ST_PASS : jr z,.st
        ld a,ST_FAIL
.st:    ld (R_st),a
        ld l,c : ld h,0 : call res_int
        ld hl,k_r35n : ld a,(.r) : call ex_kh
        ld hl,k_r35a : ld a,(.r+1) : call ex_kh
        ld hl,k_r28n : ld a,(.r+2) : call ex_kh
        ld hl,k_r28a : ld a,(.r+3) : jp ex_kh
; -> A = read after NEXTREG $56,n ; C = read after NEXTREG $56,A
.one:   nextreg $7F,$5A
        ld bc,$243B : ld a,$7F : out (c),a
        nextreg $56,HOMEP6                          ; slot 6's current page again (harmless)
        inc b : in e,(c)
        nextreg $7F,$5A
        dec b : ld a,$7F : out (c),a
        ld a,HOMEP6 : nextreg $56,a
        inc b : in c,(c)
        ld a,e
        ret
.r:     ds 4
k_r35n: db "r35n",0
k_r35a: db "r35a",0
k_r28n: db "r28n",0
k_r28a: db "r28a",0

; S06: write $07 = 0..3, read at once and after one frame; PASS if bits 5:4 and 1:0 = the value after
; the frame (spec); the immediate reads are INFO
t_s06:  ld c,0 : ld b,0                             ; C = speed, B = mismatches
.l:     push bc
        ld a,c : nextreg $07,a
        ld a,$07 : call rdreg : ld hl,.im : ld e,c : ld d,0 : add hl,de : ld (hl),a
        call frame_sync
        ld a,$07 : call rdreg : ld hl,.fr : add hl,de : ld (hl),a
        pop bc
        ld e,a : and 3 : cp c : jr nz,.bad
        ld a,e : rrca : rrca : rrca : rrca : and 3 : cp c : jr z,.ok
.bad:   inc b
.ok:    inc c : ld a,c : cp 4 : jr nz,.l
        ld a,(spd0) : nextreg $07,a
        ld a,b : or a : ld a,ST_PASS : jr z,.s
        ld a,ST_FAIL
.s:     ld (R_st),a
        ld l,b : ld h,0 : call res_int
        ld c,0
.p:     ld a,'i' : ld hl,.im : call .kv
        ld a,'f' : ld hl,.fr : call .kv
        inc c : ld a,c : cp 4 : jr nz,.p
        ret
.kv:    push af : ld a,' ' : call wchr : pop af : call wchr
        ld a,c : add a,'0' : call wchr : ld a,'=' : call wchr
        ld e,c : ld d,0 : add hl,de : ld a,(hl) : jp wdhex2
.im:    ds 4
.fr:    ds 4

; S07: the file written now (all lines so far), opened again read-only, its first 64 bytes compared
t_s07:  call txt_flush : ld a,0 : jr nc,.w1
        inc a
.w1:    ld (.wf),a
        ld hl,EXB : ld (wp),hl : ld (hl),0 : xor a : ld (wsink),a
        ld a,(.wf) : or a : jr nz,.fail
        ld hl,txtname : ld b,$01 : call f_open : jr c,.fail
        ld (.h),a
        ld ix,WORK : ld bc,64 : call f_read
        push af : push bc : ld a,(.h) : call f_close : pop bc : pop af
        jr c,.fail
        ld a,c : cp 64 : jr nz,.fail
        ld hl,0 : ld de,WORK : ld b,64
.c:     call txt_peek : ex de,hl : cp (hl) : ex de,hl : jr nz,.fail
        inc hl : inc de : djnz .c
        ld hl,64 : call res_int
        ld a,ST_PASS : ld (R_st),a
        ret
.fail:  ld a,ST_FAIL : ld (R_st),a
        ld hl,0 : jp res_int
.h:     db 0
.wf:    db 0

; ---------------------------------------------------------------- a group end whose results did not reach the card
txt_flush_g:
        call txt_flush : ret nc
        call cls
        ld a,2 : out ($FE),a
        ld hl,m_sfail : ld a,2 : call plines
        call keys_up
.k:     call getkey : or a : jr z,.k
        call keys_up
        jp gscreen
m_sfail: db "RESULTS NOT SAVED (file write",0
        db "failed). Photograph this. Then",0
        db "power off/on, start again, run",0
        db "this group again. Any key.",0,0
