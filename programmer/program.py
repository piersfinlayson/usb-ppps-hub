"""Program a USB PPPS Hub's EEPROM through a Pico or Pico 2 in BOOTSEL mode, wired to the hub as in the README.

The programmer for the Pico's chip, rp2040.uf2 or rp2350.uf2, is loaded from this file's folder.
"""
import argparse
import os
import re
import secrets
import struct
import subprocess
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REQUEST_ADDR = 0x10100000
RESULT_ADDR = REQUEST_ADDR + 0x1000
REQUEST_MAGIC = 0x51504545
RESULT_MAGIC = 0x57504545
BCD_DEVICE = 0x04
SERIAL_LEN = 0x15
SERIAL = 0x92
SERIAL_CHARS = 16
WAIT_S = 30

# main.c's result values
OK, RESET_LOW, LINES_LOW, NO_ACK, WRITE_FAILED, WRITE_TIMEOUT, READ_FAILED, MISMATCH = range(8)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def picotool(*args):
    try:
        return subprocess.run(['picotool', *args], capture_output=True, text=True)
    except FileNotFoundError:
        fail('picotool not found. Install picotool 2.1.1 or later.')


def run(*args):
    p = picotool(*args)
    if p.returncode:
        fail('picotool %s failed:\n%s' % (' '.join(args), (p.stdout + p.stderr).strip()))


def chip():
    """rp2040 or rp2350 for the Pico in BOOTSEL mode, or None if there isn't one."""
    p = picotool('info', '-d')
    out = p.stdout + p.stderr
    if 'Multiple RP-series devices' in out:
        fail('More than one Pico in BOOTSEL mode found. Connect only one.')
    m = re.search(r'type:\s+(RP2040|RP2350)', out)
    return m.group(1).lower() if m else None


def bcd(version):
    m = re.fullmatch(r'v(\d{1,2})\.(\d)\.(\d)', version)
    if not m:
        fail('--board-version %s: must be vX.Y.Z with X up to 99 and Y and Z up to 9' % version)
    major, minor, patch = (int(g) for g in m.groups())
    return bytes([minor << 4 | patch, (major // 10) << 4 | major % 10])


def board_version(image):
    lo, hi = image[BCD_DEVICE], image[BCD_DEVICE + 1]
    return 'v%d.%d.%d' % ((hi >> 4) * 10 + (hi & 15), lo >> 4, lo & 15)


def serial_number(image):
    """The serial number in an EEPROM image, or None if it doesn't contain one."""
    if image[SERIAL_LEN] != SERIAL_CHARS:
        return None
    s = image[SERIAL:SERIAL + 2 * SERIAL_CHARS].decode('utf-16-le', errors='replace')
    return s if re.fullmatch(r'[0-9A-F]{%d}' % SERIAL_CHARS, s) else None


def main():
    parser = argparse.ArgumentParser(
        description='Program a USB PPPS Hub EEPROM through a Pico or Pico 2 in BOOTSEL mode.')
    parser.add_argument('--board-version', metavar='vX.Y.Z', help="the board's version, if not the image's")
    parser.add_argument('--serial', metavar='HEX', help='the serial number, 16 hex digits, if not a random one')
    parser.add_argument('image', help='the EEPROM image')
    args = parser.parse_args()

    image = bytearray(open(args.image, 'rb').read())
    if len(image) != 256:
        fail('%s: %d bytes, not 256' % (args.image, len(image)))
    if image[SERIAL_LEN] != SERIAL_CHARS:
        fail('%s: serial number length %d, not %d' % (args.image, image[SERIAL_LEN], SERIAL_CHARS))
    if args.board_version:
        image[BCD_DEVICE:BCD_DEVICE + 2] = bcd(args.board_version)
    serial = (args.serial or secrets.token_hex(SERIAL_CHARS // 2)).upper()
    if not re.fullmatch(r'[0-9A-F]{%d}' % SERIAL_CHARS, serial):
        fail('--serial %s: must be %d hex digits' % (args.serial, SERIAL_CHARS))
    image[SERIAL:SERIAL + 2 * SERIAL_CHARS] = serial.encode('utf-16-le')
    image = bytes(image)

    c = chip()
    if not c:
        fail('No Pico in BOOTSEL mode found. Hold BOOTSEL while connecting it.')
    uf2 = os.path.join(HERE, c + '.uf2')
    if not os.path.exists(uf2):
        fail('%s not found' % uf2)

    rid = secrets.randbits(32)
    request = struct.pack('<3I', REQUEST_MAGIC, rid, zlib.crc32(image)) + image
    request += b'\xff' * (0x1000 - len(request))
    with tempfile.TemporaryDirectory() as tmp:
        req = os.path.join(tmp, 'request.bin')
        res = os.path.join(tmp, 'result.bin')
        open(req, 'wb').write(request)
        run('load', uf2)
        run('load', req, '-t', 'bin', '-o', hex(REQUEST_ADDR))
        run('reboot')
        deadline = time.monotonic() + WAIT_S
        time.sleep(1)
        while not chip():
            if time.monotonic() > deadline:
                fail("The Pico didn't return to BOOTSEL mode within %d s." % WAIT_S)
            time.sleep(1)
        run('save', '-r', hex(RESULT_ADDR), hex(RESULT_ADDR + 1024), res, '-t', 'bin')
        d = open(res, 'rb').read()

    magic, got, status, address, rst, sda, scl, clocks = struct.unpack_from('<8I', d)
    if magic != RESULT_MAGIC or got != rid:
        fail('No result from the Pico.')
    before, after = d[32:288], d[288:544]
    if status == RESET_LOW:
        fail('RESET_N is low. Check the RST wire and that the hub is powered.')
    if status == LINES_LOW:
        fail('\n'.join('%s is low. Check the %s wire and that the hub is powered.' % (n, n)
                       for n, level in (('SDA', sda), ('SCL', scl)) if not level))
    if status == NO_ACK:
        fail("The EEPROM didn't acknowledge I2C address 50h.")
    if status == WRITE_FAILED:
        fail('Writing EEPROM address %02Xh failed.' % address)
    if status == WRITE_TIMEOUT:
        fail("Writing EEPROM address %02Xh didn't complete within 20 ms." % address)
    if status == READ_FAILED:
        fail('Reading the EEPROM back failed.')
    if status == MISMATCH:
        fail('The EEPROM read back differs from the image at %s.' %
             ', '.join('%02Xh' % a for a in range(256) if after[a] != image[a]))
    if status != OK:
        fail('Unknown result %d from the Pico.' % status)
    print('Board version: %s' % board_version(image))
    print('Serial number: %s' % serial)
    print('Previous serial number: %s' % (serial_number(before) or 'none'))
    if clocks:
        print('SDA was held low and released after %d clock pulses' % clocks)
    print('Programmed and verified')


if __name__ == '__main__':
    main()
