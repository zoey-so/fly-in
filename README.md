*This project has been created as part of the 42 curriculum by smilch.*

# Fly-in

## Description

Fly-in routes a fleet of drones from a start hub to an end hub through a
network of zones, in as few simulation turns as possible. Every move must
respect the map's rules: zone capacities (`max_drones`), connection
capacities (`max_link_capacity`), zone types (normal, priority, restricted,
blocked) and simultaneous turn-by-turn movement.

The program has four parts:

1. **Parser** - reads a map file and builds a validated `DroneNetwork`, or
   stops with the line number and cause of the first error.
2. **Planner** - computes, before the simulation starts, the set of routes
   ("lanes") to use, how many drones each carries per turn, and the take-off
   turn of every drone. It is a min-cost-flow algorithm written from scratch.
3. **Simulator** - executes the plan turn by turn, checks every movement and
   capacity rule on its own, and prints one line per turn in the required
   format.
4. **Viewer** (optional, `-gui`) - a pygame window that replays the run with
   animated drones.

Every map shipped with the subject is solved in its optimal number of turns,
including the bonus map *The Impossible Dream* (43 turns):

| Map | Drones | Turns | Optimum |
| --- | --- | --- | --- |
| linear_path | 2 | 4 | 4 |
| simple_fork | 4 | 4 | 4 |
| basic_capacity | 4 | 4 | 4 |
| dead_end_trap | 5 | 8 | 8 |
| circular_loop | 6 | 10 | 10 |
| priority_puzzle | 5 | 6 | 6 |
| maze_nightmare | 8 | 13 | 13 |
| capacity_hell | 12 | 16 | 16 |
| ultimate_challenge | 15 | 26 | 26 |
| the_impossible_dream | 25 | 43 | 43 |

## Instructions

### Requirements

- Python **3.11 or later** .
- UV for package management - Makefile uses uv.
- `pygame` only for the optional graphical replay. Everything else uses the
  standard library.
- Development tools: `flake8`, `mypy`.

### Installation

```bash
make install
```

### Running

```bash
make run                                 # runs the default map
make gui                                 # runs the default map with GUI
MAP="path_to_map_file" make run          # run with custom map
```
or using uv directly:
```bash
uv run fly-in                                  # runs the default map
uv run fly-in -gui                             # runs the default map with GUI
uv run fly-in "path_to_map_file"               # run with custom map
```
- The only positional argument is the path to a map file.
- `-gui` opens the replay window after the turn lines have been printed.
- Standard output contains the turn lines.

### Other Makefile rules

| Rule | Effect |
| --- | --- |
| `make debug` | Runs the program under `pdb` |
| `make lint` | `flake8 .` and `mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs` |
| `make lint-strict` | `flake8 .` and `mypy . --strict` |
| `make clean` | Removes `__pycache__` and `.mypy_cache` |

## Algorithm and implementation strategy

### 1. Why plan with flows instead of moving drones one by one

Two quantities bound how fast the fleet can arrive:

- **Latency** - the number of turns the fastest route takes. No drone lands
  earlier.
- **Throughput** - how many drones can land per turn. It is limited by the
  narrowest "cut" of the map (the zones or connections every route must
  cross).

Sending every drone down the fastest route is optimal when that route is the
only bottleneck, but wastes turns when a second, possibly slower, route could
carry extra drones in parallel (`simple_fork`, `priority_puzzle`). Deciding
how many routes to use, and which, is a flow-network problem: the planner
treats the fleet as a flow of drones per turn. 
The program will find always the most optimal solution.

### 2. The flow network (`Planner._build_flow_network`)

The map is turned into a directed graph with capacities and costs:

- **Node splitting.** Every ordinary zone becomes two vertices, *entry* and
  *exit*, joined by one arc whose capacity is the zone's `max_drones` and
  whose cost is 0. Every connection into the zone ends at *entry* and every
  connection out of it starts at *exit*, so all drones passing through the
  zone share that one arc. This turns the zone-capacity rule into an ordinary
  arc capacity.
- **Hubs.** The start and end hubs have no capacity limit, so they stay
  single vertices.
- **Connections.** Each connection becomes two arcs, one per direction, from
  the tail's exit to the head's entry, with capacity `max_link_capacity`.
  Arcs into the start or out of the end are not created.
- **Blocked zones** and their connections are left out of the graph.
- **Costs.** An arc costs the entry cost of the zone it leads to: 1 turn,
  2 turns for a restricted zone. Costs are compared lexicographically as
  `Cost(turns, bonus)`, where `bonus` is -1 per priority zone, so priority
  zones only break ties between equally fast routes and never make a route
  slower.

A route's total cost in turns is therefore exactly its flight time.

### 3. Min-cost flow by successive shortest paths (`spfa.py`)

