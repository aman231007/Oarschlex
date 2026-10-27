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
