"""Phase 4 meta tests: stats table, settings defaults, best celebration."""
import sqlite3

import pytest

import game
from objects import meta


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
    """Fresh in-memory scoreboard + stats for the game under test."""
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE scores (name TEXT NOT NULL, score INTEGER)')
    pg.db_conn = conn
    meta.ensure_stats_table(conn)
    yield pg
    conn.close()


def test_stats_table_created_with_zeroed_keys(memdb):
    cur = memdb.db_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stats'")
    assert cur.fetchone() is not None
    assert meta.get_stats(memdb.db_conn) == {
        'lifetime_treats': 0,
        'rottens_dodged': 0,
        'best_combo': 0,
    }


def test_good_eat_bumps_lifetime_treats_and_combo(memdb):
    memdb.reset_game()
    memdb.cat.set_graph()
    memdb.treat.set_treat_pic()
    memdb.treat.kind = 'good'
    memdb.treat.points = 1
    memdb.treat.pos_x, memdb.treat.pos_y = memdb.cat.pos_x, memdb.cat.pos_y
    memdb.cat.spawn()
    memdb.treat.spawn()
    memdb.handle_eat()
    stats = meta.get_stats(memdb.db_conn)
    assert stats['lifetime_treats'] >= 1
    assert stats['best_combo'] >= 1
    assert memdb.combo >= 1


def test_missed_rotten_dodges_and_resets_combo(memdb):
    memdb.reset_game()
    memdb.combo = 5
    memdb.handle_miss('bad')
    assert memdb.combo == 0
    assert meta.get_stats(memdb.db_conn)['rottens_dodged'] == 1
    memdb.handle_miss('good')  # missed good treat: no dodge credit
    assert meta.get_stats(memdb.db_conn)['rottens_dodged'] == 1


def test_rotten_eat_resets_combo_without_treat_credit(memdb):
    memdb.reset_game()
    memdb.combo = 4
    memdb.cat.set_graph()
    memdb.treat.set_treat_pic()
    memdb.treat.kind = 'bad'
    memdb.treat.points = 0
    memdb.treat.pos_x, memdb.treat.pos_y = memdb.cat.pos_x, memdb.cat.pos_y
    memdb.cat.spawn()
    memdb.treat.spawn()
    before = meta.get_stats(memdb.db_conn)['lifetime_treats']
    memdb.handle_eat()
    assert memdb.combo == 0
    assert meta.get_stats(memdb.db_conn)['lifetime_treats'] == before


def test_settings_defaults_and_roundtrip(tmp_path):
    base = str(tmp_path)
    assert meta.load_settings(base) == meta.DEFAULT_SETTINGS
    assert meta.DEFAULT_SETTINGS == {
        'volume': 7,
        'resolution': '1080p',
        'difficulty': 'Normal',
        'skin': 'classic',
    }
    custom = {'volume': 3, 'resolution': '720p', 'difficulty': 'Hard', 'skin': 'honey'}
    assert meta.save_settings(base, custom) is True
    assert meta.load_settings(base) == custom
    # corrupt file falls back to defaults, never raises
    (tmp_path / 'settings.json').write_text('{nope')
    assert meta.load_settings(base) == meta.DEFAULT_SETTINGS


def test_difficulty_presets_affect_lives_and_speed(pg):
    assert meta.difficulty_preset('Easy') == {'lives': 12, 'fall_speed': 4.0}
    assert meta.difficulty_preset('Hard')['lives'] == 6
    pg.settings['difficulty'] = 'Hard'
    pg.reset_game()
    assert pg.player.lives == 6
    assert pg.fall_speed == pg.base_fall_speed == 7.0
    pg.settings['difficulty'] = 'Easy'
    pg.reset_game()
    assert pg.player.lives == 12


def test_skin_unlock_milestones():
    assert [s['id'] for s in meta.unlocked_skins(0)] == ['classic']
    assert [s['id'] for s in meta.unlocked_skins(50)] == ['classic', 'honey']
    assert len(meta.unlocked_skins(150)) == 3
    assert meta.skin_by_id('nope')['id'] == 'classic'


