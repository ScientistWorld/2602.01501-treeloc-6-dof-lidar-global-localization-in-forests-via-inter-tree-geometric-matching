# Problem Definition

## Research Question

Given a forest LiDAR scene, find which previously mapped place it shows and estimate its full 6-DoF pose relative to that place. Forests make this hard: scenes are repetitive, stems occlude each other, undergrowth and foliage change across seasons, the sensor carrier (a backpack, a handheld rig) rolls and pitches strongly, and GPS is degraded under the canopy.

Here each scene is already reduced to a **tree inventory**: the stems detected in an aggregated LiDAR payload, each with its 3D stem axis, a position (stem centre in the horizontal plane and base height), its diameter at breast height (DBH), and a detection quality record. The inventories are the real ones extracted from the Oxford Forest Place Recognition dataset (Evo, Stein am Rhein) and the Wild-Places dataset (Venman, two sessions about six months apart). Positions are expressed in each scene's own local sensor frame; nothing about global position, heading or time order is given.

## Why It Matters

Reliable forest localization enables autonomous navigation, repeated ecological monitoring, maintenance of digital forest inventories, and alignment of mapping sessions recorded months or years apart, while storing only compact per-tree records instead of dense point clouds.

## Success Criteria

For every query scene a system names one database scene and the rigid transform that maps query-frame points into that database scene's frame, plus a confidence score. A good system:

- names a database scene that really is near the query (place recognition),
- gives a confidence that separates its right answers from its wrong ones (precision–recall), and
- estimates a relative pose accurate to decimetres and a few degrees (localization),

both within one recording session and across sessions separated by months of environmental change.
