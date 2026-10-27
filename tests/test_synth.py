"""Tests for possession.synth -- synthetic scenes for the edge cases (issue #3)."""

import numpy as np
import pytest

from possession import schema_probe, synth
from possession import types as T

FPS = 25


def _frame(seconds):
    return int(round(seconds * FPS))


def _nearest_slot(match, frame):
    distances = np.linalg.norm(match.players[frame] - match.ball[frame], axis=1)
    return int(np.nanargmin(distances))


# -- builder primitives --------------------------------------------------------------------------

def test_builder_starts_with_two_full_teams_in_formation():
    builder = synth.SceneBuilder(seconds=2)
    case = builder.build("empty")
    assert case.match.n_frames == 50
    assert case.match.team.tolist() == [T.HOME] * 11 + [T.AWAY] * 11
    assert not np.isnan(case.match.players).any()
    home_x = case.match.players[0, :11, 0]
    away_x = case.match.players[0, 11:, 0]
    assert home_x.max() < away_x.min(), "home starts in the left half, away in the right"


def test_move_is_linear_and_position_persists_afterwards():
    builder = synth.SceneBuilder(seconds=4)
    start = builder.players[0, 5].copy()
    builder.move(5, (start[0] + 10, start[1]), 1.0, 2.0)
    players = builder.build("move").match.players
    assert players[_frame(1.6), 5, 0] == pytest.approx(start[0] + 6)  # 15 of 25 frames
    assert players[_frame(3.5), 5, 0] == pytest.approx(start[0] + 10)


def test_carry_keeps_ball_at_the_players_feet():
    builder = synth.SceneBuilder(seconds=3)
    builder.move(5, (50.0, 20.0), 0.0, 3.0)
    builder.carry(5, 0.0, 3.0)
    match = builder.build("carry").match
    gap = np.linalg.norm(match.ball - match.players[:, 5], axis=1)
    assert gap.max() <= 1.0


def test_kick_moves_ball_to_target_and_leaves_it_there():
    builder = synth.SceneBuilder(seconds=4)
    builder.carry(5, 0.0, 1.0)
    builder.kick((60.0, 30.0), 1.0, 2.0)
    ball = builder.build("kick").match.ball
    assert ball[_frame(2.0)].tolist() == pytest.approx([60.0, 30.0])
    assert ball[_frame(3.9)].tolist() == pytest.approx([60.0, 30.0])


def test_kick_to_a_slot_targets_that_players_feet():
    builder = synth.SceneBuilder(seconds=3)
    builder.carry(5, 0.0, 1.0)
    builder.kick(6, 1.0, 2.0)
    match = builder.build("kick to slot").match
    frame = _frame(2.0)
    assert np.linalg.norm(match.ball[frame] - match.players[frame, 6]) <= 1.0


def test_hidden_ball_is_nan_regardless_of_call_order():
    builder = synth.SceneBuilder(seconds=3)
    builder.hide_ball(1.0, 2.0)
    builder.carry(5, 0.0, 3.0)
    ball = builder.build("hide").match.ball
    assert np.isnan(ball[_frame(1.0):_frame(2.0)]).all()
    assert not np.isnan(ball[_frame(2.0)]).any()


def test_care_mask_skips_unlabelled_frames_and_a_margin_around_changes():
    builder = synth.SceneBuilder(seconds=4)
    builder.label("H", 0.0, 2.0)
    builder.label("A", 2.0, 3.0)
    case = builder.build("care", margin=5)
    change = _frame(2.0)
    assert not case.care[change - 5:change + 5].any()
    assert case.care[change - 6] and case.care[change + 5]
    assert (case.expected[_frame(3.0):] == "X").all()
    assert not case.care[_frame(3.0):].any()


def test_noise_is_deterministic_per_seed():
    a = synth.SceneBuilder(seconds=2, seed=1).build("n", noise=0.2).match.players
    b = synth.SceneBuilder(seconds=2, seed=1).build("n", noise=0.2).match.players
    c = synth.SceneBuilder(seconds=2, seed=2).build("n", noise=0.2).match.players
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


# -- every registered scene ----------------------------------------------------------------------

SCENES = sorted(synth.SCENES)


