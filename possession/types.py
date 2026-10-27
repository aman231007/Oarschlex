"""The shared contract every module is built against (issue #2, docs/PLAN.md).

Coordinates are metres with the origin at a corner of the pitch, x along its length and y
along its width. A missing observation is NaN, never a sentinel value. Row i of every array is
frame i of the recording; for BAR-ATH that is video frame i, which is submission row i.

Change these definitions only through an issue: every evidence module and the decoder rely on
them, and several people build against them in parallel.
"""

from dataclasses import dataclass, field

import numpy as np

# Params
FPS = 25.0
PITCH = (105.3, 68.0)  # metres, from games.py (measured on the corrected tracking)

HOME, AWAY, NOBODY = 0, 1, -1
TEAM_CODES = (HOME, AWAY, NOBODY)
LABELS = ("H", "A", "D", "X")


def _check_positions(name, array, n_frames=None):
    if not np.isfinite(array[~np.isnan(array)]).all():
        raise ValueError("{}: positions must be finite or NaN".format(name))
    if n_frames is not None and array.shape[0] != n_frames:
        raise ValueError("{}: {} frames, expected {}".format(name, array.shape[0], n_frames))


@dataclass(frozen=True, eq=False)
class Match:
    """Ball and player positions of one recording.

    ball     (n, 2)     metres, NaN where the ball is not observed
    players  (n, k, 2)  metres, NaN where a track slot is not observed
    team     (k,)       int8 per slot: HOME, AWAY or NOBODY (referee, unknown)
    halves   ((half, first_row, last_row), ...)  inclusive, ordered, non-overlapping.
             Empty means "every frame counts".
    """

    ball: np.ndarray
    players: np.ndarray
    team: np.ndarray
    pitch: tuple = PITCH
    fps: float = FPS
    halves: tuple = field(default=())

    def __post_init__(self):
        ball = np.asarray(self.ball, dtype=np.float64)
        players = np.asarray(self.players, dtype=np.float64)
        team = np.asarray(self.team)

        if ball.ndim != 2 or ball.shape[1] != 2:
            raise ValueError("ball: expected shape (n, 2), got {}".format(ball.shape))
        n_frames = ball.shape[0]
        if players.ndim != 3 or players.shape[2] != 2:
            raise ValueError("players: expected shape (n, k, 2), got {}".format(players.shape))
        _check_positions("ball", ball)
        _check_positions("players", players, n_frames)
        if team.shape != (players.shape[1],):
            raise ValueError("team: expected {} slots, got shape {}".format(
                players.shape[1], team.shape))
        if not np.isin(team, TEAM_CODES).all():
            raise ValueError("team: codes must be in {}".format(TEAM_CODES))

        halves = tuple(tuple(int(v) for v in half) for half in self.halves)
        previous_last = -1
        for half, first, last in halves:
            if not (previous_last < first <= last < n_frames):
                raise ValueError("halves: {} is out of order or outside 0..{}".format(
                    (half, first, last), n_frames - 1))
            previous_last = last

        object.__setattr__(self, "ball", ball)
        object.__setattr__(self, "players", players)
        object.__setattr__(self, "team", team.astype(np.int8))
        object.__setattr__(self, "pitch", (float(self.pitch[0]), float(self.pitch[1])))
        object.__setattr__(self, "fps", float(self.fps))
        object.__setattr__(self, "halves", halves)

    @property
    def n_frames(self):
        return self.ball.shape[0]

    @property
    def n_slots(self):
        return self.players.shape[1]

    def graded_mask(self):
        """True on frames inside a half; everything when no halves are given."""
        if not self.halves:
            return np.ones(self.n_frames, dtype=bool)
        mask = np.zeros(self.n_frames, dtype=bool)
        for _, first, last in self.halves:
            mask[first:last + 1] = True
        return mask

    @classmethod
    def from_normalised(cls, ball, players, team, pitch=PITCH, **kwargs):
        """Build from 0-1 pitch coordinates, the convention of the ATD and the homography."""
        scale = np.array(pitch, dtype=np.float64)
        return cls(ball=np.asarray(ball, dtype=np.float64) * scale,
                   players=np.asarray(players, dtype=np.float64) * scale,
                   team=team, pitch=pitch, **kwargs)


PROBABILITY_CHANNELS = ("dead", "home")
EVENT_CHANNELS = ("control", "touch")


@dataclass(eq=False)
class Evidence:
    """Per-frame evidence for the decoder. NaN / NOBODY means "no opinion".

    dead     P(ball dead)
    home     P(home team in possession | ball alive)
    control  team whose confirmed control starts in this frame, else NOBODY
    touch    team touching the ball in this frame, else NOBODY
    """

    dead: np.ndarray
    home: np.ndarray
    control: np.ndarray
    touch: np.ndarray

    def __post_init__(self):
        n_frames = len(self.dead)
        for name in PROBABILITY_CHANNELS:
            values = np.asarray(getattr(self, name), dtype=np.float64)
            if values.shape != (n_frames,):
                raise ValueError("{}: expected shape ({},), got {}".format(
                    name, n_frames, values.shape))
            known = values[~np.isnan(values)]
            if ((known < 0) | (known > 1)).any():
                raise ValueError("{}: probabilities must be in [0, 1] or NaN".format(name))
            setattr(self, name, values)
        for name in EVENT_CHANNELS:
            values = np.asarray(getattr(self, name))
            if values.shape != (n_frames,):
                raise ValueError("{}: expected shape ({},), got {}".format(
                    name, n_frames, values.shape))
            if not np.isin(values, TEAM_CODES).all():
                raise ValueError("{}: codes must be in {}".format(name, TEAM_CODES))
            setattr(self, name, values.astype(np.int8))

    @property
    def n_frames(self):
        return len(self.dead)

    def channels(self):
        return {name: getattr(self, name) for name in PROBABILITY_CHANNELS + EVENT_CHANNELS}

    @classmethod
    def empty(cls, n_frames):
        return cls(dead=np.full(n_frames, np.nan), home=np.full(n_frames, np.nan),
                   control=np.full(n_frames, NOBODY, dtype=np.int8),
                   touch=np.full(n_frames, NOBODY, dtype=np.int8))


def check_labels(labels, n_frames):
    """Raise ValueError unless labels is a length-n array of H/A/D/X."""
    labels = np.asarray(labels)
    if labels.shape != (n_frames,):
        raise ValueError("labels: length {}, expected {}".format(labels.shape, n_frames))
    unknown = sorted(set(np.unique(labels).tolist()) - set(LABELS))
    if unknown:
        raise ValueError("labels: unknown label(s) {}".format(unknown))
