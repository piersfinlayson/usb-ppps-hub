#!/bin/sh
# Write the release files for tag $1 to folder $2. The tag must match VERSION and have a dated section in
# CHANGELOG.md.
set -e
cd "$(dirname "$0")/.."
T=$1
D=${2:-build/release}
P=usb-ppps-hub
V=$(cat VERSION)
if [ "$T" != "$V" ]; then
    echo "tag $T doesn't match VERSION ($V)" >&2
    exit 1
fi
python3 scripts/changelog.py "$T" >/dev/null
scripts/generate.sh
mkdir -p "$D"
cp jlc/$P-gerbers.zip jlc/$P-bom.csv jlc/$P-cpl.csv $P-eeprom.bin kicad/$P-schematic.pdf "$D/"
rm -rf "${D:?}/$P"
mkdir "$D/$P"
cp -R kicad/. LICENSE NOTICE "$D/$P/"
rm -f "$D/$P/$P.kicad_prl" "$D/$P/$P-schematic.pdf"
(cd "$D" && python3 -m zipfile -c "$P-kicad.zip" "$P")
rm -r "${D:?}/$P"
