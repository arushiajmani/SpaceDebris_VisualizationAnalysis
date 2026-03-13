import math


def compute_distance(p1, p2):
    """
    Compute Euclidean distance between two 3D points.
    """

    return math.sqrt(
        (p1["x"] - p2["x"])**2 +
        (p1["y"] - p2["y"])**2 +
        (p1["z"] - p2["z"])**2
    )
def detect_close_approaches(positions_data, threshold_km=100):

    satellites = positions_data["satellites"]
    sat_names = list(satellites.keys())

    warnings = []

    for i in range(len(sat_names)):
        for j in range(i + 1, len(sat_names)):

            sat_a = sat_names[i]
            sat_b = sat_names[j]

            traj_a = satellites[sat_a]
            traj_b = satellites[sat_b]

            min_distance = float("inf")
            closest_time = None

            for k in range(len(traj_a)):

                pos_a = traj_a[k]["position_km"]
                pos_b = traj_b[k]["position_km"]

                distance = compute_distance(pos_a, pos_b)

                # track the closest approach
                if distance < min_distance:
                    min_distance = distance
                    closest_time = traj_a[k]["time"]

            # check threshold AFTER finding closest distance
            if min_distance < threshold_km and min_distance > 0.001:

                warnings.append({
                    "satellite_a": sat_a,
                    "satellite_b": sat_b,
                    "distance_km": min_distance,
                    "time": closest_time
                })

    return warnings


import json


def save_warnings(warnings, output_path):

    output = {
        "warning_count": len(warnings),
        "warnings": warnings
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)