// USB PPPS Hub case. Coordinates are mm from the board's bottom left corner, with ports 1 to 4
// on the y = 0 edge and z = 0 at the underside of the base. scripts/case.sh writes board.scad and board.stl.

include <board.scad>
use <Montserrat-ExtraBold.ttf>

part = "assembly"; // base, lid, both, assembly, fit-base, fit-lid, fit-case
board_stl = "board.stl";
lid_alpha = 0.5;                    // in the assembly

$fn = 64;

board_t = 1.6;
top_conns = [host, power_in];
conn = [8.94, 7.35, 3.31];          // USB-C receptacle body
led_h = 1.1;
cap_h = 5.8;                        // 100 uF cap

gap = 0.3;                          // board to wall
wall = 2;
floor_t = 2;
lid_t = 2;
lid_air = 1.5;                      // cap top to lid underside
keepout = 0.5;                      // lid features to connectors

shoulder = [6, 3];                  // peg shoulder diameter and height
peg_d = 3.0;
peg_above = 1.5;                    // peg tip above the board
peg_hole = 3.4;                     // in the lid tubes

opening = [12.6, 6.8];              // USB-C plug overmold opening
opening_r = 1.5;

led_hole = 2.5;
led_tube = 0.8;                     // wall
led_air = 0.5;                      // LED top to tube end

lip_t = 1.2;
lip_gap = 0.15;
lip_h = 2.0;
bead = 0.5;                         // out from the lip
groove = 0.45;                      // into the wall
click_flat = 0.3;
bead_corner = 10;                   // no bead this close to a corner

notch = [10, 1.2, 1.0];             // lid lifting notch: length, depth into wall, height

text_depth = 1.0;
font = "Montserrat:style=ExtraBold";
spacing = 1.1;
min_stroke = 1.0;

board_z = floor_t + shoulder[1];
board_top = board_z + board_t;
wall_h = board_top + cap_h + lid_air;
conn_z = board_top + conn[2] / 2;
click_z = wall_h - lip_h / 2;
outer = gap + wall;

assert(conn_z + opening[1] / 2 < wall_h - lip_h, "lip reaches the connector openings");
assert(click_z - click_flat / 2 - groove > conn_z + opening[1] / 2, "groove reaches the connector openings");

module outline(off) {
    offset(r = off) offset(board_r) offset(-board_r) square(board);
}

module slab(off, z0, z1) {
    translate([0, 0, z0]) linear_extrude(z1 - z0) outline(off);
}

// Ring with a trapezoid section at height z, from outline offset off out to off + depth.
module click_ring(z, off, depth) {
    h = click_flat + 2 * depth;
    hull() {
        slab(off, z - h / 2, z - h / 2 + 0.01);
        slab(off + depth, z - click_flat / 2, z + click_flat / 2);
        slab(off, z + h / 2 - 0.01, z + h / 2);
    }
}

module conn_opening(x, y) {
    translate([x, y + (y == 0 ? -1 : 1) * (gap + wall / 2), conn_z]) rotate([90, 0, 0])
        linear_extrude(wall + 2, center = true)
            union() {               // square top corners, so the top prints as one bridge
                offset(opening_r) offset(-opening_r) square(opening, center = true);
                translate([-opening[0] / 2, 0]) square([opening[0], opening[1] / 2]);
            }
}

module base() {
    for (h = holes) translate(h) {
        cylinder(d = shoulder[0], h = board_z);
        cylinder(d = peg_d, h = board_top + peg_above - 0.4);
        translate([0, 0, board_top + peg_above - 0.4]) cylinder(d1 = peg_d, d2 = peg_d - 0.8, h = 0.4);
    }
    difference() {
        slab(outer, 0, wall_h);
        slab(gap, floor_t, wall_h + 1);
        for (x = ports) conn_opening(x, 0);
        for (x = top_conns) conn_opening(x, board[1]);
        click_ring(click_z, gap, groove);
        hull() {                    // lead-in for the bead
            slab(gap, wall_h - 0.3, wall_h - 0.29);
            slab(gap + 0.3, wall_h - 0.01, wall_h + 0.01);
        }
        translate([-outer - 0.01, board[1] / 2 - notch[0] / 2, wall_h - notch[2]])
            cube([notch[1], notch[0], notch[2] + 0.01]);
    }
}

