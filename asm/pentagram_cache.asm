; 64-pattern 8bpp content cache. Caller hides sprites before replacement.
; Sampled hash + full256-byte comparison; collisions never alter picture.
; Source is page-aligned; caller supplies the complete256-byte pattern.
; HL points to256 bytes in slot1. Cache backing pages88/89 map intoMMU0.
; Caller clears sc_used[64] at frame start. A=pattern0..63 or255ifoverflow.
; Main registers lost, IX/IY and alternate set untouched.
sc_get:
        ld (sc_source),hl
        ld a,(sc_initialized)
        or a
        jr nz,.ready
        inc a
        ld (sc_initialized),a
        xor a
        ld hl,sc_heads
        ld de,sc_heads+1
        ld bc,255
        ld (hl),a
        ldir
.ready:
        ld a,(sc_hint)
        cp 64
        jr nc,.hashinit
        ld c,a
        ld l,a
        ld h,sc_valid/256
        ld a,(hl)
        or a
        jr z,.hashinit
        push bc
        call sc_map
        ex de,hl
        ld hl,(sc_source)
        ld b,32
.hintloop:
        DUP 8
        ld a,(de)
        cp (hl)
        jr nz,.hintmiss
        inc hl
        inc de
        EDUP
        djnz .hintloop
        pop bc
        jp .found
.hintmiss:
        pop bc
.hashinit:
        ld hl,(sc_source)
        ld de,0
        ld b,64
.hash: ld a,(hl)
        add a,d
        ld d,a
        ld a,e
        rlca
        xor (hl)
        ld e,a
        ld a,l
        add a,4
        ld l,a
        djnz .hash
        ld (sc_hash),de
        ld a,d
        xor e
        ld l,a
        ld h,sc_heads/256
        ld a,(hl)
.search:
        or a
        jr z,.findfree
        dec a
        ld c,a
        ld h,sc_hashes/256
        ld a,c
        add a,a
        ld l,a
        ld a,(hl)
        cp e
        jr nz,.next
        inc l
        ld a,(hl)
        cp d
        jr nz,.next
        push bc
        push de
        call sc_map
        ex de,hl
        ld hl,(sc_source)
        ld b,32
.compare:
        DUP 8
        ld a,(de)
        cp (hl)
        jr nz,.different
        inc hl
        inc de
        EDUP
        djnz .compare
        pop de
        pop bc
        jp .found
.different:
        pop de
        pop bc
.next: ld a,c
        add a,sc_next&255
        ld l,a
        ld h,sc_next/256
        ld a,(hl)
        jr .search
.findfree:
        ld c,0
.free: ld h,sc_used/256
        ld l,c
        ld a,(hl)
        or a
        jr nz,.occupied
        ld h,sc_live/256
        ld a,c
        add a,sc_live&255
        ld l,a
        ld a,(hl)
        or a
        jr z,.new
.occupied:
        inc c
        ld a,c
        cp 64
        jr c,.free
        ld a,255
        ret
.new:  ld h,sc_valid/256
        ld l,c
        ld a,(hl)
        or a
        call nz,sc_unlink
        ld h,sc_valid/256
        ld l,c
        ld (hl),1
        ld h,sc_hashes/256
        ld a,c
        add a,a
        ld l,a
        ld de,(sc_hash)
        ld (hl),e
        inc l
        ld (hl),d
        ; A bucket stores slot+1, with zero as the empty sentinel.
        ld a,d
        xor e
        ld l,a
        ld h,sc_heads/256
        ld a,c
        inc a
        ld b,(hl)
        ld (hl),a
        ld a,c
        add a,sc_next&255
        ld l,a
        ld h,sc_next/256
        ld (hl),b
        push bc
        call sc_map
        push hl
        ex de,hl
        ld hl,(sc_source)
        ld bc,256
        ldir
        pop hl
        pop bc
        push bc
        ld a,c
        ld bc,0x303B
        out (c),a
        ld bc,0x005B
        otir
        pop bc
.found:
        ld h,sc_used/256
        ld l,c
        ld (hl),1
        ld a,c
        ret
; Remove an evicted slot from its previous hash bucket. C remains slot.
; Chains have at most64 entries and only contain valid cache entries.
sc_unlink:
        ld a,c
        add a,a
        ld l,a
        ld h,sc_hashes/256
        ld a,(hl)
        inc l
        xor (hl)
        ld l,a
        ld h,sc_heads/256
        ld b,c
        inc b
.walk: ld a,(hl)
        cp b
        jr z,.remove
        or a
        ret z                  ; defensive: never dereference empty chain
        dec a
        add a,sc_next&255
        ld l,a
        ld h,sc_next/256
        jr .walk
.remove:
        push hl
        ld a,c
        add a,sc_next&255
        ld l,a
        ld h,sc_next/256
        ld a,(hl)
        pop hl
        ld (hl),a
        ret
sc_initialized:db 0
; C=pattern, HL=cache virtualaddress, AF lost.
sc_map:
        ld a,c
        and 31
        ld h,a
        ld l,0
        ld a,c
        srl a
        srl a
        srl a
        srl a
        srl a
        add a,88
        nextreg 0x50,a
        ret
sc_hint:db 255
sc_source:dw 0
sc_hash:dw 0
