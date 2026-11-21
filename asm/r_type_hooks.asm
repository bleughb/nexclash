; R-Type prototype, whole game from the start snapshot: no mid-level start-up, so
; the title screens (which also call the copier) keep Layer 2 and sprites off.
        DEFINE L2_SPRITES
        IFNDEF L2_NOGLIDE
        DEFINE L2_GLIDE          ; figures glide between updates (glide.asm)
        IFNDEF L2_NOSHIP
        DEFINE L2_SHIP           ; level 3 battleship hull on the tilemap (ship.asm)
        ENDIF
        ENDIF
        DEFINE L2_NOLAZY
        DEFINE L2_NOTAPE
        INCLUDE "r_type_l2scroll.asm"
        SAVEBIN "rtype_code.bin",hook_setup,$-hook_setup
        IFDEF L2_GLIDE
        INCLUDE "r_type_glide.asm"
        SAVEBIN "rtype_glide.bin",glide_start,glide_end-glide_start
        ENDIF
        IFDEF L2_SHIP
        INCLUDE "r_type_ship.asm"
        SAVEBIN "rtype_ship.bin",ship_start,ship_end-ship_start
        ENDIF
