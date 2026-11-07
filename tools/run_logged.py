#!/usr/bin/env python3
"""Run a command with bounded output and durable status: --log run.log -- CMD ARG..."""
import argparse
from collections import deque
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--log', required=True)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command:
        ap.error('supply a command after --')
    path = Path(a.log).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    status = Path(str(path) + '.status.json')
    info = {'command': command, 'started': time.time(), 'state': 'running', 'log': str(path)}
    def save():
        temporary = Path(str(status) + '.tmp')
        temporary.write_text(json.dumps(info, indent=2) + '\n')
        temporary.replace(status)
    save()
    try:
        with path.open('wb') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        code = result.returncode
        code = code if code >= 0 else 128 - code
    except OSError as error:
        with path.open('ab') as log:
            log.write(('Could not start command: %s\n' % error).encode())
        code = 127
    info.update(state='completed', exit_code=code, finished=time.time())
    save()
    tail, warnings = deque(maxlen=30), []
    with path.open(errors='replace') as log:
        for line in log:
            line = line.rstrip('\n')[:1000]
            tail.append(line)
            if len(warnings) < 20 and re.search(r'WARNING|FAILED|!', line):
                warnings.append(line)
    for line in warnings:
        if line not in tail:
            print(line)
    print('\n'.join(tail))
    print('Exit: %d; log: %s; status: %s' % (code, path, status))
    return code


if __name__ == '__main__':
    sys.exit(main())
