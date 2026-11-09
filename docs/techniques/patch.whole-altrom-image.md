# Write the whole alt ROM image, never only the hook bytes

```json
{
  "schema": 4,
  "id": "patch.whole-altrom-image",
  "revision": 2,
  "kind": "patch",
  "title": "Write the whole alt ROM image, never only the hook bytes",
  "question": "Does any ROM byte the game can reach come from the Next's own ROM instead of the build?",
  "tags": ["alt-rom", "rom", "boot", "stub", "nextzxos"],
  "lifecycle": "candidate",
  "superseded_by": null,
  "requires": [],
  "rejects": [],
  "conflicts": [],
  "phases": ["setup"],
  "order": {"setup": {"after": []}, "cross": ["the fill runs in the stub, before the tail enables the alt ROM ($8C = $80)"]},
  "owns": {"memory": [{"space": "alt_rom", "image": 1, "offset": ["0x0000", "0x3FFF"]}], "next_pages": [94, 95]},
  "examples": ["cauldron", "inferno"],
  "sources": ["docs/REFACTOR.md"]
}
```

## Use / do not use
Every build that hooks through the alt ROM. The Next fills alt ROM image 1 from the SYSTEM ROM3,
which is NextZXOS's (ROM3 of enNextZX.rom; enNextLG.rom's is byte-identical), not Sinclair's: it
differs in 6,423 bytes and holds 1,121 bytes of code at 0x386E-0x3CFE, the hook area of most
engines. Its IM 1 handler (0x004A CALL 0x386E), UDG / token print (0x0B52 JP 0x387E), reset and
calculator entries jump there. A build that writes only its hook bytes runs those paths into the
hooks: Starquake crashed on its first UDG print. So z80tonex writes the whole image by default for
NEW builds: Sinclair's ROM (bank 47, from SkoolKit) over 0x0000-0x3FFF, then the build's bytes lo..hi
(`patch.altrom`), then `patch.altrom_low` if any. Nothing to do in an engine. Games verified before
2026-11-04 keep the old fill (record `"pin": {"altrom_fill": "rom3"}`, applied by `auto` to their
snapshot): opt-in rework = `--altrom-fill whole`, then the full verification and new MD5s.

**Assumptions.** The game runs on Sinclair's 48K ROM in the recordings (128K games: their ROM 1 is
128-1.rom, which also has code at 0x386E; the 48K ROM keeps every ROM path self-consistent next to
the hooks). Bank 47 is not in the build.

**Validation gap.** The old fill's faults were seen in JNext (runs/altrom_audit); the whole image is
proven by the simulated boot over NextZXOS's ROM3 and the per-game verifiers, not on hardware.

## Recognise
A partial fill: a pinned game, or `--altrom-fill rom3`. Symptoms: a crash
or garbage at the first ROM print of a character >= 0x90, interrupts running hook code once DivMMC
no longer traps 0x0038 (other loaders, CSpect), a reset to the NextZXOS browser. The game's own reads count
too: Inferno's intro runs IM 2 with I = 3B, so 0x3BFF-0x3C00 is its vector and must stay FF FF; hook bytes
there stalled the tape-start build (found with JNext headless; per-level builds never reached it).

## Probe and stop
1. `nextboot.boot(nex, pc, sysrom=ROM3)`: alt image 1 minus Sinclair's ROM must be the hook bytes only.
2. `auto` with recordings and `NEXCLASH_NEXT_ROM=enNextZX.rom`: no MISMATCH in the `ROM paths` lines
   (nextboot.rom_paths); a new engine's verifier takes the image from nextboot.alt_image.

## Contract
- Alt image 1 = Sinclair's ROM + the build's bytes; independent of the card's NextZXOS version.
- Display: software = return/boundary only; hardware = checklist item "title and menus print as in the original"

## Resources owned
Bank 47 while the stub runs; the alt ROM image.

## Failure lookup
| Symptom | Cause | Probe | Fix | Rejected |
|---|---|---|---|---|
| crash at a UDG print | 0x0B52 into hooks | boot with ROM3 | whole image | moving hooks |
| bank 47 refused | build uses it | z80tonex error | move the build's bank | dropping the fill |
| stall before the intro | hooks on an IM 2 vector (I = 3B) | JNext PC trace | skip 3BFF-3C00 | - |

## Verification
Negative control: `--altrom-fill rom3` rebuilds the old image; booted over ROM3 it differs from
Sinclair's in thousands of bytes, the new one in the hook bytes only.

## Evidence
- runs/altrom_audit/AUDIT.md (Jon's local evidence, 2026-11-04; observed in JNext).
- games/cauldron.md (the first whole image, 2026-10-27). Chuckie Egg rebuilt `--altrom-fill whole`:
  bfad6be1 -> df3e97f0, image = Sinclair's ROM + the 333 hook bytes over NextZXOS's ROM3 (6,437 before).
