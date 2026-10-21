"""Generate the USB PPPS Hub schematic. Layout units are U = 2.54 mm."""
import os
import subprocess
import sys

from kisch import Schematic, U

PROJECT = 'usb-ppps-hub'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the project folder, above scripts/
SRC = os.path.join(ROOT, 'kicad-src')                                 # the committed KiCad project files

# value -> (footprint, LCSC, manufacturer and MPN)
PASSIVES = {
    '0.1uF': ('Capacitor_SMD:C_0402_1005Metric', 'C1525', 'Samsung Electro-Mechanics CL05B104KO5NNNC'),
    '1uF': ('Capacitor_SMD:C_0402_1005Metric', 'C52923', 'Samsung Electro-Mechanics CL05A105KA5NQNC'),
    '10uF': ('Capacitor_SMD:C_0603_1608Metric', 'C19702', 'Samsung Electro-Mechanics CL10A106KP8NNNC'),
    '18pF': ('Capacitor_SMD:C_0402_1005Metric', 'C1549', 'FH (Guangdong Fenghua Advanced Tech) 0402CG180J500NT'),
    '10uF_25V': ('Capacitor_SMD:C_0805_2012Metric', 'C15850', 'Samsung Electro-Mechanics CL21A106KAYNNNE'),
    '22uF': ('Capacitor_SMD:C_0805_2012Metric', 'C45783', 'Samsung Electro-Mechanics CL21A226MAQNNNE'),
    '100uF': ('Capacitor_SMD:CP_Elec_6.3x5.8', 'C249967', 'Lelon VZS101M1ETR-0606'),
    '0.22uF': ('Capacitor_SMD:C_0603_1608Metric', 'C21120', 'Samsung Electro-Mechanics CL10B224KA8NNNC'),
    '5K1': ('Resistor_SMD:R_0402_1005Metric', 'C25905', 'UNI-ROYAL(Uniroyal Elec) 0402WGF5101TCE'),
    '10K': ('Resistor_SMD:R_0402_1005Metric', 'C25744', 'UNI-ROYAL(Uniroyal Elec) 0402WGF1002TCE'),
    '12K': ('Resistor_SMD:R_0402_1005Metric', 'C25752', 'UNI-ROYAL(Uniroyal Elec) 0402WGF1202TCE'),
    '56K': ('Resistor_SMD:R_0603_1608Metric', 'C23206', 'UNI-ROYAL(Uniroyal Elec) 0603WAF5602T5E'),
    '100K': ('Resistor_SMD:R_0402_1005Metric', 'C25741', 'UNI-ROYAL(Uniroyal Elec) 0402WGF1003TCE'),
    '330K': ('Resistor_SMD:R_0603_1608Metric', 'C23137', 'UNI-ROYAL(Uniroyal Elec) 0603WAF3303T5E'),
    '1K': ('Resistor_SMD:R_0402_1005Metric', 'C11702', 'UNI-ROYAL(Uniroyal Elec) 0402WGF1001TCE'),
    '1M': ('Resistor_SMD:R_0402_1005Metric', 'C26083', 'UNI-ROYAL(Uniroyal Elec) 0402WGF1004TCE'),
    '10M': ('Resistor_SMD:R_0603_1608Metric', 'C7250', 'UNI-ROYAL(Uniroyal Elec) 0603WAF1005T5E'),
    '1R': ('Resistor_SMD:R_0603_1608Metric', 'C22936', 'UNI-ROYAL(Uniroyal Elec) 0603WAF100KT5E'),
    '2K2': ('Resistor_SMD:R_0402_1005Metric', 'C25879', 'UNI-ROYAL(Uniroyal Elec) 0402WGF2201TCE'),
    '330R': ('Resistor_SMD:R_0402_1005Metric', 'C25104', 'UNI-ROYAL(Uniroyal Elec) 0402WGF3300TCE'),
}

LED = {'Footprint': 'LED_SMD:LED_0603_1608Metric', 'LCSC': 'C965807', 'Comment': 'XINGLIGHT XL-1608UBC-04'}

# value -> second-source LCSC part, written to the LCSC alt field
ALTS = {
    '22uF': 'C602037',  # Samsung CL21A226MAYNNNE, Samsung's replacement for the NRND CL21A226MAQNNNE
}

