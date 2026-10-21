"""Write JLCPCB fabrication and assembly files for the board: zipped Gerbers and drill files, BOM and CPL.
Run with KiCad's bundled Python. DNP parts and parts excluded from the BOM or position files are left out.
The silkscreen's ${COMMIT} is set to the short hash of HEAD. Uncommitted changes or untracked files stop the script."""
import csv
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import pcbnew

from kicad_paths import KICAD_CLI

PROJECT = 'usb-ppps-hub'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the project folder, above scripts/
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'

# JLC orients and centres each part by its own footprint for that LCSC part, which can differ from KiCad's.
# By LCSC part: degrees added to KiCad's rotation, and the offset in mm from the KiCad footprint origin to
# JLC's centre, in the footprint's own unrotated axes (x right, y down). The rotations are from JLC's
# placement preview of this board. The USB-C footprint's origin is the centre of its body outline, 3.67 mm
# from the pin row. JLC's footprint for the part has its origin 2.375 mm from the pin row.
CORRECTIONS = {
    'C16251': (-90, 0, 0),          # USB2514B, QFN-36
    'C3235557': (-90, 0, 0),        # TPS2116, SOT-583-8
    'C18723540': (180, 0, 0),       # 24C02S, SOT-23-5
    'C51118': (-90, 0, 0),          # AP2112K-3.3, SOT-23-5
    'C24593': (180, 0, 0),          # TPS2051B, SOT-23-5
    'C132016': (180, 0, 0),         # TLV803S, SOT-23
    'C15999': (180, 0, 0),          # USBLC6-2P6, SOT-666
    'C2765186': (0, 0, -1.295),     # USB-C receptacle
}


def cli(*args):
    subprocess.run([KICAD_CLI] + list(args), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def git(*args):
    r = subprocess.run(['git', '-C', ROOT] + list(args), stdout=subprocess.PIPE, universal_newlines=True)
    if r.returncode:
        sys.exit(r.returncode)
    return r.stdout.strip()


def commit():
    if git('status', '--porcelain'):
        sys.exit('uncommitted changes or untracked files')
    return git('rev-parse', '--short', 'HEAD')


def natural(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def gerbers(pcb, zip_path, tmp, sha):
    d = os.path.join(tmp, 'gerbers')
    os.makedirs(d)
    cli('pcb', 'export', 'gerbers', '--layers', LAYERS, '--no-x2', '--subtract-soldermask', '-D', 'COMMIT=' + sha,
        '-o', d + '/', pcb)
    cli('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
        '--excellon-oval-format', 'alternate', '--excellon-separate-th', '-o', d + '/', pcb)
    names = sorted(os.listdir(d))
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.write(os.path.join(d, n), n)
    return names


def bom(board, path):
    """One row per value, footprint and LCSC number."""
    groups = {}
    for fp in board.GetFootprints():
        if fp.IsDNP() or fp.IsExcludedFromBOM():
            continue
        lcsc = fp.GetFieldText('LCSC') if fp.HasFieldByName('LCSC') else ''
        key = (fp.GetValue(), fp.GetFPID().GetLibItemName().wx_str(), lcsc)
        groups.setdefault(key, []).append(fp.GetReference())
    rows = sorted(groups.items(), key=lambda kv: natural(min(kv[1], key=natural)))
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (value, footprint, lcsc), refs in rows:
            w.writerow([value, ','.join(sorted(refs, key=natural)), footprint, lcsc])
    return [k for k, _ in rows if not k[2]]


def cpl(pcb, path, tmp, lcsc):
    """KiCad's position file for the top side, with JLC's column names and CORRECTIONS applied.
    lcsc maps each reference to its LCSC part."""
    pos = os.path.join(tmp, 'pos.csv')
    cli('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'front', '--exclude-dnp', '-o', pos, pcb)
    with open(pos) as f:
        rows = sorted(csv.DictReader(f), key=lambda r: natural(r['Ref']))
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in rows:
            rot, dx, dy = CORRECTIONS.get(lcsc.get(r['Ref'], ''), (0, 0, 0))
            a = math.radians(float(r['Rot']))
            # the offset turned with the footprint, then into the CPL's y up
            x = float(r['PosX']) + dx * math.cos(a) + dy * math.sin(a)
            y = float(r['PosY']) + dx * math.sin(a) - dy * math.cos(a)
            w.writerow([r['Ref'], '%.4fmm' % x, '%.4fmm' % y, 'Top', '%g' % ((float(r['Rot']) + rot) % 360)])
    return len(rows)


def main(out):
    sha = commit()
    os.makedirs(out, exist_ok=True)
    pcb = os.path.join(ROOT, 'kicad', PROJECT + '.kicad_pcb')
    board = pcbnew.LoadBoard(pcb)
    with tempfile.TemporaryDirectory() as tmp:
        names = gerbers(pcb, os.path.join(out, PROJECT + '-gerbers.zip'), tmp, sha)
        lcsc = {fp.GetReference(): fp.GetFieldText('LCSC') if fp.HasFieldByName('LCSC') else ''
                for fp in board.GetFootprints()}
        placed = cpl(pcb, os.path.join(out, PROJECT + '-cpl.csv'), tmp, lcsc)
    missing = bom(board, os.path.join(out, PROJECT + '-bom.csv'))
    print('COMMIT', sha)
    print('GERBERS', ' '.join(names))
    print('CPL %d parts' % placed)
    for value, footprint, _ in missing:
        print('NOLCSC', value, footprint)
    if missing:
        sys.exit(1)


if __name__ == '__main__':
    main(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'jlc')))
