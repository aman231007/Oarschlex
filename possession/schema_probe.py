"""Print the *structure* of the ATD -- never its values. Answers F5/F6 of docs/EDGE_CASES.md.

The competition terms forbid sending the match data, or extracts of it, to a hosted LLM. This
probe exists so the team can answer format questions without doing that: it reports counts,
field widths, tag and channel names, and nothing that could reconstruct a frame.

    python -m possession.schema_probe                  # first 20000 lines of the tactical ATD
    python -m possession.schema_probe --max-lines 0    # the whole file

Read the output before sharing it. It is designed to be safe, but you are the one sharing it.
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter

# Params
# Raw ATD line: "<frame>:<player>;<player>;...:<ball>", see starter/baseline.py.
FIELD_SEP = ":"
GROUP_SEP = ";"
VALUE_SEP = ","
MISSING = "NaN"
DEFAULT_MAX_LINES = 20000


def probe_raw(raw_path, max_lines=None):
    """Counts describing the raw file's layout. No values are kept."""
    parts_per_line = Counter()
    player_groups = Counter()
    player_fields = Counter()
    ball_fields = Counter()
    ball_missing = 0
    n_lines = 0

    with open(raw_path, encoding="utf-8") as handle:
        for line in handle:
            if max_lines and n_lines >= max_lines:
                break
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            parts = line.split(FIELD_SEP)
            parts_per_line[len(parts)] += 1
            if len(parts) < 3:
                continue

            groups = parts[1].split(GROUP_SEP)
            player_groups[len(groups)] += 1
            for group in groups:
                player_fields[len(group.split(VALUE_SEP))] += 1

            ball = parts[-1].split(VALUE_SEP)
            ball_fields[len(ball)] += 1
            if ball[0].strip() == MISSING:
                ball_missing += 1

    return {
        "n_lines": n_lines,
        "parts_per_line": dict(parts_per_line),
        "player_groups_per_line": dict(player_groups),
        "fields_per_player_group": dict(player_fields),
        "fields_per_ball_group": dict(ball_fields),
        "ball_missing_lines": ball_missing,
    }


def probe_meta(meta_path):
    """Structure of the metadata XML: teams, slots per team, channels, tags. No names or ids."""
    root = ET.parse(meta_path).getroot()
    team_ids = [team.get("id") for team in root.iter("Team")]
    position = {team_id: "team_{}".format(i + 1) for i, team_id in enumerate(team_ids)}
    slots = Counter(position.get(player.get("teamId"), "other") for player in root.iter("Player"))

    return {
        "n_teams": len(team_ids),
        "n_player_slots": sum(slots.values()),
        "slots_per_team_position": dict(slots),
        "channel_ids": sorted({c.get("id") for c in root.iter("Channel") if c.get("id")}),
        "channel_names": sorted({c.findtext("Name") for c in root.iter("Channel")
                                 if c.findtext("Name")}),
        "separator_attributes": sorted({el.get("separator") for el in root.iter()
                                        if el.get("separator") is not None}),
        "tag_names": sorted({el.tag for el in root.iter()}),
    }


def format_report(meta_report, raw_report):
    """Plain text, safe to paste: only the keys above, which hold counts and schema names."""
    lines = ["ATD structure report (no values)", ""]
    for title, report in (("metadata XML", meta_report), ("raw file", raw_report)):
        lines.append("[{}]".format(title))
        for key, value in report.items():
            lines.append("  {:<26} {}".format(key, value))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games import require  # noqa: E402

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES,
                        help="lines of the raw file to scan, 0 for all")
    parser.add_argument("--source", default="tactical", choices=("tactical", "broadcast"))
    args = parser.parse_args()

    meta_path, raw_path = require(["atd_meta", "atd_raw"], source=args.source)
    print(format_report(probe_meta(meta_path), probe_raw(raw_path, args.max_lines)))
