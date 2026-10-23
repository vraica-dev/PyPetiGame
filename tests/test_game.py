"""Core gameplay tests — the 10 most important behaviours."""
import os

import pytest

import game


def test_reset_game_clears_score_and_timer(pg):
    pg.player.points = 42
    pg.score_value = 42
    pg.timer = 3.0
    pg.reset_game()
    assert pg.timer == float(pg.init_timer)
    assert pg.player.points == 0
    assert pg.score_value == 0


def test_timer_counts_down_and_expires_at_zero(pg):
    pg.timer = 1.0
    pg.run_timmer()
    assert pg.timer == pytest.approx(1.0 - 1 / 60)
    pg.timer = 0.001
    assert pg.run_timmer() == 0
    assert pg.timer == 0
    assert pg.run_timmer() == 0


def test_scoring_normal_and_golden_treat(pg):
    pg.player.points = 0
    pg.player.add_point()
    assert pg.player.points == 1
    pg.player.add_special_points()
    assert pg.player.points == 4  # golden treat is worth 3


def test_treat_skin_is_basename_so_bonus_matches(pg):
    pg.treat.set_treat_pic()
    assert pg.treat.selected_skin in ('treats.png', 'treats_2.png')
    assert '/' not in pg.treat.selected_skin
    assert pg.treat.treatrect is not None


def test_treat_respawn_stays_in_bounds(pg):
    for _ in range(50):
        pg.treat.rand_move()
        assert 1 <= pg.treat.pos_x <= 482
        assert 1 <= pg.treat.pos_y <= 388
    # respawn also reloads the sprite and syncs the rect
    pg.treat.spawn()
    assert pg.treat.treatrect.center == (pg.treat.pos_x, pg.treat.pos_y)


def test_cat_spawn_syncs_rect_to_position(pg):
    pg.cat.set_graph()
    pg.cat.pos_x, pg.cat.pos_y = 123, 321
    pg.cat.spawn()
    assert pg.cat.catrect.center == (123, 321)


def test_collision_registers_and_scores(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    # force overlap then run the same collision branch as run_game()
    pg.treat.pos_x, pg.treat.pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    pg.treat.spawn()
    assert pg.cat.catrect.colliderect(pg.treat.treatrect)
    before = pg.player.points
    pg.player.add_point()
    pg.score_value = pg.player.points
    assert pg.score_value == before + 1


def test_scoreboard_upserts_by_player_name(memdb):
    memdb.write_scoreboard('ABCD', 5)
    memdb.write_scoreboard('ABCD', 9)  # same name -> update, not a 2nd row
    rows = memdb.read_scoreboard()
    assert rows == [('ABCD', 9)]


def test_scoreboard_returns_top5_by_score_desc(memdb):
    for i in range(7):
        memdb.write_scoreboard(f'P{i}', i)
    rows = memdb.read_scoreboard()
    assert len(rows) == 5
    assert [s for _, s in rows] == [6, 5, 4, 3, 2]


def test_app_boots_with_db_table_and_basedir(pg):
    assert os.getcwd() == game.BASE_DIR
    cur = pg.db_conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scores'"
    )
    assert cur.fetchone() is not None
