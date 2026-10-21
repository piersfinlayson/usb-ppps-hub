"""Generate the USB PPPS Hub PCB from the schematic. Run with KiCad's bundled Python.

Board coordinates are in mm from the board's top left corner, y down. Blocks are laid
out in local offsets from an origin, so moving a parameter moves the block with its
routing. Routes between blocks are built from the blocks' end points.
"""
import json
import os
import sys
import tempfile

import pcbnew

from kipcb import Board, elbow, export_netlist, length, offset_polyline, read_netlist, read_title_block

PROJECT = 'usb-ppps-hub'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the project folder, above scripts/
SRC = os.path.join(ROOT, 'kicad-src')                                 # the committed KiCad project files

# ------------------------------------------------------------ parameters

BOARD_W = 75.0
BOARD_H = 50.0
CORNER_R = 1.0
HOLE_INSET = 4.0                 # mounting hole centre from each edge
HOLE_FP = 'MountingHole:MountingHole_3.2mm_M3'

PORT_PITCH = 15.0                # downstream connectors, bottom edge, centred
TOP_PITCH = 22.0                 # upstream and power input connectors, top edge, centred
HUB = (37.5, 21.0)               # USB2514B centre
MUX = (58.0, 9.5)                # TPS2116 centre
LDO = (12.0, 26.6)               # AP2112K centre, its input pins on the +5V side of the 3.3 V island's edge
HEADER = (2.5, 13.0)             # programming header pin 1
HEADER_PINS = ('3V3', 'GND', 'SDA', 'SCL', 'RST')
HEADER_LABEL_DX = 1.6            # header pin names start this far right of the pin centre
RST_DROP = 1.0                   # the RST track runs this far below its pin, clear of the pin name
EEPROM = (10.5, 9.5)             # 24C02 centre
RESET = (14.0, 20.4)             # TLV803S centre
LOCAL_PWR_RES = (24.4, 18.9)     # LOCAL_PWR series resistor, with the ST pull-up beside it
BULK = (59.0, 21.5)              # +5V 100 uF centre
ISLAND_Y = 29.0                  # +3V3 island on In2.Cu: x up to 48, y down to here
PLANE_GAP = 0.5                  # between the +5V and +3V3 pours on In2.Cu
SILK_TITLE = (69.8, 24.0)        # title centre, reading up the right edge, the copyright beside it
SILK_COPYRIGHT_DX = 2.8
SILK_VERSION = (74.14, 9.65)     # up the right edge, below the top right mounting hole
SILK_COMMIT = (74.14, 38.35)     # up the right edge, above the bottom right mounting hole
SOURCE_LOCATION = 'https://piers.rocks'   # required on products by NOTICE
SILK_SOURCE = (3.74, 34.5)       # up the left edge, centred between the edge and C21 and between J7 and H3
SILK_GAP = 6.0                   # HOST ends this far left of its connector centre, 5V IN starts this far right
PORT_LABEL_GAP = 5.2             # port numbers end this far left of their connector centre
SILK_Y = 2.6                     # connector labels are this far in from the board edge
PORT_LED = (-6.15, -1.65)        # port power LED centre from its connector origin, above the port number
PORT_LED_R_DY = -2.55            # its resistor, above it
HS_IND_Y = 15.77                 # B.Cu run of HS_IND from the hub to its LED, between UP_VBUS's link and LOCAL_PWR
SILK_EDGE = 0.3                  # footprint silk is cut back to this far inside the edge
STITCH_PITCH = 4.0               # minimum spacing of the GND vias joining the outer pours to the In1.Cu plane

CONN_FRONT = 3.675               # USB-C footprint origin to the connector's front face
USB_C_MODEL = '${KICAD9_3DMODEL_DIR}/Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step'
UP_LINK_Y = CONN_FRONT + 11.4    # upstream VBUS vias either side of J1, above R2
UP_X = BOARD_W / 2 - TOP_PITCH / 2
PWR_X = BOARD_W / 2 + TOP_PITCH / 2
PORT_Y = BOARD_H - CONN_FRONT
HS_IND_X = UP_X + PORT_LED[0]    # hub-connected LED, where HS_IND comes up to F.Cu and runs north to it
STATUS_LED_Y = BOARD_H - PORT_Y - PORT_LED[1]   # the external power and hub-connected LEDs, as far in as the port LEDs

# B.Cu tracks running across the board above the hub, as offsets from the hub centre
UP_VBUS_DY = -9.7                # upstream VBUS, upstream connector to the mux
LOCAL_PWR_DY = -4.7              # LOCAL_PWR, hub to its series resistor
ST_DY = -2.1                     # mux ST, mux to the LOCAL_PWR resistor

# vias where ports 1 and 2's PRTPWR and OCS lines leave the hub for B.Cu, as offsets from the hub centre
PORT12_VIAS = {'PRTPWR1': (4.4, 1.8), 'OCS1_N': (5.6, 2.1), 'PRTPWR2': (7.2, 2.6), 'OCS2_N': (8.0, 3.6)}

VIA = (0.6, 0.3)                 # diameter, drill
PWR_VIA = (0.8, 0.4)
SMALL_VIA = (0.5, 0.25)

# board minimums, inside JLC's 4-layer capabilities
RULES = {
    'm_MinClearance': 0.127,
    'm_TrackMinWidth': 0.127,
    'm_ViasMinSize': 0.45,
    'm_MinThroughDrill': 0.2,
    'm_ViasMinAnnularWidth': 0.12,
    'm_CopperEdgeClearance': 0.3,
    'm_HoleClearance': 0.25,
    'm_HoleToHoleMin': 0.25,
    'm_MinSilkTextHeight': 0.8,
    'm_MinSilkTextThickness': 0.15,
}

STACKUP = '''\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01524) (material "JLCPCB Soldermask") (epsilon_r 3.8) (loss_tangent 0))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "NP-155F 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "NP-155F") (epsilon_r 4.43) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "NP-155F 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01524) (material "JLCPCB Soldermask") (epsilon_r 3.8) (loss_tangent 0))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "HAL lead-free")
\t\t\t(dielectric_constraints no)
\t\t)
'''


def net_classes():
    """{class name: settings} from the project file, with Default values filled in."""
    ns = json.load(open(os.path.join(SRC, PROJECT + '.kicad_pro')))['net_settings']['classes']
    default = next(c for c in ns if c['name'] == 'Default')
    return {c['name']: dict(default, **c) for c in ns}


