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
