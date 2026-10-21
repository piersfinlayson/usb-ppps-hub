#!/bin/sh
# Generate the schematic and PCB in a folder, run DRC with schematic parity and render layers to PNG. Fails on
# any problem.
set -e
cd "$(dirname "$0")/.."
D=${1:-build}
. scripts/kicad.sh
P=usb-ppps-hub
status=0
mkdir -p "$D"
cp -R kicad-src/. "$D/"
python3 scripts/usb_hub.py "$D" || status=1
# hide KiCad's messages on stderr but show a Python traceback
$PY scripts/usb_hub_pcb.py "$D" 2>"$D/usb_hub_pcb.err" || status=1
sed -n '/^Traceback/,$p' "$D/usb_hub_pcb.err" >&2
$K pcb drc --schematic-parity --severity-all --format json -o "$D/drc.json" "$D/$P.kicad_pcb" 2>&1 | grep -v -E 'Fontconfig|Saved|Found' || true
python3 scripts/drc_summary.py "$D/drc.json" || status=1
# board top left is at (100, 100) mm on the page
DPI=${DPI:-300}
X=$(python3 -c "print(int((100 - 2) / 25.4 * $DPI))")
S=$(python3 -c "print(int(79 / 25.4 * $DPI))")
render() {
    $K pcb export pdf --mode-single --drill-shape-opt 1 -l "$2" -o "$D/$1.pdf" "$D/$P.kicad_pcb" >/dev/null 2>&1
    pdftoppm -png -singlefile -r $DPI -x $X -y $X -W $S -H $S "$D/$1.pdf" "$D/$1"
}
render top F.Cu,F.SilkS,F.Fab,Edge.Cuts
render bottom B.Cu,Edge.Cuts
render power In2.Cu,Edge.Cuts
exit $status
