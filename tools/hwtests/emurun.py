"""Run nxsuite.nex unattended in an emulator and collect NXSUITE.TXT / .PRG (GPL-3.0-or-later, part of nexclash).

    python tools/hwtests/emurun.py jnext  --exe JNEXT_EXE  --sd DIR --nex NXSUITE.NEX [--card IMG]
    python tools/hwtests/emurun.py cspect --exe CSPECT_EXE --sd DIR --nex NXSUITE.NEX [--hz60] [--port 8766]
    then: python tools/hwtests/intake.py DIR/NXSUITE.TXT --platform "<emulator> <version>"

Nothing here names a machine's own paths: the emulator and the SD folder are arguments, and no emulator file is kept in the repository. DIR is the SD folder: the .nex is copied there,
the suite's NXSUITE.* files end up there. The run skips the first-start questions (S), presses the menu key
(--key, default A = RUN ALL: the automatic pass), waits for the suite's DONE flag ($7FFF = $A5, written after NXSUITE.TXT) or --timeout,
and stops only the emulator process it started.

- JNext: headless, its esxDOS stub serves DIR (writable); --card is passed as a read-only SD image if given.
- CSpect: -zxnext -mmc=DIR, its MCP server on --port (never another CSpect's port), read through HTTP.
- MAME 0.289 (driver tbblue) is not supported: see tools/hwtests/README.md "Emulators" (it did not reach
  the suite unattended).

An emulator result describes that emulator: it is never hardware evidence (intake --platform keeps it apart).
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

DONE_ADDR = 0x7FFF
DONE_VAL = 0xA5
PRG_FLAGS = 0x6500 + 18         # nxsuite/defs.asm PRGB + PRG_FLAGS


# ---------------------------------------------------------------- JNext
JNEXT_SCRIPT = r'''
var done = 0
on write 0x%(addr)04X when VALUE == 0x%(val)02X do
    log "NXDONE frame ${FRAME}"
    screenshot "%(shot)s"
    set done = FRAME
end
on frame when done != 0 and FRAME > done + 50 do
    exit 0
end
'''


def run_jnext(a, d):
    script = os.path.join(d, 'emurun.jds')
    with open(script, 'w', newline='\n') as f:
        f.write(JNEXT_SCRIPT % {'addr': DONE_ADDR, 'val': DONE_VAL,
                                'shot': os.path.join(d, 'done.png').replace('\\', '/')})
    cmd = [a.exe, '--headless', '--esxdos-stub-root', d, '--esxdos-stub-writable',
           '--load', os.path.join(d, 'nxsuite.nex'), '--script', script,
           '--delayed-automatic-exit-frames', str(int(a.timeout * 50)),
           '--delayed-keypress-frames', str(int((a.key_after - 10) * 50)), 's',
           '--delayed-keypress-frames', str(int(a.key_after * 50)), a.key.lower()]
    if a.card:
        cmd[2:2] = ['--sdcard', a.card, '--sdcard-readonly']
    cfg = os.path.join(d, 'jnext-config')
    os.makedirs(cfg, exist_ok=True)
    with open(os.path.join(d, 'emulator.log'), 'w') as log:
        r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=d,
                           env=dict(os.environ, JNEXT_CONFIG_DIR=cfg), timeout=a.timeout * 4 + 120)
    txt = open(os.path.join(d, 'emulator.log'), errors='replace').read()
    return 'done' if 'NXDONE' in txt else 'timeout or exit %s' % r.returncode


# ---------------------------------------------------------------- CSpect (its own MCP server over HTTP)
class Mcp:
    def __init__(s, port):
        s.url = 'http://127.0.0.1:%d/mcp' % port
        s.sid = None
        s.n = 0

    def call(s, method, params=None, note=False):
        s.n += 1
        body = {'jsonrpc': '2.0', 'method': method}
        if not note:
            body['id'] = s.n
        if params is not None:
            body['params'] = params
        req = urllib.request.Request(s.url, json.dumps(body).encode(), method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json, text/event-stream')
        if s.sid:
            req.add_header('Mcp-Session-Id', s.sid)
        with urllib.request.urlopen(req, timeout=20) as r:
            s.sid = r.headers.get('Mcp-Session-Id', s.sid)
            txt = r.read().decode('utf-8', 'replace')
        if note or not txt.strip():
            return None
        if txt.lstrip().startswith('{'):
            return json.loads(txt)
        for ln in txt.splitlines():
            if ln.startswith('data:'):
                return json.loads(ln[5:])
        return txt

    def tool(s, name, args):
        return s.call('tools/call', {'name': name, 'arguments': args})

    def shot(s, path):
        r = s.tool('screenshot', {})
        for c in r['result']['content']:
            if c.get('type') == 'image':
                with open(path, 'wb') as f:
                    f.write(base64.b64decode(c['data']))


def port_free(port):
    import socket
    with socket.socket() as k:
        k.settimeout(1)
        return k.connect_ex(('127.0.0.1', port)) != 0


def prg_flags(m):
    """the progress record's flag byte (PRGB $6500 + 18, bank 5): bit 2 = the first-start questions are done"""
    r = m.tool('read_memory', {'address': '$%04X' % PRG_FLAGS, 'length': 1})
    try:
        return int(r['result']['content'][0]['text'].split()[1], 16)
    except (KeyError, IndexError, ValueError, TypeError):
        return 0