def test_new_best_detected_before_scoreboard_update(memdb):
    memdb.write_scoreboard('ABCD', 5)
    assert meta.is_new_best(memdb.db_conn, 'ABCD', 9) is True
    assert meta.is_new_best(memdb.db_conn, 'ABCD', 5) is False
    assert meta.is_new_best(memdb.db_conn, 'NEWB', 1) is True  # first run
    assert meta.is_new_best(memdb.db_conn, 'NEWB', 0) is False


def test_end_game_flags_celebration_and_persists(monkeypatch, memdb):
    monkeypatch.setattr(memdb, 'game_over', lambda: None)  # skip UI loop
    memdb.reset_game()
    memdb.player.player_name = 'ABCD'
    memdb.player.points = 9
    memdb.combo = 3
    memdb.end_game("Time's up!")
    assert memdb.is_new_best is True
    assert memdb.read_scoreboard() == [('ABCD', 9)]
    assert meta.get_stats(memdb.db_conn)['best_combo'] == 3
    # beating nothing new -> no celebration
    memdb.reset_game()
    memdb.player.player_name = 'ABCD'
    memdb.player.points = 2
    memdb.end_game("Time's up!")
    assert memdb.is_new_best is False


# -- Phase 4 x waves/endless/multi-treat integration ---------------------

def test_difficulty_shifts_wave_speeds(pg):
    pg.settings['difficulty'] = 'Hard'
    pg.reset_game()
    assert pg.fall_speed == pytest.approx(7.0)
    pg.elapsed = 20.0
    pg._update_wave()  # Sugar Rush base 7.0 + Hard bonus 2.0
    assert pg.wave_index == 1
    assert pg.fall_speed == pytest.approx(9.0)
    for t in pg.treats:
        assert t.vy == pytest.approx(9.0)
    pg.settings['difficulty'] = 'Easy'
    pg.reset_game()
    assert pg.fall_speed == pytest.approx(4.0)
    pg.elapsed = 20.0
    pg._update_wave()
    assert pg.fall_speed == pytest.approx(6.0)  # 7.0 base - 1.0 bonus


def test_difficulty_shifts_treat_counts(pg):
    pg.settings['difficulty'] = 'Easy'
    pg.reset_game()
    assert pg.desired_treat_count() == 2
    pg.settings['difficulty'] = 'Hard'
    pg.reset_game()
    assert pg.desired_treat_count() == 4
    pg.player.points = 25  # past both TREAT_COUNT_STEPS
    assert pg.desired_treat_count() == 6  # 5 + Hard bonus, clamped


def test_multi_treat_combo_bumps_lifetime_stats(memdb):
    memdb.reset_game()
    memdb.cat.set_graph()
    for t in memdb.treats:
        t.set_treat_pic()
        t.kind = 'good'
        t.points = 1
    memdb.handle_eat(memdb.treats[1])
    memdb.handle_eat(memdb.treats[2])
    assert memdb.combo == 2
    assert memdb.best_combo == 2
    assert memdb.treats_caught == 2
    assert meta.get_stats(memdb.db_conn)['lifetime_treats'] == 2
    assert meta.get_stats(memdb.db_conn)['best_combo'] == 2


def test_wave_clear_keeps_easy_bonus_lives(pg):
    pg.settings['difficulty'] = 'Easy'
    pg.reset_game()
    assert pg.player.lives == 12
    pg.elapsed = 20.0
    pg._update_wave()  # wave-clear refill must not cut Easy back to 9
    assert pg.player.lives == 12


def test_pause_menu_resume_path(pg, monkeypatch):
    import pygame
    events = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)]
    monkeypatch.setattr(pg.game.event, 'get', lambda: events)
    assert pg.pause_menu() == 'resume'


def test_pause_menu_quit_path(pg, monkeypatch):
    import pygame
    events = [
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN),
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN),
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
    ]
    monkeypatch.setattr(pg.game.event, 'get', lambda: events)
    assert pg.pause_menu() == 'quit'