USB_C = {'Footprint': PROJECT + ':USB_C_connector_c2765186', 'LCSC': 'C2765186',
         'Comment': 'SHOU HAN TYPE-C 16PIN 2MD(073)'}


def commit_date():
    """Date of HEAD's commit, or '' if there isn't one."""
    r = subprocess.run(['git', '-C', ROOT, 'log', '-1', '--format=%cs'], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, universal_newlines=True)
    return r.stdout.strip() if r.returncode == 0 else ''


s = Schematic(PROJECT, paper='A3', title='USB PPPS Hub', date=commit_date(),
              rev=open(os.path.join(ROOT, 'VERSION')).read().strip(),
              company='piers.rocks', comments=['(c) 2026 piers.rocks'])


def P(x, y):
    return (round(x * U, 4), round(y * U, 4))


def passive(ref, value, x, y, rot=0, fields=None, dnp=False, part=None):
    """Two-pin R or C centred at (x, y) in U. Unrotated, pin 1 is at the top.
    part selects the PASSIVES entry when it differs from the value."""
    fp, lcsc, comment = PASSIVES[part or value]
    lib = 'Device:R_Small' if ref.startswith('R') else (
        'Device:C_Polarized_Small' if 'CP_Elec' in fp else 'Device:C_Small')
    props = {'Footprint': fp, 'Datasheet': '~', 'LCSC': lcsc, 'Comment': comment}
    if (part or value) in ALTS:
        props['LCSC alt'] = ALTS[part or value]
    return s.add(lib, ref, value, P(x, y), rot=rot, fields=fields, dnp=dnp, props=props)


def vpassive(ref, value, x, ytop, top=None, bottom='GND', fields=None, part=None):
    """Vertical R or C with pin 1 at (x, ytop). top/bottom: power symbol names or None."""
    p = passive(ref, value, x, ytop + 1, fields=fields, part=part)
    if top:
        s.pin_power(p, 1, top)
    if bottom:
        s.pin_power(p, 2, bottom)
    return p


def led(rref, rvalue, dref, x, ytop, top=None, bottom='GND', resistor_first=True, fields='right'):
    """A blue LED and its series resistor from (x, ytop) down to ytop + 4, anode uppermost.
    top and bottom: power symbol names or None."""
    ry, dy = (ytop, ytop + 3) if resistor_first else (ytop + 2, ytop + 1)
    r = vpassive(rref, rvalue, x, ry, bottom=None, fields=fields)
    d = s.add('Device:LED_Small', dref, 'Blue', P(x, dy), rot=90, fields=fields, props=dict(LED))
    first, last = (r, 1), (d, 1)
    if not resistor_first:
        first, last = (d, 2), (r, 2)
    if top:
        s.pin_power(*first, top)
    if bottom:
        s.pin_power(*last, bottom)
    return d


def block(x0, y0, x1, y1, title):
    s.rect(P(x0, y0), P(x1, y1))
    s.text(title, P(x0 + 1, y0 + 1.2), size=1.524, bold=True)


def W(*pts):
    s.wire(*[P(*p) for p in pts])


# ------------------------------------------------------------ USB-C connector helpers

def usb_c(ref, x, y, mirror=False):
    return s.add('Connector:USB_C_Receptacle_USB2.0_16P', ref, 'TYPE-C 16PIN 2MD(073)', P(x, y),
                 mirror='y' if mirror else None, props=dict(USB_C))


def usb_c_ground(j):
    for pin in ('A1', 'S1'):
        s.pin_power(j, pin, 'GND')


# ------------------------------------------------------------ upstream connector

