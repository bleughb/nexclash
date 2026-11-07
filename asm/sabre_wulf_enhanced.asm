; Sabre Wulf, the Enhanced colour set's hooks: the base (sabre_wulf_hooks.asm) with SABREMAN_BANKS defined. Sabreman
; (object 0) is shown in palette offsets 0-7 (his ink, bright or not) rather than ink + 8, and no other object ever is
; (every colour the game gives an object is bright: 39579, 40412, 41412, 42744, 42893, the tables 39608, 41895, 44151).
; So his offsets are his own: the setup gives his part entries (sabparts) the bright ink in offsets 0-6, the painted
; colours in offset 7 (bright white, his colour when no orchid acts), as the original shows his orchid effects by his
; colour. The same length as the base (apply's 4 bytes from two INC HL / DEC HL pairs), so every address the game and
; the stub use is the base's. Profile: docs/profiles/sabre_wulf_enhanced.json.
        DEFINE SABREMAN_BANKS
        INCLUDE "sabre_wulf_hooks.asm"
        SAVEBIN "swe_rom.bin",0x386E,rom_end-0x386E
        SAVEBIN "swe_setup.bin",0xD000,setup_end-0xD000