NC = net_classes()
W_SIG = NC['Default']['track_width']
W_USB = NC['USB']['diff_pair_width']
GAP_USB = NC['USB']['diff_pair_gap']
W_PWR = NC['Power']['track_width']
W_VBUS = NC['Port VBUS']['track_width']
PAIR_D = (W_USB + GAP_USB) / 2           # pair centreline to each track's centre


def port_x(n):
    return BOARD_W / 2 + (n - 2.5) * PORT_PITCH


def hub_y(dy):
    return HUB[1] + dy


class Frame:
    """Offsets from an origin. A flipped frame is turned 180 degrees."""

    def __init__(self, B, ox, oy, flip=False):
        self.B, self.ox, self.oy, self.s = B, ox, oy, (-1 if flip else 1)

    def L(self, dx, dy):
        return (round(self.ox + self.s * dx, 6), round(self.oy + self.s * dy, 6))

    def P(self, ref, pin):
        """A pad's centre as an offset."""
        x, y = self.B.pad(ref, pin)
        return (round(self.s * (x - self.ox), 6), round(self.s * (y - self.oy), 6))

    def at(self, ref, dx, dy, rot=0):
        self.B.place(ref, *self.L(dx, dy), (rot + (180 if self.s < 0 else 0)) % 360)

    def align(self, ref, pin, dx, dy):
        """Move a placed part so that one of its pads is at an offset."""
        self.B.move_pad_to(ref, pin, self.L(dx, dy))

    def t(self, ref, pin, w, *pts, layer='F'):
        """Track from a pad through offsets."""
        self.B.track(self.B.pad_net(ref, pin), layer, w, [self.B.pad(ref, pin)] + [self.L(*q) for q in pts])

    def tl(self, net, w, *pts, layer='F'):
        self.B.track(net, layer, w, [self.L(*q) for q in pts])

    def pp(self, ref1, pin1, ref2, pin2, w=W_SIG, straight_first=True):
        """Pad to pad, one straight and one 45 degree segment."""
        a, b = self.B.pad(ref1, pin1), self.B.pad(ref2, pin2)
        self.B.track(self.B.pad_net(ref1, pin1), 'F', w, elbow(a, b, straight_first))

    def v(self, net, dx, dy, size=VIA):
        self.B.via(net, self.L(dx, dy), *size)

    def pv(self, ref, pin, dx, dy, size=VIA, w=W_SIG):
        """Via at an offset, joined to a pad."""
        self.B.track(self.B.pad_net(ref, pin), 'F', w, elbow(self.B.pad(ref, pin), self.L(dx, dy)))
        self.v(self.B.pad_net(ref, pin), dx, dy, size)

    def pvd(self, ref, pin, ddx, ddy, size=VIA, w=W_SIG):
        """Via offset from a pad, joined to it."""
        x, y = self.P(ref, pin)
        self.pv(ref, pin, x + ddx, y + ddy, size, w)


# ------------------------------------------------------------ build

def build(out_dir):
    with tempfile.TemporaryDirectory() as tmp:
        return _build(out_dir, tmp)


def _build(out_dir, tmp):
    """Write the board to out_dir, with the netlist and DRC reports in tmp. True if a problem was printed."""
    pcbnew.KIID.SeedGenerator(1)
    sch = os.path.join(out_dir, PROJECT + '.kicad_sch')
    net_file = os.path.join(tmp, PROJECT + '.net')
    export_netlist(sch, net_file)
    comps, nets = read_netlist(net_file)
    B = Board(os.path.join(out_dir, PROJECT + '.kicad_pcb'), comps, nets, os.path.join(SRC, 'fp-lib-table'))
    ds = B.b.GetDesignSettings()
    for k, v in RULES.items():
        setattr(ds, k, pcbnew.FromMM(v))

    ports = {n: port(B, n) for n in range(1, 5)}
    up_end = upstream(B)
    power_input(B)
    mux(B)
    hub(B)
    usb_pairs(B, up_end, ports)
    port_control(B, ports)
    local_pwr(B)
    header(B)
    ldo(B)
    bulk_cap(B)
    status_leds(B)
    for ref, c in B.comps.items():
        if 'USB_C_connector' in c['footprint']:
            B.set_model(ref, USB_C_MODEL)

    missing = B.unplaced()
    if missing:
        print('UNPLACED', ' '.join(missing))

    B.outline(BOARD_W, BOARD_H, CORNER_R)
    for i, (x, y) in enumerate(((HOLE_INSET, HOLE_INSET), (BOARD_W - HOLE_INSET, HOLE_INSET),
                                (HOLE_INSET, BOARD_H - HOLE_INSET), (BOARD_W - HOLE_INSET, BOARD_H - HOLE_INSET))):
        B.board_only('H%d' % (i + 1), HOLE_FP, x, y)
    B.clip_silk(BOARD_W, BOARD_H, SILK_EDGE)
    for w in B.warnings:
        print(w)
    silkscreen(B, *read_title_block(net_file))
    zones(B)
    open(os.path.join(out_dir, PROJECT + '.kicad_dru'), 'w').write(DRC_RULES)
    B.fill(os.path.join(tmp, 'fill-drc.rpt'))
    print('STITCH %d vias' % B.stitch('GND', ('F', 'In1', 'B'), (0, 0, BOARD_W, BOARD_H), STITCH_PITCH, *VIA, 0.25))
    B.fill(os.path.join(tmp, 'fill-drc.rpt'))
    viapads = B.vias_on_pads()
    for w in viapads:
        print(w)
    B.save(STACKUP)
    pair_report(B)
    return bool(missing or B.warnings or viapads)


def silkscreen(B, title, version, copyright):
    for n in range(1, 5):
        B.text(str(n), (port_x(n) - PORT_LABEL_GAP, BOARD_H - SILK_Y), size=1.5, thickness=0.25, justify='right',
               bold=True)
    B.text('HOST', (UP_X - SILK_GAP, SILK_Y), size=1.2, thickness=0.2, justify='right')
    B.text('5V IN', (PWR_X + SILK_GAP, SILK_Y), size=1.2, thickness=0.2, justify='left')
    for n, name in enumerate(HEADER_PINS, 1):
        x, y = B.pad('J7', n)
        B.text(name, (x + HEADER_LABEL_DX, y), size=1.0, thickness=0.15, justify='left')
    x, y = SILK_TITLE
    B.text(title, (x, y), size=2.0, thickness=0.3, rot=90, bold=True)
    B.text(copyright, (x + SILK_COPYRIGHT_DX, y), size=1.2, thickness=0.18, rot=90)
    B.text(version, SILK_VERSION, size=1.0, thickness=0.15, rot=90)
    B.text('${COMMIT}', SILK_COMMIT, size=1.0, thickness=0.15, rot=90)
    B.text(SOURCE_LOCATION, SILK_SOURCE, size=1.2, thickness=0.18, rot=90)


