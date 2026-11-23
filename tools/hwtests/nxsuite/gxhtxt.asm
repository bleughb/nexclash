; nxsuite/gxhtxt.asm - XH's words and screens, page 63 at $F748 (above G6's 64-byte program at $F700,
; below the IM2 table at $FC00). GPL-3.0-or-later.
xk_irq:  db "irq",0
xk_bad:  db "bad",0
xk_bef:  db "before",0
xk_aft:  db "after",0
xk_rst:  db "reset",0
w_deaf: db "deaf",0
w_cop:  db "copied",0
w_rfree: db "reset-frees",0
w_lock: db "still-locked",0
m_xh2:  db "XH2 DONE. The DMA may now be",0
        db "deaf until a reset. NEXT:",0
        db " ",0
        db "1 press a key, let the group",0
        db "  finish (DONE on the screen)",0
        db "2 POWER OFF AND ON (or a hard",0
        db "  reset; F4 if you test that)",0
        db "3 start nxsuite.nex again from",0
        db "  the same folder: it asks at",0
        db "  once which reset you used",0
        db "  and XH2 says what it did.",0
        db " ",0
        db "Press a key.",0,0
m_xh2d: db "XH2 NOT RUN: the DMA is deaf",0
        db "already (an earlier XH2 locked",0
        db "it and no reset has freed it).",0
        db " ",0
        db "Let the group finish, then",0
        db "POWER OFF AND ON, start",0
        db "nxsuite.nex again, press H.",0
        db " ",0
        db "Press a key.",0,0
q_xh2:  db 1
        db "XH2 FOLLOW-UP",0
        db " ",0
        db "XH2 locked the DMA last time.",0
        db "Which reset came before this",0
        db "start?",0
        db " ",0
        db "1 = F4 (soft reset)",0
        db "2 = a hard reset",0
        db "3 = power off and on",0,0
        db "soft",0,"hard",0,"power",0
