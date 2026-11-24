; Jack the Nipper (Gremlin Graphics 1986, 48K) - figures as hardware sprites. Facts and design: games/jack_the_nipper.md.
; The sprite routine 0x8009 draws each object masked (AND mask, OR graphics) into a shadow screen at 0x6000-0x6FFF and
; marks its cells; the copier 0x86F9 copies marked cells to the display, 0x8735 restores them from the tile map.
; The draw code itself is NOT replaced: at its two returns from the address helper 0x87BB (0x80C9 for 16-wide
; figures, 0x8273 for 24-wide) the hook moves the shadow address from 0x6000-0x6FFF to 0x2000-0x2FFF (RES 6,H: no
; flag or register but H changes), so the draw lands in a scratch shadow in this page and the real shadow keeps the
; background. The cell marks take only H bits 3 and 0-2 and L (0x8123), so they mark the same cells.
; Memory: this file is Next page JTN_PAGE, mapped at MMU slot 1 (0x2000-0x3FFF) for the whole game (the game never
; reads the ROM there): 0x2000-0x2FFF scratch shadow, 0x3800- hook code, 0x3F00 the stub's register block.
; Interrupts are off for the whole game (no interrupt accepted in the recording).
; Stage A: the redirect only; the commit at 0xAA4A passes straight to the copier.

        DEVICE ZXSPECTRUMNEXT

D16_BACK  EQU 0x80CC        ; after PUSH HL / PUSH AF / AND A at 0x80C9 (the 16-wide path)
D24_BACK  EQU 0x8276        ; the same three bytes at 0x8273 (the 24-wide path)
COPIER    EQU 0x86F9        ; what 0xAA4A calls

        ORG 0x3800
code_start:

; e_d16 / e_d24: JP here from 0x80C9 / 0x8273, right after CALL 0x87BB (HL = the figure's bottom-row shadow address,
; A = its pixel shift, DE = mask, DE' = graphics). The three displaced bytes run here, on the scratch address.
e_d16:  res 6,h
        push hl
        push af
        and a
        jp D16_BACK

e_d24:  res 6,h
        push hl
        push af
        and a
        jp D24_BACK

; e_cmt: CALL here from 0xAA4A instead of CALL 0x86F9 (the copier): the frame's figures are all drawn by now.
e_cmt:  jp COPIER

code_end:
        ASSERT code_end <= 0x3F00

        SAVEBIN "jtn_page.bin", code_start, code_end - code_start
