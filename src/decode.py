#!/usr/bin/env python3
import re
import sys
import binascii

from elcobus.ElcobusMessage.ElcobusFrame import ElcobusFrame

__import__('elcobus.ElcobusMessage', globals(), level=0, fromlist=['*'])
# ^^^ equivalent of `from elcobus.ElcobusMessage import *`, but without polluting the namespace


for line in sys.stdin:
    match = re.match('^(.*)EBM: \[([0-9A-Fa-f]{2}(?: [0-9A-Fa-f]{2})*)\](.*)$', line)
    if not match:
        continue

    hexdump = match.group(2)
    binary = binascii.unhexlify(hexdump.replace(' ', ''))
    ebm = ElcobusFrame.from_bytes(binary)

    # optionally filter here?

    print("{}EBM: {}{}".format(
        match.group(1),
        ebm,
        match.group(3)))
