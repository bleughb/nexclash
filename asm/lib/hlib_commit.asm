; Shared hook library: double-buffered patterns and the atomic attribute commit (card
; patch.display-atomic-switch). After Nightshade's blink fix (pilot runs/nightshade, nightshade_hooks.asm
; burst / vbase). NEW engines only (Dean's rule). Unit tests and negative controls: nexclash/hooklib.py.
;
; A frame's new images go into the half of pattern memory that no sprite shows (hlib_db_back); the
; hook builds the frame's attributes in a table; hlib_commit then writes them all in one burst, hides
; the sprites used last time and not now, and flips the halves. The old image stays shown until the
; burst, the new one is complete before it. Call hlib_commit right after the ULA change it goes with
; (the game's blit) and, if the play area must not tear, after hlib_beam_wait.
; The content cache (hlib_pcache.asm) works per physical slot, so an image cached in either half is
; reused only while the hook uploads into that half.
;
; The engine defines, before the INCLUDE:
;   HLIB_V_DB   EQU <2 bytes of hook RAM, zero at start>   +0 the back half's first pattern slot, +1 sprites shown
;   HLIB_DB_HALF EQU <slots in a half: 32 for 64 8-bit slots>   HLIB_DB_SPR0 EQU <first sprite number>
; The table: 5 bytes a sprite in the $35-$39 order (attribute 3 bit 6 set: the 5-byte form).

; hlib_db_back: A = the first pattern slot of the half no sprite shows
hlib_db_back:
        ld a,(HLIB_V_DB)
        ret

; hlib_commit: HL = the attribute table, A = sprites in it (0 = none shown). AF, BC, DE, HL lost.
; Writes 5 x A bytes, then 4 zero bytes for each sprite shown last time and not now, then flips.
hlib_commit:
        ld e,a                  ; E = sprites now
        ld bc,0x303B
        ld a,HLIB_DB_SPR0
        out (c),a
        ld a,e
        or a
        jr z,.nb
        ld d,a
        ld c,0x57
.b:     ld b,5
        otir
        dec d
        jr nz,.b
.nb:    ld a,(HLIB_V_DB + 1)    ; sprites shown last time
        sub e
        jr z,.nh
        jr c,.nh
        ld d,a                  ; D = sprites to switch off, from HLIB_DB_SPR0 + E
        ld a,HLIB_DB_SPR0
        add a,e
        ld bc,0x303B
        out (c),a
        ld c,0x57
        xor a
.h:     out (c),a               ; 4 bytes, attribute 3 = 0: hidden, the 4-byte form
        out (c),a
        out (c),a
        out (c),a
        dec d
        jr nz,.h
.nh:    ld a,e
        ld (HLIB_V_DB + 1),a
        ld a,(HLIB_V_DB)
.flip:  xor HLIB_DB_HALF        ; the next frame's images go to the other half
        ld (HLIB_V_DB),a
        ret

; hlib_beam_wait: wait while the beam is on lines DE..HL-1 (the play area), at most 65536 polls.
; Needs hlib_pace.asm (hlib_line, HLIB_V_PACE + 12). AF, BC lost; DE, HL kept.
hlib_beam_wait:
        push hl
        ld hl,0
        ld (HLIB_V_PACE + 12),hl
.lp:    ld hl,(HLIB_V_PACE + 12)
        dec hl
        ld (HLIB_V_PACE + 12),hl
        ld a,h
        or l
        jr z,.out
        call hlib_line          ; HL = line, DE kept
        or a
        sbc hl,de
        jr c,.out               ; above the band
        add hl,de
        pop bc                  ; BC = the band's end
        push bc
        or a
        sbc hl,bc
        jr c,.lp                ; inside: poll again
.out:   pop hl
        ret
