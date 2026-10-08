from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ZoneType(StrEnum):
    N = "normal"
    B = "blocked"
    R = "restricted"
    P = "priority"

    @property
    def entry_turns(self) -> int:
        """Return how many turns a drone needs to enter such a zone."""
        return 2 if self is ZoneType.R else 1


class ZoneKind(StrEnum):
    ST = "start_hub"
    END = "end_hub"
    HUB = "hub"


@dataclass(frozen=True, order=True)
class Cost:
    """Cost tuple - first the turns then priority.

    Parameters
    ----------
        turns: turns to reach
        bonus: Minus one for each priority
    """
    turns: int = 0
    bonus: int = 0

    def __add__(self, other: Cost) -> Cost:
        """Mathematical sum of tuple"""
        return Cost(self.turns + other.turns, self.bonus + other.bonus)

    def __neg__(self) -> Cost:
        """Mathematical substracting tuple"""
        return Cost(-self.turns, -self.bonus)


@dataclass(frozen=True)
class Zone:
    """A vertex of the network."""
    name: str
    x: int
    y: int
    kind: ZoneKind = ZoneKind.HUB
    _type: ZoneType = ZoneType.N
    color: str | None = None
    cap: int = 1

    @property
    def unlimited(self) -> bool:
        return self.kind is not ZoneKind.HUB

    @property
    def blocked(self) -> bool:
        return self._type is ZoneType.B

    @property
    def entry_cost(self) -> Cost:
        bonus = -1 if self._type is ZoneType.P else 0
        return Cost(self._type.entry_turns, bonus)


@dataclass(frozen=True)
class Connection:
    """An undirected edge between two zones."""
    a: Zone
    b: Zone
    cap: int = 1

    @property
    def name(self) -> str:
        return f"{self.a.name}-{self.b.name}"

    def _next(self, zone: Zone) -> Zone:
        return self.b if zone == self.a else self.a


class DroneNetwork:
    """the map: zones, connections and drone count.
    Parameters
    ----------
    nb_drones: int - number of drones
    zones: list[Zone] - list with zones
    conncections: list[Zone] - list of conncections"""

    def __init__(
        self,
        nb_drones: int,
        zones: set[Zone],
        connections: list[Connection],
    ) -> None:
        self.nb_drones: int = nb_drones
        self.zones: list[Zone] = zones
        self.connections: list[Connection] = self._repair_conns(connections)
        self.start: Zone = self._hub(ZoneKind.ST)
        self.end: Zone = self._hub(ZoneKind.END)
        self._adjacent: dict[Zone, list[Connection]] = {
            zone: [] for zone in zones
        }
        self._links: dict[frozenset[Zone], Connection] = {}
        for link in connections:
            self._adjacent[link.a].append(link)
            self._adjacent[link.b].append(link)
            self._links[frozenset((link.a, link.b))] = link

    def _hub(self, kind: ZoneKind) -> str:
        """Just to set start and end zone"""
        for zone in self.zones:
            if zone.kind is kind:
                return zone

    @staticmethod
    def _repair_conns(connections: list[Connection]) -> list[Connection]:
        """Remove falsely high connection capacities."""
        conns = connections[:]
        for con in conns:
            if con.a.cap < con.cap:
                con.cap = con.a.cap
            if con.b.cap < con.cap:
                con.cap = con.b.cap
        return conns

    def links_of(self, zone: Zone) -> list[Connection]:
        """Return every connection from zone."""
        return self._adjacent[zone]

    def link_between(self, first: Zone, second: Zone) -> Connection | None:
        """Return the connection between two zones."""
        return self._links.get(frozenset((first, second)))
