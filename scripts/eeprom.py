"""Write the 24C02 configuration EEPROM image from the EEPROM contents table in spec.md."""
import os
import re
import sys

PROJECT = 'usb-ppps-hub'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the project folder, above scripts/
HEADER = '| Address | Value | Meaning |'
SIZE = 256


def rows(spec):
    """(first address, last address, values) for each row of the EEPROM contents table."""
    lines = open(spec).read().split('\n')
    if HEADER not in lines:
        sys.exit('%s: EEPROM contents table not found' % spec)
    out = []
    for line in lines[lines.index(HEADER) + 2:]:
        if not line.startswith('|'):
            break
        addr, value = [c.strip() for c in line.strip('|').split('|')[:2]]
        m = re.fullmatch(r'([0-9A-F]{2})h(?:-([0-9A-F]{2})h)?', addr)
        values = value.split()
        if not m or not values or not all(re.fullmatch(r'[0-9A-F]{2}', v) for v in values):
            sys.exit('bad row: %s' % line)
        out.append((int(m.group(1), 16), int(m.group(2) or m.group(1), 16), [int(v, 16) for v in values]))
    return out


def image(table):
    data = bytearray(SIZE)
    listed = set()
    for first, last, values in table:
        addrs = range(first, last + 1)
        if len(values) == 1:
            values = values * len(addrs)
        if len(values) != len(addrs):
            sys.exit('%02Xh-%02Xh: %d values for %d addresses' % (first, last, len(values), len(addrs)))
        for a, v in zip(addrs, values):
            if a in listed:
                sys.exit('%02Xh listed twice' % a)
            listed.add(a)
            data[a] = v
    return data


if __name__ == '__main__':
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ROOT)
    os.makedirs(out, exist_ok=True)
    data = image(rows(os.path.join(ROOT, 'spec.md')))
    open(os.path.join(out, PROJECT + '-eeprom.bin'), 'wb').write(data)
