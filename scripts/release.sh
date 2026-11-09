#!/bin/sh
# Write the release files for tag $1 to folder $2. The tag must be VERSION, or VERSION-N for a later release for
# the same board version, and have a dated section in CHANGELOG.md.
set -e
cd "$(dirname "$0")/.."
T=$1
D=${2:-build/release}
P=usb-ppps-hub
V=$(cat VERSION)
case "$T" in
    "$V"|"$V"-[2-9]|"$V"-[1-9][0-9]) ;;
    *) echo "tag $T isn't $V or $V-N" >&2; exit 1 ;;
esac
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
rm -rf "${D:?}/case" "${D:?}/case-build"
scripts/case.sh kicad/$P.kicad_pcb "$D/case-build"
mkdir "$D/case"
cp "$D/case-build/$P-case-base.stl" "$D/case-build/$P-case-lid.stl" LICENSE NOTICE "$D/case/"
(cd "$D" && python3 -m zipfile -c "$P-case.zip" case)
rm -r "${D:?}/case" "${D:?}/case-build"
scripts/build_programmer.sh --clean
rm -rf "${D:?}/programmer"
mkdir "$D/programmer"
cp programmer/program.py programmer/rp2040.uf2 programmer/rp2350.uf2 "$D/programmer/"
(cd "$D" && python3 -m zipfile -c "$P-programmer.zip" programmer)
rm -r "${D:?}/programmer"
