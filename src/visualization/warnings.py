import json

def load_warning_satellites():

    try:
        with open("debug/warnings.json") as f:
            data = json.load(f)

        warn = set()

        for w in data["warnings"]:
            warn.add(w["satellite_a"])
            warn.add(w["satellite_b"])

        return warn

    except:
        return set()