def pair_report(B):
    """Print the track length of each USB net and the difference within each pair."""
    lengths = {}
    for t in B.b.GetTracks():
        n = t.GetNetname()
        if n.endswith('_D+') or n.endswith('_D-'):
            lengths[n] = lengths.get(n, 0) + pcbnew.ToMM(t.GetLength())
    for n in sorted(lengths):
        if n.endswith('_D+'):
            m = n[:-1] + '-'
            print('PAIR %-16s D+ %6.2f  D- %6.2f  diff %5.2f mm' % (n[:-3], lengths[n], lengths[m], lengths[n] - lengths[m]))


DRC_RULES = '''(version 1)
(rule "USB pairs clear of copper pours"
  (condition "A.hasNetclass('USB') && B.Type == 'Zone'")
  (constraint clearance (min 0.5mm)))
(rule "One spoke on outer pours"
  (layer outer)
  (condition "A.Type == 'Pad' && B.Type == 'Zone'")
  (constraint min_resolved_spokes 1))
(rule "Gap between In2.Cu pours"
  (layer In2.Cu)
  (condition "A.Type == 'Zone' && B.Type == 'Zone'")
  (constraint clearance (min %gmm)))
''' % PLANE_GAP


def zones(B):
    edge = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    B.zone('GND', 'In1', edge, name='GND plane')
    B.zone('GND', 'F', edge, clearance=0.25, name='GND top')
    B.zone('GND', 'B', edge, clearance=0.25, name='GND bottom')
    B.zone('+5V', 'In2', edge, name='+5V plane')
    island = [(0, 0), (48.0, 0), (48.0, ISLAND_Y), (0, ISLAND_Y)]
    B.zone('+3V3', 'In2', island, priority=1, name='+3V3 island')


# ------------------------------------------------------------ connectors

def usb_c_data(F, j, esd):
    """USB-C data pins and their flow-through ESD, in connector offsets where the board's
    interior is negative y.

    The pair leaves from B7 and A6. A7 joins B7 under the connector body and B6 joins A6 behind
    the pins. The ESD's pin 1 is in line with B7. Returns where the pair leaves the ESD.
    """
    ex, ey = -0.213, -8.0
    F.at(esd, ex, ey, 90)
    F.t(j, 'B7', W_USB, (-0.75, -7.15))
    F.t(j, 'A6', W_USB, (-0.25, -4.6), (-0.25, -5.0), (0.324, -5.574), (0.324, -7.15))
    F.t(j, 'A7', W_SIG, (0.25, -2.75), (-0.75, -2.75), (-0.75, -3.67))
    F.t(j, 'B6', W_SIG, (0.75, -4.6), (-0.25, -4.6))
    F.t(esd, 6, W_USB, (-0.75, -9.4), (ex - PAIR_D, -9.69))
    F.t(esd, 4, W_USB, (0.324, -9.4), (ex + PAIR_D, -9.69))
    # VBUS and GND pins leave under the package between the data pins
    F.t(esd, 5, W_SIG, (ex, ey - 0.35), (ex + 0.35, ey), (3.2, ey))
    F.t(esd, 2, W_SIG, (ex, ey + 0.35), (ex - 0.35, ey), (ex - 1.6, ey))
    F.v('GND', ex - 1.6, ey)
    # shell, and each VBUS pin pair joined at its middle
    F.t(j, 'A1', 0.4, (-4.32, -3.67))
    F.t(j, 'A12', 0.4, (4.32, -3.67))
    for a, b, x in (('A4', 'B9', -2.4), ('A9', 'B4', 2.4)):
        F.t(j, a, W_SIG, (x, -3.67))
        F.t(j, b, W_SIG, (x, -3.67))
    return F.L(ex, -9.69)


def port(B, n):
    """Downstream port n. PRTPWR and OCS reach ports 1 to 3 on B.Cu through vias and port 4 on F.Cu."""
    F = Frame(B, port_x(n), PORT_Y)
    j, esd, sw = 'J%d' % (2 + n), 'U%d' % (9 + n), 'U%d' % (4 + n)
    cin, cbulk, chf = 'C%d' % (17 + 3 * n), 'C%d' % (18 + 3 * n), 'C%d' % (19 + 3 * n)
    rser, rbleed = 'R%d' % (32 + n), 'R%d' % (23 + n)
    rcc1, rcc2 = 'R%d' % (14 + 2 * n), 'R%d' % (15 + 2 * n)

    F.at(j, 0, 0)
    top = usb_c_data(F, j, esd)
    vbus = B.pad_net(j, 'A4')
    F.at(rcc1, -3.675, -5.8, 0)
    F.at(rcc2, 1.75, -6.375, 270)
    F.at(chf, -3.2, -7.5, 90)
    F.align(chf, 2, -3.2, -8.0)
    F.at(rbleed, -5.8, -7.0, 90)
    F.at(rser, -5.9, -9.225, 180)
    F.at(cbulk, -6.7, -11.6, 90)
    F.align(cbulk, 1, F.P(rser, 2)[0], -10.8)
    F.at(sw, 5.1, -9.6, 90)
    F.at(cin, 2.4, -10.7, 180)
    F.align(cin, 1, F.P(sw, 5)[0] - 1.27, F.P(sw, 5)[1])
    # CC pull-ups to the port's VBUS
    y1 = F.P(rcc1, 2)[1]
    F.t(j, 'A5', W_SIG, (-1.25, y1 + 0.6), (-1.85, y1), F.P(rcc1, 2))
    F.t(j, 'B5', W_SIG, (1.75, F.P(rcc2, 2)[1]))
    # VBUS: left pins to the caps, right pins to the switch, joined on B.Cu
    xl = F.P(rcc1, 1)[0]
    F.tl(vbus, W_VBUS, (-2.4, -3.67), (-2.4, -4.8), (xl, -4.8), (xl, F.P(rcc1, 1)[1]), (xl, F.P(rbleed, 1)[1]),
         (xl, F.P(chf, 1)[1]), (xl, -8.15), (xl, F.P(rser, 1)[1]), (xl, -10.1))
    yo = F.P(sw, 1)[1]
    F.tl(vbus, W_VBUS, (2.4, -3.67), (2.4, -4.6), (3.2, -5.4), (3.2, -6.3), (3.2, F.P(rcc2, 1)[1]), (3.2, -7.6),
         (3.2, -8.0), (3.2, yo), F.P(sw, 1))
    for ref, w in ((rbleed, W_SIG), (chf, W_SIG), (rser, W_VBUS)):
        F.t(ref, 1, w, (xl, F.P(ref, 1)[1]))
    F.t(rcc2, 1, W_SIG, (3.2, F.P(rcc2, 1)[1]))
    for q in ((xl, -8.15), (xl, -10.1), (3.2, -6.3), (3.2, -7.6)):
        F.v(vbus, *q)
    F.tl(vbus, W_VBUS, (xl, -8.15), (xl, -10.1), (2.0, -10.1), (3.2, -8.9), (3.2, -6.3), layer='B')
    # 0.1 uF, bleed resistor and the 1R + 22 uF snubber
    F.t(chf, 2, W_SIG, (-1.813, -8.0))
    F.pvd(rbleed, 2, -1.0, 0)
    F.pp(rser, 2, cbulk, 1, W_VBUS)
    F.pvd(cbulk, 2, 1.1, 0)
    # switch
    F.pv(sw, 2, F.P(sw, 2)[0], -7.3)
    F.t(sw, 5, W_VBUS, (F.P(sw, 5)[0], -12.1))
    F.v('+5V', F.P(sw, 5)[0], -12.1, PWR_VIA)
    F.pp(cin, 1, sw, 5)
    F.pvd(cin, 2, 0, -1.0)
    # power LED above the port number, fed from the VBUS track
    led, rled = 'D%d' % n, 'R%d' % (36 + n)
    lx, ly = PORT_LED
    F.at(rled, lx, ly + PORT_LED_R_DY, 270)
    F.at(led, lx, ly, 90)
    B.track(vbus, 'F', W_SIG, elbow(B.pad(rled, 1), F.L(xl, -5.3), False))
    F.pp(rled, 2, led, 2)
    F.pvd(led, 1, -1.2, 0)
    if n == 4:
        return {'pair': top, 'en': B.pad(sw, 4), 'oc': B.pad(sw, 3)}
    F.pv(sw, 4, F.P(sw, 4)[0], -12.0)
    F.pv(sw, 3, F.P(sw, 3)[0], -7.3)
    return {'pair': top, 'en': F.L(F.P(sw, 4)[0], -12.0), 'oc': F.L(F.P(sw, 3)[0], -7.3)}


