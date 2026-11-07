#!/usr/bin/env python3
"""Build the exact Mikro-Gen 48K Herbert release; source graphics come from the user's snapshot."""
from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nexclash.herbert import HerbertPatch,memory
from nexclash.z80tonex import convert
from nexclash.nextboot import check

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot');p.add_argument('-o','--out',required=True);p.add_argument('--work',required=True);p.add_argument('--screen',help='6912-byte original ULA loading screen');p.add_argument('--enhanced',action='store_true');a=p.parse_args()
 prof=json.loads((ROOT/'docs/profiles/herbert.json').read_text());src=Path(a.snapshot)
 if hashlib.md5(src.read_bytes()).hexdigest()!=prof['md5']:p.error('snapshot MD5 does not match the main Mikro-Gen release')
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);work=Path(a.work);work.mkdir(parents=True,exist_ok=True)
 patch=HerbertPatch(memory(src),work,enhanced=a.enhanced);_,tail_addr,tail,_=convert(str(src),str(out),patch=patch,quiet=True)
 errors=check(str(out),str(src),patch,tail=(tail_addr,tail_addr+len(tail)),nexload=True)
 if errors:raise RuntimeError(errors)
 # nextboot's reader assumes no screen payload. Check code/banks first, then add the screen.
 # NXC's screen-aware bank parser verifies that adding it changes none of the tested banks.
 from nexclash.nxc import nex_banks
 before=nex_banks(out.read_bytes())
 if a.screen:
  screen=Path(a.screen).read_bytes()
  if len(screen)!=6912:p.error('--screen must be 6912 bytes')
  d=bytearray(out.read_bytes());d[10]=2;out.write_bytes(d[:512]+screen+d[512:])
 assert nex_banks(out.read_bytes())==before
 print('Boot and NEXLOAD printer-buffer check: PASS; screen-aware bank comparison: IDENTICAL')
 print('SHA256',hashlib.sha256(out.read_bytes()).hexdigest(),out)
if __name__=='__main__':main()
