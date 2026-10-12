# Making a recording (Fuse)

Before recording: Options -> RZX -> turn OFF "autosave". Load the SAME .z80 you
will give the agent (title screen or in game, keyboard controls) and use "Record from snapshot".

Record one session of 3-5 minutes. Cover what the game has - every figure the build will
turn into a sprite, in every situation it can be in:
1. Start the game from the title screen with the keyboard.
2. Move through as much of the game as you can: several rooms / screens / scrolling sections.
3. Every enemy or figure type you can reach, including ones entering from the screen edges.
4. Figures walking in front of AND behind scenery (trees, walls, buildings) if the game has depth.
5. Lose a life and continue; if you can, game over and a new game.
6. Anything that covers or interacts with figures: boxes, dialogue, inventory, explosions,
   bullets, pickups, lifts, water, conveyor belts.
7. Return to a place you already visited.
8. Later levels matter: a trainer / infinite-lives option makes them reachable (say which you used).

Name files consistently: `<game>.z80` and `<game>.rzx`. Fuse may still autosave: `nexclash.py`
strips autosave snapshots itself (`nexclash.py rzx info` shows how many there were).
