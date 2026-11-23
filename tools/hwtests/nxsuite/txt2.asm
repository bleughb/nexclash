; nxsuite/txt2.asm - result file parts, keeping an earlier file, the build check. GPL-3.0-or-later.
; Bank 2 at $B800 (where the CRC table was; crcb now works bit by bit). The text buffer holds 64 KB; a
; session may write more. So when the buffer passes ROTAT bytes, the buffer is written (with its END line)
; to the next free NXSUITE.nnn ("part"), and a new buffer starts with "NXSUITE 1" and
; "C part=<nnn> src=<build>" (it continues that part); NXSUITE.TXT is written at once with that start.
; The intake follows the C lines back from NXSUITE.TXT. If a part cannot be written, rotation stops,
; the buffer fills, and every later write carries "X truncated lost=<bytes>" before its END line. At start,
; an NXSUITE.TXT from another build or one that does not check is copied unchanged to the next free part
; first (read until F_READ returns fewer bytes than asked), then a new file is started. Only the four
; documented esxDOS calls are used (spec 1.1).

ROTAT   equ $C000               ; 48 KB: a part is written when the buffer has this many bytes

; called by txt_append with HL = the pending bytes, BC = their count; returns with HL / BC unchanged
txt_rot:
        ld a,(txtlen+1) : cp ROTAT>>8 : ret c
        ld a,(rotbusy) : or a : ret nz
        ld a,(rotfail) : or a : ret nz
        inc a : ld (rotbusy),a
        ld (.src),hl : ld (.n),bc
        ld de,WORK : ldir                           ; the pending line (LB is used for the END line)
        ld hl,(wp) : ld (.wp),hl : ld a,(wsink) : ld (.ws),a
        call next_part : jr c,.fail
        ld hl,partname : call txt_wr : jr c,.fail
        ; the part is on the card: count it, start the continuation
        ld hl,(txtlen) : ld de,(txtbase) : add hl,de : ld (txtbase),hl
        jr nc,.nc : ld hl,(txtbase+2) : inc hl : ld (txtbase+2),hl
.nc:    ld hl,(txtlines) : ld de,(linebase) : add hl,de : ld (linebase),hl
        ld hl,0 : ld (txtlen),hl : ld (txtlines),hl : ld hl,$FFFF : ld (crc),hl
        call w_lb : ld hl,s_magic : call wstr : call w_len : call txt_append
        call w_lb : ld hl,s_cpart : call wstr : ld hl,partname+8 : call wstr
        ld hl,s_csrc : call wstr : ld hl,src2 : call wstr
        ld a,10 : call wchr : call w_len : call txt_append
        ld hl,(partno) : inc hl : ld (partno),hl
        call txt_flush                              ; NXSUITE.TXT = the continuation start now
        jr .back
.fail:  ld a,1 : ld (rotfail),a
.back:  ld hl,WORK : ld de,(.src) : ld bc,(.n) : ldir   ; the pending line back where it was
        ld hl,(.wp) : ld (wp),hl : ld a,(.ws) : ld (wsink),a
        xor a : ld (rotbusy),a
        ld hl,(.src) : ld bc,(.n)
        ret
.src:   dw 0
.n:     dw 0
.wp:    dw 0
.ws:    db 0
s_cpart: db "C part=",0
s_csrc: db " src=",0
rotbusy: db 0
rotfail: db 0
txtbase: ds 4                   ; bytes in parts written this session (for the screen)
linebase: dw 0
lostcnt: dw 0                   ; bytes that could not be stored ($FFFF = 65535 or more)
src2:   ds 9                    ; the build id (srcstr), copied here at start: slot 6 is not home here

; -> partname = the first NXSUITE.nnn (nnn >= partno) that does not open for reading; carry = none left
next_part:
.l:     ld hl,(partno) : ld de,1000 : or a : sbc hl,de : ccf : ret c
        ld hl,(partno) : ld de,partname+8 : call dec3
        ld hl,partname : ld b,$01 : call f_open : ccf : ret nc   ; does not open: free
        call f_close
        ld hl,(partno) : inc hl : ld (partno),hl
        jr .l
; HL < 1000 -> three digits at DE
dec3:   ld bc,100 : call .d : ld bc,10 : call .d : ld a,l : add a,'0' : ld (de),a : ret
.d:     ld a,'0'-1
.s:     inc a : or a : sbc hl,bc : jr nc,.s
        add hl,bc : ld (de),a : inc de : ret
partno: dw 1
partname: db "NXSUITE.000",0
keptname: db "NXSUITE.000",0

; copy NXSUITE.TXT unchanged to the next free part -> carry = it could not be copied (nothing is deleted
; either way); keptname = the part's name
txt_keep:
        ld hl,txtname : ld b,$01 : call f_open : jr nc,.o
        or a : ret                                  ; no file: nothing to keep
.o:     ld (.hr),a
        call next_part : jr c,.e1
        ld hl,partname : ld b,$0E : call f_open : jr c,.e1
        ld (.hw),a
.l:     ld ix,WORK : ld bc,256 : ld a,(.hr) : call f_read : jr c,.e2
        ld a,b : or c : jr z,.ok
        ld (.got),bc
        ld ix,WORK : ld a,(.hw) : call f_write : jr c,.e2
        ld hl,(.got) : or a : sbc hl,bc : jr nz,.e2
        ld a,(.got+1) : or a : jr nz,.l             ; 256 read: more may follow
.ok:    ld a,(.hw) : call f_close
        ld a,(.hr) : call f_close
        ld hl,partname : ld de,keptname : ld bc,12 : ldir
        ld hl,(partno) : inc hl : ld (partno),hl
        or a : ret
.e2:    ld a,(.hw) : call f_close
.e1:    ld a,(.hr) : call f_close
        scf : ret
.hr:    db 0
.hw:    db 0
.got:   dw 0

; the loaded text's first "src=" value against this build -> Z if the same
txt_src:
        ld hl,0
.f:     ld de,(txtlen) : push hl : inc hl : inc hl : inc hl : inc hl : or a : sbc hl,de : pop hl
        jr nc,.no
        ld a,h : cp 2 : jr nc,.no                   ; within the first 512 bytes
        ld de,.k : call .cmp : jr z,.at
        inc hl : jr .f
.at:    inc hl : inc hl : inc hl : inc hl
        ld de,src2
.v:     ld a,(de) : or a : jr z,.end
        call txt_peek : ex de,hl : cp (hl) : ex de,hl : ret nz
        inc hl : inc de : jr .v
.end:   call txt_peek : cp ' ' : ret z              ; Z if the value ends here too (space or LF)
        cp 10 : ret
.no:    or 1 : ret
; HL = offset, DE = 4 chars -> Z if the text has them there (HL kept)
.cmp:   push hl : ld b,4
.c:     call txt_peek : ex de,hl : cp (hl) : ex de,hl : jr nz,.x
        inc hl : inc de : djnz .c
.x:     pop hl : ret
.k:     db "src="

; called by txt_flush with the END line not yet added: "X truncated lost=<n>" if anything was lost
txt_lost:
        ld hl,(lostcnt) : ld a,h : or l : ret z
        call w_lb : ld hl,s_lost : call wstr : ld hl,(lostcnt) : call wdec
        ld a,10 : call wchr : call w_len : jp txt_append
s_lost: db "X truncated lost=",0
