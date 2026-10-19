// Raspberry Pi 3 Model B + Waveshare SIM7600G-H M.2 4G HAT.
// mm. Part: "base", "lid", "assembly".
// Lid is exported OUTER FACE DOWN, ready to print.
part = "assembly";
$fn = 64;
wall = 3; // Integrated corner screw channels, flush rectangular exterior.
floor_t = 2.4;
pi_bottom = 8;
pi_pcb_t = 1.6;
board_spacer = 20; // PCB top to HAT bottom; match the actual GPIO connector!
hat_pcb_t = 1.6;
heatsink_height = 15; // Height above HAT PCB upper surface.
hat_component_allowance = 12; // Existing enclosure height budget; roof clearance 3.8 mm.
headroom = 6.8;
base_h = pi_bottom + pi_pcb_t + board_spacer + hat_pcb_t + hat_component_allowance + headroom;
lid_t = 2.4;
fit_gap = 0.3;
lid_bridge_height = 10;
antenna_window_bottom = 20; // Lid-mounted lintels above connector/antenna windows.
service_radius = 1.5;
vent_radius = 1;
outer_radius = 6;
edge_chamfer = 1.5; // 45 degrees, bottom of base and outer face of lid.
lid_screws = [[-3,-3],[-3,59],[89,-3],[89,59]];
mounts = [[3.5,3.5],[61.5,3.5],[3.5,52.5],[61.5,52.5]];
module b(x,y,z,a,d,h) {translate([x,y,z]) cube([a,d,h]);}
module c(x,y,z,r,h) {translate([x,y,z]) cylinder(h=h,r=r);}
module rounded(x,y,z,a,d,h,r) {
 translate([x,y,z]) linear_extrude(h) hull()
 for (xx=[r,a-r],yy=[r,d-r]) translate([xx,yy]) circle(r=r);
}
// Rounded apertures in the YZ wall plane and stepped XZ front profile.
module yz_slot(x,y,z,w,d,h,r) {
 multmatrix([[0,0,1,x],[1,0,0,y],[0,1,0,z],[0,0,0,1]])
 rounded(0,0,0,d,h,w,r);
}
module front_slot() {
 multmatrix([[1,0,0,0],[0,0,-1,-1],[0,1,0,0],[0,0,0,1]])
 linear_extrude(8)
 offset(r=service_radius) offset(r=-2*service_radius) offset(r=service_radius)
 polygon([[-.5,8],[61.5,8],[61.5,27],[76,27],[76,base_h+2],[-.5,base_h+2]]);
}
module outline(z,h) {
 rounded(-8,-8,z,102,72,h,outer_radius);
}
// Lower inset outline rises to the full outline at edge_chamfer height.
module chamfered_outline(h) {
 union() {
  hull() {
   rounded(-8+edge_chamfer,-8+edge_chamfer,0,
    102-2*edge_chamfer,72-2*edge_chamfer,
    .00001,outer_radius-edge_chamfer);
   outline(edge_chamfer,.00001);
  }
  outline(edge_chamfer,h-edge_chamfer);
 }
}
module base() {
 difference() {
  union() {
   difference() {
    chamfered_outline(base_h);
    difference() {
     rounded(-8+wall,-8+wall,floor_t,102-2*wall,72-2*wall,base_h,outer_radius-wall);
     for(p=lid_screws)c(p[0],p[1],floor_t-.1,3,base_h);
    }
    yz_slot(87,-.5,pi_bottom,8,57,base_h,service_radius);
    front_slot();
    yz_slot(-9,3,antenna_window_bottom,8,50,base_h,service_radius);
    yz_slot(-9,18,4,8,20,6,service_radius); // microSD
   }
   for(p=mounts)c(p[0],p[1],floor_t-.1,2.9,pi_bottom-floor_t+.1);
  }
  for(p=mounts) {
   c(p[0],p[1],-.1,1.45,pi_bottom+.3);
   c(p[0],p[1],-.1,2.7,1.9);
  }
  for(p=lid_screws)c(p[0],p[1],base_h-11,1.35,12);
  for(x=[18:6:56])rounded(x,16,-.1,2.5,24,floor_t+.3,vent_radius);
 }
}
module lid_inner_frame() {
 union() {
  difference() {
   chamfered_outline(lid_t);
   for(x=[7:6:78])rounded(x,8,-.1,3,38,lid_t+.3,vent_radius);
   for(p=lid_screws)c(p[0],p[1],-.1,1.7,lid_t+.3);
  }
  // Full-thickness extensions into the three open wall tops.
  b(91,-.5+fit_gap,lid_t-.1,3,57-2*fit_gap,lid_bridge_height+.1);
  b(-.5+fit_gap,-8,lid_t-.1,76.5-2*fit_gap,3,lid_bridge_height+.1);
  b(-8,3+fit_gap,lid_t-.1,3,50-2*fit_gap,lid_bridge_height+.1);
  for(x=[0,80]) {
   b(x,61-fit_gap-1.2,lid_t-.1,5,1.2,2.1);
   b(x,-5+fit_gap,lid_t-.1,5,1.2,2.1);
  }
 }
}
// Mirror print footprint; installed lid is a real 180-degree rotation about X.
module lid() {translate([0,56,0])mirror([0,1,0])lid_inner_frame();}
if(part=="base")translate([8,8,0])base();
else if(part=="lid")translate([8,8,0])lid();
else if(part=="assembly") {
 color("SlateGray")base();
 color("Orange")translate([0,56,base_h+lid_t+15])rotate([180,0,0])lid();
 // Passive heatsink envelope (visual aid only).
 %color("Silver")b(0,-.7,pi_bottom+pi_pcb_t+board_spacer+hat_pcb_t,85,56.7,heatsink_height);
 // Translucent PCB envelopes, visual aid only; not exported with print parts.
 %color("Green")b(0,0,pi_bottom,85,56,pi_pcb_t);
 %color("Blue")b(0,-.7,pi_bottom+pi_pcb_t+board_spacer,85,56.7,hat_pcb_t);
}
