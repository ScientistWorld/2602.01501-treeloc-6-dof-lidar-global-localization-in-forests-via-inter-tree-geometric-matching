# Experiment Overview

## synthetic_forest_localization
Tests the central forest localization task on fixed query and database scenes represented as tree inventories. The experiment measures whether a system can identify the correct nearby place and produce a relative pose accurate enough for localization, while penalizing methods whose retrieved matches do not support precise pose estimates.

## synthetic_alignment_ablation
Tests whether a system remains robust when the evaluation includes viewpoint-induced roll and pitch variation. The purpose is to measure whether the full system handles viewpoint changes better than a variant that omits the viewpoint-normalization stage.
