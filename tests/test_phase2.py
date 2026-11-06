"""Phase 2 depth tests — multi-treat, power-ups, rotten variety, near-miss."""
import pytest

from objects.treats_obj import MIN_SPAWN_DISTANCE, TreatObj


def _eatable(pg, treat, cat_pos=True):
    treat.set_treat_pic()
    pg.cat.set_graph()
    if cat_pos:
        treat.pos_x, treat.pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    treat.spawn()
    return treat


# -- multiple concurrent treats ----------------------------------------

def test_game_starts_with_three_treats(pg):
    assert len(pg.treats) == 3
    assert pg.treat is pg.treats[0]  # backwards-compat alias
    for t in pg.treats:
        assert isinstance(t, TreatObj)


def test_treat_count_scales_3_to_5_with_score(pg):
    pg.reset_game()
    pg.player.points = 0
    assert pg.desired_treat_count() == 3
    pg.player.points = 10
    assert pg.desired_treat_count() == 4
    pg.player.points = 20
    assert pg.desired_treat_count() == 5
    pg.player.points = 999
    assert pg.desired_treat_count() == 5  # capped


def test_ensure_treats_grows_and_keeps_alias(pg):
    pg.reset_game()
    pg.player.points = 25
    pg.ensure_treats()
    assert len(pg.treats) == 5
    assert pg.treat is pg.treats[0]
    for t in pg.treats:
        assert t.vy == pg.fall_speed


def test_handle_eat_takes_explicit_treat(pg):
    pg.reset_game()
    _eatable(pg, pg.treats[1])
    assert pg.cat.catrect.colliderect(pg.treats[1].treatrect)
    pg.treats[1].kind = 'good'
    pg.treats[1].points = 1
    pg.handle_eat(pg.treats[1])
    assert pg.player.points == 1


def test_reset_restores_three_treats_and_clears_timers(pg):
    pg.player.points = 30
    pg.ensure_treats()
    assert len(pg.treats) == 5
    pg.magnet_timer = 4.0
    pg.frenzy_timer = 7.0
    pg.reset_game()
    assert len(pg.treats) == 3
    assert pg.treat is pg.treats[0]
    assert pg.magnet_timer == 0 and pg.frenzy_timer == 0


# -- power-ups ----------------------------------------------------------

def test_powerup_sets_kind_and_reuses_golden_sprite(pg):
    pg.treat.set_powerup('magnet')
    assert pg.treat.kind == 'powerup'
    assert pg.treat.power == 'magnet'
    assert pg.treat.selected_skin == 'treats_2.png'
    pg.treat.spawn()
    assert pg.treat.treatrect.center == (pg.treat.pos_x, pg.treat.pos_y)


