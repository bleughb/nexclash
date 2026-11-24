# Elite: the Russian 128K hack vs the standard release (notes, 2026-11-23)

Decision (owner, 2026-11-23): the engine is rebuilt for the STANDARD Firebird "[a]" release (original look and start: title,
"Load New Commander"); the hack's changes are kept in these notes and become an OPTION in the NXC (a toggle that applies them
to the standard game). The current `elite` engine (games/elite.md, record `elite`) targets the hack's RZX snapshots.
Sources: standard = Elite (1986)(Firebird)[Joystick].tap (and the identical-layout "[a]" 49,068-byte tape); hack = DockingElite.rzx
snapshot. Method and spans: C:NEXT\elite_work\HACK_VS_STANDARD.md, tapes\hackspans.pkl. The hack's own tape / disk was not found.
Plan for the option: each gameplay change (section 2 of the table: NPC combat engine, 23 blueprints, upgrade, missions, shop text)
is one byte-different build variant = one NXC toggle (kind 4, changes game logic); display-only items are not needed (the engine
draws its own display). Needs the standard engine first.

# Russian 128K hack of Elite vs Firebird standard: function by function (2026-11-23)

Method: static disassembly of the hack (Docking.z80, bank 0 at C000) against the standard code
(y_t8.tap.z80); spans from hackspans.pkl; callee tracing, cross-references, std/hack instruction diffs.
Read only; nothing under nexclash-elite was touched.
Confidence tags: [H] verified in code, [M] consistent reading of code, [L] guess from partial evidence.

## 0. Findings that change the picture

* **The hack never pages RAM.** There is no `OUT (FD)` / 7FFD write anywhere in 5D00-FFFF (std or hack). Snapshot 7FFD=0x30 is
  "48K lock" with ROM1. The "128K" is only the host machine: the 16K at C000 is simply the existing back buffer. [H]
* **Disk instead of tape.** D907-DA77 is a TR-DOS wrapper (`JP 3D2F`, TR-DOS entry in the 48K ROM, 5CD6 sysvar trick); the tape
  loader/saver at D3xx and the tape texts were removed. D8B4-D8C8 is a small JP thunk table. [H]
* **The hack uses the ZX ROM font** (`CALL 5DFB` at D4F2 picks 3D00 for digits/letters, Elite glyphs only for punctuation); the
  freed Elite font area 5D70-5FFF now holds hack code. [H]
* **Kempston joystick support removed** (title screen IN A,(C) at 73D6 replaced by JR; FC23 skips the 0x1F port read in the ISR key scan). [H]
* **The back buffer (C000, 7FBE copy) is standard.** The ~140 spans at C001-CFFF are buffer *contents* (screen image), not code. [H]
* The hack is a *rewrite*, not a patch: star field, line clipper, polygon fills, HUD, ship table, text, and the blueprint set were replaced, and the freed space was reused for a new NPC combat engine and a mission/upgrade system.

Inferred variables used below (std/hack): D05F legal status (FIST) [M]; D062/D063 kill tally word (hack DE25 increments D062, carry into D063; tests >=0x20, >=0x84) [M];
D065 galaxy number (&7) [H]; D097/D099 current system x/y on the chart [M]; D08F mission stage [M]; D08E upgrade flag (0xFD when bought) [M]; D067 charges/count of that upgrade [M];
D0AF current view/screen state (4 = special) [M]; 7103 "docked / not in flight" flag [L]; 70E4/70E5 roll/pitch, 70E6 speed [H]; 6048 + n*0x27 = ship slots, (IX+23,24) = blueprint pointer;
B457 + n*10 = NEW per-slot NPC record table, B452 = pointer to the current record [H].

## 1. Table

Cat: G gameplay, D display/presentation, P plumbing (hardware/ISR/stack/disk), B data only, S run-time state / false positive.

