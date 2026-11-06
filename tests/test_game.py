"""Core gameplay tests — falling treats, bad treats, lives, 1080p."""
import os

import pytest

import game


@pytest.fixture()
def pg():
    g = game.PetunaGame()
    yield g
    try:
        g.db_conn.close()
    except Exception:
        pass
    g.game.quit()


@pytest.fixture()
def memdb(pg):
    """Point the game at a fresh in-memory scoreboard."""
    import sqlite3
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE scores (name TEXT NOT NULL, score INTEGER)')
    conn.commit()
    pg.db_conn = conn
    yield pg
    conn.close()


def test_window_defaults_to_1080p(pg):
    assert (pg.wndw_w, pg.wndw_h) == (1920, 1080)
    assert pg.screen.get_size() == (1920, 1080)


def test_reset_game_clears_score_lives_and_timer(pg):
    pg.player.points = 42
    pg.player.lives = 3
    pg.score_value = 42
    pg.timer = 3.0
    pg.fall_speed = 11.0
    pg.reset_game()
    assert pg.timer == float(pg.init_timer)
    assert pg.player.points == 0
    assert pg.player.lives == 9
    assert pg.score_value == 0
    assert pg.fall_speed == pg.base_fall_speed


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


def test_treat_drops_from_sky_within_bounds(pg):
    for _ in range(50):
        pg.treat.rand_move()
        assert 40 <= pg.treat.pos_x <= pg.wndw_w - 40
        assert pg.treat.pos_y == -40  # spawns above the screen, falls in
    pg.treat.spawn()
    assert pg.treat.treatrect.center == (pg.treat.pos_x, pg.treat.pos_y)


def test_treat_falls_and_missed_respawns_at_top(pg):
    pg.treat.set_treat_pic()
    y0 = pg.treat.pos_y
    assert pg.treat.update() is False
    assert pg.treat.pos_y == y0 + pg.treat.vy
    pg.treat.pos_y = pg.treat.h + 61  # fell off-screen
    assert pg.treat.update() is True  # missed -> respawned at top
    assert pg.treat.pos_y == -40


def test_treat_kinds_include_bad_with_zero_points(pg):
    kinds = set()
    for _ in range(100):
        pg.treat.set_treat_pic()
        kinds.add(pg.treat.kind)
        if pg.treat.kind == 'bad':
            assert pg.treat.points == 0
        else:
            assert pg.treat.points in (1, 3)
    assert 'bad' in kinds  # bad treats actually appear
    assert pg.treat.selected_skin in ('treats.png', 'treats_2.png', 'treats_bad.png')


def test_eat_good_treat_scores_and_speeds_up(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    pg.treat.kind = 'good'
    pg.treat.points = 1
    pg.treat.pos_x, pg.treat.pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    pg.treat.spawn()
    assert pg.cat.catrect.colliderect(pg.treat.treatrect)
    pg.handle_eat()
    assert pg.player.points == 1
    assert pg.player.lives == 9  # good treats cost no lives
    assert pg.fall_speed > pg.base_fall_speed  # difficulty ramps up


def test_eat_bad_treat_costs_a_life(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    pg.treat.kind = 'bad'
    pg.treat.points = 0
    pg.treat.pos_x, pg.treat.pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    pg.treat.spawn()
    assert pg.cat.catrect.colliderect(pg.treat.treatrect)
    pg.handle_eat()
    assert pg.player.points == 0  # no points for rotten treats
    assert pg.player.lives == 8


def test_last_life_lost_ends_game(pg):
    pg.player.lives = 1
    pg.player.lose_life()
    assert pg.player.lives == 0
    assert pg.player.is_alive() is False


def test_cat_spawn_syncs_rect_to_position(pg):
    pg.cat.set_graph()
    pg.cat.pos_x, pg.cat.pos_y = 960, 950
    pg.cat.spawn()
    assert pg.cat.catrect.center == (960, 950)


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


def test_funny_font_loads_and_renders(pg):
    import os
    assert os.path.isfile(pg.font_path)  # bundled Luckiest Guy TTF
    f1, f2 = pg.font(40), pg.font(40)
    assert f1 is f2  # cached
    surf = f1.render('Petunia!', True, (255, 255, 255))
    assert surf.get_width() > 0 and surf.get_height() > 0
    # right-alignment pins the right edge regardless of text width
    r1 = pg.font(30).render('Time: 9', True, (255, 255, 255)).get_rect()
    r2 = pg.font(30).render('Time: 60', True, (255, 255, 255)).get_rect()
    assert r1.width != r2.width  # widths differ, so fixed-x blits would jitter


def test_app_boots_with_db_table_and_basedir(pg):
    assert os.getcwd() == game.BASE_DIR
    cur = pg.db_conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scores'"
    )
    assert cur.fetchone() is not None