def upstream(ox, oy):
    block(ox, oy, ox + 44, oy + 24.5, 'Upstream USB-C (to host)')
    j = usb_c('J1', ox + 8, oy + 13)
    # VBUS
    W((ox + 14, oy + 7), (ox + 38, oy + 7))
    s.power('PWR_FLAG', P(ox + 18, oy + 7))
    s.power('UP_VBUS', P(ox + 38, oy + 7))
    # CC: Rd to GND
    W((ox + 14, oy + 9), (ox + 16, oy + 9))
    W((ox + 14, oy + 10), (ox + 16, oy + 10))
    r1 = passive('R14', '5K1', ox + 17, oy + 9, rot=90, fields='above1')
    r2 = passive('R15', '5K1', ox + 17, oy + 10, rot=90, fields='below1')
    W((ox + 18, oy + 9), (ox + 19, oy + 9), (ox + 19, oy + 10), (ox + 18, oy + 10))
    s.power('GND', P(ox + 19, oy + 9.5), rot=90)
    # D-/D+ through ESD
    esd = s.add('Power_Protection:USBLC6-2P6', 'U9', 'USBLC6-2P6', P(ox + 24, oy + 13),
                props={'LCSC': 'C15999', 'Comment': 'STMicroelectronics USBLC6-2P6'})
    W((ox + 14, oy + 12), (ox + 15, oy + 12), (ox + 15, oy + 13))
    W((ox + 14, oy + 13), (ox + 22, oy + 13))
    W((ox + 14, oy + 14), (ox + 22, oy + 14))
    W((ox + 14, oy + 15), (ox + 15, oy + 15), (ox + 15, oy + 14))
    s.label('UP_CONN_D-', P(ox + 16, oy + 13), 0, kind='local')
    s.label('UP_CONN_D+', P(ox + 16, oy + 14), 0, kind='local')
    W((ox + 24, oy + 11), (ox + 24, oy + 7))
    s.pin_label(esd, 6, 'UP_D-')
    s.pin_label(esd, 4, 'UP_D+')
    s.pin_power(esd, 2, 'GND')
    for pin in ('A8', 'B8'):
        s.pin_nc(j, pin)
    usb_c_ground(j)


# ------------------------------------------------------------ power input connector

def power_input(ox, oy):
    block(ox, oy, ox + 44, oy + 24.5, 'Power input USB-C (5 V supply)')
    j = usb_c('J2', ox + 8, oy + 13)
    W((ox + 14, oy + 7), (ox + 24, oy + 7))
    s.power('PWR_FLAG', P(ox + 18, oy + 7))
    s.power('EXT_5V', P(ox + 24, oy + 7))
    W((ox + 14, oy + 9), (ox + 19, oy + 9))
    W((ox + 14, oy + 10), (ox + 16, oy + 10))
    vpassive('R12', '5K1', ox + 19, oy + 9)
    vpassive('R13', '5K1', ox + 16, oy + 10)
    led('R41', '2K2', 'D5', ox + 28, oy + 9, top='EXT_5V', resistor_first=False)
    for pin in ('A6', 'A7', 'B6', 'B7', 'A8', 'B8'):
        s.pin_nc(j, pin)
    usb_c_ground(j)
    s.power('PWR_FLAG', P(ox + 20, oy + 20))
    s.power('GND', P(ox + 20, oy + 21))
    W((ox + 20, oy + 20), (ox + 20, oy + 21))


# ------------------------------------------------------------ EEPROM and programming header

