"""Check the board STL and the intersections of the board, base and lid. Exits 1 if the board STL is missing its
parts or any intersection has volume. A missing intersection STL is an empty intersection."""
import os
import struct
import sys

MIN_HEIGHT = 5.0    # mm. The board without parts is 1.6 mm, with the 100 uF cap 7.4 mm.
MAX_VOLUME = 0.01   # mm3. Faces that only touch, for example the board on the peg shoulders, have no volume.


def triangles(path):
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:512]:
        v = [tuple(map(float, line.split()[1:4])) for line in data.decode().splitlines()
             if line.strip().startswith('vertex')]
        return [v[i:i + 3] for i in range(0, len(v), 3)]
    n = struct.unpack('<I', data[80:84])[0]
    return [[struct.unpack('<3f', data[84 + i * 50 + 12 + k * 12:84 + i * 50 + 24 + k * 12]) for k in range(3)]
            for i in range(n)]


def volume(tris):
    return abs(sum(a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0]) for a, b, c in tris)) / 6


failed = False
height = max(p[2] for t in triangles(sys.argv[1]) for p in t)
if height < MIN_HEIGHT:
    print('%s: %.1f mm high, so its parts are missing' % (sys.argv[1], height))
    failed = True
for path in sys.argv[2:]:
    v = volume(triangles(path)) if os.path.exists(path) else 0
    if v > MAX_VOLUME:
        print('%s: %.3f mm3 overlap' % (path, v))
        failed = True
sys.exit(1 if failed else 0)
