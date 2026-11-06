"""Phase 1 juice tests — combo, particles, shake/flash, animation, SFX."""
from objects.juice_obj import ParticleBurst


def _catch(pg, kind, points):
    """Place a treat of `kind` on the cat and eat it."""
    pg.treat.kind = kind
    pg.treat.points = points
    pg.treat.pos_x, pg.treat.pos_y = pg.cat.pos_x, pg.cat.pos_y
    pg.cat.spawn()
    pg.treat.spawn()
    pg.handle_eat()


def test_combo_builds_multiplier_and_caps_at_x4(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    _catch(pg, 'good', 1)
    assert (pg.combo, pg.player.points) == (1, 1)  # x1
    _catch(pg, 'good', 1)
    assert (pg.combo, pg.player.points) == (2, 3)  # +1x2
    _catch(pg, 'good', 1)
    assert (pg.combo, pg.player.points) == (3, 6)  # +1x3
    _catch(pg, 'good', 1)
    assert (pg.combo, pg.player.points) == (4, 10)  # +1x4
    _catch(pg, 'good', 1)
    assert (pg.combo, pg.player.points) == (5, 14)  # capped at x4
    assert pg.combo_mult() == 4


def test_golden_catch_scores_base_times_mult(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    _catch(pg, 'good', 1)  # combo 1 -> x1
    _catch(pg, 'golden', 3)  # combo 2 -> 3x2
    assert pg.combo == 2
    assert pg.player.points == 1 + 6


def test_rotten_resets_combo_and_triggers_shake_and_flash(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    _catch(pg, 'good', 1)
    _catch(pg, 'good', 1)
    assert pg.combo == 2
    lives = pg.player.lives
    _catch(pg, 'bad', 0)
    assert pg.combo == 0
    assert pg.combo_mult() == 1
    assert pg.player.lives == lives - 1
    assert pg.juice.shake_t > 0  # screen shake armed
    assert pg.juice.flash_t > 0  # red flash armed
    assert pg.juice.flash_color == (255, 40, 40)


def test_golden_triggers_gold_flash_not_shake(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    _catch(pg, 'golden', 3)
    assert pg.juice.flash_t > 0
    assert pg.juice.flash_color == (255, 215, 0)
    assert pg.juice.shake_t == 0  # golden path never shakes


def test_missed_good_treat_resets_combo(pg):
    pg.reset_game()
    pg.treat.set_treat_pic()
    pg.combo = 3
    pg.treat.kind = 'good'
    pg.treat.pos_y = pg.treat.h + 61  # fell off-screen
    assert pg.treat.update() is True
    assert pg.treat.missed_kind == 'good'
    # same consumption logic as the game loop
    if pg.treat.missed_kind in ('good', 'golden'):
        pg.reset_combo()
        pg.treat.missed_kind = None
    assert pg.combo == 0
    assert pg.treat.missed_kind is None


def test_missed_rotten_does_not_reset_combo(pg):
    pg.reset_game()
    pg.treat.set_treat_pic()
    pg.combo = 3
    pg.treat.kind = 'bad'
    pg.treat.pos_y = pg.treat.h + 61
    assert pg.treat.update() is True
    assert pg.treat.missed_kind == 'bad'
    if pg.treat.missed_kind in ('good', 'golden'):
        pg.reset_combo()
    assert pg.combo == 3  # dodging rotten keeps the streak


def test_catch_spawns_burst_that_dies_in_0_4s(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    assert pg.bursts == []
    _catch(pg, 'good', 1)
    assert len(pg.bursts) == 1
    burst = pg.bursts[0]
    assert len(burst.particles) > 0
    burst.update(0.2)
    assert not burst.dead  # still alive halfway
    burst.update(0.25)
    assert burst.dead  # 0.4s life expired
    # drawing a live burst headless never raises
    fresh = ParticleBurst(100, 100, (255, 220, 130))
    fresh.draw(pg.screen)


def test_shake_offset_decays_and_flash_draws_headless(pg):
    pg.reset_game()
    ox, oy = pg.juice.offset()
    assert (ox, oy) == (0, 0)  # idle -> no offset
    pg.juice.shake(dur=0.35, mag=14)
    pg.juice.update(1 / 60)
    assert pg.juice.shake_t < 0.35
    pg.juice.update(1.0)
    assert pg.juice.offset() == (0, 0)  # expired -> back to zero
    pg.juice.flash((255, 40, 40), dur=0.25)
    pg.juice.draw_flash(pg.screen)  # must not raise headless
    pg.juice.update(1.0)
    pg.juice.draw_flash(pg.screen)  # expired flash is a no-op


def test_cat_wag_changes_frame_and_lean_tilts(pg):
    pg.cat.set_graph()
    base_size = pg.cat.base_img.get_size()
    assert base_size == (140, 140)
    pg.cat.animate(0.0, moving=0)
    # wag rotates the sprite, so the frame canvas differs from the base
    assert pg.cat.catimg.get_size() != base_size
    pg.cat.animate(0.0, moving=1)
    assert pg.cat.lean == 1.0
    pg.cat.animate(0.0, moving=-1)
    assert pg.cat.lean == -1.0
    pg.cat.spawn()
    assert pg.cat.catrect.center == (pg.cat.pos_x, pg.cat.pos_y)


def test_treat_pulse_keeps_center_and_is_headless_safe(pg):
    pg.treat.set_treat_pic()
    pg.treat.spawn()
    before = pg.treat.treatrect.center
    pg.treat.pulse(0.0)
    pg.treat.pulse(123.456)
    assert pg.treat.treatrect.center == before


def test_sfx_paths_are_distinct_and_guarded(pg):
    # distinct event -> file wiring, reusing only bundled mp3s
    assert pg.SFX_FILES['eat'] == 'static/audio/cat_eat.mp3'
    assert pg.SFX_FILES['rotten'] == 'static/audio/cat_go.mp3'
    assert pg.SFX_FILES['combo'] == 'static/audio/cat_running.mp3'
    assert set(pg.SFX_FILES) == {'eat', 'golden', 'rotten', 'combo', 'gameover'}
    # every wired call is guarded — none may raise headless
    pg.eatSound()
    pg.goldenSound()
    pg.comboSound()
    pg.badSound()
    pg.goSound()
    pg._play_sfx('nonexistent')  # unknown name -> silent no-op


def test_reset_clears_combo_bursts_and_juice(pg):
    pg.reset_game()
    pg.cat.set_graph()
    pg.treat.set_treat_pic()
    _catch(pg, 'good', 1)
    _catch(pg, 'bad', 0)
    assert pg.combo == 0  # rotten already reset it; bursts/juice armed
    assert len(pg.bursts) > 0
    pg.combo = 3
    pg.reset_game()
    assert pg.combo == 0
    assert pg.bursts == []
    assert pg.juice.shake_t == 0
    assert pg.juice.flash_t == 0
    assert pg.combo_mult() == 1
