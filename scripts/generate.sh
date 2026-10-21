#!/bin/sh
# Generate kicad/, jlc/ and the EEPROM image from the current commit.
set -e
cd "$(dirname "$0")/.."
. scripts/kicad.sh
P=usb-ppps-hub
if [ -n "$(git status --porcelain)" ]; then
    echo "uncommitted changes or untracked files" >&2
    exit 1
fi
C=$(git rev-parse --short HEAD)
rm -rf ./kicad
mkdir -p kicad build
cp -R kicad-src/. kicad/
python3 - "$C" <<'PY'
import json, sys
p = 'kicad/usb-ppps-hub.kicad_pro'
d = json.load(open(p))
d['text_variables']['COMMIT'] = sys.argv[1]
open(p, 'w').write(json.dumps(d, indent=2) + '\n')
PY
python3 scripts/usb_hub.py kicad
# hide KiCad's messages on stderr but show a Python traceback
$PY scripts/usb_hub_pcb.py kicad 2>build/usb_hub_pcb.err || { sed -n '/^Traceback/,$p' build/usb_hub_pcb.err >&2; exit 1; }
$K sch export pdf -o kicad/$P-schematic.pdf kicad/$P.kicad_sch >/dev/null 2>&1
python3 scripts/eeprom.py .
$PY scripts/jlc.py 2>build/jlc.err || { sed -n '/^Traceback/,$p' build/jlc.err >&2; exit 1; }