def upstream(B):
    """Upstream connector on the top edge. Its VBUS runs to the mux on B.Cu."""
    F = Frame(B, UP_X, CONN_FRONT, flip=True)
    F.at('J1', 0, 0)
    end = usb_c_data(F, 'J1', 'U9')
    vbus = 'UP_VBUS'
    # CC: Rd to ground
    F.at('R14', -3.4, -6.4, 180)
    F.t('J1', 'A5', W_SIG, (-1.25, -5.8), (-1.85, -6.4), F.P('R14', 1))
    F.pvd('R14', 2, 0, -0.9)
    F.at('R15', 1.75, -5.9, 90)
    F.t('J1', 'B5', W_SIG, F.P('R15', 1))
    F.pvd('R15', 2, 0, -0.8)
    # VBUS: the pins nearest the hub run on to R2 and the B.Cu track to the mux,
    # the other pins and the ESD join them through B.Cu
    y_bus = hub_y(UP_VBUS_DY)
    y_link = UP_LINK_Y
    F.tl(vbus, W_VBUS, (-2.4, -3.67), (-2.4, -5.1))
    F.tl(vbus, W_PWR, (-2.4, -5.1), (-5.6, -5.1), (-5.6, CONN_FRONT - y_bus))
    F.tl(vbus, W_VBUS, (-5.6, CONN_FRONT - y_bus), (-5.6, CONN_FRONT - y_link))
    F.tl(vbus, W_VBUS, (2.4, -3.67), (2.4, -4.6), (3.2, -5.4), (3.2, -8.0), (3.2, CONN_FRONT - y_link))
    a, b, c = F.L(-5.6, CONN_FRONT - y_bus), F.L(-5.6, CONN_FRONT - y_link), F.L(3.2, CONN_FRONT - y_link)
    B.via(vbus, a, *PWR_VIA)
    B.via(vbus, b, *VIA)
    B.via(vbus, c, *VIA)
    B.track(vbus, 'B', W_VBUS, [c, b])
    # hot-plug snubber, between the top connectors
    x0, y0 = F.L(-5.6, -5.1)
    B.place('R31', x0 + 1.5, y0, 0)
    B.move_pad_to('R31', 1, (x0 + 0.7, y0))
    B.place('C33', x0 + 2.3, y0 - 2.4, 90)
    B.move_pad_to('C33', 1, (B.pad('R31', 2)[0], y0 - 1.7))
    B.track(vbus, 'F', W_SIG, [(x0, y0), B.pad('R31', 1)])
    F.pp('R31', 2, 'C33', 1)
    F.pvd('C33', 2, 0, 0.95)
    return end


def power_input(B):
    """Power input connector on the top edge. Its VBUS pin pairs join behind it, around the CC pull-downs."""
    F = Frame(B, PWR_X, CONN_FRONT, flip=True)
    F.at('J2', 0, 0)
    for a, b, x in (('A4', 'B9', -2.4), ('A9', 'B4', 2.4)):
        F.t('J2', a, W_SIG, (x, -3.67))
        F.t('J2', b, W_SIG, (x, -3.67))
    F.t('J2', 'A1', 0.4, (-4.32, -3.67))
    F.t('J2', 'A12', 0.4, (4.32, -3.67))
    y_mux = CONN_FRONT - (MUX[1] + 0.25)
    F.tl('EXT_5V', W_VBUS, (-2.4, -3.67), (-2.4, y_mux), (-2.4, -7.9), (2.4, -7.9), (2.4, -5.625), (2.4, -3.67))
    F.at('R12', -1.25, -5.75, 90)
    F.at('R13', 1.6, -5.75, 90)
    F.t('J2', 'A5', W_SIG, F.P('R12', 1))
    F.t('J2', 'B5', W_SIG, (1.75, -4.6), (1.6, -4.75), F.P('R13', 1))
    yg = F.P('R12', 2)[1]
    F.t('R12', 2, W_SIG, (0.15, yg))
    F.t('R13', 2, W_SIG, (0.15, yg))
    F.v('GND', 0.15, yg)
    # hot-plug snubber, between the top connectors
    x0, y0 = F.L(2.4, -5.625)
    B.place('R30', x0 - 3.8, y0, 180)
    B.move_pad_to('R30', 1, (x0 - 3.0, y0))
    B.place('C32', x0 - 4.6, y0 - 2.4, 90)
    B.move_pad_to('C32', 1, (B.pad('R30', 2)[0], y0 - 1.7))
    B.track('EXT_5V', 'F', W_SIG, [(x0, y0), B.pad('R30', 1)])
    F.pp('R30', 2, 'C32', 1)
    F.pvd('C32', 2, 0, 0.95)