def eeprom(ox, oy):
    block(ox, oy, ox + 44, oy + 26, 'Configuration EEPROM and programming header')
    u = s.add('Memory_EEPROM:24AA02-OT', 'U2', '24C02S', P(ox + 12, oy + 15),
              props={'LCSC': 'C18723540', 'Comment': 'XBLW 24C02S',
                     'Datasheet': 'https://www.lcsc.com/datasheet/C18723540.pdf'})
    # VCC and decoupling
    W((ox + 12, oy + 12), (ox + 12, oy + 9), (ox + 5, oy + 9))
    s.power('+3V3', P(ox + 12, oy + 9))
    c = passive('C13', '0.1uF', ox + 5, oy + 10)
    s.pin_power(c, 2, 'GND')
    s.pin_power(u, 2, 'GND')
    s.pin_power(u, 5, 'GND', length=U)
    # SDA goes up and over, SCL straight
    sda, scl = u.pin(3), u.pin(1)
    W((ox + 16, oy + 14), (ox + 18, oy + 14), (ox + 18, oy + 9), (ox + 30, oy + 9))
    W((ox + 16, oy + 15), (ox + 30, oy + 15))
    vpassive('R6', '10K', ox + 22, oy + 7, top='+3V3', bottom=None)
    vpassive('R5', '10K', ox + 25, oy + 13, top='+3V3', bottom=None)
    s.label('SDA', P(ox + 30, oy + 9), 0)
    s.label('SCL', P(ox + 30, oy + 15), 0)
    # programming header
    h = s.add('Connector:Conn_01x05_Pin', 'J7', 'EEPROM programming', P(ox + 30, oy + 21), dnp=True,
              fields={'Reference': (P(ox + 28.5, oy + 20)[0], P(ox + 28.5, oy + 20)[1], 'right', 'center', False),
                      'Value': (P(ox + 28.5, oy + 21)[0], P(ox + 28.5, oy + 21)[1], 'right', 'center', False)},
              props={'Footprint': 'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical'})
    s.pin_power(h, 1, '+3V3', length=U)
    s.pin_power(h, 2, 'GND', length=U)
    s.pin_label(h, 3, 'SDA')
    s.pin_label(h, 4, 'SCL')
    W((ox + 32, oy + 23), (ox + 33, oy + 23))
    passive('R32', '1K', ox + 34, oy + 23, rot=90, fields='below1')
    W((ox + 35, oy + 23), (ox + 36, oy + 23))
    s.label('RESET_N', P(ox + 36, oy + 23), 0)


# ------------------------------------------------------------ 3.3 V regulator

def ldo(ox, oy):
    block(ox, oy, ox + 44, oy + 15, '3.3 V regulator')
    u = s.add('Regulator_Linear:AP2112K-3.3', 'U4', 'AP2112K-3.3', P(ox + 20, oy + 9),
              props={'LCSC': 'C51118', 'Comment': 'Diodes Incorporated AP2112K-3.3TRG1'})
    W((ox + 17, oy + 8), (ox + 10, oy + 8))
    s.power('+5V', P(ox + 10, oy + 8))
    W((ox + 17, oy + 9), (ox + 15, oy + 9), (ox + 15, oy + 8))
    vpassive('C18', '1uF', ox + 12, oy + 8)
    W((ox + 23, oy + 8), (ox + 31, oy + 8))
    s.power('+3V3', P(ox + 31, oy + 8))
    vpassive('C19', '1uF', ox + 28, oy + 8)
    s.pin_nc(u, 4)
    s.pin_power(u, 2, 'GND')


# ------------------------------------------------------------ hub

