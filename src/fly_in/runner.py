"""Flow simulation: run a flight plan on a drone network."""
from dataclasses import dataclass
from collections.abc import Generator

from .errors import SimulationError
from .models import Connection, DroneNetwork, ZoneType, Zone
from .planner import DronePlan, FlightPlan


class Drone:
    def __init__(self, plan: DronePlan, start: Zone) -> None:
        self.plan: DronePlan = plan
        self._id = plan.drone_id
        self.zone: Zone = start
        self.move_n: int = 0
        self.inflight: bool = False
        self.delivered: bool = False

    def __str__(self) -> str:
        return f"D{self._id}"

    @property
    def next_zone(self) -> Zone:
        return self.plan.path.zones[self.move_n + 1]


@dataclass(frozen=True)
class Move:
    drone: Drone
    origin: Zone
    target: Zone
    link: Connection
    direct: bool

    def __str__(self) -> str:
        if not self.direct:
            return f"{self.drone}-{self.link.name}"
        return f"{self.drone}-{self.target.name}"


@dataclass(frozen=True)
class Turn:
    turn_n: int
    moves: tuple[Move, ...]
    z_occup: dict[Zone, int]
    c_occup: dict[Connection, int]

    def __str__(self) -> str:
        return " ".join(str(move) for move in self.moves)


class Simulator:
    """Simulator runs a flight plan on a drone network."""

    def __init__(self, network: DroneNetwork, plan: FlightPlan) -> None:
        self._network = network
        self._plan = plan
        self.turn: int = 0
        self.occupancy: dict[Zone, int] = {zone: 0 for zone in network.zones}
        self.occupancy[network.start] = network.nb_drones
        self._waiting: dict[int, list[Drone]] = {}
        self._active: list[Drone] = []
        self._remaining = network.nb_drones
        self.turns: list[Turn] = []
        for drone_plan in plan.drones:
            drone = Drone(drone_plan, network.start)
            self._waiting.setdefault(drone_plan.departure, []).append(drone)

    def run(self) -> Generator[Turn]:
        while self._remaining > 0:
            tr = self.step()
            self.turns.append(tr)
            yield tr

    def step(self) -> Turn:
        self.turn += 1
        if self.turn > self._plan.turns:
            raise SimulationError(
                self.turn, "plan exceeded its supposed turns")
        self._active.extend(self._waiting.pop(self.turn, []))
        moves = [self._next_move(drone) for drone in self._active]
        c_occup = self._check_links(moves)
        z_occup = self._check_zones(moves)
        for move in moves:
            self._apply(move)
        self._active = [d for d in self._active if not d.delivered]
        return Turn(self.turn, tuple(moves), z_occup, c_occup)

    def _next_move(self, drone: Drone) -> Move:
        target = drone.next_zone
        link = self._network.link_between(drone.zone, target)
        if link is None:
            raise SimulationError(
                self.turn,
                f"no connection: {drone.zone.name} -> {target.name}")
        direct = (target.type_ != ZoneType.R) or drone.inflight
        return Move(drone, drone.zone, target, link, direct)

    def _check_links(self, moves: list[Move]) -> dict[Connection, int]:
        ocup: dict[Connection, int] = {}
        for move in moves:
            if not (move.direct and move.target.type_ == ZoneType.R):
                ocup[move.link] = ocup.get(move.link, 0) + 1
        for link, count in ocup.items():
            if count > link.cap:
                raise SimulationError(
                    self.turn, f"{count} drones use {link.name}")
        return ocup

    def _check_zones(self, moves: list[Move]) -> dict[Zone, int]:
        ocup: dict[Zone, int] = {}
        for move in moves:
            if move.direct:
                ocup[move.target] = ocup.get(move.target, 0) + 1
            if not (move.direct and move.target.type_ == ZoneType.R):
                ocup[move.origin] = ocup.get(move.origin, 0) - 1
        for zone, count in ocup.items():
            after = self.occupancy[zone] + count
            if not zone.liminal and after > zone.cap:
                raise SimulationError(
                    self.turn, f"{zone.name} holds {after} drones")
            ocup[zone] = after
        return ocup

    def _apply(self, move: Move) -> None:
        drone = move.drone
        if not (move.direct and move.target.type_ == ZoneType.R):
            self.occupancy[move.origin] -= 1
        if move.direct:
            self.occupancy[move.target] += 1
            drone.move_n += 1
            drone.zone = move.target
        drone.inflight = not move.direct
        if move.target == self._network.end and move.direct:
            drone.delivered = True
            self._remaining -= 1