# ------------------------------------------------------------ power

def mux(B):
    """TPS2116 laid out as TI's example: VOUT out through the top end, VIN1 to MODE under the package."""
    F = Frame(B, *MUX)
    F.at('U3', 0, 0, 0)
    # under the package
    F.t('U3', 2, 0.3, F.P('U3', 7))
    F.t('U3', 3, W_SIG, (0, 0.25), (0, 0.75), F.P('U3', 5))
    # VOUT up to its 1 uF and the +5V plane
    F.at('C16', -2.0, -2.5, 90)
    yc = F.P('C16', 1)[1]
    F.tl('+5V', 0.4, (0, -0.25), (0, -1.9))
    F.tl('+5V', W_PWR, (0, -1.9), (0, yc), (0, -3.8))
    F.t('C16', 1, W_SIG, (0, yc))
    F.pvd('C16', 2, 0, -0.95)
    for dx in (-0.8, 0.8):
        F.v('+5V', dx, -3.8, PWR_VIA)
    F.tl('+5V', W_PWR, (-0.8, -3.8), (0.8, -3.8))
    # GND
    F.pv('U3', 1, -1.7, F.P('U3', 1)[1])
    # VIN1 from the power input connector, with its 0.1 uF, and the PR1 divider and hysteresis resistor
    F.at('C14', -3.4, -0.9, 90)
    F.at('R9', -2.4, 1.5, 0)
    F.at('R10', -2.8, 3.3, 180)
    F.at('R29', 0.2, 3.8, 180)
    x14, x9 = F.P('C14', 1)[0], F.P('R9', 1)[0]
    F.tl('EXT_5V', W_PWR, (PWR_X + 2.4 - MUX[0], 0.25), (x14, 0.25), (x9, 0.25), (-2.8, 0.25))
    F.tl('EXT_5V', 0.3, (-2.8, 0.25), (-0.9, 0.25))
    F.t('C14', 1, W_SIG, (x14, 0.25))
    F.pvd('C14', 2, 0, -0.85)
    F.t('R9', 1, W_SIG, (x9, 0.25))
    ypr = F.P('R29', 2)[1]
    F.t('U3', 4, W_SIG, (-1.4, 0.75), (-1.4, F.P('R9', 2)[1]), (-1.4, ypr), F.P('R29', 2))
    F.t('R9', 2, W_SIG, (-1.4, F.P('R9', 2)[1]))
    F.t('R10', 1, W_SIG, (-1.4, F.P('R10', 1)[1]))
    F.pvd('R10', 2, -0.8, 0)
    # ST round the right side to R29, and to B.Cu for the LOCAL_PWR resistor
    st = B.pad_net('U3', 8)
    F.t('U3', 8, W_SIG, (3.7, F.P('U3', 8)[1]), (3.7, ypr), F.P('R29', 1))
    F.v(st, 3.7, ypr)
    # VIN2 from the upstream connector on B.Cu, with its 0.22 uF
    F.v('UP_VBUS', 2.5, 0.25, PWR_VIA)
    F.tl('UP_VBUS', W_PWR, (2.5, 0.25), (1.8, 0.25))
    F.tl('UP_VBUS', 0.3, (1.8, 0.25), (0.9, 0.25))
    y_bus = hub_y(UP_VBUS_DY) - MUX[1]
    F.tl('UP_VBUS', W_PWR, (UP_X + 5.6 - MUX[0], y_bus), (2.5 - (y_bus - 0.25), y_bus), (2.5, 0.25), layer='B')
    F.at('C15', 2.5, 2.05, 270)
    F.t('C15', 1, W_VBUS, (2.5, 0.25))
    F.pvd('C15', 2, -0.95, 0)


def status_leds(B):
    """External power and hub-connected LEDs beside their connectors, under 5V IN and HOST, as far from
    the edge as the port LEDs. Each runs anode to cathode then through its resistor."""
    ly = STATUS_LED_Y
    hp = 0.7875                                  # LED pad centre from the LED centre
    # external power: EXT_5V up from its track to the mux into the anode, the resistor beside it under 5V IN
    # because C14 is below
    x = PWR_X - PORT_LED[0]
    B.place('D5', x, ly, 270)
    B.place('R41', x + 1.7, ly - hp, 0)
    B.track('EXT_5V', 'F', W_SIG, elbow((PWR_X + 5.15, MUX[1] + 0.25), B.pad('D5', 2)))
    B.track(B.pad_net('D5', 1), 'F', W_SIG, [B.pad('D5', 1), B.pad('R41', 1)])
    g = B.pad('R41', 2)
    B.track('GND', 'F', W_SIG, [g, (g[0] + 0.95, g[1])])
    B.via('GND', (g[0] + 0.95, g[1]), *VIA)
    # hub connected: +3V3 into the anode, the resistor below it to HS_IND, which the hub pulls low,
    # with HS_IND's strap pull-up beside it
    x = HS_IND_X
    B.place('D6', x, ly, 90)
    B.place('R42', x, ly - PORT_LED_R_DY, 270)
    B.place('R7', x - 1.4, ly - PORT_LED_R_DY, 270)
    v33 = (x - 1.4, ly - hp)
    B.via('+3V3', v33, *VIA)
    B.track('+3V3', 'F', W_SIG, [B.pad('D6', 2), v33, B.pad('R7', 1)])
    B.track(B.pad_net('D6', 1), 'F', W_SIG, [B.pad('D6', 1), B.pad('R42', 1)])
    hs = B.pad_net('U1', 25)
    hx, hy = HUB
    x0, y0 = hx - 1.7, hy - 6.4
    B.track(hs, 'B', W_SIG, [(x0, y0), (x0, HS_IND_Y), (x, HS_IND_Y)])
    B.via(hs, (x, HS_IND_Y), *VIA)
    B.track(hs, 'F', W_SIG, [(x, HS_IND_Y), B.pad('R42', 2), B.pad('R7', 2)])


def bulk_cap(B):
    """+5V 100 uF, on the planes between the mux and the ports. Each pad has two vias beside it."""
    F = Frame(B, *BULK)
    F.at('C17', 0, 0, 0)
    for pin in (1, 2):
        for dy in (-1.45, 1.45):
            F.pvd('C17', pin, 0, dy, PWR_VIA, W_PWR)


