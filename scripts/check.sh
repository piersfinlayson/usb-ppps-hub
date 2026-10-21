#!/bin/sh
# Generate the schematic, run ERC, compare its netlist and render PNGs. Fails on any problem.
set -e
cd "$(dirname "$0")/.."
D=${1:-build}
. scripts/kicad.sh
P=usb-ppps-hub
status=0
mkdir -p "$D"
cp -R kicad-src/. "$D/"
python3 scripts/usb_hub.py "$D" || status=1
$K sch erc --severity-all --format json -o "$D/erc.json" "$D/$P.kicad_sch" 2>&1 | grep -v Fontconfig || true
$K sch export netlist -o "$D/$P.net" "$D/$P.kicad_sch" 2>&1 | grep -v Fontconfig | grep -v Done || true
$K sch export pdf -o "$D/$P.pdf" "$D/$P.kicad_sch" 2>&1 | grep -v Fontconfig | grep -v -E 'Done|Plotted' || true
python3 scripts/compare.py "$D" || status=1
pdftoppm -png -r ${DPI:-100} "$D/$P.pdf" "$D/sheet"
exit $status
