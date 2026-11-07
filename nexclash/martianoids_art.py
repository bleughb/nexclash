"""Original Martianoids graphics, approved first-pass colours, and exact source encoding."""
from pathlib import Path
import hashlib,json
from . import coloursheet as cs,recolour as RC
COLOURS=Path(__file__).resolve().parents[1]/'docs/profiles/martianoids_colours.json'
PALETTE=[(0,0,0),(0,0,0),(182,219,255),(36,109,219),(36,73,109),(36,219,219),(36,146,146),(255,182,36),(255,255,36),(219,36,36),(255,109,36),(73,219,73),(146,73,219),(255,109,182),(255,255,255),(109,109,109)]
FIRST_SOURCE_PAGE=50
DIRECTORY=0x3100
GRAPHICS_SHA256="35a56c7a0b3697310edc026412b62a594b5c2689c88e1611ee141e71455ac507"

def initialized(mem):
    m=bytearray(mem)
    pointers=set()
    for i in range(120):
        p=m[0x60A3+i*2]|m[0x60A4+i*2]<<8
        pointers.add(p)
        if m[p]&64:continue
        m[p]|=64;w=m[p]&15;h=m[p+1]
        for n in range(w*h):m[p+3+2*n]^=m[p+2+2*n]
    # B453 reverses pairs and bits in place. Colour keys refer to the archive's
    # canonical orientation; only original graphic4D starts with bit7 set.
    rev=lambda n:int(f'{n:08b}'[::-1],2)
    for p in pointers:
        if bool(m[p]&128)==(p==0x6A71):continue
        w=m[p]&15;h=m[p+1]
        for row in range(h):
            a=p+2+row*w*2;pairs=[m[a+i:a+i+2] for i in range(0,w*2,2)]
            m[a:a+w*2]=bytes(v for pair in pairs[::-1] for v in map(rev,pair))
        m[p]^=128
    return m

def colour_identity(peek):
    m=initialized(bytes(peek(a) for a in range(65536)))
    return {'game':'martianoids','format':1,'source_md5':'5df07fbd5dabdcb9a909b86cf690a4e8','graphics_sha256':hashlib.sha256(m[0x6000:0x9601]).hexdigest()}

def load_colours():return cs.load(str(RC.build_colours_path(str(COLOURS))))

def compile(mem,cmap=None):
    """Opaque values retain the original bitmap bit in bit7; 255 clear,254 XOR.

    Colours 0..15 and 128..143 have identical RGB entries. This independent bit
    preserves original XOR semantics even after an original black pixel is painted.
    """
    m=initialized(mem);cmap=load_colours() if cmap is None else cmap
    directory=bytearray(2048);pages={};page=FIRST_SOURCE_PAGE;offset=0;seen={};usedkeys=set()
    for i in range(256):
        p=m[0x60A3+2*(i&127)]|m[0x60A4+2*(i&127)]<<8
        if not 0x6000<=p<0x9601:continue
        w=(m[p]&15)*8;h=m[p+1]
        if not(0<w<=32 and 0<h<=64):continue
        orientation=bool(m[p]&128)!=bool(i&128);key=(p,orientation)
        if key in seen:directory[8*i:8*i+8]=seen[key];continue
        data=bytearray();xor=0
        for row in range(h):
            vals=[]
            for col in range(w):
                a=p+2+2*(row*(w//8)+col//8);mask,inv=m[a:a+2];bit=128>>(col&7)
                if mask&bit:
                    cm=cmap.get(f'{a:04X}');white=not(inv&bit);default=14 if white else 1
                    if cm:
                        if cm[:2]!=[mask|(inv<<8),3]:raise ValueError('Colour check differs at '+hex(a))
                        usedkeys.add(f'{a:04X}');value=cm[2][col&7] or default
                    else:value=default
                    vals.append(value|(128 if white else 0))
                elif inv&bit:vals.append(254);xor=1
                else:vals.append(255)
            data.extend(vals[::-1] if orientation else vals)
        if offset+len(data)>8192:page+=1;offset=0
        pages.setdefault(page,bytearray(8192))[offset:offset+len(data)]=data
        entry=bytes([page,offset&255,offset>>8,w,h,xor,0,0]);directory[8*i:8*i+8]=entry;seen[key]=entry;offset+=len(data)
    unknown=set(cmap)-usedkeys
    if unknown:raise ValueError('Unknown colour keys: '+', '.join(sorted(unknown)[:5]))
    assert page<92
    # The floor is transparent outside the 160x112 original viewport.
    floor=bytearray([255])*32768
    for y in range(16,128):
        for x in range(16,176):floor[y*256+x]=132 if (x+y)%2==0 else 1
    for k in range(4):pages[44+k]=floor[k*8192:(k+1)*8192]
    for base in (32,38):
        for k in range(6):pages[base+k]=bytearray([255])*8192
    palette=bytearray()
    for rgb in PALETTE:
        rr,gg,bb=[round(v*7/255) for v in rgb];v=(rr<<6)|(gg<<3)|bb
        palette.extend([v>>1,v&1])
    return {'directory':bytes(directory),'pages':{k:bytes(v) for k,v in pages.items()},'palette':bytes(palette),'highest_page':max(pages),'orientations':len(seen),'source_bytes':sum((v[3]*v[4]) for v in seen.values())}

def expected_canvas(memory,cmap):
    """Independent pixel oracle from original pair bytes and ordered game records.

    Does not read compiled sources, directory, CPU compositor or displayed pages.
    Work pixels keep both original bitmap state and proposed colour.
    """
    m=initialized(memory);pix=[[132 if (x+y)%2==0 else 1 for x in range(192)] for y in range(128)]
    addr=0xD355
    while m[addr]:
        idx,x,bottom=m[addr:addr+3];addr+=3;p=m[0x60A3+2*(idx&127)]|m[0x60A4+2*(idx&127)]<<8
        w=(m[p]&15)*8;h=m[p+1];flip=bool(m[p]&128)!=bool(idx&128)
        for row in range(h):
            y=175-bottom-row
            if not 0<=y<128:continue
            for col in range(w):
                source=w-1-col if flip else col;a=p+2+2*(row*(w//8)+source//8);mask,inv=m[a:a+2];bit=128>>(source&7)
                yy=y+(x+col)//192;xx=(x+col)%192
                if not 0<=yy<128:continue
                if mask&bit:
                    white=not(inv&bit);cm=cmap.get(f'{a:04X}');colour=(cm[2][source&7] if cm else 0) or (14 if white else 1)
                    pix[yy][xx]=colour|(128 if white else 0)
                elif inv&bit:pix[yy][xx]=1 if pix[yy][xx]&128 else 130
    result=bytearray([255])*49152
    for y in range(16,128):result[y*256+16:y*256+176]=bytes(pix[y][16:176])
    return bytes(result)
