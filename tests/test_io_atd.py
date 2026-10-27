"""Tests for possession.io_atd -- the numpy ATD loader (issue #6). Synthetic files only."""

import textwrap

import numpy as np
import pytest

from possession import io_atd, synth
from possession import types as T

META_XML = textwrap.dedent("""\
    <main><Metadata>
      <Teams><Team id="T1"><Name>Home FC</Name></Team><Team id="T2"><Name>Away FC</Name></Team></Teams>
      <Players>
        <Player id="P1" teamId="T1"/><Player id="P2" teamId="T2"/><Player id="P3" teamId="REF"/>
      </Players>
    </Metadata></main>
""")


def _write(path, text, bom=False, crlf=False):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return str(path)


# -- teams ---------------------------------------------------------------------------------------

def test_ec19_first_team_is_home_and_other_slots_are_nobody(tmp_path):
    team = io_atd.read_teams(_write(tmp_path / "m.xml", META_XML))
    assert team.dtype == np.int8
    assert team.tolist() == [T.HOME, T.AWAY, T.NOBODY]


def test_read_teams_rejects_metadata_without_two_teams(tmp_path):
    xml = META_XML.replace('<Team id="T2"><Name>Away FC</Name></Team>', "")
    with pytest.raises(ValueError, match="2 teams"):
        io_atd.read_teams(_write(tmp_path / "m.xml", xml))


# -- raw lines -----------------------------------------------------------------------------------

P = "0.100000,0.200000,1.0;0.300000,0.400000,2.0;NaN,NaN,NaN"
RAW = "1:{p}:0.500000,0.500000,9.0\n2:{p}:NaN,NaN,NaN\n4:{p}:0.250000,0.750000,3.0\n".format(p=P)


def test_frame_id_minus_one_is_the_row_and_missing_frames_stay_nan(tmp_path):
    ball, players = io_atd.read_raw(_write(tmp_path / "r.txt", RAW), n_slots=3, n_frames=5)
    assert ball.shape == (5, 2) and players.shape == (5, 3, 2)
    np.testing.assert_allclose(ball[0], [0.5, 0.5])
    assert np.isnan(ball[1]).all(), "ball missing in frame_id 2"
    assert np.isnan(ball[2]).all() and np.isnan(players[2]).all(), "frame_id 3 is absent"
    np.testing.assert_allclose(ball[3], [0.25, 0.75])
    assert np.isnan(ball[4]).all(), "beyond the file"
    np.testing.assert_allclose(players[0, :2], [[0.1, 0.2], [0.3, 0.4]])
    assert np.isnan(players[0, 2]).all()


def test_without_n_frames_the_last_frame_id_sets_the_length(tmp_path):
    ball, _ = io_atd.read_raw(_write(tmp_path / "r.txt", RAW), n_slots=3)
    assert ball.shape == (4, 2)


def test_crlf_and_bom_parse_like_plain_files(tmp_path):
    plain = io_atd.read_raw(_write(tmp_path / "a.txt", RAW), 3)
    odd = io_atd.read_raw(_write(tmp_path / "b.txt", RAW, bom=True, crlf=True), 3)
    for a, b in zip(plain, odd):
        np.testing.assert_array_equal(a, b)
    team = io_atd.read_teams(_write(tmp_path / "m.xml", META_XML, bom=True, crlf=True))
    assert team.tolist() == [T.HOME, T.AWAY, T.NOBODY]


def test_f5_ball_group_may_carry_extra_fields(tmp_path):
    raw = "1:{}:0.500000,0.250000,9.0,1.2,1\n".format(P)
    ball, _ = io_atd.read_raw(_write(tmp_path / "r.txt", raw), 3)
    np.testing.assert_allclose(ball[0], [0.5, 0.25])


def test_trailing_blank_lines_are_ignored(tmp_path):
    ball, _ = io_atd.read_raw(_write(tmp_path / "r.txt", RAW + "\n   \n"), 3)
    assert ball.shape == (4, 2)


