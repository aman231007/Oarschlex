"""Tests for possession.synth -- synthetic scenes for the edge cases (issue #3)."""

import numpy as np
import pytest

from possession import schema_probe, synth
from possession import types as T

FPS = 25


def _frame(seconds):
    return int(np.floor(seconds * FPS + 0.5))


def _nearest_slot(match, frame):
    distances = np.linalg.norm(match.players[frame] - match.ball[frame], axis=1)
    return int(np.nanargmin(distances))


# -- time and interval conventions ---------------------------------------------------------------

def test_seconds_round_half_up_to_frames():
    builder = synth.SceneBuilder(seconds=2)
    assert [builder.frame(t) for t in (0.1, 0.3, 0.5, 0.7)] == [3, 8, 13, 18]


def test_frame_may_point_one_past_the_end_for_exclusive_ends():
    builder = synth.SceneBuilder(seconds=2)
    assert builder.frame(2.0) == 50
    assert builder.frame(9.0) == 50


def test_label_and_hide_cover_t0_to_t1_exclusive_up_to_the_last_frame():
    builder = synth.SceneBuilder(seconds=2)
    builder.carry(5, 0.0, 2.0).label("H", 0.0, 2.0).hide_ball(1.0, 2.0)
    case = builder.build("bounds")
    assert (case.expected == "H").all(), "last frame is labelled"
    assert np.isnan(case.match.ball[_frame(1.0):]).all(), "last frame is hidden"
    assert not np.isnan(case.match.ball[_frame(1.0) - 1]).any()


def test_move_is_linear_on_t0_t1_and_arrives_at_t1():
    builder = synth.SceneBuilder(seconds=4)
    start = builder.players[0, 5].copy()
    builder.move(5, (start[0] + 10, start[1]), 1.0, 2.0)
    players = builder.build("move").match.players
    assert players[_frame(1.0), 5, 0] == pytest.approx(start[0])
    assert players[_frame(1.6), 5, 0] == pytest.approx(start[0] + 6)  # 15 of 25 frames
    assert players[_frame(2.0), 5, 0] == pytest.approx(start[0] + 10)
    assert players[-1, 5, 0] == pytest.approx(start[0] + 10)


def test_carry_keeps_ball_at_the_players_feet():
    builder = synth.SceneBuilder(seconds=3)
    builder.move(5, (50.0, 20.0), 0.0, 3.0)
    builder.carry(5, 0.0, 3.0)
    match = builder.build("carry").match
    gap = np.linalg.norm(match.ball - match.players[:, 5], axis=1)
    assert gap.max() <= 1.0


def test_kick_leaves_at_t0_and_arrives_at_t1():
    builder = synth.SceneBuilder(seconds=4)
    builder.ball_at((10.0, 10.0), 0.0, 1.0)
    builder.kick((60.0, 30.0), 1.0, 2.0)
    ball = builder.build("kick").match.ball
    assert ball[_frame(1.0) - 1].tolist() == [10.0, 10.0], "at rest until t0"
    assert ball[_frame(1.0), 0] > 10.0, "moving at t0: a restart starts here"
    assert ball[_frame(2.0) - 1, 0] < 60.0
    assert ball[_frame(2.0)].tolist() == pytest.approx([60.0, 30.0])
    assert ball[-1].tolist() == pytest.approx([60.0, 30.0])


def test_kick_to_a_slot_targets_that_players_feet():
    builder = synth.SceneBuilder(seconds=3)
    builder.carry(5, 0.0, 1.0)
    builder.kick(6, 1.0, 2.0)
    match = builder.build("kick to slot").match
    frame = _frame(2.0)
    assert np.linalg.norm(match.ball[frame] - match.players[frame, 6]) <= 1.0


def test_ball_at_honours_its_interval_then_persists():
    builder = synth.SceneBuilder(seconds=3)
    builder.carry(5, 0.0, 1.0).ball_at((20.0, 20.0), 1.0, 2.0)
    ball = builder.build("ball_at").match.ball
    assert ball[_frame(1.0) - 1].tolist() != [20.0, 20.0]
    assert ball[_frame(1.0):].tolist() == [[20.0, 20.0]] * (ball.shape[0] - _frame(1.0))


def test_hidden_ball_is_nan_regardless_of_call_order_and_reported():
    builder = synth.SceneBuilder(seconds=3)
    builder.hide_ball(1.0, 2.0)
    builder.carry(5, 0.0, 3.0)
    case = builder.build("hide")
    assert np.isnan(case.match.ball[_frame(1.0):_frame(2.0)]).all()
    assert not np.isnan(case.match.ball[_frame(2.0)]).any()
    assert case.hidden.tolist() == np.isnan(case.match.ball[:, 0]).tolist()


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
def test_scene_moves_plausibly(name):
    match = synth.SCENES[name]().match
    player_speed = np.linalg.norm(np.diff(match.players, axis=0), axis=2) * FPS
    ball_speed = np.linalg.norm(np.diff(match.ball, axis=0), axis=1) * FPS
    assert np.nanmax(player_speed) <= 9.5, "nobody sprints faster than 9.5 m/s"
    assert np.nanmax(ball_speed) <= 40.0, "no ball faster than 40 m/s"