def test_scene_registry_covers_the_starting_edge_cases():
    for ec in ("EC-02a", "EC-02b", "EC-02c", "EC-05", "EC-06"):
        assert ec in synth.SCENES


@pytest.mark.parametrize("name", SCENES)
def test_scene_is_well_formed(name):
    case = synth.SCENES[name]()
    T.check_labels(case.expected, case.match.n_frames)
    assert case.care.any(), "a scene must grade something"
    assert set(np.unique(case.expected[case.care])) <= {"H", "A", "D"}
    assert case.note


@pytest.mark.parametrize("name", SCENES)
def test_scene_players_move_plausibly(name):
    players = synth.SCENES[name]().match.players
    speed = np.linalg.norm(np.diff(players, axis=0), axis=2) * FPS
    assert np.nanmax(speed) <= 9.5, "nobody sprints faster than 9.5 m/s"


@pytest.mark.parametrize("name", SCENES)
def test_scene_is_deterministic(name):
    a, b = synth.SCENES[name](), synth.SCENES[name]()
    assert np.array_equal(a.match.ball, b.match.ball, equal_nan=True)
    assert np.array_equal(a.expected, b.expected)


# -- what each scene must contain ----------------------------------------------------------------

def test_ec02_long_ball_flies_unseen_past_an_opponent():
    """EC-02: the trap -- right after the gap the nearest player is an opponent, yet it is H."""
    case = synth.SCENES["EC-02a"]()
    flight = case.match.ball[_frame(3.6):_frame(4.6)]
    assert np.isnan(flight).all()
    reappears = _frame(4.6)
    assert case.match.team[_nearest_slot(case.match, reappears)] == T.AWAY
    assert case.expected[reappears] == "H"


def test_ec02_variants_a_and_b_never_change_possession():
    for name in ("EC-02a", "EC-02b"):
        case = synth.SCENES[name]()
        assert set(case.expected[case.care]) == {"H"}, name


def test_ec02c_change_is_backdated_to_the_first_touch():
    case = synth.SCENES["EC-02c"]()
    first_touch = _frame(5.0)
    assert case.expected[first_touch - 1] == "H"
    assert (case.expected[first_touch:] == "A").all()


def test_ec05_throw_in_is_dead_from_crossing_until_the_ball_is_back_in():
    case = synth.SCENES["EC-05"]()
    y = case.match.ball[:, 1]
    out = np.where(y < 0)[0]
    crossing, back_in = out[0], out[-1] + 1
    assert case.expected[crossing - 1] == "H"
    assert (case.expected[crossing:back_in] == "D").all()
    assert (case.expected[back_in:] == "A").all()


def test_ec06_corner_restart_ends_dead_ball_when_the_ball_moves():
    case = synth.SCENES["EC-06"]()
    kick = _frame(6.0)
    still = case.match.ball[:kick]
    assert np.allclose(still, still[0])
    assert (case.expected[:kick] == "D").all()
    assert (case.expected[kick:] == "H").all()
    speeds = np.linalg.norm(np.diff(case.match.players[:kick], axis=0), axis=2)
    assert speeds.max() == 0, "everybody waits for the corner"


# -- EPTS export for loader tests (issue #6) -----------------------------------------------------

def test_write_epts_produces_the_atd_layout(tmp_path):
    case = synth.SCENES["EC-02a"]()
    meta, raw = tmp_path / "m.xml", tmp_path / "r.txt"
    synth.write_epts(case.match, str(meta), str(raw))
    raw_report = schema_probe.probe_raw(str(raw))
    assert raw_report["n_lines"] == case.match.n_frames
    assert raw_report["player_groups_per_line"] == {22: case.match.n_frames}
    assert raw_report["fields_per_ball_group"] == {3: case.match.n_frames}
    assert raw_report["ball_missing_lines"] == int(np.isnan(case.match.ball[:, 0]).sum())
    meta_report = schema_probe.probe_meta(str(meta))
    assert meta_report["slots_per_team_position"] == {"team_1": 11, "team_2": 11}
    first = raw.read_text().splitlines()[0]
    assert first.startswith("1:"), "ATD frame ids count from 1"