def run_cspect(a, d):
    if not port_free(a.port):
        return 'port %d is in use (another CSpect?): not started' % a.port
    cmd = [a.exe, '-zxnext', '-w2', '-mmc=%s\\' % d, '-mcp=%d' % a.port]
    if a.hz60:
        cmd.append('-60')
    if a.sdspeed:
        cmd.append('-sdspeed=%s' % a.sdspeed)
    cmd.append(os.path.join(d, 'nxsuite.nex'))
    log = open(os.path.join(d, 'emulator.log'), 'w')
    # the run folder as working folder: CSpect 4.6 reads cspect.ini from there (else beside CSpect.exe) and
    # saves menu changes there, so the owner's own settings are neither used from nor written to its folder
    p = subprocess.Popen(cmd, cwd=d, stdout=log, stderr=subprocess.STDOUT)
    t0 = time.time()
    m = Mcp(a.port)
    status = 'timeout'
    try:
        while True:
            try:
                m.call('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                      'clientInfo': {'name': 'nxsuite-emurun', 'version': '1'}})
                m.call('notifications/initialized', None, note=True)
                break
            except Exception as e:
                if time.time() - t0 > 60 or p.poll() is not None:
                    return 'CSpect MCP never answered: %s' % e
                time.sleep(1)
        while time.time() - t0 < a.key_after:
            time.sleep(1)
        for _ in range(30):                             # the first-start questions: S skips them
            if prg_flags(m) & 4:
                break
            m.tool('press_keys', {'keys': 'S'})
            time.sleep(2)
        m.tool('press_keys', {'keys': a.key})
        while time.time() - t0 < a.timeout:
            time.sleep(5)
            if p.poll() is not None:
                return 'CSpect exited (code %s)' % p.returncode
            r = json.dumps(m.tool('read_memory', {'address': '$%04X' % DONE_ADDR, 'length': 1})).upper()
            if 'A5' in r.replace('0XA5', 'A5'):
                status = 'done'
                time.sleep(3)
                try:
                    m.shot(os.path.join(d, 'done.png'))
                except Exception:
                    pass
                break
        if status == 'timeout':
            try:
                m.shot(os.path.join(d, 'timeout.png'))
            except Exception:
                pass
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        log.close()
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('emulator', choices=('jnext', 'cspect'))
    ap.add_argument('--exe', required=True, help='the emulator program')
    ap.add_argument('--sd', required=True, help='the SD folder (created; NXSUITE.* files end up here)')
    ap.add_argument('--nex', required=True, help='the built nxsuite.nex')
    ap.add_argument('--key', default='A', help='menu key (A = RUN ALL; 0-9 a group)')
    ap.add_argument('--key-after', type=float, default=35, help='seconds of emulated time before the key')
    ap.add_argument('--timeout', type=float, default=900, help='seconds (emulated for JNext)')
    ap.add_argument('--card', help='JNext: a read-only SD image to boot with')
    ap.add_argument('--hz60', action='store_true', help='CSpect: start at 60 Hz')
    ap.add_argument('--port', type=int, default=8766, help='CSpect: MCP port of the instance this starts')
    ap.add_argument('--sdspeed', help='CSpect 4.6+: SD card speed (unlimited, fast, normal, slowest)')
    a = ap.parse_args(argv)
    d = os.path.abspath(a.sd)
    os.makedirs(d, exist_ok=True)
    for nm in os.listdir(d):
        if nm.upper().startswith('NXSUITE.') and nm.upper() not in ('NXSUITE.NEX',):
            print('%s already has %s: the suite appends to an earlier run of the same build' % (d, nm))
            break
    shutil.copyfile(a.nex, os.path.join(d, 'nxsuite.nex'))
    t0 = time.time()
    status = {'jnext': run_jnext, 'cspect': run_cspect}[a.emulator](a, d)
    f = os.path.join(d, 'NXSUITE.TXT')
    print('%s: %s after %.0f s; NXSUITE.TXT %s' % (a.emulator, status, time.time() - t0,
                                                   '%d bytes' % os.path.getsize(f) if os.path.exists(f) else 'missing'))
    return 0 if status.startswith('done') and os.path.exists(f) else 1


if __name__ == '__main__':
    sys.exit(main())
