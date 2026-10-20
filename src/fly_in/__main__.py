from .errors import FlyInError
from .parser import MapParser
from .planner import Planner
from .runner import Simulator

import sys
import os
import argparse
from pathlib import Path


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("map_file", type=Path, help="Path to the map file")
    parser.add_argument("-gui", action="store_true", help="Run with GUI")
    args = parser.parse_args()
    if not args.map_file.exists() or not args.map_file.is_file():
        raise FlyInError(f"Map file does not exist: {args.map_file}") from None
    mp = MapParser()
    net = mp.make_network(args.map_file)
    planner = Planner(net)
    plan = planner.plan()
    sim = Simulator(net, plan)
    for step in sim.run():
        print(step)
    if args.gui:
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            from .viewer import Viewer
            vr = Viewer(net, sim.turns, plan, args.map_file.stem)
            vr.run()
        except (ModuleNotFoundError, ImportError):
            raise FlyInError(
                "GUI mode requires pygame to be installed.") from None


def main() -> None:
    try:
        run()
    except FlyInError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e!r}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
