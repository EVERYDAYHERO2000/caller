"""Generate millimetre STL meshes. pip install manifold3d trimesh numpy pillow"""
from pathlib import Path
import json, math
import manifold3d as m
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
P=dict(wall=3.0,floor=2.4,base_h=50.0,lid_t=2.4,pi_z=8.0,pcb_t=1.6,stack_gap=20.0,inner_x=96.0,inner_y=66.0,clearance=0.3,service_radius=1.5,vent_radius=1.0,heatsink_height=15.0,outer_radius=6.0,edge_chamfer=1.5,lid_bridge_height=10.0,antenna_window_bottom=20.0)
(ROOT/'parameters.json').write_text(json.dumps(P,indent=2)+'\n')
def box(x,y,z,a,b,c):return m.Manifold.cube((a,b,c)).translate((x,y,z))
def cyl(x,y,z,r,h):return m.Manifold.cylinder(h,r,circular_segments=64).translate((x,y,z))
def union(items):
 s=m.Manifold()
 for i in items:s=s+i
 return s
def rr(x,y,z,w,d,h,r):
 return union([box(x+r,y,z,w-2*r,d,h),box(x,y+r,z,w,d-2*r,h)]+[cyl(xx,yy,z,r,h) for xx in [x+r,x+w-r] for yy in [y+r,y+d-r]])
# Rounded rectangles in vertical wall planes; radius affects the aperture outline.
def yz_slot(x,y,z,w,d,h,r):
 return rr(0,0,0,d,h,w,r).transform(((0,0,1,x),(1,0,0,y),(0,1,0,z)))
def xz_profile(points,y,depth,r):
 section=m.CrossSection([points])
 # Close then open with round joins: fillet both convex and re-entrant corners.
 for delta in [r,-2*r,r]:
  section=section.offset(delta,m.JoinType.Round,circular_segments=64)
 return section.extrude(depth).transform(((1,0,0,0),(0,0,-1,y+depth),(0,1,0,0)))
lid_screws=[(-3,-3),(-3,59),(89,-3),(89,59)]
holes=[(3.5,3.5),(61.5,3.5),(3.5,52.5),(61.5,52.5)]
outer=lambda z,h:rr(-8,-8,z,102,72,h,P["outer_radius"])
def bottom_chamfered_outer(height):
 # Inset lower ring and full-size ring give an exact 45-degree perimeter chamfer.
 c=P['edge_chamfer'];r=P['outer_radius']
 points=[(cx+rad*math.cos(a*math.pi/32),cy+rad*math.sin(a*math.pi/32),z)
  for z,rad in [(0,r-c),(c,r)] for cx in [-2,88] for cy in [-2,58] for a in range(64)]
 return m.Manifold.hull_points(points)+outer(c,height-c)
base=bottom_chamfered_outer(50)-(rr(-5,-5,2.4,96,66,49,3)-union([cyl(x,y,2.3,3,48) for x,y in lid_screws]))
# Windows extend to top: no unsupported roofs. Coordinate convention:
# x=0 microSD end, x=85 Ethernet/USB end; y=0 HDMI edge.
base=base-yz_slot(87,-.5,8,8,57,44,1.5) # USB/Ethernet + HAT USB/SIM
front_profile=[(-.5,8),(61.5,8),(61.5,27),(76,27),(76,52),(-.5,52)]
base=base-xz_profile(front_profile,-9,8,1.5) # continuous rounded stepped opening
base=base-yz_slot(-9,3,P['antenna_window_bottom'],8,50,52-P['antenna_window_bottom'],1.5) # HAT SMA
# microSD access below the Pi, rounded corners R1.5.
base=base-yz_slot(-9,18,4,8,20,6,1.5)
# PCB mounting bosses, clearance bores, recessed screw heads.
base=base+union([cyl(x,y,2.3,2.9,5.7) for x,y in holes])
for x,y in holes:
 base=base-cyl(x,y,-.1,1.45,8.3)-cyl(x,y,-.1,2.7,1.9)
for x,y in lid_screws:base=base-cyl(x,y,39,1.35,12)
# Ventilation through bottom, away from supports.
for x in range(18,57,6):base=base-rr(x,16,-.1,2.5,24,2.7,1)
# Lid model in PRINT orientation: outer face on build plate, locating tabs up.
lid=bottom_chamfered_outer(2.4)
for x in range(7,79,6):lid=lid-rr(x,8,-.1,3,38,2.7,1)
for x,y in lid_screws:lid=lid-cyl(x,y,-.1,1.7,2.7)
# Tabs fit cavity with 0.3 mm clearance; all above board envelope.
for x in [0,80]:lid=lid+box(x,59.5,2.3,5,1.2,2.1)
for x in [0,80]:lid=lid+box(x,-4.7,2.3,5,1.2,2.1)
# Three lid-mounted lintels complete the open connector walls on assembly.
# 0.3 mm end clearance to the base window jambs; full wall thickness.
bridge_h=P['lid_bridge_height']
bridges=[box(91,-.2,2.3,3,56.4,bridge_h+.1),
         box(-.2,-8,2.3,75.9,3,bridge_h+.1),
         box(-8,3.3,2.3,3,49.4,bridge_h+.1)]
