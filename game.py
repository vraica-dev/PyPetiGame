import os
import sqlite3

import pygame

from objects.cursor_obj import CursorObj
from objects.juice_obj import JuiceState, ParticleBurst
from objects.meta import (
    RESOLUTIONS,
    STAT_KEYS,
    bump_stat,
    difficulty_preset,
    ensure_stats_table,
    get_stats,
    is_new_best,
    load_settings,
    save_settings,
    set_stat_max,
    skin_by_id,
    unlocked_skins,
    volume_to_mixer,
)
from objects.petun_obj import PetunaObj
from objects.player_obj import PlayerObj
from objects.treats_obj import MIN_SPAWN_DISTANCE, TreatObj

# Phase 2 — Depth tuning.
START_TREAT_COUNT = 3
MAX_TREAT_COUNT = 5
# Points thresholds that grow the concurrent treat count 3 -> 4 -> 5.
TREAT_COUNT_STEPS = (10, 20)
NEAR_MISS_THRESHOLD = 50  # px horizontal distance for the rotten dodge bonus
NEAR_MISS_POINTS = 1
MAGNET_DURATION = 5.0   # seconds good treats drift toward the cat
SHIELD_DURATION = 8.0   # seconds rotten treats cost no life
SLOWMO_DURATION = 5.0   # seconds treats fall at half speed
FRENZY_DURATION = 8.0   # seconds points are doubled
MAGNET_PULL = 7  # px/frame good treats slide toward the cat

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WAVE_DURATION = 20.0
MAX_LIVES = 9

_GOOD = 'static/images/treats.png'
_GOLD = 'static/images/treats_2.png'
_BAD = 'static/images/treats_bad.png'

# Phase 3 progression: 3 x 20s waves. Each wave shifts the fall-speed base,
# the treat mix (skin weights) and the background palette.
WAVES = [
    {
        'name': 'Tea Time',
        'base_speed': 5.0,
        'bg': (52, 106, 107),
        'skins': [
            (_GOOD, 'good', 1),
            (_GOOD, 'good', 1),
            (_GOOD, 'good', 1),
            (_GOLD, 'golden', 3),
            (_GOLD, 'golden', 3),
            (_BAD, 'bad', 0),
            (_BAD, 'bad', 0),
        ],
    },
    {
        'name': 'Sugar Rush',
        'base_speed': 7.0,
        'bg': (126, 84, 150),
        'skins': [
            (_GOOD, 'good', 1),
            (_GOOD, 'good', 1),
            (_GOOD, 'good', 1),
            (_GOLD, 'golden', 3),
            (_GOLD, 'golden', 3),
            (_GOLD, 'golden', 3),
            (_GOLD, 'golden', 3),
            (_BAD, 'bad', 0),
        ],
    },
    {
        'name': 'Rotten Storm',
        'base_speed': 9.0,
        'bg': (122, 52, 52),
        'skins': [
            (_GOOD, 'good', 1),
            (_GOOD, 'good', 1),
            (_GOOD, 'good', 1),
            (_GOLD, 'golden', 3),
            (_BAD, 'bad', 0),
            (_BAD, 'bad', 0),
            (_BAD, 'bad', 0),
            (_BAD, 'bad', 0),
        ],
    },
]

MODES = ('classic', 'endless')


