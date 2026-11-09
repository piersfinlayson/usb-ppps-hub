#!/bin/sh
# Render the generated board and its case in 3D.
set -e
cd "$(dirname "$0")/.."
. scripts/kicad.sh
P=usb-ppps-hub
mkdir -p images
# The leading space in --pan stops kicad-cli reading the negative value as an option.
$K pcb render --rotate 320,0,15 --perspective --quality high --width 1280 --height 800 --zoom 1.25 \
    --pan ' -0.45,1.5,0' -o images/$P.png kicad/$P.kicad_pcb >/dev/null 2>&1
scripts/case.sh kicad/$P.kicad_pcb build/case
${OPENSCAD:-openscad} --imgsize 1280,800 --colorscheme Tomorrow -D lid_alpha=1 --camera 37.5,25,8,62,0,335,0 \
    --autocenter --viewall -o images/$P-case.png build/case/$P-case.scad >/dev/null 2>&1