lid=lid+union(bridges)
# Print face down requires a physical 180-degree turn around X on assembly.
# Mirror the XY footprint here, so that this turn restores the base coordinates.
lid=lid.mirror((0,1,0)).translate((0,56,0))
meshes={}
report={}
for name,obj in [('base',base),('lid',lid)]:
 assert obj.status()==m.Error.NoError,(name,obj.status())
 mm=obj.to_mesh()
 mesh=trimesh.Trimesh(np.asarray(mm.vert_properties)[:,:3],np.asarray(mm.tri_verts),process=True)
 assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
 assert len(obj.decompose())==1,(name,'detached geometry')
 # Shift each printed object to positive XY; keep a shared frame for base/lid.
 mesh.apply_translation([8,8,0])
 mesh.export(ROOT/'stl'/f'{name}.stl')
 meshes[name]=mesh
 report[name]=dict(watertight=bool(mesh.is_watertight),consistent_winding=bool(mesh.is_winding_consistent),connected_components=len(obj.decompose()),bounds_mm=mesh.bounds.tolist(),volume_cm3=round(mesh.volume/1000,2),triangles=len(mesh.faces))
assembled_lid=lid.rotate((180,0,0)).translate((0,56,52.4))
# Validate each lintel in the installed frame, using the physical lid rotation.
for bridge in bridges:
 assert abs((assembled_lid^bridge.mirror((0,0,1)).translate((0,0,52.4))).volume()-bridge.volume())<1e-5
intersection=(base^assembled_lid).volume()
assert abs(intersection)<1e-5
# PCB envelopes must stay clear of case and installed lid.
pi=box(0,0,8.001,85,56,1.599)
hat=box(0,-.7,29.6,85,56.7,1.6)
assert abs((base^pi).volume())<1e-5
assert abs((base^hat).volume())<1e-5
heatsink=box(0,-.7,31.2,85,56.7,15)
assert abs((base^heatsink).volume())<1e-5
assert abs((assembled_lid^heatsink).volume())<1e-5
report['assembly']=dict(base_lid_intersection_mm3=intersection,pcb_envelopes_clear=True,
 heatsink_height_mm=15,heatsink_envelope_clear=True,heatsink_to_flat_roof_mm=3.8,
 locator_tabs_outside_heatsink_xy=True,lid_bridge_count=3,lid_bridge_height_mm=bridge_h,lid_bridge_end_clearance_mm=0.3,antenna_window_bottom_mm=P['antenna_window_bottom'],assembly_transform='rotate X 180 degrees; translate Y 56, Z 52.4')
(ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
# Lightweight, offline orthographic render of the actual triangulated meshes.
W,H=1500,1100
im=Image.new('RGB',(W,H),'#edf1f5');dr=ImageDraw.Draw(im)
font_path='/System/Library/Fonts/Supplemental/Arial.ttf'
font=ImageFont.truetype(font_path,23);small=ImageFont.truetype(font_path,18);title=ImageFont.truetype(font_path,34)
yaw=math.radians(-44);elev=math.radians(28)
# View from positive X, negative Y, showing both connector windows.
right=np.array([math.cos(yaw),-math.sin(yaw),0]);view=np.array([math.sin(yaw)*math.cos(elev),math.cos(yaw)*math.cos(elev),math.sin(elev)])
# explicitly camera from +X,-Y
view=np.array([.64,-.64,.43]);view/=np.linalg.norm(view)
right=np.cross([0,0,1],view);right/=np.linalg.norm(right);up=np.cross(view,right)
polys=[]
def addmesh(mesh,color,offset=(0,0,0),flip=False):
 v=mesh.vertices.copy()
 if flip:
  v[:,1]=72-v[:,1]
  v[:,2]=52.4-v[:,2]
 v+=np.array(offset)
 for f in mesh.faces:
  p=v[f];normal=np.cross(p[1]-p[0],p[2]-p[0]);norm=np.linalg.norm(normal)
  if norm<1e-8:continue
  normal/=norm
  shade=.63+.32*abs(np.dot(normal,view))
  co=tuple(int(c*shade) for c in color)
  pts=[(675+float(q@right-30)*6.1,765-float(q@up)*6.1) for q in p]
  polys.append((float(p.mean(axis=0)@view),pts,co))
addmesh(meshes['base'],(75,103,124))
addmesh(meshes['lid'],(238,161,67),offset=(0,0,22),flip=True)
for _,pts,col in sorted(polys,key=lambda p:p[0]):dr.polygon(pts,fill=col)
dr.text((60,45),'Raspberry Pi 3B + Waveshare SIM7600G-H M.2',font=title,fill='#172e42')
dr.text((60,100),'PRINTABLE ENCLOSURE  /  exploded view  /  mm',font=font,fill='#527088')
dr.text((60,970),'Base: 50 mm   |   Lid: 2.4 mm   |   R6 corners  /  1.5 mm chamfers / 3 mm walls',font=font,fill='#172e42')
dr.text((60,1010),'R1.5 service windows  /  R1 vent slots  /  15 mm passive heatsink',font=small,fill='#527088')
dr.text((60,1040),'Fit prototype: check actual board stack and cables before final print.',font=small,fill='#527088')
im.save(ROOT/'preview.png')
print(json.dumps(report,indent=2))
