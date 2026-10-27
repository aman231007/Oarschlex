"""Tests for possession.io_atd -- the numpy ATD loader (issue #6). Synthetic files only."""

import textwrap

import numpy as np
import pytest

from possession import io_atd
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


def test_trailing_blank_line_is_ignored(tmp_path):
    ball, _ = io_atd.read_raw(_write(tmp_path / "r.txt", RAW + "\n"), 3)
    assert ball.shape == (4, 2)


@pytest.mark.parametrize("raw, n_frames, message", [
    ("1:{p}:0.5,0.5,1\n1:{p}:0.5,0.5,1\n", None, "frame ids"),  # duplicate
    ("1:{p}:0.5\n", None, "columns"),                           # ball group too short
    ("9:{p}:0.5,0.5,1\n", 5, "frame ids"),                      # beyond n_frames
    ("0:{p}:0.5,0.5,1\n", None, "frame ids"),                   # ids count from 1
])
def test_malformed_raw_file_is_rejected(tmp_path, raw, n_frames, message):
    with pytest.raises(ValueError, match=message):
        io_atd.read_raw(_write(tmp_path / "r.txt", raw.format(p=P)), 3, n_frames)