def test_eating_powerup_activates_timer(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treats[0].set_powerup('shield')
    pg.treats[0].pos_x, pg.treats[0].pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    pg.treats[0].spawn()
    pg.handle_eat(pg.treats[0])
    assert pg.shield_timer > 0
    assert pg.player.lives == 9


def test_shield_blocks_rotten_damage(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.shield_timer = 8.0
    t = _eatable(pg, pg.treats[0])
    t.kind = 'bad'
    t.points = 0
    t.spawn()
    pg.handle_eat(t)
    assert pg.player.lives == 9  # absorbed
    assert pg.player.points == 0


def test_slowmo_halves_fall_speed(pg):
    pg.reset_game()
    pg.slowmo_timer = 5.0
    assert pg.speed_scale() == 0.5
    t = pg.treats[0]
    t.vy = 6
    t.pos_y = 0
    t.fast = False
    t.decoy = False
    t.update(speed_scale=pg.speed_scale())
    assert t.pos_y == 3.0
    pg.slowmo_timer = 0.0
    assert pg.speed_scale() == 1.0


def test_frenzy_doubles_points(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.frenzy_timer = 8.0
    t = _eatable(pg, pg.treats[0])
    t.kind = 'good'
    t.points = 1
    t.fast = False
    t.spawn()
    pg.handle_eat(t)
    assert pg.player.points == 2
    pg.frenzy_timer = 0.0
    pg.reset_combo()  # isolate frenzy-off scoring from the combo streak
    t2 = pg.treats[0]
    t2.kind = 'good'
    t2.points = 1
    t2.pos_x, t2.pos_y = pg.cat.pos_x, pg.cat.pos_y
    t2.spawn()
    pg.handle_eat(t2)
    assert pg.player.points == 3  # +1 without frenzy


def test_power_timers_tick_down(pg):
    pg.magnet_timer = 1.0
    pg.tick_power_timers(dt=0.5)
    assert pg.magnet_timer == pytest.approx(0.5)
    pg.tick_power_timers(dt=1.0)
    assert pg.magnet_timer == 0.0
    assert not pg.magnet_active


# -- rotten variety ------------------------------------------------------

def test_fast_rotten_falls_2x(pg):
    pg.treat.set_treat_pic()
    pg.treat.fast = True
    pg.treat.decoy = False
    pg.treat.vy = 5
    pg.treat.pos_y = 0
    pg.treat.update()
    assert pg.treat.pos_y == 10


def test_decoy_disguised_then_reveals(pg):
    pg.treat.set_treat_pic()
    pg.treat.make_decoy(duration=1.0)
    assert pg.treat.kind == 'bad'  # rotten all along
    assert pg.treat.looks_golden()  # ...but looks golden
    assert pg.treat.selected_skin == 'treats_2.png'
    # still disguised after half a second (dt is in 60-FPS frames)
    pg.treat.pos_y = 0
    pg.treat.update(dt=30.0)
    assert pg.treat.disguised
    assert pg.treat.looks_golden()
    # reveals after the 1s window (30 + 35 frames > 60 frames = 1s)
    pg.treat.update(dt=35.0)
    assert not pg.treat.disguised
    assert pg.treat.selected_skin == 'treats_bad.png'
    assert pg.treat.is_rotten()


def test_decoy_eaten_costs_a_life(pg):
    pg.reset_game()
    pg.cat.set_graph()
    t = pg.treats[0]
    t.set_treat_pic()
    t.make_decoy(duration=99.0)  # still disguised when caught
    t.pos_x, t.pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    t.spawn()
    pg.handle_eat(t)
    assert pg.player.lives == 8


# -- near-miss bonus -----------------------------------------------------

def test_near_miss_rotten_grants_bonus_point(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.cat.pos_x = 960
    t = pg.treats[0]
    t.set_treat_pic()
    t.kind = 'bad'
    t.points = 0
    t.fast = False
    t.decoy = False
    t.touched = False
    t.pos_x = 960 + 30  # within ~50px
    t.pos_y = t.h + 61  # falls off-screen -> miss
    before = pg.player.points
    assert t.update() is True
    assert pg.handle_near_miss(t) is True
    assert pg.player.points == before + 1


def test_near_miss_requires_proximity_and_no_touch(pg):
    pg.reset_game()
    pg.cat.pos_x = 500
    t = pg.treats[0]
    t.set_treat_pic()
    t.kind = 'bad'
    t.points = 0
    t.fast = False
    t.decoy = False
    # too far away: no bonus
    t.touched = False
    t.pos_x = 500 + 200
    t.pos_y = t.h + 61
    t.update()
    assert pg.handle_near_miss(t) is False
    # touched even when close: no bonus
    t.touched = False
    t.pos_x = 500 + 10
    t.pos_y = t.h + 61
    t.update()
    t.last_miss_touched = True  # was caught, not dodged
    before = pg.player.points
    assert pg.handle_near_miss(t) is False
    assert pg.player.points == before


def test_good_miss_grants_no_bonus(pg):
    pg.reset_game()
    pg.cat.pos_x = 700
    t = pg.treats[0]
    t.set_treat_pic()
    t.kind = 'good'
    t.points = 1
    t.fast = False
    t.decoy = False
    t.touched = False
    t.pos_x = 700 + 10
    t.pos_y = t.h + 61
    t.update()
    assert t.last_miss_kind == 'good'
    assert pg.handle_near_miss(t) is False


# -- spawn fairness --------------------------------------------------------

def test_concurrent_spawns_keep_min_distance(pg):
    pg.reset_game()
    for t in pg.treats:
        t.set_treat_pic()
    for _ in range(30):
        for t in pg.treats:
            t.rand_move(others=pg.treats, min_dist=MIN_SPAWN_DISTANCE)
        xs = sorted(t.pos_x for t in pg.treats)
        gaps = [b - a for a, b in zip(xs, xs[1:])]
        assert min(gaps) >= MIN_SPAWN_DISTANCE


def test_golden_window_can_yield_powerup(pg):
    seen_power = False
    for _ in range(300):
        pg.treat.set_treat_pic()
        if pg.treat.kind == 'powerup':
            seen_power = True
            assert pg.treat.power in ('magnet', 'shield', 'slowmo', 'frenzy')
    assert seen_power  # golden-only power-ups actually appear


# -- combined Phase 0/1/2: combo x frenzy x power-up x juice --------------

def test_combo_frenzy_powerup_stack_with_juice(pg):
    """Combo multiplier and frenzy doubling stack; power-ups keep the
    streak alive and every catch emits a juice burst (dt-safe)."""
    pg.reset_game()
    pg.cat.set_graph()
    bursts0 = len(pg.bursts)
    t = pg.treats[0]

    def eat(kind, points, power=None):
        if power is not None:
            t.set_powerup(power)
        else:
            t.set_treat_pic()
            t.kind = kind
            t.points = points
            t.power = None
            t.fast = False
            t.decoy = False
        t.pos_x, t.pos_y = pg.cat.pos_x, pg.cat.pos_y
        pg.cat.spawn()
        t.spawn()
        pg.handle_eat(t)

    eat('good', 1)  # combo 1 -> x1, +1
    assert pg.player.points == 1
    eat('good', 1)  # combo 2 -> x2, +2
    assert pg.player.points == 3
    pg.frenzy_timer = 8.0
    eat('good', 1)  # combo 3 -> x3, frenzy x2, +6
    assert pg.player.points == 9
    eat('good', 1, power='magnet')  # power-up: streak -> 4, +1*x4*2
    assert pg.magnet_timer > 0
    assert pg.combo == 4
    assert pg.player.points == 9 + 8
    assert len(pg.bursts) == bursts0 + 4  # one burst per catch
    # dt applied to all falls: slowmo is off, so full speed
    y = t.pos_y = 0.0
    t.vy = 6
    t.fast = False
    t.decoy = False
    t.update(dt=2.0, speed_scale=pg.speed_scale())
    assert t.pos_y == y + 12.0
