#!/bin/sh
# Build the EEPROM programmer for RP2040 and RP2350 Picos and copy the UF2s to programmer/.
# --clean deletes the build folders first.
#
# The SDK is used from PICO_SDK_PATH. If not present pico-sdk $SDK_VERSION is cloned into build/pico-sdk.
# If there is no insalled picotool, the SDK builds build/picotool.
set -e
cd "$(dirname "$0")/.."
SDK_VERSION=2.2.0
case "${1:-}" in
    '') ;;
    --clean) rm -rf build/programmer-rp2040 build/programmer-rp2350 ;;
    *) echo "usage: $0 [--clean]" >&2; exit 1 ;;
esac
mkdir -p build
if [ -z "$PICO_SDK_PATH" ]; then
    PICO_SDK_PATH=$PWD/build/pico-sdk
    if [ ! -d "$PICO_SDK_PATH" ]; then
        echo "Cloning pico-sdk $SDK_VERSION into build/pico-sdk"
        rm -rf build/pico-sdk.tmp
        git clone --quiet --depth 1 --branch "$SDK_VERSION" https://github.com/raspberrypi/pico-sdk.git \
            build/pico-sdk.tmp 2>/dev/null
        mv build/pico-sdk.tmp "$PICO_SDK_PATH"
    fi
fi
for CHIP in rp2040 rp2350; do
    case $CHIP in
        rp2040) BOARD="-DPICO_BOARD=pico -DPICO_DEFAULT_BOOT_STAGE2=boot2_generic_03h" ;;
        rp2350) BOARD="-DPICO_BOARD=pico2" ;;
    esac
    B=build/programmer-$CHIP
    # A build folder configured with a different SDK, or whose configure failed, can't be configured again
    if [ "$(cat $B/sdk 2>/dev/null)" != "$PICO_SDK_PATH" ]; then
        rm -rf $B
    fi
    # shellcheck disable=SC2086
    { cmake -S programmer -B $B -DPICO_SDK_PATH="$PICO_SDK_PATH" -DPICOTOOL_FETCH_FROM_GIT_PATH="$PWD/build/picotool" \
        $BOARD && echo "$PICO_SDK_PATH" >$B/sdk && cmake --build $B -j; } >$B.log 2>&1 || { cat $B.log >&2; exit 1; }
    cp $B/programmer.uf2 programmer/$CHIP.uf2
done
