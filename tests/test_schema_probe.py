"""Tests for possession.schema_probe -- answers questions F5/F6 of docs/EDGE_CASES.md.

The probe runs on the real ATD, and its output is what the team may share with an LLM. So the
property that matters most is negative: it must never print a coordinate, speed or frame number.
"""

import re
import textwrap

import pytest

from possession import schema_probe

META_XML = textwrap.dedent("""\
    <main>
      <Metadata>
        <Teams>
          <Team id="T1"><Name>Home FC</Name></Team>
          <Team id="T2"><Name>Away FC</Name></Team>
        </Teams>
        <Players>
          <Player id="P1" teamId="T1"><Name>Track 1</Name><ShirtNumber>1</ShirtNumber></Player>
          <Player id="P2" teamId="T1"><Name>Track 2</Name><ShirtNumber>2</ShirtNumber></Player>
          <Player id="P3" teamId="T2"><Name>Track 3</Name><ShirtNumber>3</ShirtNumber></Player>
          <Player id="P4" teamId="REF"><Name>Track 4</Name><ShirtNumber>4</ShirtNumber></Player>
        </Players>
        <Devices><Device id="d"><Sensors><Sensor id="s"><Channels>
          <Channel id="x"><Name>position_x</Name></Channel>
          <Channel id="y"><Name>position_y</Name></Channel>
          <Channel id="speed"><Name>speed</Name></Channel>
        </Channels></Sensor></Sensors></Device></Devices>
      </Metadata>
      <DataFormatSpecifications>
        <DataFormatSpecification startFrame="1" endFrame="3" separator=":">
          <StringRegister name="frameCount"/>
        </DataFormatSpecification>
      </DataFormatSpecifications>
    </main>
""")

# Three frames, four slots, ball present on two of them. Values are deliberately distinctive so
# a leak is easy to grep for.
RAW_LINES = [
    "1:0.123456,0.654321,1.5;NaN,NaN,NaN;0.222222,0.333333,2.5;NaN,NaN,NaN:0.777777,0.888888,9.9",
    "2:0.123456,0.654321,1.5;NaN,NaN,NaN;0.222222,0.333333,2.5;NaN,NaN,NaN:NaN,NaN,NaN",
    "3:0.123456,0.654321,1.5;0.4,0.4,0.4;0.222222,0.333333,2.5;NaN,NaN,NaN:0.777777,0.888888,9.9",
]


@pytest.fixture
def atd_files(tmp_path):
    meta = tmp_path / "atd.xml"
    raw = tmp_path / "atd.txt"
    meta.write_text(META_XML, encoding="utf-8")
    raw.write_text("\n".join(RAW_LINES) + "\n", encoding="utf-8")
    return str(meta), str(raw)


def test_raw_structure_counts_groups_and_fields(atd_files):
    _, raw = atd_files
    report = schema_probe.probe_raw(raw)
    assert report["n_lines"] == 3
    assert report["parts_per_line"] == {3: 3}
    assert report["player_groups_per_line"] == {4: 3}
    assert report["fields_per_player_group"] == {3: 12}
    assert report["fields_per_ball_group"] == {3: 3}
    assert report["ball_missing_lines"] == 1


def test_raw_probe_respects_line_limit(atd_files):
    _, raw = atd_files
    assert schema_probe.probe_raw(raw, max_lines=2)["n_lines"] == 2


def test_meta_structure_finds_teams_channels_and_foreign_slots(atd_files):
    meta, _ = atd_files
    report = schema_probe.probe_meta(meta)
    assert report["n_teams"] == 2
    assert report["n_player_slots"] == 4
    assert report["slots_per_team_position"] == {"team_1": 2, "team_2": 1, "other": 1}  # F6
    assert report["channel_ids"] == ["speed", "x", "y"]
    assert report["separator_attributes"] == [":"]


def test_report_never_leaks_values(atd_files):
    """EC policy: the printed report holds structure only -- no coordinates, no club names."""
    meta, raw = atd_files
    text = schema_probe.format_report(schema_probe.probe_meta(meta), schema_probe.probe_raw(raw))
    for leaked in ("0.123456", "0.777777", "9.9", "Home FC", "Away FC", "T1", "P1"):
        assert leaked not in text
    assert not re.search(r"\d\.\d{3,}", text), "no decimal values with 3+ places in the report"
