"""Synthetic match scenes with known answers, so every module can be tested without the match data.

Issue #3. Each scene in SCENES is a test scene from docs/EDGE_CASES.md: a `Match` plus the
labels the organisers' definition gives it. Scenes are deterministic and physically plausible;
they are small on purpose, so a failing test points at one situation.

Build a scene by calling the builder in time order. Positions persist: after `move`, `place`,
`kick` or `ball_at`, the object stays where it ended until a later call moves it. Call a
player's `move` before a `carry` that follows them, because `carry` reads their path.

Adding an edge case: write a function returning `SyntheticCase`, register it in SCENES under its
EC id (with a variant letter if needed), and add a test that names what the scene must contain.
"""

from dataclasses import dataclass

import numpy as np

from possession.types import AWAY, FPS, HOME, NOBODY, PITCH, Match

# Params
CARRY_OFFSET = (0.5, 0.0)  # ball sits half a metre in front of the carrier, metres
CARE_MARGIN = 5  # frames either side of a label change that tests do not grade

# 4-4-2 for the home side, attacking towards x = pitch length. Away mirrors it in x.
HOME_FORMATION = (
    (5.0, 34.0),                                          # 0 goalkeeper
    (25.0, 10.0), (25.0, 26.0), (25.0, 42.0), (25.0, 58.0),  # 1-4 defenders
    (40.0, 10.0), (40.0, 26.0), (40.0, 42.0), (40.0, 58.0),  # 5-8 midfielders
    (50.0, 26.0), (50.0, 42.0),                           # 9-10 forwards
)


@dataclass(eq=False)
class SyntheticCase:
    """A scene and its answer. `care` marks the frames a test should grade."""

    match: Match
    expected: np.ndarray
    care: np.ndarray
    note: str


class SceneBuilder:
    """Imperative scene construction. Times are seconds; intervals are [t0, t1]."""

    def __init__(self, seconds, fps=FPS, pitch=PITCH, seed=0):
        self.fps = float(fps)
        self.pitch = pitch
        self.seed = seed
        self.n = int(round(seconds * self.fps))
        formation = np.array(HOME_FORMATION)
        mirrored = formation.copy()
        mirrored[:, 0] = pitch[0] - mirrored[:, 0]
        self.players = np.repeat(np.concatenate([formation, mirrored])[None], self.n, axis=0)
        self.team = np.array([HOME] * 11 + [AWAY] * 11, dtype=np.int8)
        self.ball = np.full((self.n, 2), np.nan)
        self.expected = np.full(self.n, "X", dtype="<U1")
        self._hidden = np.zeros(self.n, dtype=bool)

    def frame(self, seconds):
        return min(int(round(seconds * self.fps)), self.n - 1)

    def _span(self, t0, t1):
        f0, f1 = self.frame(t0), self.frame(t1)
        if f1 < f0:
            raise ValueError("interval ends before it starts: {} > {}".format(t0, t1))
        return f0, f1

    # -- players ---------------------------------------------------------------------------------

    def place(self, slot, position, t0=0.0):
        """Put a player at a position from t0 on."""
        self.players[self.frame(t0):, slot] = position
        return self

    def move(self, slot, end, t0, t1):
        """Walk or run in a straight line from wherever the player is at t0."""
        f0, f1 = self._span(t0, t1)
        start = self.players[f0, slot].copy()
        steps = np.linspace(0.0, 1.0, f1 - f0 + 1)[:, None]
        self.players[f0:f1 + 1, slot] = start + steps * (np.asarray(end) - start)
        self.players[f1 + 1:, slot] = end
        return self

    # -- ball ------------------------------------------------------------------------------------

    def _feet(self, slot, frames):
        return self.players[frames, slot] + np.asarray(CARRY_OFFSET)

    def carry(self, slot, t0, t1):
        """The player dribbles: the ball follows their path."""
        f0, f1 = self._span(t0, t1)
        self.ball[f0:f1 + 1] = self._feet(slot, slice(f0, f1 + 1))
        self.ball[f1 + 1:] = self.ball[f1]
        return self

    def ball_at(self, position, t0, t1):
        """The ball lies still (a restart, or a ball held for a throw-in)."""
        f0, f1 = self._span(t0, t1)
        self.ball[f0:] = position
        return self

    def kick(self, target, t0, t1):
        """Pass, shot or clearance in a straight line. `target` is a position or a slot."""
        f0, f1 = self._span(t0, t1)
        start = self.ball[f0].copy()
        if np.isnan(start).any():
            raise ValueError("kick at {}s: the ball has no position to start from".format(t0))
        end = self._feet(target, f1) if isinstance(target, (int, np.integer)) else np.asarray(
            target, dtype=float)
        steps = np.linspace(0.0, 1.0, f1 - f0 + 1)[:, None]
        self.ball[f0:f1 + 1] = start + steps * (end - start)
        self.ball[f1 + 1:] = end
        return self

    def hide_ball(self, t0, t1):
        """The tracker loses the ball on [t0, t1). Applied at build time, whatever the order."""
        self._hidden[self.frame(t0):self.frame(t1)] = True
        return self

    # -- answer ----------------------------------------------------------------------------------

    def label(self, label, t0, t1=None):
        """Expected label on [t0, t1); to the end when t1 is None."""
        f1 = self.n if t1 is None else self.frame(t1)
        self.expected[self.frame(t0):f1] = label
        return self

    def label_frames(self, label, f0, f1=None):
        self.expected[f0:self.n if f1 is None else f1] = label
        return self

    def build(self, note, margin=CARE_MARGIN, noise=0.0):
        ball = self.ball.copy()
        ball[self._hidden] = np.nan
        players = self.players.copy()
        if noise:
            rng = np.random.default_rng(self.seed)
            players = players + rng.normal(0.0, noise, players.shape)
            ball = ball + rng.normal(0.0, noise, ball.shape)

        care = self.expected != "X"
        changes = np.flatnonzero(self.expected[1:] != self.expected[:-1]) + 1
        for change in changes:
            care[max(0, change - margin):change + margin] = False

        match = Match(ball=ball, players=players, team=self.team, pitch=self.pitch, fps=self.fps)
        return SyntheticCase(match=match, expected=self.expected.copy(), care=care, note=note)


