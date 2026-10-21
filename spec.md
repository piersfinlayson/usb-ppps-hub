# USB PPPS Hub – Design Spec

20 October 2026

## Overview

A 4-port USB 2.0 USB-C hi-speed hub whose downstream ports have individually switchable VBUS controlled from the host with uhubctl. It is built around a Microchip USB2514B.

- **Upstream:** 1 USB-C connector to the host.
- **Downstream:** 4 USB-C connectors, each with its own current-limited VBUS switch.
- **Power input:** 1 USB-C connector for 5 V from an external supply, for example a Raspberry Pi 4 supply (5.1 V, 3 A).
- **Power modes:** self-powered when external 5 V is present, bus-powered otherwise. Switchover is automatic.
- **Deliverables:** KiCad schematic and 4-layer PCB, assembled by JLCPCB. Parts are chosen for high JLC stock.

**Pass criteria:** `lsusb -v` prints "Per-port power switching" (wHubCharacteristics 0x0009). `uhubctl -a off -p N` removes VBUS from port N only, measured at the connector.

## Parts list

These parts are fixed. Use these LCSC numbers.

| Function | MPN | LCSC | JLC price (1), 20 Oct 2026 | Qty |
| --- | --- | --- | --- | --- |
| Hub controller | USB2514B-AEZC-TR | C16251 | $1.81 | 1 |
| Per-port VBUS switch | TPS2051BDBVR | C24593 | $0.19 | 4 |
| USB-C connector (16-pin) | TYPE-C 16PIN 2MD(073) | C2765186 | $0.07 | 6 |
| Configuration EEPROM (2 Kbit, SOT-23-5) | 24C02S (XBLW) | C18723540 | $0.03 | 1 |
| ESD protection (D+, D-, VBUS) | USBLC6-2P6 | C15999 | $0.25 | 5 |
| 3.3 V LDO | AP2112K-3.3TRG1 | C51118 | $0.18 | 1 |
| 24 MHz crystal (12 pF CL) | SX32Y024000BC1T001 | C7420736 | $0.07 | 1 |
| Reset supervisor, open drain, 2.93 V, SOT-23 | TLV803SDBZR (TI) | C132016 | $0.19 | 1 |
| Port VBUS bulk cap, 22 µF 25 V X5R, 0805 | CL21A226MAQNNNE (Samsung, NRND). Alternative: CL21A226MAYNNNE, C602037, in the schematic's LCSC alt field | C45783 | $0.19 | 4 |
| Power mux (external / upstream) | TPS2116DRLR | C3235557 | $0.40 | 1 |
| +5V bulk cap, 100 µF 25 V, 0.26 Ω, 6.3 x 5.8 mm | VZS101M1ETR-0606 (Lelon) | C249967 | $0.10 | 1 |
| Blue LED, 0603 (JLC Extended part) | XL-1608UBC-04 (XINGLIGHT) | C965807 | $0.004 | 6 |

Total for the parts above except the LEDs: $6.01 per hub, from unrounded prices. All other resistors and capacitors are generic. Pick JLC Basic parts where available.

## Power architecture

A TPS2116 power mux in priority mode feeds one 5 V rail from the external supply when present, and from upstream VBUS otherwise. Its ST output is high while the external supply is in use and drives the hub's LOCAL_PWR input.

| Net | Source | Feeds |
| --- | --- | --- |
| EXT_5V | Power-input connector VBUS | TPS2116 VIN1, MODE, PR1 divider |
| UP_VBUS | Upstream connector VBUS | TPS2116 VIN2, hub VBUS_DET divider |
| +5V | TPS2116 VOUT | 4 x TPS2051B IN, AP2112K VIN |
| +3V3 | AP2112K output | Hub VDD33/VDDA33, EEPROM, all pull-ups |

**TPS2116 connections (priority mode):**