def ldo(B):
    """AP2112K on the edge of the 3.3 V island: input pins towards +5V, output towards +3V3."""
    F = Frame(B, *LDO)
    F.at('U4', 0, 0, 90)
    yin = F.P('U4', 1)[1] + 1.1
    F.t('U4', 1, W_VBUS, (F.P('U4', 1)[0], yin + 1.1))
    F.v('+5V', F.P('U4', 1)[0], yin + 1.1, PWR_VIA)
    F.t('U4', 3, W_SIG, (F.P('U4', 3)[0], yin), (F.P('U4', 1)[0], yin))
    F.at('C18', -2.4, yin, 180)
    F.align('C18', 1, F.P('U4', 1)[0] - 1.0, yin)
    F.t('C18', 1, W_SIG, (F.P('U4', 1)[0], yin))
    F.pvd('C18', 2, 0, 0.9)
    F.pv('U4', 2, 0, 0, SMALL_VIA)
    F.at('C19', -2.6, -1.137, 180)
    F.align('C19', 1, F.P('U4', 5)[0] - 1.32, F.P('U4', 5)[1])
    F.pp('U4', 5, 'C19', 1, W_VBUS)
    F.pvd('U4', 5, 0, -1.2, PWR_VIA, W_VBUS)
    F.pvd('C19', 2, 0, 0.95)


# ------------------------------------------------------------ hub

def hub(B):
    """USB2514B with its decoupling, crystal and strap resistors. Offsets are from the chip centre."""
    F = Frame(B, *HUB)
    F.at('U1', 0, 0, 90)
    # pin 11 TEST to the exposed pad
    F.t('U1', 11, W_SIG, (1.7, 1.5))

    # bottom side: pin 5 between DN2 and DN3, through C1 to its via
    F.at('C1', 0, 6.3, 0)
    c1 = F.P('C1', 1)
    F.t('U1', 5, W_SIG, (0, c1[1] - 0.8), (c1[0], c1[1] - 0.32), c1)
    F.pvd('C1', 1, 0, 0.9)
    F.pvd('C1', 2, 0, 0.9)

    # left side, top: LOCAL_PWR drops to B.Cu, VDDA33 pin 29 to C5
    F.t('U1', 28, W_SIG, (-3.2, -2.0), (-3.2, -3.3))
    F.v('LOCAL_PWR', -3.2, -3.3, SMALL_VIA)
    F.at('C5', -4.0, -3.6, 90)
    F.t('U1', 29, W_SIG, (F.P('C5', 1)[0], -1.5), F.P('C5', 1))
    F.pvd('C5', 1, -0.9, 0)
    F.pvd('C5', 2, -0.9, 0)

    # crystal, turned so XTALOUT reaches pin 3 through the gap between the pad rows
    F.at('Y1', -8.0, 0.0, 90)
    x3 = F.P('Y1', 3)
    F.t('U1', 32, W_SIG, (x3[0], 0.0), x3)
    x1 = F.P('Y1', 1)
    F.t('U1', 33, W_SIG, (-4.6, 0.5), (-4.6 - (x1[1] - 0.5), x1[1]), x1)
    F.at('R8', -5.65, 0.62, 90)
    F.t('R8', 2, W_SIG, (F.P('R8', 2)[0], 0.0))
    F.t('R8', 1, W_SIG, (F.P('R8', 1)[0], x1[1]))
    F.at('C10', -7.15, 3.15, 270)
    F.align('C10', 1, x1[0], 2.67)
    F.pp('C10', 1, 'Y1', 1)
    F.at('C11', -8.85, -3.15, 90)
    F.align('C11', 1, x3[0], -2.67)
    F.pp('C11', 1, 'Y1', 3)
    F.pvd('C11', 2, -0.9, 0)
    F.pvd('Y1', 2, 1.15, 0)
    F.pvd('Y1', 4, -1.05, 0)

    # left side, bottom: PLLFILT, RBIAS and VDDA33 pin 36 turn west under the crystal
    F.at('C9', -5.2, 3.0, 180)
    F.at('R1', -5.2, 4.1, 0)
    F.align('R1', 1, F.P('C9', 2)[0], 4.1)
    F.at('C6', -6.2, 5.3, 180)
    F.t('U1', 34, W_SIG, (-4.15, 1.0), (-4.15, 2.6), (-4.55, 3.0), F.P('C9', 1))
    F.t('U1', 35, W_SIG, (-3.7, 1.5), (-3.7, 3.65), (-4.15, 4.1), F.P('R1', 2))
    F.t('U1', 36, W_SIG, (-3.2, 2.0), (-3.2, 4.4), (-4.1, 5.3), (-4.75, 5.3), F.P('C6', 1))
    F.v('+3V3', -4.75, 5.3)
    F.tl('GND', W_SIG, F.P('C9', 2), F.P('R1', 1), (-6.5, 4.1))
    F.v('GND', -6.5, 4.1)
    F.t('C10', 2, W_SIG, (F.P('C10', 2)[0], 4.1), (-6.5, 4.1))
    F.pvd('C6', 2, -0.82, 0)

    # right side: 17 and 16 run east over the caps and down to B.Cu, 12 and 13 to B.Cu
    # beside C2, 18 joins 19 to 21 north-east
    ox, oy = PORT12_VIAS['OCS2_N']
    F.t('U1', 17, W_SIG, (3.65, -1.5), (3.95, -1.8), (ox, -1.8), (ox, oy))
    F.v('OCS2_N', ox, oy)
    px, py = PORT12_VIAS['PRTPWR2']
    F.t('U1', 16, W_SIG, (3.8, -1.0), (4.1, -1.3), (px, -1.3), (px, py))
    F.v('PRTPWR2', px, py)
    F.at('C3', 6.0, -0.5, 0)
    F.t('U1', 15, W_SIG, (4.75, -0.5), F.P('C3', 1))
    F.v('+3V3', 4.75, -0.5)
    F.at('C8', 6.0, 0.5, 0)
    F.t('U1', 14, W_SIG, (4.3, 0.0), (4.8, 0.5), F.P('C8', 1))
    F.pp('C3', 2, 'C8', 2)
    F.pvd('C8', 2, 0, 0.95)
    F.t('U1', 13, W_SIG, (4.0, 0.5), PORT12_VIAS['OCS1_N'])
    F.v('OCS1_N', *PORT12_VIAS['OCS1_N'])
    F.t('U1', 12, W_SIG, (3.6, 1.0), PORT12_VIAS['PRTPWR1'])
    F.v('PRTPWR1', *PORT12_VIAS['PRTPWR1'])
    F.at('C2', 3.85, 3.6, 270)
    c2 = F.P('C2', 1)
    F.t('U1', 10, W_SIG, (3.35, 2.0), (c2[0], 2.0 + c2[0] - 3.35), c2)
    F.pvd('C2', 1, 0.9, 0)
    F.pvd('C2', 2, 0.82, 0.82)
    F.at('C7', 10.6, 1.0, 0)
    F.pvd('C7', 1, -0.9, 0)
    F.pvd('C7', 2, 0.9, 0)

    # top side, east: port 3 and 4 control fans out north-east, then runs east on F.Cu
    F.t('U1', 21, W_SIG, (1.0, -4.15), (3.35, -6.5))
    F.t('U1', 20, W_SIG, (1.5, -3.8), (3.7, -6.0))
    F.t('U1', 19, W_SIG, (2.0, -3.45), (4.05, -5.5))
    F.t('U1', 18, W_SIG, (3.5, -2.0), (6.5, -5.0))
    # top side, middle: SDA and SCL to B.Cu, pin 23 through its via to C4
    F.t('U1', 22, W_SIG, (0.5, -4.3), (0.9, -4.7), (0.9, -8.5))
    F.v('SDA', 0.9, -8.5)
    F.t('U1', 24, W_SIG, (-0.5, -4.3), (-0.9, -4.7), (-0.9, -7.8))
    F.v('SCL', -0.9, -7.8)
    F.at('C4', 0, -6.5, 90)
    F.t('U1', 23, W_SIG, (0, -5.0), F.P('C4', 1))
    F.v('+3V3', 0, -5.0)
    F.pv('C4', 2, 0, -7.8)
    # top side, west: HS_IND strap, RESET_N to B.Cu, VBUS_DET divider
    F.t('U1', 25, W_SIG, (-1.0, -3.65), (-1.7, -4.35), (-1.7, -6.4))
    F.v(B.pad_net('U1', 25), -1.7, -6.4)
    F.t('U1', 26, W_SIG, (-1.5, -3.55), (-2.4, -4.45), (-2.4, -7.1))
    F.v('RESET_N', -2.4, -7.1)
    F.at('R3', -3.2, -5.6, 90)
    r3 = F.P('R3', 1)
    F.at('R2', -4.92, r3[1], 0)
    F.align('R2', 1, UP_X + 5.6 - HUB[0], r3[1])
    F.t('U1', 27, W_SIG, (-2.0, -3.45), (-3.2, -4.65), r3)
    F.pp('R2', 2, 'R3', 1)
    F.pvd('R3', 2, -0.9, 0)
    B.track('UP_VBUS', 'F', W_VBUS, elbow((UP_X + 5.6, UP_LINK_Y), B.pad('R2', 1)))


