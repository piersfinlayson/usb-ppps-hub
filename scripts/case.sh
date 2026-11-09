#!/bin/sh
# Build the case STLs in folder $2 from generated PCB $1 and check that the board, base and lid don't overlap.
# Writes G-code for an Original Prusa MK3S, for each part and for both together, if PrusaSlicer is installed. Fails
# on any problem.
set -e
cd "$(dirname "$0")/.."
. scripts/kicad.sh
PCB=${1:-build/usb-ppps-hub.kicad_pcb}
D=${2:-build/case}
P=usb-ppps-hub
OPENSCAD=${OPENSCAD:-openscad}
PS_APP="/Applications/Original Prusa Drivers/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
PS=${PRUSASLICER:-$(command -v prusa-slicer || echo "$PS_APP")}
mkdir -p "$D"
cp case/$P-case.scad case/Montserrat-ExtraBold.ttf "$D/"
# hide KiCad's messages on stderr but show a Python traceback
O=$($PY scripts/case_board.py "$PCB" "$D/board.scad" 2>"$D/case_board.err") ||
    { sed -n '/^Traceback/,$p' "$D/case_board.err" >&2; exit 1; }
$K pcb export stl -f --no-dnp --user-origin "$O" -o "$D/board.stl" "$PCB" >/dev/null 2>&1
# $3 set: the part may be empty, which OpenSCAD reports as an error
scad() {
    rm -f "$D/$2"
    $OPENSCAD --backend=Manifold -D "part=\"$1\"" -o "$D/$2" "$D/$P-case.scad" >"$D/openscad.log" 2>&1 && return
    if [ -z "$3" ] || grep -q ERROR "$D/openscad.log" || ! grep -q 'top level object is empty' "$D/openscad.log"; then
        cat "$D/openscad.log" >&2
        exit 1
    fi
}
scad base $P-case-base.stl
scad lid $P-case-lid.stl
scad both $P-case.stl
for f in fit-base fit-lid fit-case; do scad $f $f.stl empty; done
python3 scripts/case_fit.py "$D/board.stl" "$D/fit-base.stl" "$D/fit-lid.stl" "$D/fit-case.stl"
slice() {
    "$PS" --printer-profile "Original Prusa i3 MK3S & MK3S+" --print-profile "0.20mm SPEED @MK3" \
        --material-profile "Prusament PLA" --fill-density 15% --export-gcode "$@" >/dev/null
}
if [ -x "$PS" ]; then
    for f in $P-case-base $P-case-lid $P-case; do slice --center 125,105 -o "$D/$f.gcode" "$D/$f.stl"; done
fi
