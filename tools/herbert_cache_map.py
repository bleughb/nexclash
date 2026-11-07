#!/usr/bin/env python3
"""Assign separate cache entries to source chunks seen in the same Herbert room.

Usage: python -B tools/herbert_cache_map.py PROFILE CENSUS [CENSUS ...]
Only address/room metadata enters PROFILE; no game images are copied.
"""
from pathlib import Path
import collections,json,sys

def assign(censuses):
 groups=collections.defaultdict(set)
 for source in censuses:
  for e in json.loads(Path(source).read_text())['shapes'].values():
   if e['site']==0x8d02:continue
   for room in e['rooms']:
    for half in range(e['height']//16):groups[int(room)].add(e['gfx']+64*half)
 graph=collections.defaultdict(set)
 for gs in groups.values():
  for g in gs:graph[g].update(gs-{g})
 keys={}
 while len(keys)<len(graph):
  g=max((g for g in graph if g not in keys),key=lambda g:(len({keys[k] for k in graph[g] if k in keys}),len(graph[g]),-g))
  used={keys[k] for k in graph[g] if k in keys};keys[g]=next(i for i in range(64) if i not in used)
 assert all(len({keys[g] for g in gs})==len(gs) for gs in groups.values())
 return {str(k):v for k,v in sorted(keys.items())}

if __name__=='__main__':
 if len(sys.argv)<3:raise SystemExit(__doc__)
 p=Path(sys.argv[1]);r=json.loads(p.read_text());r['cache_indices']=assign(sys.argv[2:]);p.write_text(json.dumps(r,indent=2)+'\n')
 print(len(r['cache_indices']),'chunks;',max(r['cache_indices'].values())+1,'cache entries')
