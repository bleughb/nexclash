"""Scenery paint by complete object, relative placement, and original glyph.

Repeated tiles inside one object may depict different materials. The lookup
therefore includes the placement within that object, never just the tile bytes.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def glyphs(mem):
 spec=json.loads((ROOT/'docs/profiles/herbert_scenery.json').read_text())['glyphs'];ids={}
 for i in range(128):
  a=0xdbb4+i*2;o=mem[a]+256*mem[a+1];ids.setdefault(o,[]).append(i)
 for key,e in sorted(spec.items()):
  os,gs,xs,ys=key.split(':');o=int(os,16);g=int(gs,16);x=int(xs)&255;y=int(ys)&255;raw=bytes(mem[g:g+8]);p=[]
  ink=iter(e['ink'])                   # one colour digit per ink pixel of the player's glyph, in bit order
  for i in range(64):p.append(int(next(ink),16) if raw[i//8]&(128>>(i%8)) else 0)
  for obj in ids.get(o,[]):yield obj,x,y,g,raw,bytes(p)
def tables(mem):
 lookup=bytearray(16384);records=[];chains={}
 def ptr(n):return bytes((66+n//128,n%128))
 for obj,x,y,g,raw,p in glyphs(mem):
  n=len(records);off=((obj*257+(x&31)+(y&31)*32)&8191)*2;r=bytearray(64)
  r[:5]=g.to_bytes(2,'little')+bytes([obj,x,y]);r[7:15]=raw
  r[15:47]=bytes(p[i]*16+p[i+1] for i in range(0,64,2))
  if off in chains:records[chains[off]][5:7]=ptr(n)
  else:lookup[off:off+2]=ptr(n)
  chains[off]=n;records.append(r)
 blob=b''.join(records);blob+=bytes((-len(blob))%16384)
 assert 66+len(blob)//8192<=86,(len(records),'scenery table overflow')
 banks={18:bytes(lookup),43:bytes(16384),44:bytes(16384),45:bytes(16384),46:bytes(16384)}
 banks.update({33+i:blob[i*16384:(i+1)*16384] for i in range(len(blob)//16384)})
 return banks
