"""Load the tactical ATD (FIFA/EPTS: metadata XML + raw text) into a `Match` (issue #6).

numpy only. Raw line: "<frame_id>:<x,y,speed>;...;<x,y,speed>:<ball x,y,...>", coordinates
normalised 0-1, "NaN" for a missing value. Row = frame_id - 1, the video frame and submission row.

EC-19: slots whose teamId is neither listed team (referee, unknown; F6) get NOBODY, not AWAY as
       in starter/baseline.py. The first team in the metadata is home.
EC-11, EC-21: halves come from games.half_video_blocks, never from the file.

    python -m possession.io_atd      # prints counts only -- safe to share
"""

import xml.etree.ElementTree as ET

import numpy as np

from games import GAME, GAMES, half_video_blocks, require, source_frames
from possession.types import AWAY, HOME, NOBODY, Match

# Params
FIELD_SEP, GROUP_SEP, VALUE_SEP = ":", ";", ","
PLAYER_FIELDS = 3  # x, y, speed per slot
BALL_XY = 2  # the ball group may carry more fields (F5); only x, y are used


def read_teams(meta_path):
    """Team code per track slot, in metadata order: first team HOME, second AWAY, else NOBODY."""
    root = ET.parse(meta_path).getroot()
    team_ids = [team.get("id") for team in root.iter("Team")]
    if len(team_ids) != 2:
        raise ValueError("{}: expected 2 teams, found {}".format(meta_path, len(team_ids)))
    code = {team_ids[0]: HOME, team_ids[1]: AWAY}
    slots = [code.get(player.get("teamId"), NOBODY) for player in root.iter("Player")]
    if not slots:
        raise ValueError("{}: no Player entries".format(meta_path))
    return np.array(slots, dtype=np.int8)


def read_raw(raw_path, n_slots, n_frames=None):
    """(ball (n, 2), players (n, k, 2)) in 0-1 pitch units; rows absent from the file stay NaN.

    n is n_frames, or the largest frame id when not given. Every line must have the same layout:
    frame id, PLAYER_FIELDS values per slot, then the ball group (x, y and possibly more).
    """
    # utf-8-sig drops a BOM; text mode turns CRLF into LF; loadtxt skips blank lines.
    with open(raw_path, encoding="utf-8-sig") as handle:
        lines = (line.replace(FIELD_SEP, VALUE_SEP).replace(GROUP_SEP, VALUE_SEP)
                 for line in handle)
        table = np.loadtxt(lines, delimiter=VALUE_SEP, dtype=np.float64, ndmin=2)

    width = 1 + PLAYER_FIELDS * n_slots
    if table.shape[1] < width + BALL_XY:
        raise ValueError("{}: {} columns, need at least {} for {} slots and the ball".format(
            raw_path, table.shape[1], width + BALL_XY, n_slots))
    ids = table[:, 0].astype(np.int64)
    n = int(ids.max()) if n_frames is None else int(n_frames)
    if ids.min() < 1 or ids.max() > n or np.unique(ids).size != ids.size:
        raise ValueError("{}: frame ids must be unique and within 1..{}".format(raw_path, n))

    rows = ids - 1
    players = np.full((n, n_slots, 2), np.nan)
    players[rows] = table[:, 1:width].reshape(-1, n_slots, PLAYER_FIELDS)[:, :, :2]
    ball = np.full((n, 2), np.nan)
    ball[rows] = table[:, width:width + BALL_XY]
    return ball, players


def load_atd(meta_path, raw_path, pitch, fps, n_frames=None, halves=()):
    """An ATD pair as a Match in metres. Pitch, fps and halves are not in the file (see #6)."""
    team = read_teams(meta_path)
    ball, players = read_raw(raw_path, len(team), n_frames)
    return Match.from_normalised(ball, players, team, pitch=pitch, fps=fps, halves=halves)


def load(game=GAME, data_dir=None):
    """The tactical ATD of a game; pitch, fps, frame count and halves come from games.py."""
    meta, raw = require(["atd_meta", "atd_raw"], game, data_dir)
    entry = GAMES[game]
    return load_atd(meta, raw, pitch=entry["pitch"], fps=entry["fps"],
                    n_frames=source_frames("tactical", game),
                    halves=tuple(half_video_blocks(game)))


def summary(match):
    """Counts a human may share from a real run (issue #6): no positions, no frame numbers."""
    seen = ~np.isnan(match.ball[:, 0])
    return {
        "n_frames": match.n_frames,
        "n_slots": match.n_slots,
        "slots_home_away_nobody": tuple(int((match.team == code).sum())
                                        for code in (HOME, AWAY, NOBODY)),
        "ball_visible_share": round(float(seen.mean()), 4),
        "ball_visible_share_graded": round(float(seen[match.graded_mask()].mean()), 4),
    }


if __name__ == "__main__":
    for key, value in summary(load()).items():
        print("{:<28} {}".format(key, value))