def hub(ox, oy):
    block(ox, oy, ox + 54, oy + 60, 'USB2514B hub controller')
    cx, cy = ox + 33, oy + 30
    u = s.add('Interface_USB:USB2514B_Bi', 'U1', 'USB2514B', P(cx, cy),
              fields={'Reference': (P(cx + 4, cy + 16.5)[0], P(cx + 4, cy + 16.5)[1], 'left', 'center', False),
                      'Value': (P(cx + 4, cy + 17.5)[0], P(cx + 4, cy + 17.5)[1], 'left', 'center', False)},
              props={'Footprint': 'Package_DFN_QFN:QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm_ThermalVias',
                     'LCSC': 'C16251', 'Comment': 'Microchip USB2514B-AEZC-TR'})
    # supply pins to a 3V3 rail with one 0.1 uF per pin and a 10 uF bulk cap
    rail_y = cy - 18
    for pin in ('5', '10', '29', '36', '15', '23'):
        x, y = u.pin(pin)
        s.wire((x, y), (x, rail_y * U))
    caps = [('C1', '0.1uF'), ('C2', '0.1uF'), ('C3', '0.1uF'), ('C4', '0.1uF'), ('C5', '0.1uF'),
            ('C6', '0.1uF'), ('C7', '10uF')]
    x0 = cx - 31
    for i, (ref, val) in enumerate(caps):
        vpassive(ref, val, x0 + 4 * i, rail_y)
    W((x0, rail_y), (cx + 5, rail_y))
    s.power('+3V3', P(cx + 5, rail_y))
    s.pin_power(u, 37, 'GND')
    # left side
    xl = cx - 11
    W((xl, cy - 9), (cx - 21, cy - 9))
    vpassive('R2', '100K', cx - 21, cy - 11, top='UP_VBUS', bottom=None)
    vpassive('R3', '100K', cx - 21, cy - 9)
    s.pin_label(u, 30, 'UP_D-')
    s.pin_label(u, 31, 'UP_D+')
    s.pin_label(u, 26, 'RESET_N')
    s.pin_power(u, 11, 'GND', length=U)
    W((xl, cy - 1), (xl - 3, cy - 1))
    r = passive('R1', '12K', xl - 4, cy - 1, rot=90, fields='above1')
    s.pin_power(r, 1, 'GND')
    s.pin_label(u, 33, 'XTALIN', kind='local')
    s.pin_label(u, 32, 'XTALOUT', kind='local')
    s.pin_label(u, 34, 'PLLFILT', kind='local')
    s.pin_label(u, 14, 'CRFILT', kind='local')
    s.pin_label(u, 24, 'SCL')
    s.pin_label(u, 22, 'SDA')
    s.pin_label(u, 28, 'LOCAL_PWR')
    W((xl, cy + 11), (cx - 21, cy + 11))
    vpassive('R7', '100K', cx - 21, cy + 9, top='+3V3', bottom=None)
    led('R42', '330R', 'D6', cx - 24, cy + 7, top='+3V3', bottom=None, resistor_first=False, fields='left')
    W((cx - 24, cy + 11), (cx - 21, cy + 11))
    # right side
    for pin, name in ((1, 'DN1_D-'), (2, 'DN1_D+'), (12, 'PRTPWR1'), (13, 'OCS1_N'),
                      (3, 'DN2_D-'), (4, 'DN2_D+'), (16, 'PRTPWR2'), (17, 'OCS2_N'),
                      (6, 'DN3_D-'), (7, 'DN3_D+'), (18, 'PRTPWR3'), (19, 'OCS3_N'),
                      (8, 'DN4_D-'), (9, 'DN4_D+'), (20, 'PRTPWR4'), (21, 'OCS4_N')):
        s.pin_label(u, pin, name)
    # crystal
    by = cy + 20
    y = s.add('Device:Crystal_GND24', 'Y1', '24MHz', P(ox + 12, by + 5),
              fields={'Reference': (P(ox + 11.6, by + 3.4)[0], P(ox + 11.6, by + 3.4)[1], 'right', 'center', False),
                      'Value': (P(ox + 12.4, by + 3.4)[0], P(ox + 12.4, by + 3.4)[1], 'left', 'center', False)},
              props={'Footprint': 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm', 'LCSC': 'C7420736',
                     'Comment': 'TKD SX32Y024000BC1T001',
                     'Datasheet': 'https://www.lcsc.com/datasheet/C7420736.pdf'})
    W((ox + 5, by), (ox + 9, by), (ox + 9, by + 5), (ox + 10.5, by + 5))
    W((ox + 19, by), (ox + 15, by), (ox + 15, by + 5), (ox + 13.5, by + 5))
    s.label('XTALIN', P(ox + 5, by), 0, kind='local')
    s.label('XTALOUT', P(ox + 19, by), 180, kind='local')
    passive('R8', '1M', ox + 12, by + 2, rot=90, fields='above1', dnp=True)
    W((ox + 9, by + 2), (ox + 11, by + 2))
    W((ox + 13, by + 2), (ox + 15, by + 2))
    passive('C10', '18pF', ox + 9, by + 6, fields='left')
    passive('C11', '18pF', ox + 15, by + 6, fields='right')
    W((ox + 9, by + 7), (ox + 15, by + 7))
    s.power('GND', P(ox + 12, by + 7))
    # PLL and core filter caps
    W((ox + 22, by), (ox + 27, by))
    s.label('PLLFILT', P(ox + 22, by), 0, kind='local')
    vpassive('C9', '0.1uF', ox + 27, by)
    W((ox + 22, by + 5), (ox + 27, by + 5))
    s.label('CRFILT', P(ox + 22, by + 5), 0, kind='local')
    vpassive('C8', '0.1uF', ox + 27, by + 5)
    # reset: open-drain supervisor holds RESET_N low until +3V3 is valid
    s.need(PROJECT + ':TLV803S', path=os.path.join(SRC, PROJECT + '.kicad_sym'))
    sup = s.add(PROJECT + ':TLV803S', 'U14', 'TLV803S', P(ox + 48, by + 3), mirror='y',
                fields={'Reference': (P(ox + 50.5, by + 4.5)[0], P(ox + 50.5, by + 4.5)[1], 'right', 'center', False),
                        'Value': (P(ox + 50.5, by + 5.5)[0], P(ox + 50.5, by + 5.5)[1], 'right', 'center', False)},
                props={'LCSC': 'C132016', 'Comment': 'Texas Instruments TLV803SDBZR'})
    W((ox + 38, by + 3), (ox + 45, by + 3))
    s.label('RESET_N', P(ox + 38, by + 3), 180)
    vpassive('R4', '10K', ox + 42, by + 1, top='+3V3', bottom=None)
    s.pin_power(sup, 3, '+3V3')
    W((ox + 48, by - 1), (ox + 51, by - 1))
    vpassive('C34', '0.1uF', ox + 51, by - 1)
    s.pin_power(sup, 1, 'GND')


