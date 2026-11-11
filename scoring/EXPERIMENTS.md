# Experiment Overview

Both experiments score the same thing: given a query forest scene (a tree inventory in its own local frame), name the database scene it was recorded near and estimate the 6-DoF relative pose to it, with a confidence score. Train and hidden-test slices use different forests (intra-session) or disjoint regions of the same forest (inter-session), so a method tuned to the visible slice is checked on unseen places.

## intra_session_localization (weight 0.6)
Revisits within one recording: the database is the first part of a traversal and the queries are later passes through the same places. It establishes whether a method recognizes a place it has seen and recovers an accurate full pose despite strong roll/pitch of the sensor carrier and viewpoint changes between passes. Train: Oxford Evo. Hidden test: Oxford Stein am Rhein (the paper's localization benchmark).

## inter_session_localization (weight 0.4)
Revisits across recording sessions about six months apart (Wild-Places Venman V-03 queries against a V-02 database). It establishes whether recognition and pose estimation survive seasonal and structural change of the forest. Train: regions outside the official Wild-Places test regions. Hidden test: inside them.

In both experiments the benefit side is place recognition (`R_at_1`, `F1`, `AUC`) and localization success (`R_at_50`, `SR`); the constraint side is pose accuracy (`TE_m`, `RE_deg`, and the unconditional `TE_all_m`, `RE_all_deg`), so that more aggressive matching cannot buy recall with imprecise poses.
