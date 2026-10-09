# What the three tests do, and what they do not claim

## Weights

Every piece weighs its volume times a density: timber and rafters 500 kg/m³ (air-dry pine). The
roof covering weighs 7 kN on every square metre of the roof's footprint (tiles, boarding and the
clay bed together), shared among the covering pieces by their own plan area. A covering piece is a plate: nine
points over its plan each find the highest timber or rafter under them, and the weight is
shared among what was found. Every other piece hands what it carries to what carries it, in
proportion to contact area, or equally to its near misses (within 30 cm, the gaps-closed reading)
when it has no seat; pieces are taken highest first so each has received everything before it
passes on. The ground receives the total; anything with nothing under it is reported as not
carried, never silently dropped.

Snow goes down the same way: 0.35 kN/m² over the roof's footprint, the 100-year snow pressure at
Yuanping, the nearest station in GB 50009-2012 table E.5 (the temple's own village, 50 km east, is
not listed), with the roof-shape coefficient at 1.0. A tiled clay roof weighs twenty times that, so
snow decides little on this hall: 360 kN on the Foguang hall's 9,229 kN.

Each column is then judged as a timber standard judges it. The design load is 1.3 times what it
carries of the building's own weight plus 1.5 times its snow (GB 50068-2018, 8.2.9). That load, over
the round section the column's two narrow sides give, is divided by the share of its crushing
strength a column keeps before it bows, from its slenderness (height over a quarter of the
diameter; GB 50005-2003, 5.1.4, the curve for the TC11 and TC13 grades), and compared with 10 MPa,
the compression allowed in the lowest softwood grade (GB 50005 table 4.3.1-3). The 10 MPa and the
curve are from memory of the standards and are to be confirmed against them before they are quoted.
The Foguang hall's heaviest column carries 518 kN, 705 kN as a design load, at 0.54 m across and a
slenderness of 36: 4.0 MPa of the 10. A column is an upright standing on the ground, a stone or the
platform; one standing on other timber (a king post, a short post on a beam) is a post of the frame,
judged the same way and listed apart. The two used to be counted together, so the temple
had 38 "columns" and a rebuilt hall 40, and an engineer's review read a 0.30 m king post as the
lightest column. An upright resting on nothing stays a column, so hanging never lets a piece off.

This is a static estimate of how the drawn geometry shares the load, with one strength check on the
columns. It is not a structural analysis: no stiffness, no bending, no beams or joints checked, no wind.

## Settle

The physics check's gravity test, made general. Every timber and rafter piece becomes a rigid
body with a convex hull shrunk 2 mm, eased 3 mm a side and 1.5 mm top and bottom so an exact fit
still fits once the solver adds its 1 mm contact skin; pieces drawn through one another, pieces
of one block (foot, seat, ears), and all rafters with the covering are locked as one body, the
way a notched joint holds. Masses keep their order but are compressed (mass to the power 0.3)
so the solver stays stable across four orders of magnitude; friction 0.4; 60 substeps and 60
iterations a frame; four seconds. A piece that moved more than a metre fell; 10 cm to a metre,
shifted.

This is a rigid-body test of the drawn pieces. It says whether they hold each other up when let
go, and where. It says nothing about strength, and the joints it locks are the model's overlaps,
not real carpentry.

## Shake

The settle test with the ground moving. The numbers are the Foguang hall's own site in China's
seismic design code GB 50011-2010 (2016 edition): appendix A lists Wutai county at intensity 8,
0.20 g, group 2; table 5.1.4-2 gives that group a characteristic period of 0.40 s on class II
ground; table 5.1.2-2 gives the frequent earthquake at intensity 8 a peak of 70 cm/s².

Two pushes, along the plan's diagonal so both rows of columns are pushed. First the ground, an
animated body the solver cannot push, moves as a sine wave at 2.5 Hz that swells for half a second,
holds and fades: two seconds, 0.20 g at its peak, which at that speed is only 8 mm each way. Then,
after a pause, gravity leans over: a steady sideways pull of 0.07 g swells, holds for a second and a
half and lets go, the engineer's tilt table. A second of stillness follows and six seconds are
baked in all. A piece has come down when it dropped 10 cm, tipped 10 degrees or ended a metre from
where it stood; how far the rest drifted is told, and is not a fall.

What was found while building it, and why the numbers are what they are:

- The shaking alone finds almost nothing the settle test missed. A post a thirtieth as wide as it is
  tall, stood on end, rode out 0.20 g: the ground moves too little to tip it. The pull is what finds
  what is only balanced.
- The pull cannot be the design peak. Held steady at 0.20 g the real temple's own model crept 0.4 m
  and three of its bracket sets tipped 10 to 16 degrees. Its joints are drawn as pieces resting in
  one another, not as the stiff mortises they are, so the model has none of the turning stiffness the
  real frame has. At the frequent earthquake's 0.07 g the real temple stands: nothing came down, the
  most any piece drifted was 0.15 m, in 372 s. The rebuilt hall that was adopted stands too:
  nothing came down, 0.04 m, in 49 s.
- The solver multiplies the two touching bodies' friction, so the settle test's 0.4 on every body
  grips as 0.16. That is stricter than timber and no fault when pieces are only let go, but under a
  sideways pull a loose plank slid 1.5 m across the slab. The shake test gives every body 1.0: the
  solver still lets a light block squeezed between heavy bodies creep, and the test looks for what
  tips, not for what slides.

This finds a piece that is only stood up, not held. It is one steady wave and one steady pull, not
a recorded earthquake, the joints are as simple as the settle test's, and nothing here is bent,
cracked or pulled out of its mortise: it does not certify that a hall would survive an earthquake.