Each call to `FlowNetwork.augment` finds the cheapest path that still has
free capacity in the **residual graph** and pushes as many drones per turn as
that path allows.

- Every arc has a reverse twin with capacity 0 and opposite cost. Pushing
  flow along an arc opens its twin, so a later path can partly cancel an
  earlier choice and reroute it. This is what lets the algorithm find two
  disjoint routes where a greedy approach would block itself.
- Because twin arcs have negative costs, Dijkstra cannot be used. The search
  is **SPFA** (Shortest Path Faster Algorithm), the queue-based form of
  Bellman-Ford: a vertex is re-examined whenever its distance improves. It
  terminates because the residual graph of a min-cost flow never contains a
  negative cycle.
- After each augmentation, the flow is the cheapest flow of its value, and
  successive augmenting paths never get cheaper.

### 4. From flow to lanes (`FlowNetwork.decompose`, `Planner._extract_paths`)

The flow is split back into source-to-sink paths by repeatedly following
arcs that still carry flow and removing the smallest amount found on the
way (flow decomposition). Consecutive entry/exit vertices of the same zone
are merged, which gives zone routes. Each route becomes a `FlightPath` with:

- `turns` - its flight time,
- `flow` - how many drones can take off on it together every turn.

### 5. How many lanes, and how many turns (`Planner.plan`, `_turns_needed`)

If drones are launched back to back, a lane of length `L` and flow `r` lands
`r * (T - L + 1)` drones by turn `T`. The smallest `T` for which the lanes
land all `N` drones is found by binary search between the shortest lane
length and that length plus `N - 1`.

The planner repeats: augment once, rebuild the lanes, compute `T`, keep the
best plan. It stops when:

- no augmenting path is left (maximum flow reached),
- the flow can already launch every drone on turn 1, or
- the next path is at least as long as the best `T`: a lane of length
  `L >= T` cannot land anything before turn `T`, and later paths are never
  shorter.

Adding a lane does not always improve `T` immediately (several slower lanes
may be needed together before the total crosses `N` one turn earlier), so
the loop continues past lanes that do not help yet, and only stops on the
rules above.

This construction is the "temporally repeated flow" of Ford and Fulkerson,
which they proved delivers the maximum number of units by a given time. For
every shipped map, the resulting `T` equals the subject's optimum.

### 6. Scheduling the drones (`Planner._schedule`)

Every lane offers `flow` take-off slots per turn; a slot taken on turn `d`
lands on turn `d + L - 1`. The scheduler walks landing turns from the
earliest possible to `T` and takes slots in that order until all `N` drones
are placed, then numbers the drones by take-off turn. Taking the earliest
landings guarantees every drone arrives by `T`.

Drones never wait once they have taken off, so each one occupies each zone
of its route for exactly one turn. Per turn, the drones in a zone or on a
connection are then at most the flow through it, which is at most its
capacity: the schedule respects every rule without any conflict resolution.
Waiting happens only at the start hub, which has no capacity limit.

### 7. Simulation (`runner.py`)

`Simulator.run()` is a generator that plays one turn per step:

1. Drones whose take-off turn has come join the active list.
2. Each active drone produces its next `Move`: a normal step, a take-off
   toward a restricted zone (printed as `D<id>-<connection>`), or the
   mandatory landing on the next turn.
3. Link usage (take-offs and steps; landings do not occupy the link) and
   end-of-turn zone occupancy are checked for all moves at once, so a zone
   vacated this turn is available this turn.
4. Moves are applied, delivered drones are removed, and the turn is printed.

Any violation of rules raises `SimulationError`, however it cant happen with `FlightPlan` coming from my `Planner`.

### 8. Complexity

| Part | Cost |
| --- | --- |
| Parsing | O(lines) |
| One augmentation (SPFA) | O(V * E) worst case, V and E counted on the split graph |
| Number of augmentations | at most the maximum flow, bounded by capacities near the start hub, not by `N` |
| Scheduling | O(T * lanes + N log N) |
| Simulation | O(number of turns) |

Paths are computed once, before the simulation; nothing is recalculated per
turn. Planning does not depend on the number of drones, so large fleets cost
only their output: *The Impossible Dream* runs in about 80 ms, and
`linear_path` with 10 000 drones (10 002 turns) in under a second.

### 9. Error handling

- Map errors stop the program with `FlyInError: Line: <n> - <cause>`.
- A map whose start cannot reach its end prints
  `FlyInError: no path links start_hub with end_hub` instead of looping.
- Unknown metadata keys are ignored with a warning on standard error.
- Every other exception is caught in `main()`, so no traceback is shown.

## Visual representation

Run with `-gui` to replay the finished simulation in a pygame window.