@pytest.mark.parametrize("raw, n_frames, message", [
    ("1:{p}:0.5,0.5,1\n1:{p}:0.5,0.5,1\n", None, "frame ids"),  # duplicate
    ("1:{p}:0.5\n", None, "columns"),                           # ball group too short
    ("9:{p}:0.5,0.5,1\n", 5, "frame ids"),                      # beyond n_frames
    ("0:{p}:0.5,0.5,1\n", None, "frame ids"),                   # ids count from 1
    ("1.5:{p}:0.5,0.5,1\n", None, "frame ids"),                 # ids are integers
    ("\n", None, "no frames"),                                 # nothing to load
])
def test_malformed_raw_file_is_rejected(tmp_path, raw, n_frames, message):
    with pytest.raises(ValueError, match=message):
        io_atd.read_raw(_write(tmp_path / "r.txt", raw.format(p=P)), 3, n_frames)


# -- Match ---------------------------------------------------------------------------------------

def test_round_trip_of_a_synthetic_scene(tmp_path):
    match = synth.SCENES["EC-05"]().match
    meta, raw = str(tmp_path / "m.xml"), str(tmp_path / "r.txt")
    synth.write_epts(match, meta, raw)
    loaded = io_atd.load_atd(meta, raw, pitch=match.pitch, fps=match.fps)
    assert loaded.n_frames == match.n_frames and loaded.fps == match.fps
    np.testing.assert_array_equal(loaded.team, match.team)
    np.testing.assert_array_equal(np.isnan(loaded.ball), np.isnan(match.ball))
    np.testing.assert_allclose(loaded.ball, match.ball, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(loaded.players, match.players, atol=1e-4, equal_nan=True)


def test_ec11_ec21_load_takes_pitch_fps_length_and_halves_from_games(tmp_path):
    match = synth.SCENES["EC-06"]().match
    folder = tmp_path / "tactical"
    folder.mkdir()
    synth.write_epts(match, str(folder / "BAR-ATH_tactical_atd.xml"),
                     str(folder / "BAR-ATH_tactical_atd.txt"))
    loaded = io_atd.load(data_dir=str(tmp_path))
    assert loaded.n_frames == 199319
    assert loaded.pitch == (105.3, 68.0) and loaded.fps == 25.0
    assert loaded.halves == ((1, 11185, 90651), (2, 110808, 190197))
    np.testing.assert_allclose(loaded.ball[:match.n_frames], match.ball, atol=1e-4,
                               equal_nan=True)
    assert np.isnan(loaded.ball[match.n_frames:]).all()


def test_summary_holds_only_counts_and_shares():
    ball = np.array([[1.0, 1.0], [np.nan, np.nan], [2.0, 2.0], [np.nan, np.nan]])
    match = T.Match(ball=ball, players=np.zeros((4, 3, 2)),
                    team=np.array([0, 1, -1], dtype=np.int8), halves=((1, 0, 2),))
    assert io_atd.summary(match) == {
        "n_frames": 4, "n_slots": 3, "slots_home_away_nobody": (1, 1, 1),
        "ball_visible_share": 0.5, "ball_visible_share_graded": 0.6667}


@pytest.mark.parametrize("raw", [
    "1:{p};0.7,0.8,3.0:0.5,0.5,1\n",                           # F6: more groups than slots
    "1:0.1,0.2;0.3,0.4;NaN,NaN:0.5,0.5,1,2,3,4\n",             # F5: two fields per group
    "1:{p}:0.5,0.5,1\n2:{p};0.7,0.8,3.0:0.5,0.5\n",              # layout changes mid-file
])
def test_f5_f6_layout_not_matching_the_metadata_is_rejected_not_misread(tmp_path, raw):
    with pytest.raises(ValueError, match="layout"):
        io_atd.read_raw(_write(tmp_path / "r.txt", raw.format(p=P)), 3)
