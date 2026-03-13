import requests


CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"


def fetch_tle_data(url: str = CELESTRAK_URL) -> str:
    """
    Fetch TLE data from CelesTrak.

    Returns
    -------
    str
        Raw TLE text.
    """

    response = requests.get(url)

    if response.status_code != 200:
        raise Exception("Failed to fetch TLE data")

    return response.text