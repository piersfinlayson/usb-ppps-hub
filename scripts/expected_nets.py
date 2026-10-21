"""Netlist written from the design spec, independent of the drawing code.

Nets in named() must match by name and members. Nets in UNNAMED match by members only.
Two-pin unpolarised R/C pins may be swapped.
"""

CONN_VBUS = ('A4', 'A9', 'B4', 'B9')
CONN_GND = ('A1', 'A12', 'B1', 'B12', 'S1')


def named():
    n = {}

    def add(name, *nodes):
        n.setdefault(name, set()).update(nodes)

    gnd = ['U14.1', 'C34.2', 'U1.11', 'U1.37', 'U2.2', 'U2.5', 'U3.1', 'U4.2', 'Y1.2', 'Y1.4', 'J7.2',
           'R1.2', 'R3.2', 'R10.2', 'R12.2', 'R13.2', 'R14.2', 'R15.2']
    gnd += ['C%d.2' % i for i in range(1, 20) if i != 12] + ['C32.2', 'C33.2']
    for j in range(1, 7):
        gnd += ['J%d.%s' % (j, p) for p in CONN_GND]
    for u in range(5, 14):
        gnd.append('U%d.2' % u)
    add('GND', *gnd)

    add('+3V3', 'U1.5', 'U1.10', 'U1.15', 'U1.23', 'U1.29', 'U1.36', 'U4.5', 'U2.4', 'J7.1',
        'R4.1', 'R5.1', 'R6.1', 'R7.1', 'R11.1', 'D6.2', 'U14.3', 'C34.1', *['C%d.1' % i for i in range(1, 8)], 'C13.1', 'C19.1')
    add('+5V', 'U3.2', 'U3.7', 'U4.1', 'U4.3', 'C16.1', 'C17.1', 'C18.1')
    add('EXT_5V', *['J2.' + p for p in CONN_VBUS], 'U3.3', 'U3.5', 'R9.1', 'C14.1', 'R30.1', 'D5.2')
    add('GND', 'R41.2')
    add('UP_VBUS', *['J1.' + p for p in CONN_VBUS], 'U3.6', 'R2.1', 'U9.5', 'C15.1', 'R31.1')

    add('LOCAL_PWR', 'U1.28', 'R28.2')
    add('XTALIN', 'U1.33', 'Y1.1', 'C10.1', 'R8.1')
    add('XTALOUT', 'U1.32', 'Y1.3', 'C11.1', 'R8.2')
    add('PLLFILT', 'U1.34', 'C9.1')
    add('CRFILT', 'U1.14', 'C8.1')
    add('RESET_N', 'U1.26', 'R4.2', 'R32.2', 'U14.2')
    add('SCL', 'U1.24', 'U2.1', 'R5.2', 'J7.4')
    add('SDA', 'U1.22', 'U2.3', 'R6.2', 'J7.3')

    # USBLC6-2P6 is flow-through: the hub side and the connector side are separate nets
    add('UP_D-', 'U1.30', 'U9.6')
    add('UP_D+', 'U1.31', 'U9.4')
    add('UP_CONN_D-', 'J1.A7', 'J1.B7', 'U9.1')
    add('UP_CONN_D+', 'J1.A6', 'J1.B6', 'U9.3')

    prtpwr = {1: 12, 2: 16, 3: 18, 4: 20}
    ocs = {1: 13, 2: 17, 3: 19, 4: 21}
    dm = {1: 1, 2: 3, 3: 6, 4: 8}
    dp = {1: 2, 2: 4, 3: 7, 4: 9}
    for p in range(1, 5):
        sw, esd, j = 'U%d' % (4 + p), 'U%d' % (9 + p), 'J%d' % (2 + p)
        rcc1, rcc2 = 'R%d' % (14 + 2 * p), 'R%d' % (15 + 2 * p)
        cin, cbulk, chf = 'C%d' % (17 + 3 * p), 'C%d' % (18 + 3 * p), 'C%d' % (19 + 3 * p)
        add('PRTPWR%d' % p, 'U1.%d' % prtpwr[p], sw + '.4')
        add('OCS%d_N' % p, 'U1.%d' % ocs[p], sw + '.3')
        add('VBUS%d' % p, sw + '.1', *[j + '.' + x for x in CONN_VBUS], 'R%d.1' % (32 + p), chf + '.1',
            rcc1 + '.1', rcc2 + '.1', esd + '.5', 'R%d.1' % (23 + p), 'R%d.1' % (36 + p))
        add('DN%d_D-' % p, 'U1.%d' % dm[p], esd + '.6')
        add('DN%d_D+' % p, 'U1.%d' % dp[p], esd + '.4')
        add('DN%d_CONN_D-' % p, j + '.A7', j + '.B7', esd + '.1')
        add('DN%d_CONN_D+' % p, j + '.A6', j + '.B6', esd + '.3')
        add('+5V', sw + '.5', cin + '.1')
        add('GND', cin + '.2', cbulk + '.2', chf + '.2', 'R%d.2' % (23 + p), 'D%d.1' % p)
    return n


UNNAMED = [
    {'U3.4', 'R9.2', 'R10.1', 'R29.2'},                      # PR1
    {'U3.8', 'R11.2', 'R28.1', 'R29.1'},                     # mux ST
    {'R30.2', 'C32.1'}, {'R31.2', 'C33.1'},                  # input snubbers
    {'J7.5', 'R32.1'},                                       # programming header reset
] + [{'R%d.2' % (32 + p), 'C%d.1' % (18 + 3 * p)} for p in range(1, 5)] + [   # port bulk caps behind 1 ohm
    {'U1.27', 'R2.2', 'R3.1'},
    {'U1.35', 'R1.1'},
    {'U1.25', 'R7.2', 'R42.2'},                              # HS_IND, through R42 to its LED's cathode
    {'D5.1', 'R41.1'}, {'D6.1', 'R42.1'},                    # power input and hub-connected LEDs
    {'J1.A5', 'R14.1'}, {'J1.B5', 'R15.1'}, {'J2.A5', 'R12.1'}, {'J2.B5', 'R13.1'},
] + [{'J%d.A5' % (2 + p), 'R%d.2' % (14 + 2 * p)} for p in range(1, 5)] \
  + [{'J%d.B5' % (2 + p), 'R%d.2' % (15 + 2 * p)} for p in range(1, 5)] \
  + [{'R%d.2' % (36 + p), 'D%d.2' % p} for p in range(1, 5)]   # port LEDs

# Pins deliberately left unconnected
NO_CONNECT = ['U4.4', 'J1.A8', 'J1.B8', 'J2.A6', 'J2.A7', 'J2.B6', 'J2.B7', 'J2.A8', 'J2.B8'] + \
    ['J%d.%s' % (j, p) for j in range(3, 7) for p in ('A8', 'B8')]