module conn_keepouts() {
    for (x = ports) translate([x - conn[0] / 2 - keepout, -1, board_top - 1])
        cube([conn[0] + 2 * keepout, conn[1] + keepout + 1, conn[2] + keepout + 1]);
    for (x = top_conns) translate([x - conn[0] / 2 - keepout, board[1] - conn[1] - keepout, board_top - 1])
        cube([conn[0] + 2 * keepout, conn[1] + keepout + 1, conn[2] + keepout + 1]);
}

// thinnest is the text's thinnest stroke in mm, measured. The text is widened to min_stroke.
module label(s, size, thinnest, x, y, halign = "center") {
    translate([x, y]) offset(r = max(0, (min_stroke - thinnest) / 2))
        text(s, size = size, font = font, spacing = spacing, halign = halign, valign = "center");
}

module lid_text() {
    translate([0, 0, wall_h + lid_t - text_depth]) linear_extrude(text_depth + 0.01) {
        for (i = [0 : 3]) label(str(i + 1), 4, 0.87, ports[i], 4.5);
        label("HOST", 4, 0.91, top_conns[0] + conn[0] / 2, 39.5, "right");
        label("5V IN", 4, 0.86, top_conns[1] - conn[0] / 2, 39.5, "left");
    }
}

module lid() {
    difference() {
        union() {
            slab(outer, wall_h, wall_h + lid_t);
            difference() {
                slab(gap - lip_gap, wall_h - lip_h, wall_h);
                slab(gap - lip_gap - lip_t, wall_h - lip_h - 1, wall_h + 1);
            }
            intersection() {
                difference() {
                    click_ring(click_z, gap - lip_gap, bead);
                    slab(gap - lip_gap - 0.01, 0, wall_h + 1);
                }
                union() {
                    translate([bead_corner, -10, 0]) cube([board[0] - 2 * bead_corner, board[1] + 20, wall_h + 1]);
                    translate([-10, bead_corner, 0]) cube([board[0] + 20, board[1] - 2 * bead_corner, wall_h + 1]);
                }
            }
            for (h = holes) translate([h[0], h[1], board_top]) cylinder(d = shoulder[0], h = wall_h - board_top + 0.01);
            for (l = leds) translate([l[0], l[1], board_top + led_h + led_air])
                cylinder(d = led_hole + 2 * led_tube, h = wall_h - board_top - led_h - led_air + 0.01);
        }
        for (h = holes) translate([h[0], h[1], board_top - 1]) cylinder(d = peg_hole, h = peg_above + 1.5);
        for (l = leds) translate([l[0], l[1], 0]) cylinder(d = led_hole, h = wall_h + lid_t + 1);
        conn_keepouts();
        lid_text();
    }
}

module board_model() {
    translate([0, 0, board_z]) import(board_stl);
}

// Printing: the base as modelled, the lid upside down.
module lid_print() {
    translate([0, 0, wall_h + lid_t]) rotate([180, 0, 0]) lid();
}

if (part == "base") base();
else if (part == "lid") lid_print();
else if (part == "both") { base(); translate([board[0] + 2 * outer + 10, board[1], 0]) lid_print(); }
else if (part == "fit-base") intersection() { base(); board_model(); }
else if (part == "fit-lid") intersection() { lid(); board_model(); }
else if (part == "fit-case") intersection() { lid(); base(); }
else if (part == "assembly") {
    color("SteelBlue") base();
    color("DarkGreen") board_model();
    color("LightGray", lid_alpha) lid();
}
