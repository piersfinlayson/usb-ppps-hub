"""Write the USB PPPD Hub's 24C02 configuration EEPROM image from the EEPROM contents table in spec.md."""
import os
import re
import sys

PROJECT = 'usb-ppps-hub'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the project folder, above scripts/
HEADER = '| Address | Value | Meaning |'
SIZE = 256


def bcd(version):
    """bcdDevice for a version vX.Y.Z, low byte first."""
    m = re.fullmatch(r'v(\d{1,2})\.(\d)\.(\d)', version)
    if not m:
        sys.exit('version %s: bcdDevice only holds vX.Y.Z with X up to 99 and Y and Z up to 9' % version)
    major, minor, patch = (int(g) for g in m.groups())
    return [minor << 4 | patch, (major // 10) << 4 | major % 10]


def rows(spec):
    """(first address, last address, values, whether the values must fill the range exactly) for each row of the
    EEPROM contents table. A string is written as UTF-16LE and VERSION as bcdDevice."""
    lines = open(spec).read().split('\n')
    if HEADER not in lines:
        sys.exit('%s: EEPROM contents table not found' % spec)
    out = []
    for line in lines[lines.index(HEADER) + 2:]:
        if not line.startswith('|'):
            break
        addr, value = [c.strip() for c in line.strip('|').split('|')[:2]]
        m = re.fullmatch(r'([0-9A-F]{2})h(?:-([0-9A-F]{2})h)?', addr)
        if not m:
            sys.exit('bad row: %s' % line)
        first, last = int(m.group(1), 16), int(m.group(2) or m.group(1), 16)
        if len(value) > 1 and value[0] == value[-1] == '"':
            out.append((first, last, list(value[1:-1].encode('utf-16-le')), True))
            continue
        if value == 'VERSION':
            out.append((first, last, bcd(open(os.path.join(ROOT, 'VERSION')).read().strip()), True))
            continue
        values = value.split()
        if not values or not all(re.fullmatch(r'[0-9A-F]{2}', v) for v in values):
            sys.exit('bad row: %s' % line)
        out.append((first, last, [int(v, 16) for v in values], False))
    return out


def image(table):
    data = bytearray(SIZE)
    listed = set()
    for first, last, values, exact in table:
        addrs = range(first, last + 1)
        if len(values) == 1 and not exact:
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
