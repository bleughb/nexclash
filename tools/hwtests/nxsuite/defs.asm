; nxsuite/defs.asm - addresses and constants (GPL-3.0-or-later, part of nexclash)

SUITE_VER   equ 1               ; file format "NXSUITE 1"
MSTACK      equ $BE00           ; main stack (bank 2)
TBUF        equ $B000           ; timing block (up to $B4FF)
TBUF2       equ $B500           ; the empty block of the same shape
TBUF_END    equ $B800
CODE2B      equ $B800           ; txt2.asm (result file parts), up to $BB00 (stack: $BC00-$BDFF)
CODE2B_END  equ $BB00
SCRATCH     equ $F000           ; 2 KB scratch in page 1
IRQAREA     equ $F800           ; interrupt tables (G3)

LB          equ $5D00           ; line buffer (256)
EXB         equ $5E80           ; extras buffer for the current test (240; LB is 384)
VARS        equ $5F00           ; variables (256)
WIN         equ $6000           ; z80ntest FUNC window (G2), 1 KB
NRSNAP      equ $6400           ; NextReg snapshot at launch, 256 bytes
PRGB        equ $6500           ; progress record, 64 bytes
WORK        equ $6600           ; 512 bytes of work space (strings copied from the string page, ...)
B5CODE      equ $6800           ; bank 5 timing block (C02)
STAB        equ $7000           ; results table "NXS1": 6 bytes header + 8 per test
G2REC       equ $7800           ; G2 per-case records
NXHT        equ $7E00
DONEFLAG    equ $7FFF

STRPAGE     equ 62              ; string page (claims, titles, group names)
DATAPAGE    equ 56              ; G1 data page (slot 3 during a timed row)
SBX6        equ 56              ; G2 sandbox pages for slots 6 / 7
SBX7        equ 57
HOMEP6      equ 0               ; our pages in slots 6 / 7
HOMEP7      equ 1

; status codes (file words in harness.asm stnames)
ST_PASS     equ 1
ST_FAIL     equ 2
ST_INFO     equ 3
ST_SKIP     equ 4
ST_HANG     equ 5
ST_VISUAL   equ 6
ST_VSHOWN   equ 7
ST_OPER     equ 8
ST_PENDOP   equ 9

; value kinds
VK_NONE     equ 0
VK_NUM      equ 1               ; signed dword x 100
VK_HEX      equ 2               ; one byte
VK_WORD     equ 3               ; choice word (pointer)
VK_HEX16    equ 4               ; a 16-bit raw value

; progress record (64 bytes; spec 32 + per-group state, see README)
PRG_STATE   equ 6               ; 0 idle, 1 running, 2 done
PRG_TIDX    equ 7               ; word
PRG_TID     equ 9               ; 8 chars
PRG_GROUP   equ 17
PRG_FLAGS   equ 18
PRG_MODE    equ 19              ; 0 RUN ALL, 1 + group = one group
PRG_HUNG    equ 20              ; 6 words, $FFFF = free
PRG_FLEN    equ 48              ; word: NXSUITE.TXT's length at its last good write (read back exactly that)
PRG_GST     equ 32              ; 16 bytes: per group 0 not run, 1 done, 2 done with a FAIL, 3 operator
                                ; questions pending, 4 hung, 5 running
GS_NOTRUN   equ 0
GS_DONE     equ 1
GS_FAILS    equ 2
GS_PENDOP   equ 3
GS_HUNG     equ 4
GS_RUN      equ 5
