#!/bin/sh
# Render the generated board in 3D.
set -e
cd "$(dirname "$0")/.."
. scripts/kicad.sh
P=usb-ppps-hub
mkdir -p images
# The leading space in --pan stops kicad-cli reading the negative value as an option.
$K pcb render --rotate 320,0,15 --perspective --quality high --width 1280 --height 800 --zoom 1.25 \
    --pan ' -0.45,1.5,0' -o images/$P.png kicad/$P.kicad_pcb >/dev/null 2>&1