# ------------------------------------------------------------ power mux

def mux(ox, oy):
    block(ox, oy, ox + 54, oy + 31, 'Power mux: external 5 V first, upstream VBUS otherwise')
    u = s.add('Power_Management:TPS2116DRL', 'U3', 'TPS2116', P(ox + 18, oy + 11),
              props={'LCSC': 'C3235557', 'Comment': 'Texas Instruments TPS2116DRLR'})
    vin1, pr1, mode, vin2 = u.pin(3), u.pin(4), u.pin(5), u.pin(6)
    s.pin_power(u, 3, 'EXT_5V', length=2 * U, rot=0)
    s.pin_label(u, 4, 'PR1', kind='local')
    s.pin_power(u, 5, 'EXT_5V', length=U)
    s.pin_power(u, 6, 'UP_VBUS', length=3 * U)
    s.pin_power(u, 1, 'GND')
    s.pin_power(u, 2, '+5V', length=2 * U, rot=0)
    # ST: pull-up, series resistor to the hub's LOCAL_PWR, hysteresis resistor to PR1
    W((ox + 22, oy + 13), (ox + 29, oy + 13))
    vpassive('R11', '10K', ox + 25, oy + 11, top='+3V3', bottom=None)
    passive('R28', '5K1', ox + 30, oy + 13, rot=90, fields='above1')
    W((ox + 31, oy + 13), (ox + 33, oy + 13))
    s.label('LOCAL_PWR', P(ox + 33, oy + 13), 0)
    vpassive('R29', '10M', ox + 27, oy + 13, bottom=None, fields='right')
    W((ox + 27, oy + 15), (ox + 27, oy + 16), (ox + 28, oy + 16))
    s.label('PR1', P(ox + 28, oy + 16), 0, kind='local')
    # decoupling and divider, drawn as groups below
    gy = oy + 23
    # input caps, each with a 1R + 10 uF snubber to damp hot-plug ringing
    vpassive('C14', '0.1uF', ox + 4, gy, top='EXT_5V')
    vpassive('R30', '1R', ox + 8, gy, bottom=None)
    vpassive('C32', '22uF', ox + 8, gy + 2)
    W((ox + 4, gy), (ox + 8, gy))
    vpassive('C15', '0.22uF', ox + 12, gy, top='UP_VBUS')
    vpassive('R31', '1R', ox + 16, gy, bottom=None)
    vpassive('C33', '10uF', ox + 16, gy + 2, part='10uF_25V')
    W((ox + 12, gy), (ox + 16, gy))
    vpassive('R9', '1M', ox + 23, gy - 1, top='EXT_5V', bottom=None)
    vpassive('R10', '330K', ox + 23, gy + 1)
    W((ox + 23, gy + 1), (ox + 20.5, gy + 1))
    s.label('PR1', P(ox + 20.5, gy + 1), 0, kind='local')
    W((ox + 29, gy), (ox + 33, gy))
    vpassive('C16', '1uF', ox + 29, gy, top='+5V')
    vpassive('C17', '100uF', ox + 33, gy)


# ------------------------------------------------------------ downstream port

