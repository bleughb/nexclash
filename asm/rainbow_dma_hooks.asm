; Experimental sky-rework tcommit extension, page 28 offset $1000 (CPU $5000).
; Slot 0 page 26, slot 1 alt ROM, slot 2 page 28, slot 3 page 14.
; Entry at 28 MHz, DI, private stack in page 26. HL=$4000, DE=$61E8.
; Page 28 $0000-$04FF shadow rows, $0600 LASTT, $0C00-$0FFF X8T.
; Upper $1000-$1FFF is reserved here; no DMA source touches ROM/alt ROM.
; NEX boot establishes exclusive idle DMA ownership and pulse mode ($C0=0).
; Game's software IM2 and AY queue do not use DMA. Recheck hardware IM2 each job;
; fall back to CPU without changing any masks if it has become enabled.
        DEVICE ZXSPECTRUMNEXT
        ORG $5000
LSAMP   EQU 0x3b00
transfer:
        call LSAMP              ; elapsed raster sample before bounded job
        push hl
        push de
        ld a,1
        call hlib_dma_init      ; core version AND hardware-IM2 gate; never EI under game ISR
        pop de
        pop hl
        call hlib_dma_rect      ; continuous: CPU resumes after transfer completes
        call LSAMP              ; include transfer stalls in overrun recovery
        ret
        INCLUDE "lib/hlib_dma.asm"
end_transfer:
        ASSERT end_transfer <= $6000
        SAVEBIN "rd_extension.bin",$5000,end_transfer-$5000
