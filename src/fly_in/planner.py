"""Flight plan generator for drone networks."""
from dataclasses import dataclass

from .errors import UnsolvableMapError
from .spfa import FlowNetwork
from .models import Cost, DroneNetwork, Zone


@dataclass(frozen=True)
class FlightPath:
    """
    Attributes:
        zones: Zone from the start hub to the end hub.
        turns: Turns a drone needs to fly the whole route.
        flow: Drones that fly together on every turn.
    """
    zones: tuple[Zone, ...]
    turns: int
    flow: int

    def deliveries_by(self, turn: int) -> int:
        """return how many drones this path can land by turn"""
        return self.flow * max(0, turn - self.turns + 1)


@dataclass(frozen=True)
class DronePlan:
    """Route and take-off turn of one drone."""
    drone_id: int
    path: FlightPath
    departure: int

    @property
    def arrival(self) -> int:
        """the turn on which the drone reaches the end hub."""
        return self.departure + self.path.turns - 1


@dataclass(frozen=True)
class FlightPlan:
    """Final plan for all drones includes paths,
    plan for each drone and number of turns needed for all.
    """
    paths: tuple[FlightPath, ...]
    drones: tuple[DronePlan, ...]
    turns: int


class Planner:
    """Planner translates the DroneNetwork into residual graph,
    finds best paths using spfa and stops when no more rewarding
    augumentation is possible."""
    def __init__(self, network: DroneNetwork) -> None:
        """_node_zone - list of zones,
                the indexes becomes int vertices in graph
            _entry - dict from zone to its entry vertex after split
            _exit - dict from zone to its exit vertex aftern split
        """
        self._network = network
        self._node_zone: list[Zone] = []
        self._entry: dict[Zone, int] = {}
        self._exit: dict[Zone, int] = {}

    def plan(self) -> FlightPlan:
        """loop:finds the path using spfa, calculates number of turns needed
            keeps adding paths if calculated turns are better.
            early exits - no more paths, path longer than current needed
            raises UnsolvableMapError if the first response from spfa is None
        """
        flow_net, source, sink = self._build_flow_network()
        nb_drones = self._network.nb_drones
        best_turns = 0
        best_paths: list[FlightPath] = []
        pushed = 0
        while pushed < nb_drones:
            step = flow_net.augment(source, sink, nb_drones - pushed)
            if step is None:
                break
            if best_paths and step.unit_cost.turns >= best_turns:
                break
            pushed += step.flow
            paths = self._extract_paths(flow_net, source, sink)
            turns = self._turns_needed(paths)
            if not best_paths or turns < best_turns:
                best_turns, best_paths = turns, paths
        if not best_paths:
            raise UnsolvableMapError(
                "no path links start_hub with end_hub")
        drones = self._schedule(best_paths, best_turns)
        return FlightPlan(tuple(best_paths), drones, best_turns)

    def _new_node(self, zone: Zone) -> int:
        """Add a vertex that belongs to zone, return the index."""
        self._node_zone.append(zone)
        return len(self._node_zone) - 1

    def _build_flow_network(self) -> tuple[FlowNetwork, int, int]:
        """Build a bidirectional directed graph
        with splitting vertexes to keep zone capacity"""
        net = self._network
        self._node_zone, self._entry, self._exit = [], {}, {}
        for zone in net.zones:
            self._entry[zone] = self._new_node(zone)
            self._exit[zone] = (self._entry[zone]
                                if zone.liminal
                                else self._new_node(zone))
        flow = FlowNetwork(len(self._node_zone))
        for zone in net.zones:
            if not zone.liminal:
                flow.add_arc(
                    self._entry[zone], self._exit[zone],
                    zone.cap, Cost(),
                )
        for link in net.connections:
            directions = ((link.a, link.b), (link.b, link.a))
            for tail, head in directions:
                if not (tail == net.end or head == net.start):
                    flow.add_arc(
                        self._exit[tail], self._entry[head],
                        link.cap, head.entry_cost,
                    )
        return flow, self._entry[net.start], self._entry[net.end]

    def _extract_paths(
        self, flow: FlowNetwork, source: int, sink: int
    ) -> list[FlightPath]:
        rates: dict[tuple[Zone, ...], int] = {}
        for nodes, amount in flow.decompose(source, sink):
            path: list[Zone] = []
            for node in nodes:
                zone = self._node_zone[node]
                if not path or path[-1] != zone:
                    path.append(zone)
            rates[tuple(path)] = rates.get(tuple(path), 0) + amount
        costs = {path: self._path_cost(path) for path in rates}
        ordered = sorted(rates, key=lambda path: costs[path])
        return [
            FlightPath(path, costs[path].turns, rates[path])
            for path in ordered
        ]

    def _path_cost(self, path: tuple[Zone, ...]) -> Cost:
        total = Cost()
        for zone in path[1:]:
            total = total + zone.entry_cost
        return total

    def _turns_needed(self, paths: list[FlightPath]) -> int:
        """Return the T at which all land using given paths."""
        nb_drones = self._network.nb_drones
        low = min(path.turns for path in paths)
        high = low + nb_drones - 1
        while low < high:
            middle = (low + high) // 2
            landed = sum(path.deliveries_by(middle) for path in paths)
            if landed >= nb_drones:
                high = middle
            else:
                low = middle + 1
        return low

    def _schedule(
        self, paths: list[FlightPath], turns: int
    ) -> tuple[DronePlan, ...]:
        """create plan for every drone."""
        slots: list[tuple[int, FlightPath, int]] = []
        missing = self._network.nb_drones
        for i in range(1, turns + 1):
            for path in paths:
                nb = min(path.flow, missing)
                slots.append((i, path, nb))
                missing -= nb
                if missing == 0:
                    break
            if missing == 0:
                break
        plans: list[DronePlan] = []
        for departure, path, count in slots:
            for _ in range(count):
                plans.append(
                    DronePlan(len(plans) + 1, path, departure)
                )
        return tuple(plans)
