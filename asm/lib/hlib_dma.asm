; Synchronous transfer backend for NEW engines / explicit reworks only.
; Writable hook RAM required (packets are patched). No ISR/reentrant use.
; hlib_dma_init: A=1 ONLY after establishing exclusive DMA ownership, stable RAM mappings,
; and a bounded job shorter than one frame. A=0 revokes ownership. No active DMA may exist.
; AF,BC,DE lost on init. Run init AND transfer calls at 28 MHz; NR C0 hardware-IM2 mode conservatively forces CPU fallback. Re-init if the
; interrupt configuration changes. Never silently clear a game's interrupt source masks.
; Policy: 2 prefer blitter (default), 1 ordinary DMA only, 0 CPU only. Runtime policy may be
; lowered at any time; raising it requires the same init contract. Old cores never see extensions.
; Define HLIB_NO_BLITTER or HLIB_CPU_ONLY before INCLUDE for build-time overrides.
; Continuous DMA completes before return; no asynchronous cache/attribute publication.
; Timing is hardware-dependent: profile setup + stall + hook, not just CPU instructions.

hlib_dma_policy:
    IFDEF HLIB_CPU_ONLY
        db 0
    ELSE
        IFDEF HLIB_NO_BLITTER
        db 1
        ELSE
        db 2
        ENDIF
    ENDIF
hlib_dma_cap: db 0              ; 0 CPU, 1 ordinary DMA, 2 DDMA; fail closed before init

hlib_dma_init:
        cp 1
        ld a,0
        ld (hlib_dma_cap),a
        ret nz
        ld bc,0x243B
        ld a,0xC0
        out (c),a
        inc b
        in a,(c)
        and 1
        ret nz                  ; do not risk DMA hold under DI / hardware IM2
        dec b
        ld a,1                  ; NR 01 = major << 4 | minor
        out (c),a
        inc b
        in a,(c)
        cp 0xFF
        ret z                   ; absent/unknown Next register interface
        cp 0x30
        ret c                   ; conservative supported baseline: core 3.x+
        ld d,1
        cp 0x33                 ; documented DDMA baseline 3.03.00 (no prerelease guessing)
        jr c,.set
        inc d
.set:
    IFDEF HLIB_CPU_ONLY
        xor a
    ELSE
        IFDEF HLIB_NO_BLITTER
        ld a,1
        ELSE
        ld a,d
        ENDIF
    ENDIF
        ld (hlib_dma_cap),a
        ret

; A = effective backend. No port writes. AF lost.
hlib_dma_backend:
        ld a,(hlib_dma_policy)
        or a
        ret z
        ld a,(hlib_dma_cap)
        or a
        ret z
        push hl
        ld hl,hlib_dma_policy
        cp (hl)
        jr c,.done
        ld a,(hl)
.done:  pop hl
        ret

; HL = 256 source bytes, sprite slot already selected. AF,BC,HL lost; DE kept.
; Uses ordinary DMA even on DDMA cores: 2D adds nothing to a contiguous I/O upload.
hlib_dma_sprite:
        call hlib_dma_backend
        or a
        jr z,.cpu
        ld (hlib_dma_sp_src),hl
        ld hl,hlib_dma_sp
        ld bc,(hlib_dma_sp_end-hlib_dma_sp)*256+0x6B
        otir
        ret
.cpu:
        ld bc,0x005B
    IFDEF HLIB_PC_OTIR
        otir
    ELSE
        DUP 256
        outi
        EDUP
    ENDIF
        ret
hlib_dma_sp:
        db 0x83,0xC3,0x7D
hlib_dma_sp_src: dw 0
        dw 256
        db 0x14,0x28,0xAD       ; memory increment -> fixed I/O, continuous
        dw 0x005B
        db 0x82,0xCF,0x87       ; stop at end, load, enable (last byte)
hlib_dma_sp_end:

; Rainbow tcommit geometry prototype: HL=source, DE=destination, 20 x 64 bytes,
; source stride 64, destination stride 80. AF,BC,DE,HL lost. Maps supplied by caller.
; All paths preserve source and destination gaps; no Layer 2 XY addressing.
hlib_dma_rect:
        call hlib_dma_backend
        cp 2
        jr z,.blitter
        cp 1
        jr z,.rows
        ld a,20
.cpu:   ld bc,64
        ldir
        ex de,hl
        ld bc,16
        add hl,bc
        ex de,hl
        dec a
        jr nz,.cpu
        ret
.rows:  ld a,20
.row:   push af
        ld (hlib_dma_row_src),hl
        ld (hlib_dma_row_dst),de
        push hl
        push de
        ld hl,hlib_dma_row
        ld bc,(hlib_dma_row_end-hlib_dma_row)*256+0x6B
        otir
        pop de
        pop hl
        ld bc,64
        add hl,bc
        ex de,hl
        ld bc,80
        add hl,bc
        ex de,hl
        pop af
        dec a
        jr nz,.row
        ret
.blitter:
        ld (hlib_dma_rect_src),hl
        ld (hlib_dma_rect_dst),de
        ld hl,hlib_dma_rect_prog
        ld bc,(hlib_dma_rect_end-hlib_dma_rect_prog)*256+0x6B
        otir
        ret
hlib_dma_row:
        db 0x83,0xC3,0x7D
hlib_dma_row_src: dw 0
hlib_dma_row_len: dw 64
        db 0x14,0x10,0xAD
hlib_dma_row_dst: dw 0
        db 0x82,0xCF,0x87
hlib_dma_row_end:
hlib_dma_rect_prog:
        db 0x83,0xC3,0x7D
hlib_dma_rect_src: dw 0
        dw 0                    ; ignored in 2D
        db 0x14,0x10,0xAD
hlib_dma_rect_dst: dw 0
        db 0x82,0xDF,2          ; virtual memory + 2D, all other flags off
        db 0xE3
hlib_dma_rect_width: dw 64
        db 0xE7
hlib_dma_rect_rows: dw 20
        db 0xEB
hlib_dma_rect_astride: dw 64
        db 0xEF
hlib_dma_rect_bstride: dw 80
        db 0xCF,0x87
hlib_dma_rect_end:
