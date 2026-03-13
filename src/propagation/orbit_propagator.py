from skyfield.api import EarthSatellite, load
from datetime import timedelta

def build_satellites(tle_list):

    satellites = []

    for sat in tle_list:
        satellite = EarthSatellite(sat.line1, sat.line2, sat.name)
        satellites.append(satellite)

    return satellites


def generate_time_steps(minutes=90, step=1):

    ts = load.timescale()
    t0 = ts.now()

    times = []

    for i in range(0, minutes, step):
        times.append(ts.utc(t0.utc_datetime() + timedelta(minutes=i)))

    return times

def propagate_positions(satellites, times):

    positions = {}

    for sat in satellites:

        sat_positions = []

        for t in times:

            geocentric = sat.at(t)
            position = geocentric.position.km

            sat_positions.append({
                "x": float(position[0]),
                "y": float(position[1]),
                "z": float(position[2])
            })

        positions[sat.name] = sat_positions

    return positions