@pytest.mark.parametrize("name", SCENES)
def test_scene_is_deterministic(name):
    a, b = synth.SCENES[name](), synth.SCENES[name]()
    assert np.array_equal(a.match.ball, b.match.ball, equal_nan=True)
    assert np.array_equal(a.match.players, b.match.players, equal_nan=True)
    assert np.array_equal(a.expected, b.expected)
    assert np.array_equal(a.care, b.care)


# -- what each scene must contain ----------------------------------------------------------------

@pytest.mark.parametrize("name", ["EC-02a", "EC-02b", "EC-02c"])
def test_ec02_long_ball_flies_unseen_past_an_opponent(name):
    """EC-02: ~2 s without ball; when it reappears the nearest player is an opponent."""
    case = synth.SCENES[name]()
    gap = np.flatnonzero(case.hidden)
    assert (gap[-1] - gap[0] + 1) / FPS >= 1.8
    reappears = gap[-1] + 1
    assert case.match.team[_nearest_slot(case.match, reappears)] == T.AWAY
    assert case.expected[reappears] == "H"


def test_ec02_variants_a_and_b_never_change_possession():
    for name in ("EC-02a", "EC-02b"):
        case = synth.SCENES[name]()
        assert set(case.expected[case.care]) == {"H"}, name


def test_ec02b_away_touches_the_ball_without_control():
    case = synth.SCENES["EC-02b"]()
    header = _frame(5.4)
    assert case.match.team[_nearest_slot(case.match, header)] == T.AWAY
    assert case.expected[header] == "H"


def test_ec02c_change_is_backdated_to_the_first_touch():
    case = synth.SCENES["EC-02c"]()
    first_touch = _frame(5.4)
    assert case.match.team[_nearest_slot(case.match, first_touch)] == T.AWAY
    assert case.expected[first_touch - 1] == "H"
    assert (case.expected[first_touch:] == "A").all()


def test_ec05_throw_in_is_dead_from_crossing_until_the_ball_is_back_in():
    case = synth.SCENES["EC-05"]()
    y = case.match.ball[:, 1]
    out = np.flatnonzero(y < 0)
    crossing, back_in = out[0], out[-1] + 1
    assert crossing / FPS == pytest.approx(4.4, abs=0.05)
    assert back_in / FPS == pytest.approx(12.04, abs=0.05)
    assert case.expected[crossing - 1] == "H"
    assert (case.expected[crossing:back_in] == "D").all()
    assert (case.expected[back_in:] == "A").all()


def test_ec06_corner_restart_ends_dead_ball_when_the_ball_moves():
    case = synth.SCENES["EC-06"]()
    kick = _frame(6.0)
    still = case.match.ball[:kick]
    assert np.allclose(still, still[0])
    assert not np.allclose(case.match.ball[kick], still[0]), "ball moves at the kick frame"
    assert (case.expected[:kick] == "D").all()
    assert (case.expected[kick:] == "H").all()
    speeds = np.linalg.norm(np.diff(case.match.players[:kick + 1], axis=0), axis=2)
    assert speeds.max() == 0, "everybody waits for the corner"


# -- EPTS export for loader tests (issue #6) -----------------------------------------------------

def _read_epts(raw_path, pitch):
    frames, players, ball = [], [], []
    with open(raw_path, encoding="utf-8") as handle:
        for line in handle:
            frame, groups, ball_group = line.rstrip("\n").split(":")
            frames.append(int(frame))
            players.append([[float(v) for v in g.split(",")] for g in groups.split(";")])
            ball.append([float(v) for v in ball_group.split(",")])
    scale = np.array(pitch)
    return (np.array(frames), np.array(players)[:, :, :2] * scale, np.array(players)[:, :, 2],
            np.array(ball)[:, :2] * scale)


def test_write_epts_round_trips_positions_in_the_atd_layout(tmp_path):
    match = synth.SCENES["EC-02a"]().match
    meta, raw = tmp_path / "m.xml", tmp_path / "r.txt"
    synth.write_epts(match, str(meta), str(raw))

    frames, players, speed, ball = _read_epts(str(raw), match.pitch)
    assert frames.tolist() == list(range(1, match.n_frames + 1)), "ATD frame ids count from 1"
    np.testing.assert_allclose(players, match.players, atol=1e-4)
    np.testing.assert_allclose(ball, match.ball, atol=1e-4)
    moved = np.linalg.norm(match.players[11] - match.players[10], axis=1) * match.fps
    np.testing.assert_allclose(speed[11], moved, atol=1e-3)

    report = schema_probe.probe_raw(str(raw))
    assert report["player_groups_per_line"] == {22: match.n_frames}
    assert report["fields_per_ball_group"] == {3: match.n_frames}
    assert schema_probe.probe_meta(str(meta))["slots_per_team_position"] == {
        "team_1": 11, "team_2": 11}


def test_write_epts_refuses_slots_without_a_team(tmp_path):
    match = synth.SCENES["EC-06"]().match
    team = match.team.copy()
    team[0] = T.NOBODY
    odd = T.Match(ball=match.ball, players=match.players, team=team)
    with pytest.raises(ValueError, match="team"):
        synth.write_epts(odd, str(tmp_path / "m.xml"), str(tmp_path / "r.txt"))
