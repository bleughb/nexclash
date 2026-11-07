; Dynamite Dan v1.1: QUIT and PAUSE definable on the game's own define-keys screen (Jon Attree, .nxc v1.1).
; Our code and data only, at fixed addresses in the game's RAM; no game bytes are included. The engine
; (dynamite_dan.define_keys, rework v11) lays these blocks over the sprite build's RAM banks and rewrites the
; define-keys page text (0xFD93) from the player's own snapshot: the Q / P warning record dropped, "CHOOSE 3" -> "CHOOSE 5".
; Code in spare RAM at SPARE = 0xFF11 (the loader's old BASIC stack and UDG copies: never touched in the 52
; recordings, nor referenced by the game's code; the game's stack bottoms at 0xFFD9); data at 0xFE0C, the page
; text's freed tail. Profile: docs/profiles/dynamite_dan_keys.json (tools/asm2profile.py dynamite_dan_keys).
;
; Original play loop (0xC834-0xC865):
;   C834 LD BC,0400 / CALL D4AF        delay, 1024 x (DEC BC, LD A,B, OR C, JR NZ) = 4 M1, 26 T each
;   C83A LD A,DF / IN A,(FE) / RRA / JR C,C858      P not held -> quit check
;   C841..C857 wait release, wait P, wait release   (pause)
;   C858 LD A,FB / IN A,(FE) / RRA / JR C,C80A      Q not held -> next tick
;   C85F LD HL,C87F / SET 7,(HL) / JR C804          quit (C865 = the "Disable Q quit key" cheat byte)
; New: C83A jumps to KCHK, which does the same with the defined keys. Every path from C834 to its exit
; (C80A, C85F) costs 4 M1 more than the original (JP in, 2 NOPs, the exit JP); the delay is one iteration
; (4 M1, 26 T) shorter, so R at the exit is the original's and the tick is 3 T longer.

        DEVICE ZXSPECTRUM48
SPARE   EQU 0xFF11

; ---- in place -------------------------------------------------------------------------------------
        ORG 0xC834
        LD BC,0x03FF            ; was 0x0400
c834_end:
        ORG 0xC83A
        JP KCHK                 ; was LD A,DF / IN A,(FE) (C83D-C85E stay as they were, unused)
c83a_end:
        ORG 0xF2EE
        JP KDEF                 ; was CALL F2F4 (the original's tidy-up after JUMP); F2F1 JP CA56 unused
f2ee_end:

; data in the page text's freed tail (0xFE0C-0xFE2A: only the page's printer read it; the rewritten text ends at 0xFE0B)
        ORG 0xFE0C
KCODES: DB 0x25,0x22            ; QUIT, PAUSE as key codes (Q, P), stored as the game stores LEFT, RIGHT, JUMP
KTQUIT: DB 0x0C,0x09, 0x19,0x1D,0x12,0x1C,0x2C, 0xFF            ; QUIT:
KTPAUSE: DB 0x0C,0x09, 0x18,0x0A,0x1D,0x1B,0x0E,0x2C, 0xFF      ; PAUSE:
KDATA_END:

; ---- new code and data in spare RAM -----------------------------------------------------------------
        ORG SPARE
KCHK:   NOP                     ; 2 M1 of padding: every path +4 M1 = the delay iteration removed
        NOP
        LD A,0xDF               ; pause row (P)
KPP1    EQU $-1
        IN A,(0xFE)
        AND 0x01                ; pause bit
KPM1    EQU $-1
        JR NZ,KQ                ; not held: quit check (4 M1, as LD / IN / RRA / JR C)
KW1:    XOR A                   ; wait for every key up (as C841)
        IN A,(0xFE)
        CPL
        AND 0x1F
        JR NZ,KW1
KW2:    LD A,0xDF               ; wait for the pause key again (as C849)
KPP2    EQU $-1
        IN A,(0xFE)
        AND 0x01
KPM2    EQU $-1
        JR NZ,KW2
KW3:    XOR A                   ; wait for every key up (as C850)
        IN A,(0xFE)
        CPL
        AND 0x1F
        JR NZ,KW3
KQ:     LD A,0xFB               ; quit row (Q)
KQP     EQU $-1
        IN A,(0xFE)
        AND 0x01                ; quit bit
KQM     EQU $-1
        JR Z,KQUIT
        JP 0xC80A               ; next tick
KQUIT:  JP 0xC85F               ; the original's quit (its JR at C864 keeps the cheat byte C865)

; after JUMP: two more prompts in the same style, then the original's tidy-up and return
KDEF:   CALL 0xF2F4             ; clear the screen, wait for every key up
        LD HL,KTQUIT
        CALL 0xEEF1             ; print "QUIT:" at row 12 col 9, as LEFT: / RIGHT: / JUMP:
        CALL 0xF300             ; one key -> D (the game's own reader: any single key)
        LD A,D
        LD (KCODES),A
        CALL KSET               ; -> D row, E bit
        LD A,D
        LD (KQP),A
        LD A,E
        LD (KQM),A
        CALL 0xF2F4
        LD HL,KTPAUSE
        CALL 0xEEF1
        CALL 0xF300
        LD A,D
        LD (KCODES+1),A
        CALL KSET
        LD A,D
        LD (KPP1),A
        LD (KPP2),A
        LD A,E
        LD (KPM1),A
        LD (KPM2),A
        CALL 0xF2F4             ; as the original after JUMP
        JP 0xCA56               ; as the original

; key code (the game's: as at F26E, decoded as 0xF32A does) -> D = port high byte, E = bit mask
KSET:   LD C,A
        AND 0x07
        INC A
        LD B,A
        LD A,0xFE
KS1:    RRCA
        DJNZ KS1
        LD D,A
        LD A,C
        RRCA
        RRCA
        RRCA
        AND 0x1F
        LD C,A
        LD A,5
        SUB C
        LD B,A
        XOR A
        SCF
KS2:    RLA
        DJNZ KS2
        LD E,A
        RET

KEND:

        ASSERT KDATA_END <= 0xFE2B
        ASSERT KEND <= 0xFFA0
        SAVEBIN "ddk_c834.bin",0xC834,c834_end-0xC834
        SAVEBIN "ddk_c83a.bin",0xC83A,c83a_end-0xC83A
        SAVEBIN "ddk_f2ee.bin",0xF2EE,f2ee_end-0xF2EE
        SAVEBIN "ddk_data.bin",0xFE0C,KDATA_END-0xFE0C
        SAVEBIN "ddk_code.bin",SPARE,KEND-SPARE
