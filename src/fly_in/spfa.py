"""
Shortest Path Faster Algorithm (SPFA)
implementation for min-cost max-flow.
"""
from collections import deque
from dataclasses import dataclass

from .models import Cost


@dataclass
class Arc:
    """Directed edge of the residual graph.

    Attributes:
        head: index of Node the arc points to usig graph[head].
        cap: available capacity.
        init_cap: Initial capacity (0 for backwards).
        cost: cost of one donre.
        reverse: index of the reverse arc graph[head][reverse].
    """

    head: int
    cap: int
    init_cap: int
    cost: Cost
    reverse: int

    @property
    def flow(self) -> int:
        """Return the units pushed through this arc."""
        return self.init_cap - self.cap if self.init_cap > 0 else 0


@dataclass(frozen=True)
class Augmentation:
    """Result of pushing along one residual path."""
    flow: int
    unit_cost: Cost


class FlowNetwork:
    """Directed graph with capacities and costs on arcs."""

    def __init__(self, v_count: int) -> None:
        """Create list of vertices that are lists with arcs from the vertex"""
        self._graph: list[list[Arc]] = [[] for _ in range(v_count)]

    def add_arc(self, tail: int, head: int, cap: int, cost: Cost) -> None:
        """Add arc tail -> head plus its empty reverse twin."""
        forward = Arc(head, cap, cap, cost, len(self._graph[head]))
        backward = Arc(tail, 0, 0, -cost, len(self._graph[tail]))
        self._graph[tail].append(forward)
        self._graph[head].append(backward)

    def augment(
        self, source: int, sink: int, limit: int
    ) -> Augmentation | None:
        """queue-based SPFA to be called in loop to try doing more paths
        after each call calculate the created path
        Returns
        --------
        Augumentation - cost of path found and max flow on the path
        None - when the sink is unreachable.
        """
        size = len(self._graph)
        dist: list[Cost | None] = [None] * size
        via: list[tuple[int, int] | None] = [None] * size
        queued = [False] * size
        dist[source] = Cost()
        queue = deque([source])
        queued[source] = True
        while queue:
            node = queue.popleft()
            queued[node] = False
            here = dist[node]
            if here is None:
                continue
            for index, arc in enumerate(self._graph[node]):
                if arc.cap == 0:
                    continue
                candidate = here + arc.cost
                known = dist[arc.head]
                if known is None or candidate < known:
                    dist[arc.head] = candidate
                    via[arc.head] = (node, index)
                    if not queued[arc.head]:
                        queued[arc.head] = True
                        queue.append(arc.head)
        total = dist[sink]
        if total is None:
            return None
        steps = self._trace(via, source, sink)
        amount = min([limit] + [self._graph[u][i].cap for u, i in steps])
        for u, i in steps:
            arc = self._graph[u][i]
            arc.cap -= amount
            self._graph[arc.head][arc.reverse].cap += amount
        return Augmentation(amount, total)

    def _trace(
        self, via: list[tuple[int, int] | None], source: int, sink: int
    ) -> list[tuple[int, int]]:
        """Return the (node, arc index) steps from source to sink."""
        steps: list[tuple[int, int]] = []
        node = sink
        while node != source:
            step = via[node]
            if step is not None:
                steps.append(step)
                node = step[0]
        steps.reverse()
        return steps

    def decompose(self, source: int, sink: int) -> list[tuple[list[int], int]]:
        """extracts the paths from current state of graph"""
        left = {
            (node, index): arc.flow
            for node, arcs in enumerate(self._graph)
            for index, arc in enumerate(arcs)
            if arc.flow > 0
        }
        paths: list[tuple[list[int], int]] = []
        while True:
            nodes = [source]
            steps: list[tuple[int, int]] = []
            while nodes[-1] != sink:
                node = nodes[-1]
                index = next(
                    (i for i in range(len(self._graph[node]))
                     if left.get((node, i), 0) > 0),
                    -1,
                )
                if index == -1:
                    break
                steps.append((node, index))
                nodes.append(self._graph[node][index].head)
            if nodes[-1] != sink:
                return paths
            amount = min(left[step] for step in steps)
            for step in steps:
                left[step] -= amount
            paths.append((nodes, amount))