| address range | what it reaches / does | cat | effect |
|---|---|---|---|
| 5D70-5D77 (called from DC5F) | `LD HL,D08D; if nonzero INC (HL)`. Std zeroed D08D at galactic jump | G (L) | D08D becomes a counter bumped per galactic jump instead of cleared; no visible effect found |
| 5DC8 (call at 74B3) | `if 7103==0 JP 7861` | G (M) | Main loop re-ordered: the planet-crash check (7861) only runs in flight; 7EDE (key J/hyperspace launch) and 7853 now also run when 7103!=0 (std skipped them) |
| 5DFB-5E19 (call at D4F2) | font chooser: ROM font 3D00 for space/digits/letters, 5D70 Elite font for the rest | D | Text uses Spectrum ROM font; Elite font mostly unused |
| 5E1A-5E35 (call at E278) | token 0xDC special: calls D5B4, self-patches 7013 and DE6A to RET (C9) | G (L) | Toggle used by the shop/menu code; effect not determined |
| 5E36-5E54 (calls at 8B25, 8C24, 8D26) | fill N bytes backwards with byte at 8FB6 via LDDR | D | Replaces the std unrolled `PUSH AF` fast fills (8A37-8D30, F5 F5 ...) used for sun/planet disc fill: slower, smaller code |
| 5E55-5E67 (JP at 945A, hack ending of docking/arrival) | E07A flag: if set, E07B/E07C word ++ then JP 813E | G (L) | Statistics counter (arrivals/jumps); E07A cleared in D8DD. No gameplay effect seen |
| 5E78-5EC4 (call at D1D4) | event step: if D08F<2 and D062>=0x20 and flag in D0C9 area -> sets D062=D08F=0x81, clears bit in D0B0, else sets bit 7 of D0C9 area | G (M) | Mission trigger tied to kill count (>=32) and stage |
| 5EC5-5F10 (calls at B950, ptr at E153) | spawn helper: B898, then if D08F>=2, D0B0 bit5, D062>=0x84 turns the ship into blueprint 633C (type 16), or blueprint 636A (type 18) on key D / D07B condition | G (M) | Scripted mission ship (the hunter) appears at kill rating >=132 after the mission stage is reached |
| 5F11-5FA0 (call at 7874, replaces `CALL 9C83` in planet check 7861) | planet/body proximity handler: distance via 8D2B, 83FE; spawns police/guard blueprint copy into slot 1 (LDIR to 606F); legal status test (D05F>=0x7F -> hostile wave B=8) | G (M) | Approaching the planet/station with D05F (legal) >=0x7F launches police; mission ships near the target system; extra checks around D065 |
| 5FA1-5FD4 (call at 9452 after launch/arrival) | D6F9 mission/offer logic, 7278, then if D067!=0 and slot1 flags==0x0C and D08E==0: prompt (token 5C) Y/N; on Y: D08E=0xFD, D067-- | G (M) | **Upgrade offer**: after arrival you may buy a one-shot upgrade (see 7F81, 79F9). Costs a charge |
| 5FD5-6043 (JP from A1CB and 7F61) | when the second body (IX=7110) overflows coordinates (flying past the edge, or J jump overshoot) -> change D097/D099 by 1, DF74, DCE9 new system, 7F64 re-init | G (M) | **Fly out to a neighbouring system** instead of clamping the coordinate; hyperspace by sublight travel (probable) |
| 6000-6160 | ship slot table 6048.. + variables | S | run-time state (false positive) |
| 6174-6183 | 4 bytes before table, 2C 02 C0 00 .. | B | header bytes of new blueprint set |
| 6180-61E2 | ship type table (23 entries x 4 bytes: AI flags, ptr, class) | B/G | std has 19 types with byte0 constant C3. Hack: byte0 is meaningful per-type NPC flags (80,84,B0,93,D0,F0..) read by 7A9E; 4 new types |
| 61E3-63DD | 23-byte blueprint headers (types 1..22) + type 0 at 63C6 | B | std types 0-16,18 kept, std type 17 moved to idx 22; **new idx 17,19,20,21** (energy 0x55,0xF0,0x90,0x8C). Per-type tweaks: byte +0x15 (damage/ram) added: missile C0->50, asteroid 19->2F, others 0->80/90/2F; +0x14 5/8 on types 10,11,13,18; +0x0A on 7,10,11,15; +0x0B on 16; |
| 63DE-701B | model vertex/edge/face data (re-encoded, pointers inside headers differ) plus code tails 6ED4 (equipment price/affordability), 6FF8-700F (buy confirmation 'Y' handler) | B/G | Ship models re-packed (compact format). The readers were patched: AA91, AAAB, AACA, AC0D, AC2B, AC4E (face byte from AA0F cache), AA31, AE0E, AE26 (pointer 6FEB), BCE3, BD01, BD51 |
| 6ED4-6EE7, 6FFB-7014 | equipment shop confirm: on 'Y' (0x59) sets D084=FF, D087=0, tests D08E | G (M) | Shop gets a **"DO YOU WANT TO BUY x ? (Y/N)"** confirmation (text at F326 and F8xx) |
| 7095-7096 | `INC (HL)` instead of clearing D08A | G (L) | D08A becomes a counter (key-held state); effect unclear |
| 73D6-73E1 | title screen: `JR 73E2` over `IN A,(C); BIT 5` | G/P | Kempston joystick selection on title removed |
| 7435-7438, 7461-7468, D171-D174, EB6E-EB71 | attribute clears start at 5820 not 5800 and are 0xF0/0x02E0 bytes | D | top row of attributes left alone |
| 74AF-74BA, 74FD-7508 | main loop reorder: 5DC8; render via ED60 (8F0D, 7FBE, 96D9) then 84D9, EI | D/P | Same draw order; EI after draw |
| 7555-7556, 7578-7582, 7594, 75B9, 785F, 856D, 8597, 85B9, 861A-8629, 8F15, 8F77, 92FA, 9318, 93D1, 9524, 95AE, 962B, 96BF, 96DA, 99A3, 9C93, 9CB4, 9F80, A2BA, A2D7, A408, A98E-A997, B96C, B9BA, BB7D, BCC8, 8BD3/8CD3/8DC9 | address operands / constants / padding changed (e.g. 8F14->8A4A, 8A7D->8A4A) | B | pointer fix-ups to the relocated fill code and tables; no behaviour of their own |
| 789E (CALL F9A8) | F9A8 = `LD (7EDD),A` + F9AB: clears B456..B4A6 (NPC record table), sets B456 bit2 if D05F>=0x38; B=5, HL=FF08 | G (H) | On launch/system arrival the NPC interaction table is reset; "criminal" flag (legal >=0x38) recorded |
| 94F6 (CALL F9AB) | same reset at std 94F4 path | G (H) | same |
| 78B1-79F8 | star dust (32 stars in 7A39 table, LD A,R randomisation), 79F9 below | D | New compact star field replacing the std 7898..7EDD tables |
| 79F9-7A26 (call at DC68) | read digit rows F7 and EF via 8B2A and pick galaxy 1-8; delta applied to seeds via DC83 x3 | G (H) | **Galactic hyperdrive destination can be chosen with number keys** when D08E>=5 (else next galaxy as std). DC5F-DC7B also resets legal D05F=0 |
| 7A27-7A38 (call F0F7) | returns 0x0C or 0xBC from D08F/D062>=0x84 | G (L) | status page colour/rank text selector |
| 7A39-7A58 | star position table | S | state |
| 7A59-7A83 | star clip helper | D | |
| 7A84-7A94, 7A95-7A9D | self-mod toggles (972F, B3B3), sets 96C4 | D (L) | |
| 7A9E-7B13 (calls B738, F928) | **NPC record init**: finds ship's blueprint in table 6180, writes flags into B457 record, random team/target bits, bit tests with D0B0 | G (H) | each ship gets an AI team/flag byte |
| 7B14-7B49 | per-ship record (B452) fill: projected points + AE50, B4BA | G/D (M) | |
| 7B4A-7BBD, 7BBE-7C12 | NPC-vs-NPC proximity test and collision/hit: compares positions (|dx|,|dy|,|dz| < 0x24), damages (IY+22) by difference of energies, SET 4 on loser (explode) | G (H) | **NPCs ram/shoot each other and die**; no bounty for the player |
| 7C13-7C5F | target acquisition: loops other slots with team mask (7B6A), type 6A special-case (Cobra Mk III escort) | G (M) | |
| 7C60-7D37 (called F8E4 loop end) | **per-frame NPC combat loop**: timer (IY+7) countdown, picks target, draws laser line between ships with B044, damages | G (H) | Visible laser lines between ships; ships fight pirates vs police vs traders |
| 7D38-7D4C (A4BB) | only blueprint lo E3 (type 1, missile) explodes on contact | G (M) | |
| 7D4D-7DC4, 7DC5-7E01 (B70A, A407) | AI message/target-slot selection (B867 wrapper, IY from B452) | G (M) | |
| 7E02-7EA8 (A7D6) | NPC laser fire at target ship (F945/F92D store line endpoints), joins std 7A9E tail | G (M) | |
| 7EA9-7EDD | bomb/mass-lock helper and slot walk (7EC8) | G (L) | |
| 7EEB-7F0E (std 7EDE key-J jump) | in-system jump precondition: now `7103==0`, HL=(81A4)==0 and (711D)==0xFF; self-mod 7F0B | G (M) | **J (in-system jump) allowed under different conditions** (std: blocked if 81A4/81A5==1 or 711D==0) |
| 7F64-7F80 (calls 6028, B96B) | FCEA special-system test (D097=5D,D099=3, D062 bit6) then clear slots, D0AF=4 | G (M) | Scripted arrival at one special system forces a reset (mission location) |
| 7F81-7F9F (call at A173) | `if D08E: if key J (row BF bit3): 70E4,70E5,70E6 = 2x|x| style bit mix` | G (H) | **J = turbo**: roll/pitch/speed values boosted while held (needs the D08E upgrade) |
| 7FA1-7FBD | scoop/dock check with D08F>=2, D062 vs 0x84, EC40 | G (L) | called from E8B7 (std `LD A,(HL); BIT 5,A`): another mission gate |
| 7FF0-8044 (call EF01) | ship-type rewrite for types 7..0x11 except 9,0F: 8E64, D67A, EC40, 711C, B799 -> type 6 or 0F | G (M) | Random encounters at some systems/mission states become boulders/Thargoids |
| 8080-80D2 | back-buffer init by LDDR (std: stack-push blast from C000) | D | same buffer content, smaller code |
| 807D (JP 8459), 8459-8490, 83xx-84B5 | scanner/compass sprite blit changed (84B5 draws 0x18 rows via LDI; 98A2 patches self-mod) | D | |
| 8142-8144, 8153, 8154 | stack set removed, CALL D006 | P | |
| 81A5-81F4, 8208-821D, 8B3F | docking-tolerance test: `7103 | (IX+2)|(IX+5)|(IX+8)` &7F==0 (std: each <2) | G (M) | **Stricter docking alignment** (std allowed |z|,|y|<2; hack needs 0) |
| 827A-827D (CALL FD02) | FD02 toggles slot base (7103: 6048 vs 8ABA) | G/P (L) | |
| 8336 | JR NC | B (L) | |
| 8396-83FF, 8442 | 4x4 sprite blit (explosion/planet marker) rewritten | D | |
| 8429 (call B569) | large-ship proximity: (IX+1A)*2>=4, (IX+0)&C0 | (IX+3) &F0 != 0 | G (M) | feeds ram damage at B595: damage = 0x0C + 2*speed (70E6) |
| 8A37-8D30 | std unrolled PUSH fill blocks replaced with: 8A37 circle ptr setup, 8AA3 Thargoid-child routine (type 0x25: D086 +=2, spawns type 4 each 128), 8C29, 8D2B distance D097-D099 &F8, 8D38 status line | D/G | planet/sun fill uses LDDR (5E36); 8AA3 gives Thargon respawn |
| 8D3E-8D4C | status screen 'D08E' text (token F9) | D/G | shows the upgrade on the status page |
| 8F54-8F5D, 8F8E-8FA5 | sun/planet disc: step +3 and C-=4 (4x fewer rings), fill masks 4F->CF, 3F->BF, calls F8D7 (8F74,86D0,7FBE) | D | faster, coarser disc |
| 9453-9459 | JP 5E55, CALL 5FA1 (see above) | G | |
| 946F (CALL E6EE) | `LD (D041),A; LD A,(D06A); LD (7105),A` | G (L) | restores a saved value (D06A) into 7105 at arrival |
| 9AE0-9B1A, 9B41-9BA9, 9C14-9C18 | HUD cockpit status (bars/indicators): D083 energy banks replaced with direct attribute writes (5AD5), 9B41 timer with D08F->D0C7 | D/G (L) | HUD changed; D08F moves by 1 per tick (mission timer) |
| 9C45-9C58 | new-game reset: B=0x0D instead of 0x11 entries cleared, D089 untouched, uses 848A | G (L) | default commander differs |
| 9D94-9D97 (CALL F9C9) | `SET 2,(IX+21)` (hostile) made conditional: only if D0AF==4, or B456 bit2 (legal>=0x38), or (IX+26) bit3 clear | G (H) | Ships turn hostile to the player only when you are a criminal / special state |
| 9E44 (JP F8B4) | ship draw wrapper: DI, FEFE=C9 (disables ISR), SP=4020 (screen), CALL A6DF, SP=411A, FEFE=18, EI | P/D | Ship drawing with stack in the screen; ISR muted during draw |
| 9E5D-9E69 (CALL A8EC, JP F8E4) | loop epilog: advances B452 by 10, E=0x27; F8E4 saves 0x30 screen bytes FFD0, runs 9E66, restores | P | |
| A173 (CALL 7F81) | turbo hook, A1CB (JP 5FD5) | G | see above |
| A3BC-A3D2 (CALL F95A) | std: tests (617B) and random; hack: search slots 6159.. for a live ship with id (9CB4), then `type E3` -> value 8 | G (M) | AI "missile target" choice differs |
| A42F (CALL B4C4) | `(B452)+8 &0F ==1` and bit1 of (IX+21) | G (M) | AI: tests whether the NPC has a target in the table |
| A4C4 | `LD A,C; AND 0F` instead of (IX+25) | G (M) | |
| A505 (CALL F97E) | station-hit branch: only `A537` path if (IX+26) bit0, else team flags (B452) mask D0 -> hit logic with (IY+26)==0C | G (M) | |
| A513-A52F (CALL D6AA, D0AE) | attack on station/police: type lo 3C special; sets D05F=FF (fugitive) | G (H) | **Hitting a specific ship type (blueprint 633C) makes you a fugitive** (D05F=0xFF) |
| A65D (CALL FA84), A79C | `SET 3,(IX+20)` (fire laser at player) made conditional: NPC with another target does not fire at you; A79C replaces POP/PUSH with self-mod `LD A,imm` (8) | G (H) | **NPCs engaged with other ships do not shoot you** unless D05F>=0x38 |
| A7D6, A875 (CALL 61DD), A884 (CALL 7B37), A8DE-A8E9 | AI hooks to 7E02, B44.., F945/F92D | G (M) | |
| A897-A8A6 | std set bit7 of B348 around B044 line draw; hack removes and relocates | D | |
| B044-B451 | rewritten line clipper + line drawer (std used table AFF0) | D | faster lines, slightly different clipping |
| B452-B4D7 | NPC record table contents | S | run-time state |
| B532 (CALL B73D) | on ship kill sets FABA bit7 (9389) then B5DF | G (M) | player kill flag |
| B569-B5A9, B5CA-B5DB, B5F9-B5FF | collision/missile damage: `damage = (IY+0x15) | B` (std: accumulate A+B), 8429 ram, parent kill: only ships with odd blueprint low bit die (8C29), 8AA3 Thargoid child | G (H) | **Missile/ram damage now per-ship (+0x15)**; std missile 0xC0 -> 0x50 (weaker) |
| B686-B68C (CALL 9389) | kill counter ++ and FABA flag | G (M) | |
| B6CA-B6CD (CALL F9E1) | F9C9 hostile test + 7D64 | G (M) | |
| B70A-B746 | AI selection moved to 7DC5; B71C spawn with 7EC8/B898/7A9E; B743 | G (M) | |
| B867, B898-B8CC (calls DA51, EF01, D60B) | spawn: EF01 type swap; D60B ammo mask: `25% 0 missiles, else (D061|junk)&(IY+0A)&7` | G (H/M) | **New ship types in 31% of encounters; fewer missiles per ship** |
| B922-B92A (CALL FACA/B71C) | spawn variant | G (L) | |
| B951-B952, B96C-B96F | constants (CALL 5EC5; spawn count mask &03+3) | G | pirate pack size 3-6 instead of 1+... |
| BCE3, BD01, BD51 | ship face visibility reader patched for packed models | D | |
| C001-CFFF | back buffer contents | S | false positive |
| D000-D04F | vector table JP targets | B | same except D04D-> D907 |
| D04F-D06A, D07C-D08C, D09C-D0C8 | commander save data (JAMESON vs MILICEVIC) and new variable bytes D08E, D08F, D067, D06A | S/B | state, but the *existence* of D08E etc is part of the hack |
| D0F6-D142 | message box / token attributes (5A attribute, 581F/5917 direct attribute address) | D | |
| D172-D1C4 | scoop handler rewritten: BIT7 (IX+26), D086++, token F3/7D, table D06B+n, DEC (HL) | G (L) | cargo scoop messages and hold counting changed; hold capacity (D07C) decrement not found in this path |
| D1D4 (CALL 5E78) | mission step hook | G (M) | |
| D201-D212 | scoop/sell table index with (HL)+0x85 | G (L) | |
| D4DD-D4DF, D4F2 | NOP the tape check; font chooser | D/P | |
| D55C-D569, D5B4-D5E0 | D5CB copies 6 entries from 738E to 8ABA (docked slot table) | G/P (L) | |
| D5F5-D60A | market buy hook: for item 0 or 10, EC40 -> sets D0B0 bit1 | G (M) | special goods/mission flag when buying |
| D60B-D61C | missile mask (see B8CC) | G | |
| D61D-D672 | clear screen + attribute fill (4200..57FF, 07), 7FD5 | D | |
| D67A-D6A8 | "state test": D065==0?, D08F>=2 -> compare (D097,D099) to target via E6C6 | G (M) | gates many events (EC40, 7FF0, FD29) |
| D6AA-D6F8 | attack-on-station/police effect: type 3C -> D05F=FF; D0AF=0; D08F bit7 clear | G (H) | see A513 |
| D6F9-D754 | mission offer text printer (D08F stage, D062 bits, messages B4-B8, AD) | G (M) | mission briefings by kills |
| D755-D787 | status line "ranking" message (D062 &0x0E tokens) | G/D (M) | |
| D78A-D799 | misc | B | |
| D7AA-D7B8 (call A6DF) | at ship draw start: writes FF to (B452)+1 and +4 | D/G (M) | clears record points |
| D7B9-D7E1 | nearest-ship selection (FBE0 compare x3) | G (M) | target selector |
| D7E2-D830 | token jump table dispatch (D7E9, D800..) | G/B | extra menu tokens |
| D8B4-D8E4 | JP thunks into E2A9, E1E8, D61D, E2B1, D55C, E36B, E35A, E2B8; D8DD | P | |
| D907-DA77 | TR-DOS save/load of commander (D95E etc, JP 3D2F) | P/G | disk not tape |
| DAFE, DC5F-DC79 | galactic jump: 5D70, 79F9, D065&7, clear legal D05F | G (H) | |
| DCAA-DCBB | 7060/ 8C3C replaces `LD A,(7105)` | G/D (L) | |
| DCED-DCEF, DD21-DD5C | system generation: planet/sun positions from seeds recomputed with compact code (DD48-DD5C) | G/D (M) | planet/sun distance/size at arrival differ |
| DDEB-DDF6, DE25-DE38 | std wrote D099/D097; hack: CP 0F -> EB62; tally: D062/D063 word increment, bit7 handling | G (M) | kill tally |
| DE67-DE8D | helper (LD DE,(HL)); target-system mission steps (DE7C CALL 6FF8) | G (M) | |
| DECC-DECF, DEF6, DF88-DF89, DFEA-DFF0 | pricing/time constants | B | |
| E06C-E07F | E07A/E07B counters | S/G (L) | |
| E142-E14A, E1C3-E1E7, E279-E27A, E2D5-E2F7 | menu/prompt code (E1E8 etc.) | G/P (L) | |
| E30A-E30D, E394-E397, E3C9-E3CB, E401, E52B-E52D | patched operands for hack tokens | B | |
| E6B5-E6F7 | save/load commander prompt (D081, FD23 price gate, E6EE restore) | G/P (M) | |
| E75F-E768, E814 | operands | B | |
| E8A4-E8CB | equipment screen tail: 7FA1 check, D087=0 | G (L) | |
| E93C-E959 | market row: 700F, D5F5, DE67 | G (M) | |
| E9E0-EA03, EA50-EA78, EA90-EA93 | equipment purchase: D084 test -> 6FFB; EC4B; DDEC | G (M) | confirmation (Y) flow |
| EB30-EB35, EB5E-EB72 | CALL 80B4; attribute 5820 | D | |
| EBB2, EBEE-EC01 | screen clear by LDDR | D | |
| EC36-EC5D | EC35 bit change SET 3,B; EC40 helper (D67A INC A), EC4B | G (M) | |
| ECDF-ECF3, ED0C-ED0D, ED1F-ED77 | planet disc call chain (FB03, FB7B, FB00 self-mod OR (HL)) | D | small disc routine |
| EDA7, EDC9-EDCA, EE88-EE9A | price display: EE8C CALL 6ED4 | G (M) | |
| EECE-EF20 | EEDB: if D065==0 ... sets D0AF=4 from EC40/D675; EF01 ship swap | G (H) | |
| EF99-EFA4, EFFE-F0A0, F0F8 | status page: equipment list incl. D08E token CF, ranks, D07D.. | G/D (M) | shows upgrade |
| F11C | operand | B | |
| F160-F20F (text) | species adjectives and tape texts removed | G/D | alien races always "HUManOID/alIen" |
| F210-F8B3 | message token table rewritten: removed tape prompts, "ALLOYS", species names; added "DO YOU WANT TO BUY .. ? (Y/N)", "SUPer", "COBra MK4 For SAle", ranks | D/G | |
| F8B4-F8E3 | ship draw wrapper | P | |
| F8E4-F90D | screen save/restore | P | |
| F90E-F915, F916-F92C | misc | G/D | |
| F92D-F944, F945-F959 | NPC line endpoint setters | G/D | |
| F95A-F97D | find live ship by id in slots 6159.. | G (M) | |
| F97E-F9A7 | station-hit branch | G | |
| F9A8-F9C8 | reset NPC table | G | |
| F9C9-F9E7 | hostile test | G | |
| F9E8-FA83 | NPC team/target matching (mask C0/F0 compare, B461 table walk) | G (M) | |
| FA84-FAC9 | decide whether NPC fires at player: IY=(B452); needs no other target, or legal flag; FABA | G (H) | |
| FACA-FB02 | spawn slot finder / pointers | G (L) | |
| FB00-FBDF | small disc routine | D | |
| FBE0-FC04 | nearest ship compare | G | |
| FC05-FC22, FC23-FC3B | key table tail, joystick removed (JR FC3D) | P | |
| FC33-FC38 | message print wrapper (E07A=0, JP D0D7) | G/P | |
| FCEA-FD01 | special system test | G (M) | |
| FD02-FD22 | slot base switch | G | |
| FD23-FD40 | purchase affordability (D081, EC40, D062>=0x84) | G (M) | |
| FD48-FD49, FD8D, FD94, FDF3, FDFB | key table entries FF FF; operands | P | |
| FEFE-FF2A, FF56, FF0D | ISR: stack to screen 4020 instead of FFBF; vectors | P | |
| FFC1-FFFF | small patches (pointers, bytes) | P/B | |

