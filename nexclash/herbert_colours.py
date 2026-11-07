"""Optional toy-shop palette. Paint only original ink; keep every mask/detail pixel.

Source bytes are read from the owner's exact snapshot, never stored here. Parts
follow the original drawing, with pose-specific nappy edges and mirrored paints.
The runtime accepts an image only after comparing every byte and its mask type.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# RGB332: index 1 remains the game's per-figure ink; 0 transparent, 8 black.
PALETTE = {2:(7,4,2), 3:(7,7,3), 4:(4,2,0), 5:(1,6,0),
           6:(7,0,0), 7:(0,3,3), 9:(7,7,0), 10:(7,6,2),
           11:(7,3,0), 12:(1,6,3), 13:(5,1,3), 14:(3,3,2), 15:(6,3,1)}

def rgb(index, ink=14):
    if index in (0,8): return (0,0,0)
    if index == 1:
        v=255 if ink&8 else 182
        return (v if ink&2 else 0,v if ink&4 else 0,v if ink&1 else 0)
    r,g,b=PALETTE[index]
    return (round(r*255/7),round(g*255/7),round(b*255/3))

def monochrome(raw, masked, height):
    pix=[];step=4 if masked else 2
    for y in range(height):
        for x in range(16):
            bit=128>>(x&7);off=y*step+x//8
            pix.append(1 if raw[off+(2 if masked else 0)]&bit else
                       8 if masked and not raw[off]&bit else 0)
    if not masked:
        todo=[i for i,v in enumerate(pix) if not v and (i<16 or i>=height*16-16 or i%16 in (0,15))]
        seen=set(todo)
        for i in todo:
            for j in (i-16 if i>=16 else -1,i+16 if i<(height-1)*16 else -1,
                      i-1 if i%16 else -1,i+1 if i%16<15 else -1):
                if j>=0 and not pix[j] and j not in seen:seen.add(j);todo.append(j)
        pix=[v if v else 0 if i in seen else 8 for i,v in enumerate(pix)]
    return pix

def part(g,x,y):
    # Herbert: exposed skin throughout, with a cloth region around his hips.
    # The arm's black diagonal and narrowing waist define the nappy's top edge.
    if 0xf4b0<=g<=0xf930:
        if g in (0xf4b0,0xf6b0):
            edges={19:(12,13),20:(11,13),21:(11,12),22:(4,12),23:(6,11)}
        elif g in (0xf8b0,0xf930):
            edges={19:(14,15),20:(12,15),21:(10,15),22:(9,15),23:(6,14),24:(7,10)}
        else:
            bob=1 if g in (0xf5b0,0xf7b0) else 0
            edges={a+bob:b for a,b in {19:(12,13),20:(10,13),21:(7,13),22:(4,12),23:(5,11)}.items()}
        return 3 if y in edges and edges[y][0]<=x<=edges[y][1] else 2
    # Marching toy soldiers: blue cap/trousers, red coat, white belt,
    # pink face, white gloves, wooden musket with a silver bayonet.
    if g in (0xefb0,0xf030,0xf0b0,0xf130):
        yy=y-(1 if g in (0xf030,0xf130) else 0)
        if yy<=4:return 9 if (x,y)==(6,2) else 7
        if x>=13 and yy<=12:return 14
        if x>=13 and yy>=17:return 4
        if yy<=9:return 2
        if yy>=30:return 14
        if yy>=23:return 7
        if yy==21 and x<=11:return 3
        if x<=3 or (x>=12 and 12<=yy<=16):return 3
        return 6
    # Two bonneted dolls: pink faces, purple dresses, white bonnet and cuffs.
    if g in (0xf9b0,0xfa30):
        if y<=5:return 3
        if y<=9:return 2
        if y==10:return 3
        if y>=30:return 6
        if y>=25:return 3
        if 11<=y<=14 and x in (1,2,14,15):return 3
        if y==17:return 3
        return 13
    # Cupcake: cherry, white icing/drips, golden-brown case.
    if g==0xf2b0:return 6 if y<=6 else 3 if y<=11 else 4
    if g==0xb2ba:return 10 if x<=5 else 3  # cream shell edge follows its curve
    if g in (0xf1b0,0xf1f0):return 6 if x>=12 else 12  # toy planes
    if g in (0xb23a,0xb25a,0xb27a,0xb29a):return 11  # birds
    if 0xb68f<=g<=0xb74f:return 5  # snakes
    if g in (0xbb6a,0xbbaa,0xbbea,0xbc2a):return 5  # tennis balls
    if 0xb8d2<=g<=0xba12:return 9  # sun and stars
    if g in (0xc424,0xc444,0xc484):return 9  # coin, keys
    if g in (0xa7c1,0xa7e1,0xa801,0xa821,0xa841,0xa861):return 12
    if g in (0xc1c4,0xc1e4):return 6 if y>=7 else 9  # toy robot
    if g==0xc204:return 12
    if 0xc224<=g<=0xc2a4:return 9
    if g==0xc2c4:return 11 if y<=7 else 12  # rattle
    if g==0xc2e4:return 3 if y<=4 else 7   # bottle
    if g==0xc304:return 6                 # the game's named RED WHALE
    if g==0xc324:return 4                 # teddy
    if g==0xc344:return 11                # toy face
    if g in (0xc364,0xa720):return 2       # hand
    if g==0xc384:return 9 if y<7 else 6   # radio
    if g==0xc3a4:return 6                 # alphabet block
    if g==0xc3c4:return 9                 # ball
    if g==0xc3e4:return 11                # brick
    if g==0xc404:return 14                # camera
    if g in (0xc4a4,0xc544):return 9      # toy gun
    if g==0xc4e4:return 3 if y<10 else 4  # tennis racket
    if g==0xc504:return 4                # cricket stump
    if g==0xc524:return 6                # flag
    if g==0xc564:return 6 if y<5 else 7   # toy soldier collectible
    if g==0xc584:return 10               # ice-cream cone
    if g==0xc5c4:return 7                # book
    if g==0xc5e4:return 6                # bow tie
    if g==0xc604:return 5                # plant
    if g==0xc624:return 11               # hoop
    if g==0xc664:return 10               # light bulb
    if g==0xc684:return 9                # rubber duck
    if g==0xf270:return 6 if x<5 else 14  # torch
    if g==0xf290:return 5                # crocodile
    if g==0xf310:return 13               # wrapped sweet
    if 0xb7d2<=g<=0xb892:return 7         # spinning toy
    return 1

PARTS=json.loads((ROOT/'docs/profiles/herbert_parts.json').read_text())

def painting(g,raw,masked,height):
    base=monochrome(raw,masked,height)
    mask=PARTS.get(f'{g:04x}')
    if mask:                            # one colour digit per ink pixel of the player's image, in pixel order
        ink=iter(mask['ink']);out=[int(next(ink),16) if v==1 else v for v in base]
        assert next(ink,None) is None,'herbert_parts: %04x has more colours than ink pixels'%g
        return out
    return [part(g,i%16,i//16) if v==1 else v for i,v in enumerate(base)]

def mirror(raw):
    return bytes(int(f'{raw[i^1]:08b}'[::-1],2) for i in range(len(raw)))

def figures(mem):
    spec=json.loads((ROOT/'docs/profiles/herbert_colours.json').read_text())['graphics']
    for gs,e in sorted(spec.items()):
        g=int(gs,16);h=e['height'];masked=e['masked'];raw=bytes(mem[g:g+h*(4 if masked else 2)])
        pix=painting(g,raw,masked,h)
        yield g,masked,h,raw,pix,False
        rev=mirror(raw)
        if rev!=raw:
            yield g,masked,h,rev,[pix[y*16+15-x] for y in range(h) for x in range(16)],True

def tables(mem):
    chunks={}
    for g,masked,h,raw,pix,mirrored in figures(mem):
        for half in range(h//16):
            key=g+half*64;start=half*64 if masked else 0
            dat=raw[start:start+(64 if masked else 32)];p=pix[half*256:(half+1)*256]
            chunks.setdefault(key,{})[(masked,dat)]=bytes((p[i]<<4)|p[i+1] for i in range(0,256,2))
    records=[];lookup=bytearray(65536)
    for g,variants in sorted(chunks.items()):
        first=len(records)
        for (masked,raw),pat in variants.items():
            record=bytearray(256);record[:len(raw)]=raw;record[64:192]=pat;record[194]=len(raw)
            records.append(record)
        for idx in range(first,len(records)-1):records[idx][192:194]=bytes((56+(idx+1)//32,0x40+(idx+1)%32))
        lookup[(g-0x8000)*2:(g-0x8000)*2+2]=bytes((56+first//32,0x40+first%32))
    blob=b''.join(records);blob+=bytes((-len(blob))%16384)
    assert 56+len(blob)//8192<=94, 'paint tables must not overlap the hidden ROM'
    banks={24+i:bytes(lookup[i*16384:(i+1)*16384]) for i in range(4)}
    banks.update({28+i:blob[i*16384:(i+1)*16384] for i in range(len(blob)//16384)})
    return banks,dict(addresses=len(chunks),variants=len(records),table_bytes=len(lookup)+len(blob))
