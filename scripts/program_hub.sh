#!/bin/sh
# Program a hub's EEPROM using the definition in spec.md using a Pico or Pico 2 in BOOTSEL mode.
# The Pico/Pico 2 must be connected to the hub as described in the README.
# Options: --board-version vX.Y.Z and --serial <16 hex digits>.
set -e
cd "$(dirname "$0")/.."
python3 scripts/eeprom.py build
scripts/build_programmer.sh
exec python3 programmer/program.py "$@" build/usb-ppps-hub-eeprom.bin
