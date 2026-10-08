from .parser import MapParser
import sys


def main() -> None:
    mp = MapParser()
    for k, v in mp.make_network(sys.argv[1]).__dict__.items():
        print(f"{k}: {v}")
