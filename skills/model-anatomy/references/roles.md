# Roles, by collection name

A piece takes the first role whose keywords appear in the names of the collections it sits in
(underscores read as spaces, case ignored). Order matters: ground, wall, rafter, timber, covering.

| Role | Keywords | Plays |
|---|---|---|
| ground | platform, stone, ground, courtyard, terrace, floor, plinth, slab | never moves; the last thing weight reaches |
| wall | wall, door, window, infill, plaster | held in place; carries nothing |
| rafter | rafter, eave board, eaves | moves with the roof |
| timber | column, pillar, bracket, dougong, beam, purlin, tier, ceiling, frame, timber, lintel, post, fang, gong, dou, ang, truss | each piece stands on its own |
| covering | tile, roof, ridge, covering, bedding, clay, thatch | weight only, carried by what is beneath |

Ignored whatever the collection: cameras, lights, empties, curves without a body, and any
object whose name contains fissure or crack (the Foguang hall's weathering lines).

Foguang East Hall v25: `01_Stone_Platform` and `09_Courtyard` are ground, `03_Walls_Doors` wall,
`06_Rafters` rafter, `07_Roof_Tiles` and `08_Ridges` covering, everything numbered 02, 04 and 05
timber.