def port(n, ox, oy):
    block(ox, oy, ox + 54, oy + 22.5, 'Downstream port %d' % n)
    sw = s.add('Power_Management:TPS2051CDBV', 'U%d' % (4 + n), 'TPS2051B', P(ox + 12, oy + 6),
               props={'LCSC': 'C24593', 'Comment': 'Texas Instruments TPS2051BDBVR',
                      'Datasheet': 'https://www.ti.com/lit/ds/symlink/tps2051b.pdf'})
    s.pin_power(sw, 5, '+5V', length=U, rot=0)
    s.pin_label(sw, 4, 'PRTPWR%d' % n)
    s.pin_label(sw, 3, 'OCS%d_N' % n)
    s.pin_power(sw, 2, 'GND')
    vpassive('C%d' % (17 + 3 * n), '1uF', ox + 4, oy + 10, top='+5V')
    # switched VBUS
    W((ox + 16, oy + 5), (ox + 42, oy + 5))
    s.label('VBUS%d' % n, P(ox + 18, oy + 5), 0, kind='local')
    vpassive('R%d' % (32 + n), '1R', ox + 23, oy + 5, bottom=None)
    W((ox + 21.5, oy + 5), (ox + 21.5, oy + 9))
    led('R%d' % (36 + n), '2K2', 'D%d' % n, ox + 21.5, oy + 9, fields='left')
    vpassive('C%d' % (18 + 3 * n), '22uF', ox + 23, oy + 7)
    vpassive('C%d' % (19 + 3 * n), '0.1uF', ox + 28, oy + 5)
    vpassive('R%d' % (23 + n), '10K', ox + 35, oy + 5, fields='left')
    vpassive('R%d' % (15 + 2 * n), '56K', ox + 38.5, oy + 5, bottom=None, fields='left')
    vpassive('R%d' % (14 + 2 * n), '56K', ox + 40.5, oy + 5, bottom=None)
    W((ox + 38.5, oy + 7), (ox + 38.5, oy + 8), (ox + 42, oy + 8))
    W((ox + 40.5, oy + 7), (ox + 42, oy + 7))
    j = usb_c('J%d' % (2 + n), ox + 48, oy + 11, mirror=True)
    esd = s.add('Power_Protection:USBLC6-2P6', 'U%d' % (9 + n), 'USBLC6-2P6', P(ox + 32, oy + 11), mirror='y',
                props={'LCSC': 'C15999', 'Comment': 'STMicroelectronics USBLC6-2P6'})
    W((ox + 32, oy + 9), (ox + 32, oy + 5))
    W((ox + 42, oy + 10), (ox + 41, oy + 10), (ox + 41, oy + 11))
    W((ox + 42, oy + 11), (ox + 34, oy + 11))
    W((ox + 42, oy + 12), (ox + 34, oy + 12))
    W((ox + 42, oy + 13), (ox + 41, oy + 13), (ox + 41, oy + 12))
    s.label('DN%d_CONN_D-' % n, P(ox + 35, oy + 11), 0, kind='local')
    s.label('DN%d_CONN_D+' % n, P(ox + 35, oy + 12), 0, kind='local')
    s.pin_label(esd, 6, 'DN%d_D-' % n)
    s.pin_label(esd, 4, 'DN%d_D+' % n)
    s.pin_power(esd, 2, 'GND')
    for pin in ('A8', 'B8'):
        s.pin_nc(j, pin)
    usb_c_ground(j)


upstream(5, 5)
power_input(5, 30)
eeprom(5, 55)
ldo(5, 81.5)
hub(50, 5)
mux(50, 65.5)
for n in range(1, 5):
    port(n, 105, 5 + (n - 1) * 23)

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build')
    os.makedirs(out, exist_ok=True)
    text = s.render()
    open(os.path.join(out, PROJECT + '.kicad_sch'), 'w').write(text)
    pro = os.path.join(out, PROJECT + '.kicad_pro')
    if not os.path.exists(pro):
        open(pro, 'w').write('{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 3\n  }\n}\n' % PROJECT)
    issues = s.check()
    for i in issues:
        print('LAYOUT', i)
    sys.exit(1 if issues else 0)
