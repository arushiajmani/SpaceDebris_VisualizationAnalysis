from dataclasses import dataclass
from typing import List


@dataclass
class SatelliteTLE:
    name: str
    line1: str
    line2: str


def parse_tle_data(raw_tle: str) -> List[SatelliteTLE]:
    """
    Parse raw TLE text into SatelliteTLE objects.
    """

    lines = raw_tle.strip().split("\n")
    satellites = []

    for i in range(0, len(lines), 3):
        try:
            name = lines[i].strip()
            line1 = lines[i + 1].strip()
            line2 = lines[i + 2].strip()

            satellites.append(SatelliteTLE(name, line1, line2))

        except IndexError:
            # Skip incomplete records
            continue

    return satellites