- **VIN1:** EXT_5V, with 0.1 µF ceramic at the pin and 1 Ω in series with 22 µF ceramic to GND, which damps hot-plug ringing.
- **MODE:** tied to VIN1. This selects priority mode.
- **PR1:** divider from VIN1 to GND, 1 MΩ over 330 kΩ, plus 10 MΩ from ST to PR1 for hysteresis. PR1's threshold is 1.0 V (0.92 to 1.08 V). The mux switches to VIN2 when EXT_5V drops below about 3.8 V (3.5 to 4.1 V) and returns to VIN1 above about 4.1 V (3.8 to 4.5 V).
- **VIN2:** UP_VBUS, with 0.22 µF ceramic at the pin and 1 Ω in series with 10 µF ceramic to GND, which damps hot-plug ringing. Together they present 10.2 µF at 0 V, slightly over USB 2.0's 10 µF device limit. The 1 Ω keeps the plug-in spike below a bare 10 µF's, and the charge drawn, about 41 µC, is under the 50 µC that 10 µF at 5 V allows.
- **VOUT:** +5V, with the low-impedance 100 µF bulk cap (C249967, 0.26 Ω) plus 1 µF ceramic close to the pin.
- **ST:** open drain, 10 kΩ pull-up to +3V3, connected through 5.1 kΩ to the hub's LOCAL_PWR pin (28). High means external power is in use. The 5.1 kΩ limits the current if pin 28 drives as an output before the hub has read its EEPROM.

**Constraints:**

- **Current:** 4 ports x 500 mA plus the hub is about 2.2 A. The TPS2116's 2.5 A rating is also its absolute maximum and the board doesn't limit the total, so the ports together must stay under 2 A.
- **Inrush:** the 100 µF on +5V holds the rail up when a device is plugged into a port. When bus-powered, the TPS2116's 1.7 ms soft start keeps the plug-in current near 0.3 A, within what a host port supplies. The charge is about ten times USB 2.0's 10 µF attach limit, so the hub would fail a formal inrush test. The port caps are on the TPS2051B outputs, which are off at power-up, so they aren't charged at attach.
- **Voltage:** the board drops up to about 0.2 V from either input connector to a port at full load, through the TPS2116 and the port's TPS2051B. Plugging a device into one port dips the others by at most about 300 mV, within USB 2.0's 330 mV, mainly because the +5V bulk cap is low impedance.
- **Back-feed:** the TPS2116's reverse-current blocking stops either supply feeding the other and keeps the power-input connector unpowered when unplugged.
- **Bus-powered current:** with all four ports active the hub draws up to about 155 mA (USB2514B Table 6-4) but reports Microchip's default 100 mA in EEPROM bytes 0Dh and 0Fh. Accepted.
- **Suspend current:** when bus-powered and suspended with its ports on, the four 10 kΩ bleeds add 2 mA and the four port LEDs about 4 mA. The hub then draws about 8 mA against USB's 2.5 mA allowance for the hub itself, more if the hub-connected LED stays lit in suspend. Accepted.
- **VBUS before attach:** each downstream port gets VBUS whenever the hub enables it, not only after a sink's Rd is detected as the Type-C spec requires. Accepted. A USB-C charger on a C-to-C cable stays off because the port has Rp on CC, not Rd. An A-to-C cable from a USB-A charger or PC port joins two 5 V supplies through that port's TPS2051B.

## Hub configuration

The hub is configured from the I²C EEPROM: CFG_SEL[1:0] = 11. The EEPROM is required because automatic self/bus-powered switching (the DYNAMIC bit) can only be set through EEPROM or SMBus, not straps.

- **EEPROM address:** 1010000b (0x50). Use Microchip datasheet DS00001692.
- **Straps:** disabled in EEPROM mode. Only CFG_SEL[1:0] is sampled at reset.
- **Blank EEPROM:** leaves the hub misconfigured. Program it in-circuit before first use.
- **Programming:** hold RESET_N low to tri-state the hub's SDA/SCL, then write the EEPROM from the programming header.

**EEPROM contents.** Addresses not listed are 0x00.

