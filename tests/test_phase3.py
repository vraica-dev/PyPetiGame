"""Phase 3: waves, life cap, endless mode, persistent bests."""
import pytest

from game import MAX_LIVES, WAVES


def test_waves_have_distinct_speed_mix_and_bg(pg):
    assert len(WAVES) == 3
    assert [w['name'] for w in WAVES] == ['Tea Time', 'Sugar Rush', 'Rotten Storm']
    speeds = [w['base_speed'] for w in WAVES]
    assert speeds == sorted(speeds)  # escalating
    bgs = {tuple(w['bg']) for w in WAVES}
    assert len(bgs) == 3  # palette shift per wave

    def kinds(pool):
        return {k for _, k, _ in pool}

    assert kinds(WAVES[0]['skins']) == {'good', 'golden', 'bad'}
    # Sugar Rush is golden-heavy, Rotten Storm is rotten-heavy
    def count(pool, kind):
        return sum(1 for _, k, _ in pool if k == kind)

    assert count(WAVES[1]['skins'], 'golden') > count(WAVES[0]['skins'], 'golden')
    assert count(WAVES[2]['skins'], 'bad') > count(WAVES[0]['skins'], 'bad')


def test_classic_advances_wave_every_20s(pg):
    pg.reset_game(mode='classic')
    assert pg.wave_index == 0
    assert pg.current_wave()['name'] == 'Tea Time'
    pg.elapsed = 20.0
    assert pg._update_wave() is True
    assert pg.wave_index == 1
    assert pg.current_wave()['name'] == 'Sugar Rush'
    assert pg.fall_speed == pytest.approx(WAVES[1]['base_speed'])
    pg.elapsed = 45.0
    pg._update_wave()
    assert pg.current_wave()['name'] == 'Rotten Storm'


def test_run_timmer_drives_waves_in_classic(pg):
    pg.reset_game(mode='classic')
    pg.timer = 60.0
    for _ in range(20 * 60):
        pg.run_timmer()
    assert pg.wave_index == 1
    assert pg.timer == pytest.approx(40.0)


def test_wave_clear_grants_life_capped_at_9(pg):
    pg.reset_game(mode='classic')
    pg.player.lives = 5
    pg.elapsed = 20.0
    pg._update_wave()
    assert pg.player.lives == 6
    pg.player.lives = MAX_LIVES
    pg.elapsed = 40.0
    pg._update_wave()
    assert pg.player.lives == MAX_LIVES == 9


def test_default_mode_is_classic(pg):
    pg.reset_game()
    assert pg.mode == 'classic'


def test_endless_has_no_timer_expiry_and_escalates(pg):
    pg.reset_game(mode='endless')
    for _ in range(60 * 61):  # 61s of frames
        assert pg.run_timmer() == float('inf')
    assert pg.timer == float(pg.init_timer)  # untouched
    assert pg.wave_index >= 3  # past Rotten Storm
    wave = pg.current_wave()
    assert wave['base_speed'] > WAVES[-1]['base_speed']
    assert wave['bg'] == tuple(WAVES[-1]['bg']) or list(wave['bg']) == list(
        WAVES[-1]['bg']
    )


def test_endless_wave_clear_still_grants_life(pg):
    pg.reset_game(mode='endless')
    pg.player.lives = 4
    pg.elapsed = 20.0
    pg._update_wave()
    assert pg.player.lives == 5


def test_bests_max_merge_and_combo_caught(pg, memdb):
    memdb.reset_game()
    assert memdb.record_result('ABCD', 10, combo_p=3, caught_p=7) is True
    assert memdb.record_result('ABCD', 6, combo_p=9, caught_p=2) is False
    rows = memdb.read_bests()
    assert rows == [('ABCD', 10, 9, 7)]  # per-field max, best not overwritten


def test_read_scoreboard_still_top5_compat(memdb):
    for i in range(7):
        memdb.write_scoreboard(f'P{i}', i)
    rows = memdb.read_scoreboard()
    assert len(rows) == 5
    assert [s for _, s in rows] == [6, 5, 4, 3, 2]


def test_handle_eat_tracks_combo_and_caught(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    for _ in range(2):
        pg.treat.kind = 'good'
        pg.treat.points = 1
        pg.handle_eat()
    assert pg.combo == 2
    assert pg.best_combo == 2
    assert pg.treats_caught == 2
    pg.treat.kind = 'bad'
    pg.handle_eat()
    assert pg.combo == 0  # rotten resets combo
    assert pg.best_combo == 2  # longest kept