- **The map at its real coordinates.** Zones are drawn where the file places
  them, scaled to fit the window, in the colour given by `color=`. A table of
  over 1 500 colour names is supported; unknown names get a stable colour
  derived from the name, and `rainbow` cycles through colours.
- **Capacities at a glance.** Connection thickness grows with
  `max_link_capacity`, and every zone shows `occupancy/max_drones`; the start
  hub shows how many drones are still waiting and the end hub how many are
  home.
- **The plan made visible.** Connections used by the planner's lanes are
  highlighted, so you can see which routes the algorithm chose and which
  traps it ignored. Connections touching blocked zones have their own colour.
- **Animated drones.** Each drone has its own colour and glides from zone to
  zone. A drone flying to a restricted zone stops halfway along the
  connection on its take-off turn and lands on the next turn, which shows
  the 2-turn rule directly.
- **Status.** The header shows the current turn, the number of drones home
  and a progress bar for the current turn; the footer lists the controls.

| Key | Action |
| --- | --- |
| Space | Play / pause (restarts at the end) |
| Left / Right | Step backward / forward |
| Home or R / End | Jump to the start / end |
| L | Show / hide zone and drone labels |
| Esc or Q | Quit |

Watching the replay makes the algorithm's behaviour visible in a way the
text output does not: the steady one-drone-per-turn stream on throughput-1
maps, several lanes filling in parallel on wider maps, and drones queueing
for restricted connections.

## Example

Input (`maps/medium/03_priority_puzzle.txt`):

```text
nb_drones: 5

start_hub: start 0 0 [color=green]
hub: slow_path1 1 -1 [zone=restricted color=red]
hub: slow_path2 2 -1 [color=red]
hub: fast_junction 1 0 [zone=priority color=blue max_drones=2]
hub: fast_path 2 0 [zone=priority color=blue]
hub: merge_point 3 0 [color=yellow max_drones=3]
end_hub: goal 4 0 [color=green]

connection: start-slow_path1
connection: start-fast_junction
connection: slow_path1-slow_path2
connection: slow_path2-merge_point
connection: fast_junction-fast_path
connection: fast_path-merge_point
connection: merge_point-goal [max_link_capacity=2]
```

Command and output:

```text
$ uv run fly-in maps/medium/03_priority_puzzle.txt
D1-fast_junction D2-start-slow_path1
D1-fast_path D2-slow_path1 D3-fast_junction D4-start-slow_path1
D1-merge_point D2-slow_path2 D3-fast_path D4-slow_path1 D5-fast_junction
D1-goal D2-merge_point D3-merge_point D4-slow_path2 D5-fast_path
D2-goal D3-goal D4-merge_point D5-merge_point
D4-goal D5-goal
```

Six turns, the optimum. The planner uses two lanes: the fast priority route
(4 turns) and the slower route through the restricted `slow_path1`
(5 turns). `D2-start-slow_path1` is D2 taking off on the connection toward
the restricted zone; it lands one turn later (`D2-slow_path1`), while D4
takes off behind it on the same connection.

Error examples:

```text
$ uv run fly-in maps/broken_dash.txt
FlyInError: Line: 4 - Zone name can't use dashes, got 'a-b'.

$ uv run fly-in maps/disconnected.txt
FlyInError: no path links start_hub with end_hub
```

## Resources

### Algorithms

- [Minimum-cost flow - Successive shortest path algorithm](https://cp-algorithms.com/graph/min_cost_flow.html) (cp-algorithms)
- [Maximum flow - Ford-Fulkerson and Edmonds-Karp](https://cp-algorithms.com/graph/edmonds_karp.html) (cp-algorithms)
- [Bellman-Ford Algorithm](https://cp-algorithms.com/graph/bellman_ford.html) (cp-algorithms)
- [Minimum-cost flow - Successive shortest path algorithm](https://cp-algorithms.com/graph/min_cost_flow.html) (cp-algorithms)
- [SPFA explanation](https://www.geeksforgeeks.org/dsa/shortest-path-faster-algorithm/) (geeksforgeeks)
- [Shortest Path Faster Algorithm](https://en.wikipedia.org/wiki/Shortest_path_faster_algorithm)
  and [Minimum-cost flow problem](https://en.wikipedia.org/wiki/Minimum-cost_flow_problem)
  (Wikipedia).

### Tools and documentation

- [pygame documentation](https://www.pygame.org/docs/).


### Use of AI

**Claude (Anthropic):**

- **Code review:**
  - making test maps in `maps/addons/`
  - finding a major bug in `Planner._schedule` (launching on every lane each turn)
  - minor problems (printing one of the parser's warnings to standard output, building list(COLOR_DICT) on every frame)
- **Documentation:** drafting this README.

**GitHub Copilot Autocompletion** was used for some docstrings.

All the code was written manually.