| Address | Value | Meaning |
| --- | --- | --- |
| 00h-01h | 24 04 | VID 0x0424 (Microchip default) |
| 02h-03h | 14 25 | PID 0x2514 |
| 04h-05h | B3 0B | Device ID 0x0BB3 |
| 06h | 9B | Microchip default. Individual port power switching, individual over-current sensing, multi-TT, EOP generation disabled. The self-powered bit is overridden by DYNAMIC |
| 07h | A0 | DYNAMIC = 1 (automatic self/bus switching from LOCAL_PWR), over-current timer 8 ms |
| 08h | 02 | Microchip default (string descriptors off) |
| 09h | 00 | All ports removable |
| 0Ah-0Bh | 00 00 | All ports enabled |
| 0Ch | 01 | Max power, self-powered: 2 mA |
| 0Dh | 32 | Max power, bus-powered: 100 mA |
| 0Eh | 01 | Hub controller current, self-powered: 2 mA |
| 0Fh | 32 | Hub controller current, bus-powered: 100 mA |
| 10h | 32 | Port power-on time: 100 ms |
| D0h | 00 | Battery charging off on all ports |
| FAh-FCh | 00 | D+/D- not swapped, ports not remapped |

## Circuit requirements

Pin numbers are for the USB2514B 36-pin QFN.

### USB2514B

| Pin(s) | Name | Connection |
| --- | --- | --- |
| 5, 10, 15, 23, 29, 36 | VDD33 / VDDA33 | +3V3. 0.1 µF ceramic at each pin, plus 10 µF bulk nearby |
| Exposed pad | VSS | GND, with multiple vias. It is the chip's only ground |
| 14 | CRFILT | 0.1 µF low-ESR to GND |
| 34 | PLLFILT | 0.1 µF low-ESR to GND |
| 35 | RBIAS | 12.0 kΩ 1% to GND |
| 33, 32 | XTALIN, XTALOUT | 24 MHz crystal between them, with 18 pF from each pin to GND. C = 2 × CL − Cs, with C0 taken as 0 per Microchip Note 7-1. CL = 12 pF (from the LCSC listing) and Cs is about 6 to 8 pF, so C is 16 to 18 pF. A 1 MΩ across the crystal isn't fitted because the hub has one inside |
| 11 | TEST | GND |
| 26 | RESET_N | 10 kΩ pull-up to +3V3. A TLV803S open-drain supervisor, with 0.1 µF at its VDD, holds it low until +3V3 has been above 2.93 V for about 200 ms. Also to the programming header through 1 kΩ, which limits the current if a programmer drives the pin high while the supervisor holds it low |
| 27 | VBUS_DET | 100 kΩ / 100 kΩ divider from UP_VBUS |
| 24 | SCL / CFG_SEL0 | EEPROM SCL. 10 kΩ pull-up to +3V3, which also straps CFG_SEL0 = 1 |
| 22 | SDA | EEPROM SDA. 10 kΩ pull-up to +3V3 |
| 25 | HS_IND / CFG_SEL1 | 100 kΩ pull-up to +3V3, strapping CFG_SEL1 = 1. A blue LED and 330 Ω in series from +3V3 to the pin, lit while the hub is connected at high speed. With CFG_SEL1 strapped high the pin drives low when asserted (datasheet section 3.3.1.3). The LED draws 1 to 2 mA, depending on its forward voltage |
| 28 | LOCAL_PWR | From TPS2116 ST through 5.1 kΩ |
| 12, 16, 18, 20 | PRTPWR1 to PRTPWR4 | EN of each port's TPS2051B, without pull-ups |
| 13, 17, 19, 21 | OCS_N1 to OCS_N4 | FLG of each port's TPS2051B (open drain, pulled up inside the hub) |
| 2/1, 4/3, 7/6, 9/8 | USBDP/USBDM_DN1 to DN4 | Downstream connector D+/D-, without series resistors because termination is inside the hub |
| 31/30 | USBDP/USBDM_UP | Upstream connector D+/D- |

The datasheet requires +3V3 to rise in 400 µs or less (10% to 90%), and RESET_N held low at least 1 µs after supplies are valid. +3V3 follows the TPS2116's 1.7 ms soft start and takes about 1 ms to rise, so the design relies on Note 6-2, which allows up to 100 ms while RESET_N is actively driven low. The supervisor drives it low.

### Each downstream port (x4)

