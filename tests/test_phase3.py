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


# -- combined Phase 0+1+2+3 integration ---------------------------------

def test_wave_pool_and_speed_apply_to_all_treats(pg):
    pg.reset_game(mode='classic')
    pg.elapsed = 20.0
    pg._update_wave()  # Sugar Rush
    assert pg.wave_index == 1
    for t in pg.treats:
        assert t.pool == WAVES[1]['skins']
        assert t.vy == pytest.approx(WAVES[1]['base_speed'])


def test_late_added_treats_inherit_current_wave_pool(pg):
    pg.reset_game(mode='classic')
    pg.elapsed = 40.0
    pg._update_wave()  # Rotten Storm
    pg.player.points = 25  # force 5 concurrent treats
    pg.ensure_treats()
    assert len(pg.treats) == 5
    for t in pg.treats:
        assert t.pool == WAVES[2]['skins']


def test_wave_pool_respects_powerup_conversion(pg, monkeypatch):
    import objects.treats_obj as treats_mod
    monkeypatch.setattr(treats_mod, 'GOLDEN_TO_POWERUP_CHANCE', 1.0)
    pg.reset_game(mode='classic')
    golden_pool = [('static/images/treats_2.png', 'golden', 3)]
    pg.treat.pool = golden_pool
    pg.treat.set_treat_pic()
    # golden-only window: forced conversion turns the roll into a power-up
    assert pg.treat.kind == 'powerup'
    assert pg.treat.power in treats_mod.POWERUP_TYPES


def test_wave_speed_scales_multi_treat_updates(pg):
    pg.reset_game(mode='classic')
    pg.slowmo_timer = 5.0  # slowmo halves falls via speed_scale()
    assert pg.speed_scale() == 0.5
    for t in pg.treats:
        t.vy = 6.0
        t.pos_y = 100.0
        t.update(1.0, speed_scale=pg.speed_scale())
        assert t.pos_y == pytest.approx(103.0)  # 6 * 0.5 * dt


def test_run_timmer_is_dt_correct(pg):
    pg.reset_game(mode='classic')
    pg.timer = 60.0
    pg.run_timmer(dt=2.0)  # one slow frame ~= 2/60s
    assert pg.elapsed == pytest.approx(2.0 / 60.0)
    assert pg.timer == pytest.approx(60.0 - 2.0 / 60.0)


def test_reset_clears_waves_bests_fields_and_reapplies_pool(pg):
    pg.reset_game(mode='endless')
    pg.wave_index = 2
    pg.elapsed = 45.0
    pg.combo = 5
    pg.best_combo = 5
    pg.treats_caught = 9
    pg.reset_game(mode='classic')
    assert pg.wave_index == 0
    assert pg.elapsed == 0.0
    assert pg.combo == 0
    assert pg.best_combo == 0
    assert pg.treats_caught == 0
    assert pg.mode == 'classic'
    for t in pg.treats:
        assert t.pool == WAVES[0]['skins']
        assert t.vy == pytest.approx(WAVES[0]['base_speed'])
