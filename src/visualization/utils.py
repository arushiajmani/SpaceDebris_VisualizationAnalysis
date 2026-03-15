import json

def load_positions(path):
    with open(path) as f:
        return json.load(f)
