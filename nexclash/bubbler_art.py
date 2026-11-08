"""Bubbler's original mask/ink graphics and approved per-pixel colour map.

The game supplied by the user provides all shape bytes. Colour-map values are
one plus the runtime palette index: zero remains the shared sheet's 'default'.
The source-only skip value 254 is never a paint colour. Runtime 255 inherits
the unchanged Spectrum picture, including its room attributes.
"""
from pathlib import Path
import hashlib
import json
from . import coloursheet as cs, recolour as RC

ROOT=Path(__file__).resolve().parents[1]
COLOURS=ROOT/'docs/profiles/bubbler_colours.json'
ART=ROOT/'docs/profiles/bubbler_art.json'

def specification():
    return json.loads(ART.read_text())

def load_colours():
    return cs.load(str(RC.build_colours_path(str(COLOURS))))

def colour_identity(peek):
    spec=specification()
    return dict(schema=1,game='bubbler',engine='bubbler',
                keys='original-ink-address:left-bit:wide-v2',
                inputs={'graphics':hashlib.sha256(bytes(peek(a) for a in range(0x6600,0x8700))).hexdigest()},
                geometry=hashlib.sha256(json.dumps(spec['geometries'],sort_keys=True).encode()).hexdigest())

def geometries(mem):
    moving=sorted({mem[a]|mem[a+1]<<8 for a in range(0x66C2,0x674E,2)})
    for base in moving:
        width,height=mem[base:base+2]
        yield dict(base=base,width=width,height=height,static=False)
    for row in specification()['geometries']:
        yield dict(base=row['base'],width=row['width'],height=row['height'],static=True)

def byte_address(row,x,y):
    bx=x//8; width=row['width']; height=row['height']
    offset=(((bx//2)*height+y)*2+bx%2)*2 if row['static'] and width==4 else (y*width+bx)*2
    return row['base']+(1 if row['static'] else 2)+offset+1

def compile(mem,cmap=None):
    cmap=load_colours() if cmap is None else cmap
    spec=specification()
    identity=colour_identity(lambda a:mem[a])
    if identity['inputs']['graphics']!=spec['graphics_sha256']:
        raise ValueError('Original Bubbler graphics differ from the supported release')
    assets=[bytearray(12*8192) for _ in range(2)]
    for side in assets:
        for a in range(0x6000,0x9000):
            side[(a-0x6000)*8:(a-0x6000+1)*8]=bytes(255 if mem[a]&(128>>b) else 0 for b in range(8))
    written={};used=set()
    for row in geometries(mem):
        width,height=row['width'],row['height']
        if not (0<width<=4 and 0<height<=64):raise ValueError('Bad original graphic dimensions')
        for flip in range(2 if row['static'] else 1):
            for y in range(height):
                for x in range(width*8):
                    sx=width*8-1-x if flip else x
                    source=byte_address(row,sx,y);dest=byte_address(row,x,y)
                    mask,ink=mem[source-1:source+1];bit=128>>(sx&7)
                    key=f'{source:04x}';cm=cmap.get(key)
                    colour=255 if ink&bit else 0
                    if cm:
                        if cm[:2]!=[ink,1] or len(cm[2])!=8:
                            raise ValueError('Colour check or width differs at '+key)
                        used.add(key);value=cm[2][sx&7]
                        if not isinstance(value,int) or not 0<=value<=256:
                            raise ValueError('Invalid paint value at '+key)
                        if value:colour=value-1
                        if len(cm)>3 and cm[3]&(128>>(sx&7)):
                            raise ValueError('Bubbler does not support changing the original mask')
                    support=bool((mask|ink)&bit)
                    if support and colour==254:raise ValueError('Colour254 is reserved for source skip')
                    if not support and colour not in (0,):raise ValueError('Paint outside original mask at '+key)
                    value=colour if support else 254
                    offset=(dest-0x6000)*8+(x&7);k=(flip,offset)
                    if k in written and written[k]!=value:raise ValueError('Conflicting original source alias')
                    written[k]=value;assets[flip][offset]=value
                    assets[flip][(dest-1-0x6000)*8]=0xA7
    unknown=set(cmap)-used
    if unknown:raise ValueError('Unknown colour keys: '+', '.join(sorted(unknown)[:5]))
    pages={40+side*12+n:bytes(data[n*8192:(n+1)*8192])
           for side,data in enumerate(assets) for n in range(12)}
    return dict(pages=pages,palette=spec['palette'],identity=identity)

def sheets(mem,out,name='BUBBLER',colours=None):
    """New complete v2 sheets; refuse to replace a user-editable PNG."""
    from PIL import Image
    colours=load_colours() if colours is None else colours
    compile(mem,colours)  # validate source identity and every map entry first
    palette=[(0,0,0)]+[tuple(v) for v in specification()['palette']]
    palette[256]=(255,255,0)  # inherited original ink represented in the sheet
    identity=colour_identity(lambda a:mem[a]);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    results=[]
    for static,part in ((False,'SPRITES'),(True,'SCENERY')):
        png=out/f'{name}_PAINTING_{part}.png';layout=png.with_name(png.stem+'_layout.json')
        if png.exists():raise FileExistsError('Preserve the editable painting: '+str(png))
        collector=cs.Collector()
        for row in geometries(mem):
            if row['static']!=static:continue
            width,height=row['width'],row['height'];pixels=[];entries={}
            for y in range(height):
                for x in range(width*8):
                    a=byte_address(row,x,y);mask,ink=mem[a-1:a+1];bit=128>>(x&7)
                    if not (mask|ink)&bit:continue
                    key=f'{a:04x}';entries[key]=[ink,1]
                    pixels.append((x,height-1-y,key,x&7,1 if ink&bit else 2,256 if ink&bit else 1))
            collector.add_frame([dict(id=row['base'],size=height,w=width*8,h=height,x=0,y=0,mir=0,
                                     group=part,pixels=pixels,entries=entries)])
        comps=collector.composites([part])
        cs.write(comps,str(png),str(layout),palette,colours=colours,unique=False,identity=identity)
        image=Image.open(png)
        image.resize((image.width*4,image.height*4),Image.Resampling.NEAREST).save(out/f'{name}_{part}_REFERENCE_4X.png')
        results.append(str(png))
    return results