def usb_pairs(B, up_end, ports):
    """Upstream and downstream pairs between the connectors' ESDs and the hub."""
    hx, hy = HUB
    edge = hy + 3.35                        # outer end of the hub's bottom pads

    def pair(n_net, p_net, pts, p_left):
        d = PAIR_D if p_left else -PAIR_D
        a, b = offset_polyline(pts, d), offset_polyline(pts, -d)
        B.track(p_net, 'F', W_USB, a, chamfer=0)
        B.track(n_net, 'F', W_USB, b, chamfer=0)
        return b, a

    def stub(ref, pin, q):
        B.track(B.pad_net(ref, pin), 'F', W_USB, [B.pad(ref, pin), q], chamfer=0)

    # upstream: diagonally down from the ESD, then east into pins 30 and 31
    x0, y0 = up_end
    yc, xe = hy - 0.75, hx - 4.287
    n, p = pair('UP_D-', 'UP_D+', [(x0, y0), (x0, yc - (xe - x0)), (xe, yc), (hx - 3.35, yc)], False)
    stub('U1', 30, n[-1])
    stub('U1', 31, p[-1])
    # downstream: (hub D- pin, straight length below the pins, lane below the hub or None)
    lanes = {1: (1, 0.65, 6.5), 2: (3, 1.65, None), 3: (6, 1.65, None), 4: (8, 0.65, 6.5)}
    for k, (pin, bend, lane) in lanes.items():
        xs = hx - 2.0 + 0.5 * (pin - 1) + 0.25
        xp, ye = ports[k]['pair']
        s = 1 if xp > xs else -1
        pts = [(xs, edge), (xs, edge + bend)]
        yb = edge + bend
        if lane is None:
            pts.append((xp, yb + abs(xp - xs)))
        else:
            ly = hy + lane
            pts += [(xs + s * (ly - yb), ly), (xp - s * 3.0, ly), (xp, ly + 3.0)]
        pts.append((xp, ye))
        n, p = pair('DN%d_D-' % k, 'DN%d_D+' % k, pts, True)
        stub('U1', pin, n[0])
        stub('U1', pin + 1, p[0])


# ------------------------------------------------------------ control lines

def port_control(B, ports):
    """PRTPWR and OCS from the hub to each port's switch.

    Ports 1 and 2 run on B.Cu from vias at the hub's right side, nested so they don't cross.
    Ports 3 and 4 run east on F.Cu above the hub. Port 3 drops to B.Cu before DN4's lane.
    """
    hx, hy = HUB
    # ports 1 and 2: south from the vias, west below the hub, south to the switch
    for net, lane, (x, y) in (
            ('PRTPWR1', 8.1, ports[1]['en']),
            ('OCS1_N', 8.8, ports[1]['oc']),
            ('PRTPWR2', 9.5, ports[2]['en']),
            ('OCS2_N', 10.2, ports[2]['oc'])):
        vx, vy = hx + PORT12_VIAS[net][0], hy + PORT12_VIAS[net][1]
        if net == 'PRTPWR1':
            pts = [(vx, vy), (vx - 0.4, vy + 0.4), (vx - 0.4, hy + lane)]
        else:
            pts = [(vx, vy), (vx, hy + lane)]
        xl = x if net.startswith('PRTPWR') else x + 0.85
        pts += [(xl, hy + lane), (xl, y)]
        if xl != x:
            pts.append((x, y))
        B.track(net, 'B', W_SIG, pts)
    # ports 3 and 4: east legs from the fan's ends.
    for net, start, (x, y), off in (('OCS4_N', (3.35, -6.5), ports[4]['oc'], 0.85),
                                    ('PRTPWR4', (3.7, -6.0), ports[4]['en'], 0.0),
                                    ('OCS3_N', (4.05, -5.5), ports[3]['oc'], 1.05),
                                    ('PRTPWR3', (6.5, -5.0), ports[3]['en'], 0.0)):
        sx, sy = hx + start[0], hy + start[1]
        xd = x + off
        if net[-3:-2] == '4' or net.endswith('4'):
            pts = [(sx, sy), (xd, sy), (xd, y)]
            if off:
                pts.append((x, y))
            B.track(net, 'F', W_SIG, pts)
        else:
            yv = hy + 4.0 + off
            B.track(net, 'F', W_SIG, [(sx, sy), (xd, sy), (xd, yv)])
            B.via(net, (xd, yv), *VIA)
            pts = [(xd, yv), (xd, y)]
            if off:
                pts.append((x, y))
            B.track(net, 'B', W_SIG, pts)


