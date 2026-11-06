; Shared hook library: the immutable sprite image content cache (card optimise.pattern-cache §Contract).
; Rainbow Islands' design, as applied to Atic Atac v1.1 (pilot runs/atic_atac: upload, CACHEPG /
; CACHERW). NEW engines only (Dean's rule). Unit tests and negative control: nexclash/hooklib.py.
;
; Each 256-byte pattern slot (one 8-bit pattern, or a pair of 4-bit ones) remembers the 16-bit key
; of the immutable image last uploaded into it. An upload with the same key is skipped; any other
; upload writes the slot and its key. The rules that keep it right:
; - key 0 = a MUTABLE image (a work buffer the hook rebuilds): always uploaded, and the slot's key
;   invalidated, so the next immutable image there is uploaded again (the negative control drops that);
; - an immutable key names its bytes forever: (source page, row), a graphic address the game never
;   rewrites; hooklib.pcache_key builds one (never 0);
; - free, hide and clear keep pattern RAM, so they keep the keys: only code that overwrites pattern
;   RAM some other way calls hlib_pc_inval / hlib_pc_reset.
; The 0x303B write also sets the 0x57 attribute index (bits 6:0): select the sprite again before
; writing attributes through port 0x57.
;
; The engine defines, before the INCLUDE:
;   HLIB_PCACHE EQU <128 bytes of hook RAM, 256-aligned, zero at start>  +slot key low, +64+slot key high

        INCLUDE "hlib_dma.asm"

        ASSERT (HLIB_PCACHE & 0xFF) == 0

; hlib_pc_upload: A = pattern slot 0-63, DE = key (0 = mutable), HL = the 256 source bytes.
; AF, BC, HL lost; DE kept. Hit: 101 T; miss: selected synchronous transport + cache/setup.
; Initialize hlib_dma_init before enabling DMA (see hlib_dma.asm); otherwise CPU fallback.
hlib_pc_upload:
        push hl
        ld l,a
        ld h,high HLIB_PCACHE
        ld a,d
        or e
        jr z,.mut
        ld a,e
        cp (hl)
        jr nz,.miss
        set 6,l
        ld a,d
        cp (hl)
        jr nz,.hi
        pop hl                  ; hit: the slot holds this image
        ret
.miss:  ld (hl),e
        set 6,l
.hi:    ld (hl),d
        jr .go
.mut:                           ; A = 0
.inv:   ld (hl),a               ; mutable: the slot's key invalidated
        set 6,l
.inv2:  ld (hl),a
.go:    ld a,l
        and 63
        pop hl
        ld bc,0x303B
        out (c),a
        call hlib_dma_sprite   ; synchronous; capability-gated, cache hits never enter here
        ret

; hlib_pc_inval: A = slot -> its key 0 (pattern RAM overwritten by other code). AF lost.
hlib_pc_inval:
        push hl
        ld l,a
        ld h,high HLIB_PCACHE
        xor a
        ld (hl),a
        set 6,l
        ld (hl),a
        pop hl
        ret

; hlib_pc_reset: every key 0 (all pattern RAM rewritten: a set-up). AF, BC lost.
hlib_pc_reset:
        push hl
        ld hl,HLIB_PCACHE
        ld b,128
        xor a
.l:     ld (hl),a
        inc l
        djnz .l
        pop hl
        ret