# -- scenes --------------------------------------------------------------------------------------

def _long_ball(variant):
    """EC-02: home centre-back plays 45 m; the ball is lost in flight next to an opponent."""
    b = SceneBuilder(seconds=12)
    b.move(2, (30.0, 28.0), 0.0, 3.0).carry(2, 0.0, 3.0)
    b.move(13, (63.0, 31.0), 0.0, 3.0)  # away defender under the flight path: the trap
    b.hide_ball(3.6, 4.6)

    if variant == "a":
        b.move(9, (75.0, 30.0), 0.0, 5.0).kick(9, 3.0, 5.0)
        b.move(9, (85.0, 32.0), 5.0, 12.0).carry(9, 5.0, 12.0)
        b.label("H", 0.0)
        note = "EC-02a: long ball, home forward receives"
    elif variant == "b":
        b.move(15, (76.0, 31.0), 0.0, 5.0).kick(15, 3.0, 5.0)
        b.kick((68.0, 40.0), 5.0, 5.6)  # away header, no control
        b.move(8, (68.0, 40.0), 0.0, 5.6)
        b.move(8, (75.0, 45.0), 5.6, 12.0).carry(8, 5.6, 12.0)
        b.label("H", 0.0)
        note = "EC-02b: long ball, away heads it away without control, home recovers"
    elif variant == "c":
        b.move(15, (76.0, 31.0), 0.0, 5.0).kick(15, 3.0, 5.0)
        b.move(15, (70.0, 32.0), 5.0, 6.5).carry(15, 5.0, 6.5)
        b.move(16, (66.0, 24.0), 0.0, 6.5).kick(16, 6.5, 7.3)
        b.move(16, (60.0, 28.0), 7.3, 12.0).carry(16, 7.3, 12.0)
        b.label("H", 0.0, 5.0).label("A", 5.0)
        note = "EC-02c: long ball intercepted, away controls and passes; change at first touch"
    else:
        raise ValueError(variant)
    return b.build(note)