- **VBUS switch:** TPS2051B with IN on +5V (1 µF ceramic at IN), EN from PRTPWRn, OUT to the port's VBUS, FLG to OCS_Nn.
- **Port VBUS caps:** 0.1 µF ceramic directly on the switched VBUS, and 22 µF ceramic in series with 1 Ω to GND. The 1 Ω damps ringing with the cable, so a plug-in or a short doesn't pull VBUS below the TPS2051B's −0.3 V limit. 10 kΩ to GND makes the port's VBUS fall when it is switched off.
- **Data:** connector D+ pins A6 and B6 tied together, D- pins A7 and B7 tied together.
- **CC:** CC1 and CC2 each have 56 kΩ Rp to the port's switched VBUS (Default USB Power). With Rp tied to the switched VBUS, a switched-off port doesn't present a source.
- **ESD:** USBLC6-2P6 at the connector on D+, D- and VBUS.
- **Shell:** GND.
- **Power LED:** blue, with 2.2 kΩ from the port's switched VBUS to GND, about 1 mA. Lit while the port has power.

### Upstream connector

- **Data:** A6/B6 and A7/B7 tied as above, to USBDP_UP/USBDM_UP.
- **CC:** CC1 and CC2 each 5.1 kΩ Rd to GND.
- **VBUS:** UP_VBUS.
- **ESD:** USBLC6-2P6 at the connector.
- **Shell:** GND.

### Power-input connector

- **VBUS:** EXT_5V.
- **Supply:** must be a 5 V, 3 A USB-C supply. The board doesn't check the current a supply advertises.
- **CC:** CC1 and CC2 each 5.1 kΩ Rd to GND. A USB-C supply doesn't turn on VBUS without them.
- **Data:** D+/D- not connected.
- **Shell:** GND.
- **LED:** blue, in series with 2.2 kΩ from EXT_5V to GND, about 1 mA. Lit while a supply is plugged in.

### EEPROM (24C02S, SOT-23-5)

- **VCC:** +3V3, with 0.1 µF ceramic to GND. **GND:** GND.
- **SDA/SCL:** to hub pins 22 and 24.
- **WP:** GND, so it is always writable.

### Programming header (1 x 5)

+3V3, GND, SDA, SCL, RESET_N (through 1 kΩ) on a 2.54 mm header footprint, not fitted. Press in or solder a header to program. Power the board over USB while programming, not through the +3V3 pin. Without +5V the AP2112K switches a 60 Ω discharge resistor across its output, which would draw about 55 mA from a supply on that pin.

### 3.3 V regulator (AP2112K-3.3)

VIN from +5V, EN tied to VIN, 1 µF ceramic on input and output.

## PCB requirements

A 4-layer board on a JLC impedance-controlled stackup, with a solid ground plane on layer 2 under all USB data pairs.

- **Stackup:** JLC04161H-7628, JLC's standard 1.6 mm 4-layer stackup (7628 prepreg, 0.21 mm from L1 to L2). L1 signal, L2 solid GND, L3 power, L4 signal.
- **USB pairs:** the upstream pair and the four downstream pairs are 90 Ω differential on L1 over L2. JLC's impedance calculator for this stackup returns 11.44 mil tracks with an 8 mil gap. The project's USB net class has these values and applies to every net ending in _D+ or _D-.
- **Pair routing:** keep pairs short and length-matched within each pair, route the two traces together, avoid stubs and vias, and never cross a gap in L2.
- **ESD:** each USBLC6-2P6 at its connector pins, before anything else on the lines, with a short direct path to GND.
- **Crystal:** crystal and its load caps close to pins 32/33.
- **Decoupling:** each 0.1 µF at its VDD33/VDDA33 pin. Exposed pad via array to L2.
- **Power traces:** EXT_5V, UP_VBUS and +5V sized for 2.5 A: 40 mil, in the project's Power net class. Each port's switched VBUS sized for 1.25 A (the TPS2051B's maximum current limit): 20 mil, in the Port VBUS net class. Both widths are IPC-2221 figures for 1 oz outer copper and about a 10 °C rise. Other tracks default to 8 mil. All track widths are set in mils.
- **TPS2116:** input and output caps close to the device, and wide VIN1, VIN2, VOUT and GND traces, following the datasheet layout example.
- **Connectors:** the `usb-ppps-hub:USB_C_connector_c2765186` footprint for C2765186, from the project footprint library.
- **Silkscreen:** the board's name, copyright, version and the Git commit the Gerbers were generated from, up the right edge. https://piers.rocks up the left edge between the programming header and the bottom left mounting hole. [NOTICE](NOTICE) requires it on every board.
