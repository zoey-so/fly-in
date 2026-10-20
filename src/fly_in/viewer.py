"""Pygame window that replays a finished simulation with animation."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from types import TracebackType

import pygame

from .errors import FlyInError
from .models import DroneNetwork, Zone, ZoneType
from .runner import Turn, Move
from .planner import FlightPlan
from ._color_data import COLOR_DICT

RGB = tuple[int, int, int]
Point = tuple[float, float]

COLOR_DICT: dict[str, RGB] = COLOR_DICT

THEME: dict[str, RGB] = {
    "BACKGROUND": COLOR_DICT["almostblack"],
    "LINK": COLOR_DICT["bananayellow"],
    "LANE": COLOR_DICT["bluegrey"],
    "TEXT": COLOR_DICT["white"],
    "MUTED": COLOR_DICT["lightgrey"],
    "BLOCKED": COLOR_DICT["palevioletred"],
    "OUTLINE": COLOR_DICT["powderblue"],
    "PANEL": COLOR_DICT["navyblue"],
    "PROG": COLOR_DICT["green"]
}


class Palette:
    """create rgb tuples colors for zones and drones."""

    _RNBW = {
        0: "red",
        1: "orange",
        2: "yellow",
        3: "green",
        4: "blue",
        5: "violet"
    }

    _LCD = list(COLOR_DICT)

    def zone(self, key: str, name: str, mod: float) -> RGB:
        key = key.lower() if key else name.lower()
        if key == "rainbow":
            key = self._RNBW[int(mod * 10) % 6]
        elif key not in COLOR_DICT:
            i = sum(map(ord, key)) % len(COLOR_DICT)
            key = self._LCD[i]
        return COLOR_DICT[key]

    def drone(self, drone_id: int) -> RGB:
        return self._hsv(drone_id * 0.618034, 0.45, 1.0)

    def _hsv(self, hue: float, saturation: float, value: float) -> RGB:
        red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
        return (int(red * 255), int(green * 255), int(blue * 255))

    def dim(self, color: RGB, amount: float) -> RGB:
        bg = THEME["BACKGROUND"]
        return (
            int(bg[0] + (color[0] - bg[0]) * amount),
            int(bg[1] + (color[1] - bg[1]) * amount),
            int(bg[2] + (color[2] - bg[2]) * amount),
        )


@dataclass(frozen=True)
class Layout:
    """Maps zone coordinates to window pixels, with y pointing up."""
    scale: float
    origin_x: float
    origin_y: float
    radius: float

    MARGIN = 26
    MAX_SCALE = 200.0

    @classmethod
    def fit(
        cls, network: DroneNetwork, area: tuple[int, int, int, int]
    ) -> Layout:
        """Return the largest layout that fits (x, y, w, h)."""
        left, top, width, height = area
        xs = [zone.x for zone in network.org_zones]
        ys = [zone.y for zone in network.org_zones]
        usable_x = max(1, width - 2 * cls.MARGIN)
        usable_y = max(1, height - 2 * cls.MARGIN)
        scale = min(
            usable_x / max(1, max(xs) - min(xs)),
            usable_y / max(1, max(ys) - min(ys)),
            cls.MAX_SCALE,
        )
        middle_x = (min(xs) + max(xs)) / 2
        middle_y = (min(ys) + max(ys)) / 2
        return cls(
            scale=scale,
            origin_x=left + width / 2 - middle_x * scale,
            origin_y=top + height / 2 + middle_y * scale,
            radius=max(9.0, min(26.0, scale * 0.28)),
        )

    def point_xy(self, x: float, y: float) -> Point:
        """Return the pixel position of (x, y)."""
        return (self.origin_x + x * self.scale, self.origin_y - y * self.scale)

    def point(self, zone: Zone) -> Point:
        """Pixel coordinates of the center of a zone."""
        return self.point_xy(zone.x, zone.y)


class Window:
    """Context manager for pygame and its display window."""
    def __init__(self, size: tuple[int, int], title: str) -> None:
        self._size = size
        self._title = title

    def __enter__(self) -> pygame.Surface:
        pygame.init()
        try:
            screen = pygame.display.set_mode(self._size, pygame.RESIZABLE)
        except pygame.error as error:
            pygame.quit()
            raise FlyInError(f"cannot open a window: {error}") from None
        pygame.display.set_caption(self._title)
        return screen

    def __exit__(self, kind: type[BaseException] | None,
                 value: BaseException | None,
                 trace: TracebackType | None,
                 ) -> None:
        pygame.quit()


class Viewer:
    """Main class that draws the simulation in a pygame window.
    Parameters
    ----------
    network: DroneNetwork - the map
    turns: list[Turn] - the simulation steps
    plan: FlightPlan - the flight plan
    title: str - the window title
    """

    SIZE = (1440, 847)
    FPS = 30
    TOP = 56
    BOTTOM = 56
    HINTS = (
        "[SPACE] play/pause       "
        "[LEFT]/[RIGHT] step forward/backward       "
        "[L] labels on/off         "
        "[ESC] quit"
    )

    def __init__(
        self,
        network: DroneNetwork,
        turns: list[Turn],
        plan: FlightPlan,
        title: str,
    ) -> None:
        self._net = network
        self._turns = turns
        self._palette = Palette()
        self._title = title
        self._path_edges: set[frozenset[Zone]] = {
            frozenset(pair)
            for path in plan.paths
            for pair in zip(path.zones, path.zones[1:])
        }
        self._labels: bool = True
        self._play: bool = True
        self._seconds = 0.0
        self._frame = 0
        self._rate = 2
        self._max_frame = self.FPS * self._rate * (plan.turns)
        self._fonts: dict[int, pygame.font.Font] = {}

    def run(self) -> None:
        """Open the window and play until the user closes it."""
        with Window(self.SIZE, f"Fly-in - {self._title}") as screen:
            clock = pygame.time.Clock()
            running = True
            while running:
                seconds = min(clock.tick(self.FPS) / 1000.0, 0.25)
                self._seconds += seconds
                for event in pygame.event.get():
                    if not self._handle(event):
                        running = False
                # self._playback.advance(seconds)
                self.draw(screen)
                pygame.display.flip()

    def _handle(self, event: pygame.event.Event) -> bool:
        """React to one event; return False to close the window."""
        if event.type == pygame.QUIT:
            return False
        elif event.type == pygame.KEYDOWN:
            return self._key(event.key)
        return True

    def _key(self, key: int) -> bool:
        """Apply one keyboard shortcut; return False to quit."""
        if key in (pygame.K_ESCAPE, pygame.K_q):
            return False
        if key == pygame.K_SPACE:
            if self._frame == self._max_frame:
                self._frame = 0
                self._play = True
            else:
                self._play = not self._play
        elif key == pygame.K_RIGHT:
            self._play = False
            if self._frame != self._max_frame:
                self._frame = min(self._frame + 10, self._max_frame)
        elif key == pygame.K_LEFT:
            self._play = False
            if self._frame != 0:
                self._frame = max(self._frame - 10, 0)
        elif key in (pygame.K_HOME, pygame.K_r):
            self._frame = 0
        elif key == pygame.K_END:
            self._frame = self._max_frame
        elif key == pygame.K_l:
            self._labels = not self._labels
        return True

    def draw(self, screen: pygame.Surface) -> None:
        """Draw one complete frame"""
        turn_n = self._frame // (self.FPS * self._rate)
        prog: float = (
            self._frame % (self.FPS * self._rate)) / (self.FPS * self._rate)
        if turn_n >= len(self._turns):
            turn_n = len(self._turns) - 1
            prog = 1.0
        turn = self._turns[turn_n]
        prev_turn = self._turns[turn_n - 1] if turn_n > 0 else None
        # width, height = screen.get_size()
        layout = self._layout(screen)
        screen.fill(THEME["BACKGROUND"])
        self._draw_edges(screen, layout)
        self._draw_zones(screen, layout, turn, prev_turn, prog)
        self._draw_drones(screen, layout, turn, prog)
        self._draw_header(screen, screen.get_width(), turn, prev_turn, prog)
        self._draw_footer(screen, screen.get_width(), screen.get_height())
        if self._labels:
            self._draw_labels(screen, layout)
        if self._play:
            if self._frame == self._max_frame:
                self._play = False
            else:
                self._frame += 1

    def _layout(self, screen: pygame.Surface) -> Layout:
        """Fit the map between the header and the footer."""
        width, height = screen.get_size()
        area = (0, self.TOP, width, height - self.TOP - self.BOTTOM)
        return Layout.fit(self._net, area)

    def _draw_edges(self, screen: pygame.Surface, layout: Layout) -> None:
        """Connections thicker for more capacity, path wider"""
        for link in self._net.org_connections:
            start, end = layout.point(link.a), layout.point(link.b)
            width = 1 + min(link.cap, 4)
            is_path = frozenset((link.a, link.b)) in self._path_edges
            if is_path:
                pygame.draw.line(screen, THEME["LANE"], start, end, width + 8)
            dead = link.a.blocked or link.b.blocked
            color = THEME["BLOCKED"] if dead else THEME["LINK"]
            pygame.draw.line(screen, color, start, end, width)

    def _draw_zones(
            self, screen: pygame.Surface, layout: Layout,
            turn: Turn, prev_turn: Turn | None, prog: float) -> None:
        for zone in self._net.org_zones:
            self._draw_zone(screen, layout, turn, zone, prev_turn, prog)

    def _draw_zone(
        self, screen: pygame.Surface, layout: Layout, turn: Turn, zone: Zone,
            prev_turn: Turn | None, prog: float) -> None:
        centre = layout.point(zone)
        radius = layout.radius
        color = self._palette.zone(
            zone.color,
            zone.name,
            (self._frame % (self.FPS * 6)) / (self.FPS * 6))
        if not prev_turn:
            count = self._net.nb_drones if zone == self._net.start else 0
        elif prog >= 1:
            count = turn.z_occup.get(zone, 0)
        else:
            count = prev_turn.z_occup.get(zone, 0)
        pygame.draw.circle(
            screen, self._palette.dim(color, 0.3), centre, radius)
        pygame.draw.circle(screen, color, centre, radius, 4)
        below = (round(centre[0]), round(centre[1] + radius + 3))
        if zone == self._net.start:
            self._text(screen, "START", centre, 14, THEME["TEXT"], "center")
            self._text(screen, f"{count} waiting", below, 15,
                       THEME["MUTED"], "midtop")
        elif zone == self._net.end:
            self._text(screen, "END", centre, 14, THEME["TEXT"], "center")
            self._text(screen, f"{count}/{self._net.nb_drones} home",
                       below, 15, THEME["MUTED"], "midtop")
        else:
            self._text(screen, f"{count}/{zone.cap}", below, 15,
                       THEME["MUTED"], "midtop")

    def _draw_drones(
            self, screen: pygame.Surface, layout: Layout,
            turn: Turn, prog: float) -> None:
        moves: dict[int, Move] = {move.drone._id: move for move in turn.moves}
        conns: dict[tuple[Zone, Zone, int], list[int]] = {}
        for d_id, move in moves.items():
            mode = 1
            if move.target.type_ == ZoneType.R:
                if move.direct:
                    mode = 2
                else:
                    mode = 3
            conns.setdefault((move.origin, move.target, mode), []).append(d_id)
        spots: dict[int, Point] = {}
        for conn, ids in conns.items():
            ax, ay = layout.point(conn[0])
            bx, by = layout.point(conn[1])
            if conn[2] == 2:
                ax, ay = ax + (bx - ax) * 0.5, ay + (by - ay) * 0.5
            if conn[2] == 3:
                bx, by = ax + (bx - ax) * 0.5, ay + (by - ay) * 0.5
            dx, dy = ax + (bx - ax) * prog, ay + (by - ay) * prog
            ids.sort()
            for i, d_id in enumerate(ids):
                shift = (i - (len(ids) - 1) / 2) * layout.radius * 0.7
                spots[d_id] = (dx + shift, dy + shift)
        size = max(4.0, layout.radius * 0.34)
        for d_id, spot in spots.items():
            pygame.draw.circle(screen, THEME["OUTLINE"], spot, size + 1.5)
            pygame.draw.circle(screen, self._palette.drone(d_id), spot, size)
            if self._labels:
                corner = (round(spot[0] + size + 2), round(spot[1] - size))
                self._text(screen, f"D{d_id}", corner, 14,
                           THEME["TEXT"], "bottomleft")

    def _draw_labels(self, screen: pygame.Surface, layout: Layout) -> None:
        """Zone names above their circles."""
        for zone in self._net.zones:
            cx, cy = layout.point(zone)
            radius = layout.radius * (1.3 if zone.liminal else 1.0)
            above = (round(cx), round(cy - radius - 3))
            self._text(
                screen, zone.name, above, 15, THEME["TEXT"], "midbottom")

    def _draw_header(self, screen: pygame.Surface, width: int,
                     turn: Turn, prev_turn: Turn | None, prog: float) -> None:
        pygame.draw.rect(screen, THEME["PANEL"], (0, 0, width, self.TOP))
        pygame.draw.rect(
            screen, THEME["PROG"], (0, self.TOP - 10, width * prog, 10))
        self._text(screen, f"Fly-in  |  {self._title}", (16, 18), 26,
                   THEME["TEXT"], "topleft")
        if prev_turn is None:
            homed = 0
        elif prog >= 1:
            homed = turn.z_occup.get(self._net.end, 0)
        else:
            homed = prev_turn.z_occup.get(self._net.end, 0)
        stats = (
            f"Turn {turn.turn_n}/{len(self._turns)}  "
            f"            Home {homed}/{self._net.nb_drones}"
        )
        self._text(
            screen, stats, (width // 2, 20), 22, THEME["TEXT"], "midtop")

    def _draw_footer(
            self, screen: pygame.Surface, width: int, height: int) -> None:
        pygame.draw.rect(
            screen, THEME["PANEL"],
            (0, height - self.BOTTOM, width, self.BOTTOM))
        font = self._font(22)
        txt_size = font.size(self.HINTS)
        if txt_size[0] <= width:
            x = (width - txt_size[0]) / 2
            y = height - self.BOTTOM + (self.BOTTOM - txt_size[1]) / 2
            self._text(
                screen, self.HINTS, (x, y), 22, THEME["TEXT"], "topleft")

    def _font(self, size: int) -> pygame.font.Font:
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    def _text(
        self, screen: pygame.Surface, text: str, pos: tuple[float, float],
        size: int, color: RGB, anchor: str = "topleft",
    ) -> int:
        image = self._font(size).render(text, True, color)
        box = image.get_rect()
        setattr(box, anchor, (round(pos[0]), round(pos[1])))
        screen.blit(image, box)
        return box.right
