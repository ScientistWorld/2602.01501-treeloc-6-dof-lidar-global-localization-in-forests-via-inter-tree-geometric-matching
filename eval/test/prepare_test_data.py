#!/usr/bin/env python3
"""Build the hidden test side of the TreeLoc gym (lives only in eval/test/).

Source: the TreeLoc authors' released RealtimeTrees inventories
(https://github.com/minwoo0611/TreeLoc, branch ``TreeLoc++``, folder ``data/``).
This script is self-contained (it shares no code with data/ or eval/train/).

* ``intra_session_localization``: Oxford Stein am Rhein (the paper's Table I /
  Table III localization setting). The first 50% of frames is the database;
  later frames revisiting a database place within 10 m, at least 50 frames
  after the database ends, are the queries.
* ``inter_session_localization``: Wild-Places Venman, V-03 queries inside the
  official Venman test regions against a V-02 database (~6 months earlier)
  restricted to frames within 15 m of those regions.

Frame IDs come from a private seed and frames are shuffled. The output is
written to eval/test/data/ and is never copied anywhere a method can read.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
from pathlib import Path

TREE_FIELDS = [
    "x", "y", "z", "axis_x", "axis_y", "axis_z",
    "dbh", "dbh_approximation", "score", "reconstructed", "number_clusters",
]
CROP_RADIUS_M = 45.0
POSITIVE_RADIUS_M = 10.0
EXCLUSION_FRAMES = 50
ID_SEED = "hidden-test::7f3c91e2a5b84d06::c41d9a77e0f2b318::treeloc-gym-test-v2"

# Official Wild-Places Venman test regions (as used by the TreeLoc++ evaluator).
VENMAN_TEST_POLYGONS = [
    [(-468.0, -82.0), (-468.0, 44.0), (-314.0, 44.0), (-305.0, 12.0), (-192.0, 44.0), (-192.0, -82.0)],
    [(-78.0, -171.0), (-78.0, -215.0), (-305.0, -215.0), (-305.0, -171.0)],
    [(-62.0, 70.0), (95.0, 70.0), (142.0, 0.0), (140.0, -142.0), (-62.0, -142.0)],
]
TEST_DB_MARGIN_M = 15.0


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def segment_distance(x: float, y: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)


def distance_to_test_regions(x: float, y: float) -> float:
    if any(point_in_polygon(x, y, poly) for poly in VENMAN_TEST_POLYGONS):
        return 0.0
    return min(
        segment_distance(x, y, poly[i], poly[(i + 1) % len(poly)])
        for poly in VENMAN_TEST_POLYGONS
        for i in range(len(poly))
    )


def read_trajectory(seq_dir: Path) -> list[list[float]]:
    poses = []
    for line in seq_dir.joinpath("trajectory.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        poses.append([float(v) for v in parts[1:8]])
    return poses


def _num(value: str) -> float | None:
    value = value.strip()
    if value == "":
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def read_trees(seq_dir: Path, index: int) -> list[list]:
    path = seq_dir / f"TreeManagerState_{index}.csv"
    trees = []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            x, y, z = _num(row["location_x"]), _num(row["location_y"]), _num(row.get("location_z", ""))
            if x is None or y is None or z is None or math.hypot(x, y) > CROP_RADIUS_M:
                continue
            ax, ay, az = _num(row["axis_02"]), _num(row["axis_12"]), _num(row["axis_22"])
            if ax is None or ay is None or az is None:
                continue
            dbh = _num(row.get("dbh", ""))
            dbh_approx = _num(row.get("dbh_approximation", ""))
            if dbh is None and dbh_approx is None:
                continue
            score = _num(row.get("score", "") or row.get("scores", "")) or 0.0
            rec = row.get("reconstructed", "").strip().lower() in ("true", "1")
            nclu = row.get("number_clusters", "").strip()
            trees.append(
                [
                    round(x, 3), round(y, 3), round(z, 3),
                    round(ax, 4), round(ay, 4), round(az, 4),
                    None if dbh is None else round(dbh, 4),
                    None if dbh_approx is None else round(dbh_approx, 4),
                    round(score, 3), int(rec), int(nclu) if nclu else 0,
                ]
            )
    return trees


class Grid:
    def __init__(self, points: dict[int, tuple[float, float]], cell: float = POSITIVE_RADIUS_M):
        self.cell = cell
        self.cells: dict[tuple[int, int], list[int]] = {}
        self.points = points
        for idx, (x, y) in points.items():
            self.cells.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(idx)

    def any_within(self, x: float, y: float, radius: float) -> bool:
        cx, cy = int(math.floor(x / self.cell)), int(math.floor(y / self.cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for idx in self.cells.get((cx + dx, cy + dy), []):
                    px, py = self.points[idx]
                    if math.hypot(px - x, py - y) <= radius:
                        return True
        return False


def evaluable_queries(query_traj, query_idx, db_traj, db_idx) -> list[int]:
    grid = Grid({i: (db_traj[i][0], db_traj[i][1]) for i in db_idx})
    return [i for i in query_idx if grid.any_within(query_traj[i][0], query_traj[i][1], POSITIVE_RADIUS_M)]



# ----------------------------------------------------------------------------- inter-session ground truth
# The released V-02 and V-03 trajectories are each self-consistent, but V-03 is
# offset from V-02 by about half a metre (and slowly varying) in the world frame,
# so V-03 -> V-02 relative poses taken directly from them are off by ~0.5 m.
# Each V-03 position is therefore registered to the V-02 frame before relative
# poses are formed: its world-projected reconstructed stems (and those of the
# neighbouring frames) are matched to the V-02 stem map (nearest stem with
# similar DBH) and the median displacement is added to the V-03 position.
# Two passes (1.0 m, then 0.35 m matching radius). Rotations are unchanged.

REG_RANGE_M = 25.0
REG_DBH_GATE_M = 0.15
REG_WINDOW = 5
REG_MIN_PAIRS = 15


def quat_to_rot(qx: float, qy: float, qz: float, qw: float) -> list[list[float]]:
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]


def world_stems(seq_dir: Path, index: int, pose: list[float]) -> list[tuple[float, float, float, float]]:
    """Reconstructed stems of one frame within REG_RANGE_M, in world coordinates."""
    r = quat_to_rot(*pose[3:7])
    out = []
    for row in read_trees(seq_dir, index):
        if row[9] != 1 or math.hypot(row[0], row[1]) > REG_RANGE_M:
            continue
        d = row[6] if row[6] is not None else row[7]
        x, y, z = row[0], row[1], row[2]
        out.append(tuple(r[k][0] * x + r[k][1] * y + r[k][2] * z + pose[k] for k in range(3)) + (d,))
    return out



def _median(values: list[float]) -> float:
    s = sorted(values)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def session_registration_offsets(ref_dir: Path, q_dir: Path) -> dict[int, tuple[float, float, float]]:
    """Per-frame world translation registering q_dir's trajectory to ref_dir's frame."""
    ref_traj, q_traj = read_trajectory(ref_dir), read_trajectory(q_dir)
    grid: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
    for i, pose in enumerate(ref_traj):
        for p in world_stems(ref_dir, i, pose):
            grid.setdefault((int(math.floor(p[0])), int(math.floor(p[1]))), []).append(p)
    q_stems = []
    for i, pose in enumerate(q_traj):
        q_stems.append(world_stems(q_dir, i, pose))

    def displacements(stems, offset, radius):
        out = []
        reach = int(math.ceil(radius))
        for x, y, z, d in stems:
            x, y, z = x + offset[0], y + offset[1], z + offset[2]
            cx, cy = int(math.floor(x)), int(math.floor(y))
            best, best_d = None, radius
            for gx in range(cx - reach, cx + reach + 1):
                for gy in range(cy - reach, cy + reach + 1):
                    for p in grid.get((gx, gy), ()):
                        if abs(p[3] - d) > REG_DBH_GATE_M:
                            continue
                        dist = math.hypot(p[0] - x, p[1] - y)
                        if dist < best_d:
                            best, best_d = p, dist
            if best is not None:
                out.append((best[0] - x, best[1] - y, best[2] - z))
        return out

    n = len(q_traj)
    offsets = [(0.0, 0.0, 0.0)] * n
    for radius in (1.0, 0.35):
        per_frame = [displacements(q_stems[i], offsets[i], radius) for i in range(n)]
        pooled_all = [v for frame in per_frame for v in frame]
        global_med = tuple(_median([v[k] for v in pooled_all]) for k in range(3)) if pooled_all else (0.0, 0.0, 0.0)
        new = []
        for i in range(n):
            pooled = []
            for w in (REG_WINDOW, 4 * REG_WINDOW):
                pooled = [v for j in range(max(0, i - w), min(n, i + w + 1)) for v in per_frame[j]]
                if len(pooled) >= REG_MIN_PAIRS:
                    break
            med = tuple(_median([v[k] for v in pooled]) for k in range(3)) if len(pooled) >= REG_MIN_PAIRS else global_med
            new.append(tuple(offsets[i][k] + med[k] for k in range(3)))
        offsets = new
    return {i: offsets[i] for i in range(n)}


def build_experiment(setting: str, db_dir: Path, db_idx: list[int], q_dir: Path, q_idx: list[int], rng: random.Random, seq_name: str, q_offsets: dict | None = None):
    db_traj = read_trajectory(db_dir)
    q_traj = read_trajectory(q_dir)
    q_idx = evaluable_queries(q_traj, q_idx, db_traj, db_idx)
    used: set[str] = set()

    def new_id() -> str:
        while True:
            value = "f" + format(rng.getrandbits(48), "012x")
            if value not in used:
                used.add(value)
                return value

    database, queries, truth_db, truth_q, source = [], [], {}, {}, {}
    for i in db_idx:
        fid = new_id()
        database.append({"id": fid, "trees": read_trees(db_dir, i)})
        truth_db[fid] = [round(v, 6) for v in db_traj[i]]
        source[fid] = f"{db_dir.name}:{i}"
    for i in q_idx:
        fid = new_id()
        queries.append({"id": fid, "trees": read_trees(q_dir, i)})
        pose = list(q_traj[i])
        if q_offsets is not None:
            pose[0:3] = [pose[k] + q_offsets[i][k] for k in range(3)]
        truth_q[fid] = [round(v, 6) for v in pose]
        source[fid] = f"{q_dir.name}:{i}"
    rng.shuffle(database)
    rng.shuffle(queries)
    payload = {
        "format": "treeloc-gym/2",
        "setting": setting,
        "tree_fields": TREE_FIELDS,
        "sequences": [{"name": seq_name, "database": database, "queries": queries}],
    }
    truth = {"pose_format": "x y z qx qy qz qw (frame-to-world)", "database": truth_db, "queries": truth_q, "source": source}
    if q_offsets is not None:
        truth["note"] = f"query positions registered to the {db_dir.name} frame by stem-map alignment (session_registration_offsets)"
    return payload, truth


def write_json_gz(path: Path, value) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=False).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0, compresslevel=9) as gz:
            gz.write(raw)
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="data/ folder of a TreeLoc++ checkout (kept outside the workspace)")
    parser.add_argument("--output", default="eval/test/data")
    args = parser.parse_args()
    src = Path(args.source)
    out = Path(args.output)
    rng = random.Random(ID_SEED)

    experiments = {}
    # Intra-session: Oxford Stein, database = first 50% of frames.
    stein = src / "Oxford_Stein"
    n_stein = len(read_trajectory(stein))
    split = int(n_stein * 0.5)
    experiments["intra_session_localization"] = build_experiment(
        "intra_session", stein, list(range(split)), stein, list(range(split + EXCLUSION_FRAMES, n_stein)), rng, "seq_s"
    )
    # Inter-session: Venman V-03 queries inside the official test regions vs V-02.
    v02, v03 = src / "Wild_V02", src / "Wild_V03"
    t02, t03 = read_trajectory(v02), read_trajectory(v03)
    db_idx = [i for i, p in enumerate(t02) if distance_to_test_regions(p[0], p[1]) <= TEST_DB_MARGIN_M]
    q_idx = [i for i, p in enumerate(t03) if distance_to_test_regions(p[0], p[1]) == 0.0]
    experiments["inter_session_localization"] = build_experiment(
        "inter_session", v02, db_idx, v03, q_idx, rng, "seq_v", q_offsets=session_registration_offsets(v02, v03)
    )

    hashes = {}
    truth_all = {}
    for name, (payload, truth) in experiments.items():
        hashes[f"{name}.input.json.gz"] = write_json_gz(out / f"{name}.input.json.gz", payload)
        truth_all[name] = truth
        seq = payload["sequences"][0]
        print(f"{name}: {len(seq['database'])} database frames, {len(seq['queries'])} queries")
    hashes["truth.json.gz"] = write_json_gz(out / "truth.json.gz", {"experiments": truth_all})
    (out / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