def local_pwr(B):
    """The hub's LOCAL_PWR and the mux's ST meet at R28, west of the hub."""
    hx, hy = HUB
    st = B.pad_net('U3', 8)
    rx, ry = LOCAL_PWR_RES
    B.place('R28', rx, ry, 180)
    r1 = B.pad('R28', 1)
    B.place('R11', r1[0] + 1.0, ry - 1.3, 270)
    B.move_pad_to('R11', 2, (r1[0] + 1.0, ry - 0.8))
    # ST from the mux on B.Cu
    mx, my = MUX
    ys = hy + ST_DY
    ystart = B.pad('R29', 1)[1]
    B.track(st, 'B', W_SIG, [(mx + 3.7, ystart), (mx + 3.7, ys), (r1[0] + 1.0, ys)])
    B.via(st, (r1[0] + 1.0, ys), *VIA)
    B.track(st, 'F', W_SIG, [(r1[0] + 1.0, ys), r1])
    B.track(st, 'F', W_SIG, [B.pad('R11', 2), (r1[0] + 1.0, ys)])
    q = B.pad('R11', 1)
    B.track('+3V3', 'F', W_SIG, [q, (q[0] + 0.8, q[1])])
    B.via('+3V3', (q[0] + 0.8, q[1]), *VIA)
    # LOCAL_PWR to the hub on B.Cu
    yl = hy + LOCAL_PWR_DY
    r2 = B.pad('R28', 2)
    B.track('LOCAL_PWR', 'F', W_SIG, [r2, (r2[0] - 0.9, ry)])
    B.via('LOCAL_PWR', (r2[0] - 0.9, ry), *VIA)
    B.track('LOCAL_PWR', 'B', W_SIG, [(r2[0] - 0.9, ry), (r2[0] - 0.9, yl), (hx - 3.2, yl), (hx - 3.2, hy - 3.3)])


def header(B):
    """Programming header on the left edge, with the EEPROM, I2C pull-ups and reset supervisor.
    SDA, SCL and RESET_N arrive on B.Cu from vias above the hub and run into the header's pins."""
    hx, hy = HUB
    jx, jy = HEADER
    B.place('J7', jx, jy, 0)
    pin = {n: B.pad('J7', n) for n in range(1, 6)}
    # west along B.Cu, then south and into the header, the northern line turning furthest west
    start = {'SDA': (hx + 0.9, hy - 8.5), 'SCL': (hx - 0.9, hy - 7.8), 'RESET_N': (hx - 2.4, hy - 7.1)}
    turn = {'SDA': jx + 1.8, 'SCL': jx + 2.5, 'RESET_N': jx + 7.1}
    for net, n in (('SDA', 3), ('SCL', 4)):
        sx, sy = start[net]
        B.track(net, 'B', W_SIG, [(sx, sy), (turn[net], sy), (turn[net], pin[n][1]), pin[n]])
    # EEPROM north of the bus lines, its SDA and SCL dropping to them through vias
    ex, ey = EEPROM
    F = Frame(B, ex, ey)
    F.at('U2', 0, 0, 90)
    for net, n in (('SDA', 3), ('SCL', 1)):
        u = F.P('U2', n)
        F.t('U2', n, W_SIG, (u[0], 2.5), (u[0], start[net][1] - ey))
        F.v(net, u[0], start[net][1] - ey)
    F.pvd('U2', 2, 0, 1.0)
    F.t('U2', 5, W_SIG, (F.P('U2', 5)[0], -2.0), (0, -2.0))
    F.v('GND', 0, -2.0)
    F.at('C13', 2.9, F.P('U2', 4)[1], 0)
    F.align('C13', 1, F.P('U2', 4)[0] + 1.47, F.P('U2', 4)[1])
    F.pp('U2', 4, 'C13', 1)
    F.pvd('U2', 4, 0, -1.0)
    F.pvd('C13', 2, 0, -1.0)
    # pull-ups beside the EEPROM's bus stubs
    for ref, n, dx in (('R6', 3, 1.4), ('R5', 1, -1.4)):
        u = F.P('U2', n)
        F.at(ref, u[0] + dx, 2.0, 270)
        F.align(ref, 2, u[0] + dx, 2.5)
        F.t(ref, 2, W_SIG, (u[0], 2.5))
        F.pvd(ref, 1, 0, -0.9)
    # reset: series resistor to the header, supervisor and pull-up
    sx, sy = start['RESET_N']
    yr = pin[5][1] + RST_DROP
    q = (turn['RESET_N'], yr)
    B.track('RESET_N', 'B', W_SIG, [(sx, sy), (turn['RESET_N'], sy), q])
    B.via('RESET_N', q, *VIA)
    B.place('R32', jx + 3.5, yr, 0)
    B.move_pad_to('R32', 2, (q[0] - 1.1, yr))
    B.track('RESET_N', 'F', W_SIG, [q, B.pad('R32', 2)])
    B.track(B.pad_net('R32', 1), 'F', W_SIG, [B.pad('R32', 1), (pin[5][0] + RST_DROP, yr), pin[5]])
    G = Frame(B, *RESET)
    G.at('U14', 0, 0, 0)
    G.at('R4', -2.5, 0.0, 270)
    G.align('R4', 2, -2.5, G.P('U14', 2)[1])
    B.track('RESET_N', 'F', W_SIG, elbow(q, B.pad('R4', 2), False) + [B.pad('U14', 2)])
    G.pvd('R4', 1, 0, -0.9)
    G.at('C34', 2.2, 0.0, 90)
    G.align('C34', 1, G.P('U14', 3)[0] + 1.6, G.P('U14', 3)[1])
    G.pp('U14', 3, 'C34', 1)
    G.pvd('U14', 3, 0, 1.0)
    G.pvd('C34', 2, 0, -0.9)
    G.pvd('U14', 1, 0, -1.0)


if __name__ == '__main__':
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build'))
    os.makedirs(out, exist_ok=True)
    sys.exit(1 if build(out) else 0)
