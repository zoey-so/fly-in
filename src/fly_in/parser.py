from typing import Any
import sys

from .errors import FlyInError, ParseError
from .models import Connection, DroneNetwork, ZoneKind, Zone, ZoneType


ST = ZoneKind.ST
END = ZoneKind.END


class MapParser:
    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._drones_nb: int | None = None
        self._zones: dict[str, Zone] = {}
        self._coords: list[tuple[int, int]] = []
        self._conns: list[Connection] = []
        self._linked: list[set[str]] = []
        self._st: str = ""
        self._end: str = ""

    def make_network(self, map_file: str) -> DroneNetwork:
        try:
            with open(map_file, 'r', encoding='utf-8') as f:
                txt = f.read()
        except Exception as e:
            raise FlyInError(f"Cant't read file: {e}") from None

        for i, line in enumerate(txt.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            _key, sep, rest = line.partition(':')
            if not sep:
                raise ParseError(
                    i,
                    "No ':' found - format: 'keyword: definition [metadata]'")
            rest = rest.partition(' #')[0]
            if self._drones_nb is None:
                if _key != "nb_drones":
                    raise ParseError(
                            i,
                            "First line format: 'nb_drones: int'\n"
                            )
                self._drones_nb = self._posint(rest, i, "nb_drones")
                continue
            if _key in ("start_hub", "end_hub", "hub"):
                self._parse_zone(ZoneKind(_key), rest, i)
            elif _key == "connection":
                self._parse_connection(rest, i)
            else:
                raise ParseError(
                    i,
                    f"Unkown keyword: '{_key}'.")
        if self._drones_nb is None:
            raise ParseError(0, "Map file is an empty file.")
        if not (self._st and self._end):
            raise ParseError(0, "Map file has no start or end hub.")
        return DroneNetwork(
            self._drones_nb,
            list(self._zones.values()),
            self._conns
        )

    def _parse_zone(self, hub: ZoneKind, s: str, l_n: int) -> None:
        args: dict[str, Any] = {}
        if (self._st and hub == ST) or (self._end and hub == END):
            raise ParseError(
                l_n,
                "Map can have only one start hub and one end hub."
            )
        args["kind"] = hub
        try:
            name, x_str, y_str, *rest = s.split(maxsplit=3)
        except ValueError:
            raise ParseError(
                l_n,
                "Zone definition format: <name> <x> <y> [metadata], "
                f"got: '{s}'.") from None
        if '-' in name:
            raise ParseError(
                l_n,
                f"Zone name can't use dashes, got '{name}'."
            )
        if name in self._zones.keys():
            raise ParseError(
                l_n,
                f"Zone name must be unique, got '{name}.'"
            )
        if hub == "start_hub" or hub == "end_hub":
            if hub == "start_hub":
                self._st = name
            else:
                self._end = name
        args["name"] = name
        x = self._int(x_str, l_n, "Zone coordinate 'x'")
        y = self._int(y_str, l_n, "Zone coordinate 'y'")
        if (x, y) in self._coords:
            raise ParseError(
                l_n,
                f"Zone coordinates must be unique, got '{name} {x} {y}'."
            )
        args["x"] = x
        args["y"] = y
        if rest:
            s = rest[0]
            if not (s.startswith('[') and s.endswith(']')):
                raise ParseError(
                    l_n,
                    f"Incorrect value after zone definition: '{s}."
                )
            args = self._get_zone_meta(s[1:-1], args, l_n)
        self._zones[name] = Zone(**args)
        self._coords.append((x, y))

    def _get_zone_meta(self, s: str, args: dict[str, Any], l_n: int
                       ) -> dict[str, Any]:
        for pair in s.split():
            try:
                k, v = pair.split('=')
            except ValueError:
                raise ParseError(
                    l_n,
                    f"Metadata format: 'key=value', got: {pair}"
                )
            if k == "zone":
                if v not in ZoneType._value2member_map_:
                    raise ParseError(
                        l_n,
                        "Zone type must be one of: "
                        f"{ZoneType._value2member_map_.keys()}"
                        f", got: {v}"
                    )
                args["type_"] = ZoneType(v)
            elif k == "color":
                args["color"] = v
            elif k == "max_drones":
                args["cap"] = self._posint(v, l_n, k)
            else:
                print(f"Map parsing: Unknown key {k} on line {l_n}, "
                      "skipping ...", file=sys.stderr)
        return args

    def _parse_connection(self, s: str, l_n: int) -> None:
        args: dict[str, Any] = {}
        try:
            con, *rest = s.split(maxsplit=1)
        except ValueError:
            raise ParseError(
                l_n,
                "Connection definition format: <name>-<name> [metadata], "
                f"got: '{s}'.") from None
        try:
            a, b = con.split('-')
            if any(x not in self._zones.keys() for x in [a, b]):
                raise ValueError
            if a == b or {a, b} in self._linked:
                raise ValueError
        except ValueError:
            raise ParseError(
                l_n,
                "Connection definition must be unique and "
                "use previously defined zone names "
                f"in format: <name>-<name> got: '{con}'.") from None
        args['a'] = self._zones[a]
        args['b'] = self._zones[b]
        if rest:
            s = rest[0]
            if not (s.startswith('[') and s.endswith(']')):
                raise ParseError(
                    l_n,
                    f"Incorrect value after connection definition: '{s}."
                )
            for pair in s[1:-1].split():
                try:
                    k, v = pair.split('=')
                except ValueError:
                    raise ParseError(
                        l_n,
                        f"Metadata format: 'key=value', got: {pair}"
                    )
                if k == "max_link_capacity":
                    args["cap"] = self._posint(v, l_n, k)
                else:
                    print(f"Map parsing: Unknown key '{k}' on line {l_n}, "
                          "skipping ...", file=sys.stderr)
        self._conns.append(Connection(**args))
        self._linked.append({a, b})

    @staticmethod
    def _posint(s: str, n_line: int, what: str) -> int:
        try:
            res = int(s)
            if res <= 0:
                raise ValueError()
            return res
        except ValueError:
            raise ParseError(
                n_line,
                f"{what} must be positive integer not '{s}'"
                ) from None

    @staticmethod
    def _int(s: str, n_line: int, what: str) -> int:
        try:
            res = int(s)
            return res
        except ValueError:
            raise ParseError(
                n_line,
                f"{what} must be integer not '{s}'"
                ) from None