class PetunaGame:
    def __init__(self):
        # Run all relative asset paths from the game root no matter
        # where the player launches the script from.
        os.chdir(BASE_DIR)

        self.game = pygame
        self.game_running = False
        self.app_running = True
        # Phase 4 meta: persisted settings (volume / window size /
        # difficulty / skin). Defaults keep the classic 1080p loop.
        self.settings = load_settings(BASE_DIR)
        res = RESOLUTIONS.get(
            self.settings.get('resolution', '1080p'), (1920, 1080)
        )
        self.wndw_w, self.wndw_h = res
        self.paused = False
        self.muted = False

        self.db_path = os.path.join(BASE_DIR, 'scoreboard_db', 'scores_db')
        self.db_conn = self.init_db()
        ensure_stats_table(self.db_conn)

        # Combo + celebration state (classic loop has no combo system;
        # Phase 4 tracks consecutive good eats for the stats screen).
        self.combo = 0
        self.is_new_best = False
        self.current_skin = skin_by_id(self.settings.get('skin', 'classic'))

        self.game.init()
        try:
            self.game.mixer.init()
        except pygame.error as e:
            print(f'[warn] mixer init failed (no audio device?): {e}')
        self.apply_volume()
        self.game.display.set_caption('Petunia Game')

        self.clock = self.game.time.Clock()
        self.screen = self.game.display.set_mode([self.wndw_w, self.wndw_h])

        self.cat = PetunaObj(self.wndw_w, self.wndw_h)
        self.treat = TreatObj(self.wndw_w, self.wndw_h)
        # Phase 2: concurrent treats scale 3-5 with score. self.treat is
        # kept as an alias of self.treats[0] for backwards compatibility.
        self.treats = [
            self.treat,
            TreatObj(self.wndw_w, self.wndw_h),
            TreatObj(self.wndw_w, self.wndw_h),
        ]
        # Power-up effect timers (seconds remaining, 0 = inactive).
        self.magnet_timer = 0.0
        self.shield_timer = 0.0
        self.slowmo_timer = 0.0
        self.frenzy_timer = 0.0
        self.player = PlayerObj()
        self.menu_cursor = CursorObj()

        self.init_timer = 60
        self.timer = float(self.init_timer)
        self.mode = 'classic'  # 'classic' (60s timed) or 'endless'
        self.wave_duration = WAVE_DURATION
        self.wave_index = 0
        self.elapsed = 0.0
        self.treats_caught = 0
        self.combo = 0
        self.best_combo = 0
        self.is_new_best = False

        self.velocity = 14
        # Bundled funny font (Luckiest Guy, OFL 1.1). Falls back to a
        # system font if the file ever goes missing.
        self.font_path = os.path.join(
            BASE_DIR, 'static', 'fonts', 'LuckiestGuy-Regular.ttf'
        )
        self._fonts = {}
        self.base_fall_speed = 5
        self.fall_speed = self.base_fall_speed
        self.apply_difficulty()
        self.score_value = 0
        self.game_over_reason = ''

        # --- Phase 1 juice (feel only) ---
        self.bursts = []  # active ParticleBurst list
        self.juice = JuiceState()  # shake + flash timers
        self._sfx = {}  # name -> pygame.mixer.Sound, guarded
        self._sfx_channels = {}  # name -> dedicated mixer Channel
        self._init_sfx()

    def apply_difficulty(self):
        """Apply the difficulty preset to lives + fall speed.

        Lives are stored on the game (``start_lives``) and pushed onto
        the player, so ``PlayerObj.reset()`` stays at the classic 9
        while runs start at the preset value."""
        preset = difficulty_preset(self.settings.get('difficulty', 'Normal'))
        self.base_fall_speed = float(preset['fall_speed'])
        self.fall_speed = self.base_fall_speed
        self.start_lives = int(preset['lives'])
        if hasattr(self, 'player'):
            self.player.lives = self.start_lives

    def difficulty_speed_bonus(self):
        """Fall-speed offset vs Normal, added on top of each wave base.

        Easy slows every wave by 1.0, Hard speeds them by 2.0."""
        preset = difficulty_preset(self.settings.get('difficulty', 'Normal'))
        return float(preset['fall_speed']) - float(WAVES[0]['base_speed'])

    def difficulty_treat_bonus(self):
        """Concurrent-treat offset: Easy -1, Normal 0, Hard +1."""
        return {'Easy': -1, 'Normal': 0, 'Hard': 1}.get(
            self.settings.get('difficulty', 'Normal'), 0
        )

    def apply_volume(self):
        try:
            if getattr(self, 'muted', False):
                self.game.mixer.music.set_volume(0.0)
            else:
                self.game.mixer.music.set_volume(
                    volume_to_mixer(self.settings.get('volume', 7))
                )
        except pygame.error:
            pass

    def apply_resolution(self):
        res = RESOLUTIONS.get(
            self.settings.get('resolution', '1080p'), (1920, 1080)
        )
        self.wndw_w, self.wndw_h = res
        self.screen = self.game.display.set_mode([self.wndw_w, self.wndw_h])
        self.treat.set_bounds(self.wndw_w, self.wndw_h)

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'CREATE TABLE IF NOT EXISTS scores (name TEXT NOT NULL, score INTEGER)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS player_bests ('
            'name TEXT PRIMARY KEY, best_score INTEGER DEFAULT 0, '
            'longest_combo INTEGER DEFAULT 0, treats_caught INTEGER DEFAULT 0)'
        )
        conn.commit()
        # Migrate: every legacy scores row seeds a bests row (best-effort).
        try:
            conn.execute(
                'INSERT OR IGNORE INTO player_bests (name, best_score) '
                'SELECT name, score FROM scores'
            )
            conn.commit()
        except sqlite3.Error:
            pass
        return conn

    def read_scoreboard(self):
        """Legacy top-5 view (backward compat): latest score per name."""
        c = self.db_conn.cursor()
        view_str = "SELECT * FROM scores ORDER BY score DESC LIMIT 5 "
        c.execute(view_str)
        res = c.fetchall()
        return res

    def read_bests(self, limit=5):
        """Persistent bests per player: best score, longest combo, caught."""
        c = self.db_conn.cursor()
        try:
            c.execute(
                'SELECT name, best_score, longest_combo, treats_caught '
                'FROM player_bests ORDER BY best_score DESC LIMIT ?',
                (limit,),
            )
            return c.fetchall()
        except sqlite3.Error:
            return []

    def record_result(self, name_p, score_p, combo_p=0, caught_p=0):
        """Max-merge a run into player_bests. Returns True if best improved."""
        self.db_conn.execute(
            'CREATE TABLE IF NOT EXISTS player_bests ('
            'name TEXT PRIMARY KEY, best_score INTEGER DEFAULT 0, '
            'longest_combo INTEGER DEFAULT 0, treats_caught INTEGER DEFAULT 0)'
        )
        c = self.db_conn.cursor()
        c.execute(
            'SELECT best_score FROM player_bests WHERE name = ?', (name_p,)
        )
        row = c.fetchone()
        prev = row[0] if row else 0
        c.execute(
            'INSERT INTO player_bests (name, best_score, longest_combo, '
            'treats_caught) VALUES (?, ?, ?, ?) '
            'ON CONFLICT(name) DO UPDATE SET '
            'best_score = max(best_score, excluded.best_score), '
            'longest_combo = max(longest_combo, excluded.longest_combo), '
            'treats_caught = max(treats_caught, excluded.treats_caught)',
            (name_p, score_p, combo_p, caught_p),
        )
        self.db_conn.commit()
        return score_p > (prev or 0)

    def write_scoreboard(self, name_p, score_p):
        c = self.db_conn.cursor()
        update_str = "UPDATE scores SET score =? WHERE name =?"
        query_str = "SELECT * FROM scores WHERE name =?"
        sql_str = "INSERT INTO scores (name, score) VALUES (?, ?)"

        c.execute(query_str, (name_p,))
        result = c.fetchone()

        if result:
            # BEST per player: only overwrite when the new score beats the old.
            if score_p > result[1]:
                c.execute(update_str, (score_p, name_p))
        else:
            c.execute(sql_str, (name_p, score_p))

        self.db_conn.commit()

    def font(self, font_size):
        """Cached funny font; system-font fallback if bundled file is missing."""
        if font_size not in self._fonts:
            try:
                self._fonts[font_size] = self.game.font.Font(
                    self.font_path, font_size
                )
            except OSError:
                self._fonts[font_size] = self.game.font.SysFont(
                    'comicsans', font_size, 1
                )
        return self._fonts[font_size]

    def draw_info(self, text_line=None, x=None, y=None, font_size=25,
                  color=(255, 255, 255)):
        font = self.font(font_size)
        if text_line is None and x is None and y is None:
            render = font.render(f'Score: {self.score_value}', True, (255, 255, 255))
            self.screen.blit(render, (7, 7))
        else:
            render = font.render(text_line, True, color)
            self.screen.blit(render, (x, y))

    def draw_centered(self, text, y, font_size=36):
        render = self.font(font_size).render(text, True, (255, 255, 255))
        rect = render.get_rect(center=(self.wndw_w // 2, y))
        self.screen.blit(render, rect)

    def draw_right(self, text, right, y, font_size=28):
        """Right-aligned text: right edge fixed, so values changing width
        (e.g. Time: 9 vs Time: 60) don't make the column jitter."""
        render = self.font(font_size).render(text, True, (255, 255, 255))
        rect = render.get_rect(right=right, top=y)
        self.screen.blit(render, rect)

    def draw_cursor(self, txt):
        render_font = self.font(self.menu_cursor.font_size).render(
            txt, True, (255, 255, 255)
        )
        self.screen.blit(render_font, (self.menu_cursor.pos_x, self.menu_cursor.pos_y))

    def effective_wave(self, index):
        """Wave dict for any index; past the last wave endless escalates."""
        if index < len(WAVES):
            return WAVES[index]
        last = WAVES[-1]
        extra = index - (len(WAVES) - 1)
        return {
            'name': f"{last['name']} +{extra}",
            'base_speed': last['base_speed'] + extra * 1.0,
            'bg': last['bg'],
            'skins': last['skins'],
        }

    def current_wave(self):
        return self.effective_wave(self.wave_index)

    def apply_wave(self, index):
        wave = self.effective_wave(index)
        # Difficulty shifts every wave's base speed (Easy -1, Hard +2).
        self.fall_speed = min(
            wave['base_speed'] + self.difficulty_speed_bonus(), 12
        )
        # Wave mix + speed apply to ALL concurrent treats.
        for t in self.treats:
            t.pool = wave['skins']
            t.vy = self.fall_speed

    def _update_wave(self):
        new_index = int(self.elapsed // self.wave_duration)
        if self.mode == 'classic':
            new_index = min(new_index, len(WAVES) - 1)
        if new_index != self.wave_index:
            self.wave_index = new_index
            self.apply_wave(new_index)
            # Wave-clear bonus: +1 life refill, capped so Easy's extra
            # lives are never cut back down to the classic 9.
            self.player.gain_life(
                1, cap=max(MAX_LIVES, self.start_lives)
            )
            return True
        return False

    def draw_game_over(self):
        self.draw_centered('* GAME OVER *', 350, 72)
        if self.is_new_best:
            self.draw_centered('*** NEW BEST! ***', 300, 48)
        self.draw_centered(self.game_over_reason, 430, 32)
        self.draw_centered(f'Final Score: {self.player.points}', 540, 40)
        self.draw_centered(f'Player:  {self.player.player_name}', 620, 40)
        mode_label = self.mode.capitalize()
        wave_label = self.current_wave()['name']
        self.draw_centered(
            f'{mode_label}  |  Wave: {wave_label}  |  '
            f'Best combo: {self.best_combo}  |  Caught: {self.treats_caught}',
            680, 26,
        )
        if self.is_new_best:
            self.draw_centered('NEW BEST!', 725, 32)

    def drawing(self):
        self.draw_info()
        self.draw_info(f'Lives: {self.player.lives}', 10, 50, 30)
        wave = self.current_wave()
        self.draw_info(f"Wave: {wave['name']}", 10, 93, 30)
        if self.combo >= 2:
            self.draw_info(
                f'COMBO x{self.combo_mult()}', 10, 130, 34, (255, 215, 0)
            )
        self.draw_right(
            f'Player: {self.player.player_name}', self.wndw_w - 20, 10, 30
        )
        if self.muted:
            # Stack below the wave/combo readouts so they never overlap.
            muted_y = 170 if self.combo >= 2 else 130
            self.draw_info('MUTED (M)', 10, muted_y, 30)

    def run_timmer(self, dt=1.0):
        """Advance the wave clock + count the timer down.

        dt is in 60-FPS frames (1.0 ~= 1/60s); wave/elapsed bookkeeping
        runs in real seconds so waves stay dt-correct at any frame rate."""
        self.elapsed += dt / 60.0
        self._update_wave()
        if self.mode == 'endless':
            return float('inf')  # no timer expiry in endless
        if self.timer > 0:
            self.timer -= dt / 60
            if self.timer < 0:
                self.timer = 0
            return self.timer
        else:
            return 0

    def toggle_pause(self):
        """Flip the pause flag; the run_game loop renders the overlay."""
        self.paused = not self.paused
        return self.paused

    def toggle_mute(self):
        """Flip mute; silences music mixer, HUD shows MUTED indicator."""
        self.muted = not self.muted
        try:
            if self.muted:
                self.game.mixer.music.set_volume(0.0)
            else:
                self.game.mixer.music.set_volume(
                    volume_to_mixer(self.settings.get('volume', 7))
                )
        except pygame.error as e:
            print(f'[warn] mute toggle failed: {e}')
        return self.muted

    def draw_pause_overlay(self):
        cx = self.wndw_w // 2
        cy = self.wndw_h // 2
        overlay = self.game.Surface((self.wndw_w, self.wndw_h))
        overlay.set_alpha(150)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        self.draw_centered('* PAUSED *', cy - 20, 72)
        self.draw_centered('Press P to resume   ESC: quit to menu', cy + 60, 28)
        # keep player name visible under overlay for context
        _ = cx

    def game_over_screen(self):
        self.screen.fill((0, 0, 0))

    # --- Phase 1 SFX: distinct event -> file mapping, each on its own
    # channel so catches/combos/rotten never cut each other off. Reuses
    # only the bundled static/audio/*.mp3. Everything guarded so a
    # headless/dummy mixer can never break gameplay.
    SFX_FILES = {
        'eat': 'static/audio/cat_eat.mp3',  # normal catch
        'golden': 'static/audio/cat_eat.mp3',  # golden catch, own channel
        'rotten': 'static/audio/cat_go.mp3',  # rotten eat
        'combo': 'static/audio/cat_running.mp3',  # combo-up fanfare
        'gameover': 'static/audio/cat_go.mp3',  # game over, own channel
    }

    def _init_sfx(self):
        try:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
            except pygame.error as e:
                print(f'[warn] mixer init failed (no audio device?): {e}')
                return
            for i, (name, path) in enumerate(self.SFX_FILES.items()):
                try:
                    snd = pygame.mixer.Sound(path)
                    if name == 'golden':
                        snd.set_volume(1.0)  # golden sits above the mix
                    self._sfx[name] = snd
                    try:
                        self._sfx_channels[name] = pygame.mixer.Channel(i)
                    except pygame.error:
                        pass  # channels unavailable — fall back to Sound.play
                except pygame.error as e:
                    print(f'[warn] cannot load {path}: {e}')
        except Exception as e:  # noqa: BLE001 — audio must never break the game
            print(f'[warn] sfx disabled: {e}')

    def _play_sfx(self, name):
        """Play one SFX on its dedicated channel; no-op if unavailable."""
        try:
            snd = self._sfx.get(name)
            if snd is None:
                return
            ch = self._sfx_channels.get(name)
            if ch is not None:
                ch.play(snd)
            else:
                snd.play()
        except pygame.error:
            pass

    def _play_sound(self, path):
        # Legacy music-channel playback, kept as a guarded fallback.
        try:
            self.game.mixer.music.load(path)
            self.game.mixer.music.play(0)
        except pygame.error as e:
            print(f'[warn] cannot play {path}: {e}')

    def eatSound(self):
        self._play_sfx('eat')

    def goldenSound(self):
        # Distinct path from normal catch (own channel + full volume).
        # True resampling/pitch-up would need a new asset — out of scope —
        # so golden gets its own channel, max volume, and the gold flash.
        self._play_sfx('golden')

    def comboSound(self):
        self._play_sfx('combo')

    def badSound(self):
        self._play_sfx('rotten')

    def goSound(self):
        self._play_sfx('gameover')

    # --- Phase 1 combo: consecutive good catches build x2/x3/x4 ---
    COMBO_CAP = 4
    BURST_COLORS = {
        'good': (255, 220, 130),
        'golden': (255, 215, 0),
        'bad': (120, 200, 120),
        'powerup': (255, 200, 60),
    }

    def combo_mult(self):
        """Score multiplier from the current combo (x1/x2/x3/x4, capped)."""
        return max(1, min(self.combo, self.COMBO_CAP))

    def reset_combo(self):
        self.combo = 0

    def reset_game(self, mode=None):
        if mode in MODES:
            self.mode = mode
        self.timer = float(self.init_timer)
        self.apply_difficulty()
        self.paused = False
        self.player.reset()
        self.player.lives = self.start_lives
        self.combo = 0
        self.is_new_best = False
        self.score_value = 0
        # Wave-0 base shifted by difficulty (Easy 4.0 / Normal 5.0 /
        # Hard 7.0); later waves re-apply via apply_wave().
        self.base_fall_speed = float(WAVES[0]['base_speed']) + \
            self.difficulty_speed_bonus()
        self.fall_speed = self.base_fall_speed
        self.game_over_reason = ''
        self.wave_index = 0
        self.elapsed = 0.0
        self.treats_caught = 0
        self.best_combo = 0
        self.is_new_best = False
        self.combo = 0
        self.bursts = []
        self.juice = JuiceState()
        self.cat.pos_x = self.wndw_w // 2
        self.cat.pos_y = self.wndw_h - 130
        self.magnet_timer = 0.0
        self.shield_timer = 0.0
        self.slowmo_timer = 0.0
        self.frenzy_timer = 0.0
        self.cat.lean = 0.0
        while len(self.treats) > START_TREAT_COUNT:
            self.treats.pop()
        while len(self.treats) < START_TREAT_COUNT:
            self.treats.append(TreatObj(self.wndw_w, self.wndw_h))
        self.treat = self.treats[0]
        for t in self.treats:
            t.set_bounds(self.wndw_w, self.wndw_h)
            t.pool = WAVES[0]['skins']
            t.vy = self.fall_speed

    # -- Phase 2: depth ---------------------------------------------

    def desired_treat_count(self):
        """Concurrent treats scale 3-5 with score (THE intensity fix).

        Difficulty shifts the band: Easy runs one fewer treat, Hard one
        more, clamped to at least 1."""
        count = START_TREAT_COUNT
        for step in TREAT_COUNT_STEPS:
            if self.player.points >= step:
                count += 1
        count += self.difficulty_treat_bonus()
        return max(1, min(count, MAX_TREAT_COUNT + 1))

    def ensure_treats(self):
        """Grow the treat list toward the desired count (never shrinks)."""
        while len(self.treats) < self.desired_treat_count():
            t = TreatObj(self.wndw_w, self.wndw_h)
            t.pool = self.current_wave()['skins']  # wave mix for late adds
            t.vy = self.fall_speed
            t.set_treat_pic()
            # Fair spawn: keep a min x-distance from siblings.
            t.rand_move(others=self.treats, min_dist=MIN_SPAWN_DISTANCE)
            t.vy = self.fall_speed
            self.treats.append(t)
        self.treat = self.treats[0]

    def tick_power_timers(self, dt=1 / 60):
        for attr in (
            'magnet_timer', 'shield_timer', 'slowmo_timer', 'frenzy_timer'
        ):
            val = getattr(self, attr) - dt
            setattr(self, attr, max(0.0, val))

    @property
    def magnet_active(self):
        return self.magnet_timer > 0

    @property
    def shield_active(self):
        return self.shield_timer > 0

    @property
    def slowmo_active(self):
        return self.slowmo_timer > 0

    @property
    def frenzy_active(self):
        return self.frenzy_timer > 0

    def speed_scale(self):
        return 0.5 if self.slowmo_active else 1.0

    def score_multiplier(self):
        return 2 if self.frenzy_active else 1

    def activate_powerup(self, power):
        if power == 'magnet':
            self.magnet_timer = MAGNET_DURATION
        elif power == 'shield':
            self.shield_timer = SHIELD_DURATION
        elif power == 'slowmo':
            self.slowmo_timer = SLOWMO_DURATION
        elif power == 'frenzy':
            self.frenzy_timer = FRENZY_DURATION

    def handle_near_miss(self, treat):
        """+1 when a rotten treat falls past within ~50px, untouched."""
        if (
            treat.last_miss_kind == 'bad'
            and not treat.last_miss_touched
            and treat.last_miss_x is not None
            and abs(treat.last_miss_x - self.cat.pos_x) <= NEAR_MISS_THRESHOLD
        ):
            self.player.add_points(NEAR_MISS_POINTS)
            self.score_value = self.player.points
            return True
        return False

    def end_game(self, reason):
        self.game_running = False
        self.game_over_reason = reason
        # Celebration flag must be computed BEFORE the scoreboard update.
        self.is_new_best = is_new_best(
            self.db_conn, self.player.player_name, self.player.points
        )
        try:
            set_stat_max(self.db_conn, 'best_combo', self.combo)
        except Exception:
            pass
        self.write_scoreboard(self.player.player_name, self.player.points)
        self.is_new_best = self.record_result(
            self.player.player_name,
            self.player.points,
            self.best_combo,
            self.treats_caught,
        )
        self.game_over()

    def show_scoreboard(self):
        cx = self.wndw_w // 2
        showing_score = True
        while showing_score and self.app_running:
            self.screen.fill((255, 124, 100))
            self.draw_info(' *** SCOREBOARD *** ', cx - 170, 200, 36)

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    showing_score = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        showing_score = False

            player_details = self.read_scoreboard()
            self.draw_info('Player -- Score', cx - 140, 280, 30)

            x, y = cx - 140, 330
            for p, s in player_details:
                self.draw_info(f'{p}     --      {s}', x, y, 30)
                y += 45

            y += 20
            self.draw_info('Bests: name  score  combo  caught', x, y, 26)
            y += 40
            for name, best, combo, caught in self.read_bests():
                self.draw_info(
                    f'{name}  {best}  x{combo}  {caught}', x, y, 26
                )
                y += 36

            self.game.display.update()
            self.clock.tick(60)

    def change_player_name(self):
        """
        new player name screen
        :return: player name
        """
        cx = self.wndw_w // 2
        inserting_new_name = True
        new_name = ''
        while inserting_new_name and self.app_running:
            self.screen.fill((255, 124, 100))
            self.draw_info('Insert new player name: ', cx - 260, 400, 36)

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    inserting_new_name = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        new_name = new_name[:-1]
                    elif event.key == pygame.K_RETURN:
                        if new_name.strip():
                            self.player.player_name = new_name.strip()[:4].upper()
                        inserting_new_name = False
                    elif event.key == pygame.K_ESCAPE:
                        inserting_new_name = False
                    else:
                        new_name += event.unicode

            self.draw_info(f'{new_name}', cx - 260, 460, 36)
            self.game.display.update()

    def game_start_screen(self):
        """
        represents the start screen where user can select START/Change Player Name/SCOREBOARD
        :return: na
        """
        cx = self.wndw_w // 2
        rows = [380, 450, 520, 590, 660, 730, 800]
        items = [
            'START GAME',
            f'MODE: {self.mode.upper()}',
            'PLAYER NAME',
            'SCOREBOARD',
            'STATS',
            'SKINS',
            'SETTINGS',
        ]
        sel = 0
        fs = True
        while fs and self.app_running:
            self.screen.fill((60, 60, 60))

            items[1] = f'MODE: {self.mode.upper()}'
            self.draw_centered('* Welcome To Petunia Game *', 180, 64)
            dif = self.settings.get('difficulty', 'Normal')
            lives = difficulty_preset(dif)['lives']
            self.draw_centered(
                f'Catch treats, dodge the rotten ones!  {lives} lives ({dif}).',
                250, 28,
            )
            for i, item in enumerate(items):
                self.draw_info(f'  {item} ', cx - 160, rows[i], 34)
            self.menu_cursor.pos_x = cx - 230
            self.menu_cursor.pos_y = rows[sel]
            self.draw_cursor('>>')

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    fs = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        sel = (sel + 1) % len(rows)

                    if event.key == pygame.K_UP:
                        sel = (sel - 1) % len(rows)

                    if event.key == pygame.K_RETURN:
                        if sel == 0:
                            fs = False
                            self.game_running = True
                            self.run_game()
                        elif sel == 1:
                            self.mode = (
                                'endless' if self.mode == 'classic' else 'classic'
                            )
                        elif sel == 2:
                            self.change_player_name()
                        elif sel == 3:
                            self.show_scoreboard()
                        elif sel == 4:
                            self.show_stats()
                        elif sel == 5:
                            self.show_skins()
                        elif sel == 6:
                            self.show_settings()

            self.game.display.update()
            self.clock.tick(60)

    def show_stats(self):
        """Lifetime stats screen (new ``stats`` DB table)."""
        showing = True
        while showing and self.app_running:
            self.screen.fill((70, 90, 140))
            cx = self.wndw_w // 2
            self.draw_info(' *** STATS *** ', cx - 150, 200, 40)
            try:
                stats = get_stats(self.db_conn)
            except Exception:
                stats = dict.fromkeys(STAT_KEYS, 0)
            lines = [
                f"Treats caught (all time): {stats['lifetime_treats']}",
                f"Rotten treats dodged:     {stats['rottens_dodged']}",
                f"Best combo:               {stats['best_combo']}",
            ]
            y = 320
            for line in lines:
                self.draw_info(line, cx - 330, y, 30)
                y += 60
            self.draw_centered('ESC: back', 640, 26)
            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    showing = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        showing = False
            self.game.display.update()
            self.clock.tick(60)

    def show_skins(self):
        """Unlockable cat skins, milestones at 50/150 lifetime treats."""
        showing = True
        sel_idx = 0
        while showing and self.app_running:
            self.screen.fill((90, 60, 110))
            cx = self.wndw_w // 2
            self.draw_info(' *** CAT SKINS *** ', cx - 180, 160, 40)
            try:
                lifetime = get_stats(self.db_conn)['lifetime_treats']
            except Exception:
                lifetime = 0
            unlocked = {s['id'] for s in unlocked_skins(lifetime)}
            self.draw_info(
                f'Lifetime treats: {lifetime}', cx - 180, 230, 28
            )
            y = 300
            from objects.meta import CAT_SKINS
            for i, skin in enumerate(CAT_SKINS):
                mark = '>>' if i == sel_idx else '  '
                if skin['id'] in unlocked:
                    cur = '  [current]' if skin['id'] == self.current_skin['id'] else ''
                    label = f"{mark} {skin['name']}{cur}"
                else:
                    label = f"{mark} ??? (unlock at {skin['treats']} treats)"
                self.draw_info(label, cx - 330, y, 30)
                y += 55
            self.draw_centered('UP/DOWN: browse  ENTER: wear  ESC: back', 700, 26)
            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    showing = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        showing = False
                    elif event.key == pygame.K_DOWN:
                        sel_idx = (sel_idx + 1) % len(CAT_SKINS)
                    elif event.key == pygame.K_UP:
                        sel_idx = (sel_idx - 1) % len(CAT_SKINS)
                    elif event.key == pygame.K_RETURN:
                        pick = CAT_SKINS[sel_idx]
                        if pick['id'] in unlocked:
                            self.current_skin = pick
                            self.settings['skin'] = pick['id']
                            save_settings(BASE_DIR, self.settings)
            self.game.display.update()
            self.clock.tick(60)

    def show_settings(self):
        """Settings screen: volume 0-10, window size, difficulty."""
        showing = True
        rows = ['volume', 'resolution', 'difficulty']
        sel = 0
        while showing and self.app_running:
            self.screen.fill((40, 80, 80))
            cx = self.wndw_w // 2
            self.draw_info(' *** SETTINGS *** ', cx - 170, 160, 40)
            vol = self.settings.get('volume', 7)
            res = self.settings.get('resolution', '1080p')
            dif = self.settings.get('difficulty', 'Normal')
            w, h = RESOLUTIONS.get(res, (1920, 1080))
            values = [f'Volume: {vol}/10', f'Window: {w}x{h}', f'Difficulty: {dif}']
            y = 300
            for i, val in enumerate(values):
                mark = '>>' if i == sel else '  '
                self.draw_info(f'{mark} {val}', cx - 260, y, 32)
                y += 60
            self.draw_centered('UP/DOWN: pick  LEFT/RIGHT: change  ESC: back', 640, 26)
            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    showing = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        showing = False
                    elif event.key == pygame.K_DOWN:
                        sel = (sel + 1) % len(rows)
                    elif event.key == pygame.K_UP:
                        sel = (sel - 1) % len(rows)
                    elif rows[sel] == 'volume':
                        if event.key == pygame.K_LEFT:
                            self.settings['volume'] = max(0, vol - 1)
                            self.apply_volume()
                        elif event.key == pygame.K_RIGHT:
                            self.settings['volume'] = min(10, vol + 1)
                            self.apply_volume()
                    elif rows[sel] == 'resolution':
                        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                            self.settings['resolution'] = (
                                '720p' if res == '1080p' else '1080p'
                            )
                            self.apply_resolution()
                    elif rows[sel] == 'difficulty':
                        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                            from objects.meta import DIFFICULTIES
                            idx = DIFFICULTIES.index(dif) \
                                if dif in DIFFICULTIES else 1
                            step = 1 if event.key == pygame.K_RIGHT else -1
                            self.settings['difficulty'] = DIFFICULTIES[
                                (idx + step) % len(DIFFICULTIES)
                            ]
                            self.apply_difficulty()
            save_settings(BASE_DIR, self.settings)
            self.game.display.update()
            self.clock.tick(60)

    def pause_menu(self):
        """Pause overlay: resume / settings / quit to menu.

        Returns 'resume' or 'quit'. Settings opens the settings screen
        and drops back into the pause menu."""
        items = ['RESUME', 'SETTINGS', 'QUIT TO MENU']
        sel = 0
        cx = self.wndw_w // 2
        paused = True
        choice = 'resume'
        while paused and self.app_running:
            self.screen.fill((30, 30, 40))
            self.draw_centered('* PAUSED *', 300, 64)
            y = 450
            for i, item in enumerate(items):
                mark = '>>' if i == sel else '  '
                self.draw_info(f'{mark} {item}', cx - 200, y, 34)
                y += 70
            self.draw_centered('UP/DOWN + ENTER   (P: resume)', 700, 26)
            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    paused = False
                    choice = 'quit'
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        sel = (sel + 1) % len(items)
                    elif event.key == pygame.K_UP:
                        sel = (sel - 1) % len(items)
                    elif event.key in (pygame.K_p, pygame.K_ESCAPE):
                        paused = False
                        choice = 'resume'
                    elif event.key == pygame.K_RETURN:
                        if sel == 0:
                            paused = False
                            choice = 'resume'
                        elif sel == 1:
                            self.show_settings()
                        elif sel == 2:
                            paused = False
                            choice = 'quit'
            self.game.display.update()
            self.clock.tick(60)
        return choice

    def game_over(self):
        """
        screen used when the game is done - timer done or lives lost;
        :return: na
        """

        self.goSound()
        if self.is_new_best:
            # 'New best!' fanfare: celebratory eat jingle over game-over.
            self.eatSound()
        go = True
        while go and self.app_running:
            self.game.display.update()
            self.screen.fill((60, 60, 60))
            self.draw_game_over()
            self.draw_centered('SPACE: play again   ESC: menu', 760, 26)

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    go = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        go = False
                        self.game_running = True
                        self.run_game()
                        return
                    if event.key == pygame.K_ESCAPE:
                        go = False

            self.clock.tick(60)

    def _bump_catch_stats(self):
        """Phase 4 lifetime stats for a good/power-up catch."""
        try:
            bump_stat(self.db_conn, 'lifetime_treats', 1)
            set_stat_max(self.db_conn, 'best_combo', self.combo)
        except Exception:
            pass

    def handle_eat(self, treat=None):
        """Score (or lose a life for) the treat touching the cat.

        Phase 1 juice (combo / bursts / shake / flash) combined with
        Phase 2 depth (power-ups, shield absorb, frenzy doubling) and
        Phase 4 lifetime stats. ``treat`` defaults to the
        backwards-compat alias ``self.treat`` (``self.treats[0]``); pass
        an explicit treat for multi-treat eats.
        """
        if treat is None:
            treat = self.treat
        cx, cy = treat.pos_x, treat.pos_y
        treat.touched = True
        frenzy = self.score_multiplier()
        if treat.kind == 'powerup':
            self.eatSound()
            self.activate_powerup(treat.power)
            self.combo += 1  # power-up keeps the streak alive
            self.best_combo = max(self.best_combo, self.combo)
            self.treats_caught += 1
            self._bump_catch_stats()
            if self.combo_mult() >= 2:
                self.comboSound()  # combo-up fanfare on top of the catch
            self.player.add_points(1 * self.combo_mult() * frenzy)
            self.bursts.append(
                ParticleBurst(cx, cy, self.BURST_COLORS['powerup'])
            )
        elif treat.kind == 'bad':
            if self.shield_active:
                self.eatSound()  # shield absorbs the rotten treat
                self.bursts.append(
                    ParticleBurst(cx, cy, self.BURST_COLORS['bad'], count=6)
                )
            else:
                self.badSound()
                self.player.lose_life()
                self.reset_combo()  # rotten resets the combo
                self.juice.shake(dur=0.35, mag=14)  # rotten: shake ...
                self.juice.flash((255, 40, 40), dur=0.25)  # ... + red flash
                self.bursts.append(
                    ParticleBurst(cx, cy, self.BURST_COLORS['bad'], count=10)
                )
        else:
            self.combo += 1  # consecutive good catch builds the combo
            self.best_combo = max(self.best_combo, self.combo)
            self.treats_caught += 1
            self._bump_catch_stats()
            mult = self.combo_mult() * frenzy
            if treat.kind == 'golden':
                self.goldenSound()  # distinct path from normal catch
                self.juice.flash((255, 215, 0), dur=0.3)  # golden flash
            else:
                self.eatSound()
            if self.combo_mult() >= 2:
                self.comboSound()  # combo-up fanfare on top of the catch
            self.player.add_points(treat.points * mult)
            self.bursts.append(
                ParticleBurst(cx, cy, self.BURST_COLORS[treat.kind])
            )
            # treats fall faster as you score — gentle difficulty ramp
            self.fall_speed = min(self.fall_speed + 0.15, 12)
            for t in self.treats:
                t.vy = self.fall_speed
        self.score_value = self.player.points
        treat.rand_move(others=self.treats, min_dist=MIN_SPAWN_DISTANCE)
        treat.vy = self.fall_speed
        self.ensure_treats()

    def handle_miss(self, missed_kind):
        """A treat fell off-screen untouched. Rottens dodged count up;
        any miss breaks the combo streak."""
        self.combo = 0
        if missed_kind == 'bad':
            try:
                bump_stat(self.db_conn, 'rottens_dodged', 1)
            except Exception:
                pass

    def run_game(self):
        """
        main screen; game itself — treats drop from the sky;
        :return: na
        """

        self.reset_game()
        self.cat.set_graph(self.current_skin)
        for t in self.treats:
            t.set_treat_pic()
        # Fair opening spread: no overlapping spawns.
        for i, t in enumerate(self.treats):
            t.rand_move(
                others=self.treats[:i], min_dist=MIN_SPAWN_DISTANCE
            )
            t.vy = self.fall_speed
        self.paused = False

        while self.game_running and self.app_running:
            # Delta time in 60-FPS frames: dt=1.0 at 60 FPS, 2.0 at 30 FPS.
            ms = self.clock.tick(60)
            dt = ms / 16.6667 if ms > 0 else 1.0
            dt = min(dt, 3.0)  # clamp tab-out spikes

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    self.game_running = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        # Phase 4 pause menu (resume / settings / quit)
                        # works in both classic and endless/wave runs.
                        if self.pause_menu() == 'quit':
                            self.game_running = False
                            return
                    elif event.key == pygame.K_m:
                        self.toggle_mute()
                    elif event.key == pygame.K_ESCAPE:
                        self.game_running = False

            if self.paused:
                self.draw_pause_overlay()
                self.game.display.update()
                continue

            tmr = self.run_timmer(dt)
            self.tick_power_timers(dt / 60.0)  # power timers run in seconds
            now_s = self.game.time.get_ticks() / 1000.0
            self.game.display.update()
            self.screen.fill(self.current_wave()['bg'])
            ox, oy = self.juice.offset()  # rotten-eat screen shake
            self.screen.blit(
                self.cat.catimg, self.cat.catrect.move(ox, oy)
            )
            for t in self.treats:
                self.screen.blit(t.treatimg, t.treatrect.move(ox, oy))
            for burst in self.bursts:
                burst.draw(self.screen)
            self.juice.draw_flash(self.screen)
            self.drawing()

            if self.mode == 'endless':
                mins, secs = divmod(int(self.elapsed), 60)
                self.draw_right(
                    f'{mins}:{secs:02d}  W{self.wave_index + 1}',
                    self.wndw_w - 20, 50, 30,
                )
            else:
                self.draw_right(
                    f'Time: {int(self.timer)}', self.wndw_w - 20, 50, 30
                )
            self.draw_centered('P: pause   M: mute', 40, 22)

            for t in list(self.treats):
                # Magnet: good treats drift toward the cat (dt-scaled).
                if self.magnet_active and t.kind in ('good', 'golden'):
                    if t.pos_x < self.cat.pos_x:
                        t.pos_x = min(t.pos_x + MAGNET_PULL * dt,
                                      self.cat.pos_x)
                    elif t.pos_x > self.cat.pos_x:
                        t.pos_x = max(t.pos_x - MAGNET_PULL * dt,
                                      self.cat.pos_x)
                # treats drop from the sky (dt-scaled, slowmo halves falls)
                missed = t.update(dt, speed_scale=self.speed_scale())
                if missed:
                    self.handle_near_miss(t)
                    if t.missed_kind in ('good', 'golden'):
                        self.reset_combo()  # missed good resets the combo
                    t.missed_kind = None  # rotten missed: no penalty
                t.pulse(now_s)  # squash & stretch while falling
                t.spawn()
            self.juice.update(dt)
            for burst in self.bursts:
                burst.update(dt)
            self.bursts = [b for b in self.bursts if not b.dead]
            self.cat.spawn()

            key_pressed = self.game.key.get_pressed()

            if key_pressed[pygame.K_ESCAPE]:
                self.game_running = False

            moving = 0
            if key_pressed[pygame.K_LEFT]:
                moving = -1
            elif key_pressed[pygame.K_RIGHT]:
                moving = 1
            self.cat.animate(now_s, moving)  # wag + lean (squash & stretch)

            step = self.velocity * dt
            if key_pressed[pygame.K_UP]:
                if self.cat.pos_y - self.cat.catbox_offset > self.velocity:
                    self.cat.pos_y -= step

            if key_pressed[pygame.K_DOWN]:
                if self.cat.pos_y < (self.wndw_h - self.cat.cat_H - self.velocity):
                    self.cat.pos_y += step

            if key_pressed[pygame.K_LEFT]:
                if self.cat.pos_x - self.cat.catbox_offset > self.velocity:
                    self.cat.pos_x -= step

            if key_pressed[pygame.K_RIGHT]:
                if self.cat.pos_x < (self.wndw_w - self.cat.cat_H - self.velocity):
                    self.cat.pos_x += step

            for t in list(self.treats):
                if self.cat.catrect.colliderect(t.treatrect):
                    self.handle_eat(t)
                    break

            if not self.player.is_alive():
                self.end_game('Out of lives!')
                return

            if self.mode == 'classic' and tmr == 0:
                self.end_game("Time's up!")
                return

            self.game.display.update()