## 2. Net effect on gameplay

1. **The big one: NPC ships fight each other.** A new interaction engine (7A9E-7EDD, F92D-FAC9, table at 6180 flags, per-slot records at B457) gives every ship a team/target. They aim lasers and missiles at each other (laser lines drawn between ships), ram each other, and die without paying you a bounty. A ship that already has another target does not shoot you (FA84). Ships only turn hostile to you when you are a criminal (D05F>=0x38), or in special states (F9C9).
2. **More ship variety.** Four new blueprints (idx 17, 19, 20, 21; recording author says Mamba MkII and PuffAdder), older idx 17 moved to 22; 31% of spawns of types 13-17 are replaced by the new types (EF01); per-ship damage (+0x15) replaces the fixed missile/ram damage; ships carry fewer missiles (25% none, others masked).
3. **Progression / missions tied to kills.** Kill tally thresholds 0x20 and 0x84 trigger a mission chain (D08F, D062 bits, scripted ships 633C/636A, special system D097=5D, D099=3).
4. **One-shot upgrade offered after arrival (Y/N):** J becomes a turbo (roll/pitch/speed boost) and the galactic hyperdrive can be steered with digit keys 1-8.
5. **Travel changes:** flying out of the coordinate range changes system (5FD5); in-system jump (J) conditions changed.
6. **Docking tolerance stricter** (all of x,y,z hi bytes must be 0, std <2 for y,z). [M]
7. **Shop:** buy prompts confirm (Y/N); new market hooks; alien species/descriptions trimmed.
8. **Persistence:** TR-DOS disk save/load; no tape; no Kempston.
9. Display/sound/timing: ROM font; faster, simpler star field, line clipper, polygon fills; planet/sun drawn with fewer rings; direct attribute writes; ship drawing runs with ISR muted and stack in screen memory (timing: ship draw not interrupted). No sound change found (the ISR body only scans keys, FD69/FE01/7125).

## 3. Uncertain / not determined

* Exact identity of the new ships (idx 17,19-21 vs Mamba MkII / Puff Adder) not determined; stats only.
* Roles of D08A, D083, D086, D087, D08D, D0C7 counters are inferred; scoop path (D172-D1C4) hold accounting not verified; launch speed was not found changed.
* 7103 meaning (docked vs special) not proven.
* Behaviour of E1xx/E2xx/E3xx operand patches is by inspection only; not run in the emulator.
* Verify the turbo/galaxy-select upgrade by driving the hack (set D08E=0xFD and press J / digit keys).