def throw_in():
    """EC-05: home plays it out over the touchline; away throws in. D until the ball is back."""
    b = SceneBuilder(seconds=16)
    b.move(5, (48.0, 4.0), 0.0, 4.0).carry(5, 0.0, 4.0)
    b.kick((52.0, -2.0), 4.0, 4.6)
    b.hide_ball(4.6, 8.0)
    b.move(16, (52.0, -0.5), 4.0, 9.0)  # thrower walks to the line
    b.move(17, (58.0, 9.0), 4.0, 11.0)  # receiver gets free
    b.ball_at((52.0, -0.8), 8.0, 12.0)
    b.kick(17, 12.0, 12.8)
    b.move(17, (64.0, 14.0), 12.8, 16.0).carry(17, 12.8, 16.0)

    outside = b.ball[:, 1] < 0
    crossing = int(np.argmax(outside))
    back_in = int(np.flatnonzero(outside)[-1]) + 1
    b.label_frames("H", 0, crossing).label_frames("D", crossing, back_in)
    b.label_frames("A", back_in)
    return b.build("EC-05: throw-in, dead from crossing the line until the ball re-enters")


def corner():
    """EC-06: corner for home; everybody waits, D ends when the ball is struck."""
    b = SceneBuilder(seconds=10)
    length = b.pitch[0]
    b.ball_at((length - 0.5, 0.5), 0.0, 6.0)
    b.place(10, (length - 1.0, 1.0))
    for slot, position in ((9, (96.0, 31.0)), (8, (99.0, 38.0)), (7, (97.0, 26.0)),
                           (11, (104.0, 34.0)), (12, (100.0, 30.0)), (13, (100.0, 36.0)),
                           (14, (98.0, 34.0)), (20, (96.0, 38.0))):
        b.place(slot, position)
    b.move(9, (95.0, 30.0), 6.0, 7.2)
    b.kick(9, 6.0, 7.2)
    b.hide_ball(6.3, 7.0)
    b.move(9, (98.0, 32.0), 7.2, 10.0).carry(9, 7.2, 10.0)
    b.label("D", 0.0, 6.0).label("H", 6.0)
    return b.build("EC-06: corner restart, dead ball until the kick")


SCENES = {
    "EC-02a": lambda: _long_ball("a"),
    "EC-02b": lambda: _long_ball("b"),
    "EC-02c": lambda: _long_ball("c"),
    "EC-05": throw_in,
    "EC-06": corner,
}


# -- EPTS export ---------------------------------------------------------------------------------

def _format(values):
    return ",".join("NaN" if np.isnan(v) else "{:.6f}".format(v) for v in values)


def write_epts(match, meta_path, raw_path):
    """Write a match in the ATD layout (metadata XML + raw text), for loader tests (#6).

    Coordinates are normalised to 0-1 and frame ids count from 1, as in the provided ATD.
    """
    scale = np.array(match.pitch)
    players = match.players / scale
    ball = match.ball / scale

    def speeds(track):
        step = np.linalg.norm(np.diff(track * scale, axis=0), axis=-1) * match.fps
        return np.concatenate([np.zeros((1,) + step.shape[1:]), step])

    player_speed, ball_speed = speeds(players), speeds(ball)
    with open(raw_path, "w", encoding="utf-8", newline="\n") as handle:
        for frame in range(match.n_frames):
            groups = ";".join(_format((*players[frame, slot], player_speed[frame, slot]))
                              for slot in range(match.n_slots))
            handle.write("{}:{}:{}\n".format(frame + 1, groups,
                                             _format((*ball[frame], ball_speed[frame]))))

    team_ids = {HOME: "T1", AWAY: "T2", NOBODY: "OTHER"}
    player_xml = "\n".join(
        '      <Player id="P{0}" teamId="{1}"><Name>Track {0}</Name>'
        '<ShirtNumber>{0}</ShirtNumber></Player>'.format(slot + 1, team_ids[int(code)])
        for slot, code in enumerate(match.team))
    meta = """<main>
  <Metadata>
    <Teams>
      <Team id="T1"><Name>Home</Name></Team>
      <Team id="T2"><Name>Away</Name></Team>
    </Teams>
    <Players>
{players}
    </Players>
    <Devices><Device id="d"><Sensors><Sensor id="s"><Channels>
      <Channel id="x"><Name>position_x</Name></Channel>
      <Channel id="y"><Name>position_y</Name></Channel>
      <Channel id="speed"><Name>speed</Name></Channel>
    </Channels></Sensor></Sensors></Device></Devices>
  </Metadata>
  <DataFormatSpecifications>
    <DataFormatSpecification startFrame="1" endFrame="{n}" separator=":">
      <StringRegister name="frameCount"/>
    </DataFormatSpecification>
  </DataFormatSpecifications>
</main>
""".format(players=player_xml, n=match.n_frames)
    with open(meta_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(meta)
