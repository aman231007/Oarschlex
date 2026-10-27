"""Tests for possession.types -- the shared contract of issue #2 (see docs/PLAN.md)."""

import numpy as np
import pytest

from possession import types as T


def _match(n=10, k=4, **kwargs):
    ball = np.zeros((n, 2))
    players = np.zeros((n, k, 2))
    team = np.array([0, 0, 1, 1][:k], dtype=np.int8)
    return T.Match(ball=ball, players=players, team=team, **kwargs)


# -- Match ---------------------------------------------------------------------------------------

def test_match_defaults_and_sizes():
    match = _match()
    assert match.n_frames == 10
    assert match.n_slots == 4
    assert match.fps == 25.0
    assert match.pitch == (105.3, 68.0)


def test_match_rejects_ball_with_wrong_shape():
    with pytest.raises(ValueError, match="ball"):
        T.Match(ball=np.zeros((10, 3)), players=np.zeros((10, 4, 2)),
                team=np.zeros(4, dtype=np.int8))


def test_match_rejects_players_with_other_frame_count():
    with pytest.raises(ValueError, match="players"):
        T.Match(ball=np.zeros((10, 2)), players=np.zeros((9, 4, 2)),
                team=np.zeros(4, dtype=np.int8))


def test_match_rejects_team_length_mismatch():
    with pytest.raises(ValueError, match="team"):
        T.Match(ball=np.zeros((10, 2)), players=np.zeros((10, 4, 2)),
                team=np.zeros(3, dtype=np.int8))


def test_match_rejects_unknown_team_codes():
    with pytest.raises(ValueError, match="team"):
        T.Match(ball=np.zeros((10, 2)), players=np.zeros((10, 2, 2)),
                team=np.array([0, 2], dtype=np.int8))


def test_match_allows_nan_for_missing_observations():
    match = _match()
    match.ball[3] = np.nan
    assert np.isnan(match.ball[3]).all()


def test_match_rejects_infinite_positions():
    ball = np.zeros((10, 2))
    ball[0, 0] = np.inf
    with pytest.raises(ValueError, match="finite"):
        T.Match(ball=ball, players=np.zeros((10, 2, 2)), team=np.array([0, 1], dtype=np.int8))


def test_match_halves_must_be_ordered_and_inside_the_match():
    _match(halves=((1, 0, 4), (2, 6, 9)))
    for bad in (((1, 0, 10),), ((1, 5, 4),), ((1, 0, 5), (2, 5, 9)), ((2, 6, 9), (1, 0, 4))):
        with pytest.raises(ValueError, match="halves"):
            _match(halves=bad)


def test_graded_mask_covers_halves_only():
    mask = _match(halves=((1, 1, 3), (2, 6, 7))).graded_mask()
    assert mask.tolist() == [False, True, True, True, False, False, True, True, False, False]


def test_graded_mask_is_everything_without_halves():
    assert _match().graded_mask().all()


def test_from_normalised_scales_to_metres_and_keeps_nan():
    ball = np.array([[0.5, 0.5], [np.nan, np.nan]])
    players = np.array([[[0.0, 1.0]], [[1.0, 0.0]]])
    match = T.Match.from_normalised(ball, players, np.array([0], dtype=np.int8),
                                    pitch=(100.0, 50.0))
    assert match.ball[0].tolist() == [50.0, 25.0]
    assert np.isnan(match.ball[1]).all()
    assert match.players[:, 0].tolist() == [[0.0, 50.0], [100.0, 0.0]]


def test_match_stores_float64_and_int8():
    match = T.Match(ball=np.zeros((2, 2), dtype=np.float32), players=np.zeros((2, 1, 2)),
                    team=np.array([1]))
    assert match.ball.dtype == np.float64
    assert match.team.dtype == np.int8


# -- Evidence ------------------------------------------------------------------------------------

def test_empty_evidence_has_no_opinion():
    ev = T.Evidence.empty(5)
    assert ev.n_frames == 5
    assert np.isnan(ev.dead).all() and np.isnan(ev.home).all()
    assert (ev.control == T.NOBODY).all() and (ev.touch == T.NOBODY).all()


def test_evidence_rejects_length_mismatch():
    with pytest.raises(ValueError, match="home"):
        T.Evidence(dead=np.full(5, np.nan), home=np.full(4, np.nan),
                   control=np.full(5, -1, dtype=np.int8), touch=np.full(5, -1, dtype=np.int8))


@pytest.mark.parametrize("channel", ["dead", "home"])
def test_evidence_probabilities_must_be_in_unit_interval(channel):
    ev = T.Evidence.empty(3)
    values = np.array([0.0, 1.0, 1.5])
    with pytest.raises(ValueError, match=channel):
        T.Evidence(**{**ev.channels(), channel: values})


@pytest.mark.parametrize("channel", ["control", "touch"])
def test_evidence_event_channels_hold_team_codes(channel):
    ev = T.Evidence.empty(3)
    with pytest.raises(ValueError, match=channel):
        T.Evidence(**{**ev.channels(), channel: np.array([-1, 0, 3])})


# -- labels --------------------------------------------------------------------------------------

def test_check_labels_accepts_valid_array():
    T.check_labels(np.array(list("HADX")), 4)


def test_check_labels_rejects_unknown_label_and_wrong_length():
    with pytest.raises(ValueError, match="label"):
        T.check_labels(np.array(list("HAZ")), 3)
    with pytest.raises(ValueError, match="length"):
        T.check_labels(np.array(list("HA")), 3)
