import os
import sqlite3

import pygame

from objects.cursor_obj import CursorObj
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


class PetunaGame:
    def __init__(self):
        # Run all relative asset paths from the game root no matter
        # where the player launches the script from.
        os.chdir(BASE_DIR)

        self.game = pygame
        self.game_running = False
        self.app_running = True
        self.wndw_w = 1920
        self.wndw_h = 1080

        self.db_path = os.path.join(BASE_DIR, 'scoreboard_db', 'scores_db')
        self.db_conn = self.init_db()

        self.game.init()
        try:
            self.game.mixer.init()
        except pygame.error as e:
            print(f'[warn] mixer init failed (no audio device?): {e}')
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

        self.velocity = 14
        # Bundled funny font (Luckiest Guy, OFL 1.1). Falls back to a
        # system font if the file ever goes missing.
        self.font_path = os.path.join(
            BASE_DIR, 'static', 'fonts', 'LuckiestGuy-Regular.ttf'
        )
        self._fonts = {}
        self.base_fall_speed = 5
        self.fall_speed = self.base_fall_speed
        self.score_value = 0
        self.game_over_reason = ''

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'CREATE TABLE IF NOT EXISTS scores (name TEXT NOT NULL, score INTEGER)'
        )
        conn.commit()
        return conn

    def read_scoreboard(self):
        c = self.db_conn.cursor()
        view_str = "SELECT * FROM scores ORDER BY score DESC LIMIT 5 "
        c.execute(view_str)
        res = c.fetchall()
        return res

    def write_scoreboard(self, name_p, score_p):
        c = self.db_conn.cursor()
        update_str = "UPDATE scores SET score =? WHERE name =?"
        query_str = "SELECT * FROM scores WHERE name =?"
        sql_str = "INSERT INTO scores (name, score) VALUES (?, ?)"

        c.execute(query_str, (name_p,))
        result = c.fetchone()

        if result:
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

    def draw_info(self, text_line=None, x=None, y=None, font_size=25):
        font = self.font(font_size)
        if text_line is None and x is None and y is None:
            render = font.render(f'Score: {self.score_value}', True, (255, 255, 255))
            self.screen.blit(render, (7, 7))
        else:
            render = font.render(text_line, True, (255, 255, 255))
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

    def draw_game_over(self):
        self.draw_centered('* GAME OVER *', 350, 72)
        self.draw_centered(self.game_over_reason, 430, 32)
        self.draw_centered(f'Final Score: {self.player.points}', 540, 40)
        self.draw_centered(f'Player:  {self.player.player_name}', 620, 40)

    def drawing(self):
        self.draw_info()
        self.draw_info(f'Lives: {self.player.lives}', 10, 50, 30)
        self.draw_right(
            f'Player: {self.player.player_name}', self.wndw_w - 20, 10, 30
        )

    def run_timmer(self):
        if self.timer > 0:
            self.timer -= 1 / 60
            if self.timer < 0:
                self.timer = 0
            return self.timer
        else:
            return 0

    def game_over_screen(self):
        self.screen.fill((0, 0, 0))

    def _play_sound(self, path):
        try:
            self.game.mixer.music.load(path)
            self.game.mixer.music.play(0)
        except pygame.error as e:
            print(f'[warn] cannot play {path}: {e}')

    def eatSound(self):
        self._play_sound('static/audio/cat_eat.mp3')

    def badSound(self):
        self._play_sound('static/audio/cat_go.mp3')

    def goSound(self):
        self._play_sound('static/audio/cat_go.mp3')

    def reset_game(self):
        self.timer = float(self.init_timer)
        self.player.reset()
        self.score_value = 0
        self.fall_speed = self.base_fall_speed
        self.game_over_reason = ''
        self.cat.pos_x = self.wndw_w // 2
        self.cat.pos_y = self.wndw_h - 130
        self.magnet_timer = 0.0
        self.shield_timer = 0.0
        self.slowmo_timer = 0.0
        self.frenzy_timer = 0.0
        while len(self.treats) > START_TREAT_COUNT:
            self.treats.pop()
        while len(self.treats) < START_TREAT_COUNT:
            self.treats.append(TreatObj(self.wndw_w, self.wndw_h))
        self.treat = self.treats[0]
        for t in self.treats:
            t.set_bounds(self.wndw_w, self.wndw_h)
            t.vy = self.fall_speed

    # -- Phase 2: depth ---------------------------------------------

    def desired_treat_count(self):
        """Concurrent treats scale 3-5 with score (THE intensity fix)."""
        count = START_TREAT_COUNT
        for step in TREAT_COUNT_STEPS:
            if self.player.points >= step:
                count += 1
        return min(count, MAX_TREAT_COUNT)

    def ensure_treats(self):
        """Grow the treat list toward the desired count (never shrinks)."""
        while len(self.treats) < self.desired_treat_count():
            t = TreatObj(self.wndw_w, self.wndw_h)
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
        self.write_scoreboard(self.player.player_name, self.player.points)
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
        rows = [430, 510, 590]
        items = ['START GAME', 'PLAYER NAME', 'SCOREBOARD']
        sel = 0
        fs = True
        while fs and self.app_running:
            self.screen.fill((60, 60, 60))

            self.draw_centered('* Welcome To Petunia Game *', 180, 64)
            self.draw_centered('Catch treats, dodge the rotten ones!  9 lives.', 250, 28)
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
                            self.change_player_name()
                        elif sel == 2:
                            self.show_scoreboard()

            self.game.display.update()
            self.clock.tick(60)

    def game_over(self):
        """
        screen used when the game is done - timer done or lives lost;
        :return: na
        """

        self.goSound()
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

    def handle_eat(self, treat=None):
        """Score (or lose a life for) the treat touching the cat."""
        if treat is None:
            treat = self.treat
        treat.touched = True
        if treat.kind == 'powerup':
            self.eatSound()
            self.activate_powerup(treat.power)
            self.player.add_points(1 * self.score_multiplier())
        elif treat.kind == 'bad':
            if self.shield_active:
                self.eatSound()  # shield absorbs the rotten treat
            else:
                self.badSound()
                self.player.lose_life()
        else:
            self.eatSound()
            self.player.add_points(treat.points * self.score_multiplier())
            # treats fall faster as you score — gentle difficulty ramp
            self.fall_speed = min(self.fall_speed + 0.15, 12)
            for t in self.treats:
                t.vy = self.fall_speed
        self.score_value = self.player.points
        treat.rand_move(others=self.treats, min_dist=MIN_SPAWN_DISTANCE)
        treat.vy = self.fall_speed
        self.ensure_treats()

    def run_game(self):
        """
        main screen; game itself — treats drop from the sky;
        :return: na
        """

        self.reset_game()
        self.cat.set_graph()
        for t in self.treats:
            t.set_treat_pic()
        # Fair opening spread: no overlapping spawns.
        for i, t in enumerate(self.treats):
            t.rand_move(
                others=self.treats[:i], min_dist=MIN_SPAWN_DISTANCE
            )
            t.vy = self.fall_speed

        while self.game_running and self.app_running:

            tmr = self.run_timmer()
            self.tick_power_timers()
            self.game.display.update()
            self.screen.fill((52, 106, 107))
            self.screen.blit(self.cat.catimg, self.cat.catrect)
            for t in self.treats:
                self.screen.blit(t.treatimg, t.treatrect)
            self.drawing()

            self.draw_right(f'Time: {int(self.timer)}', self.wndw_w - 20, 50, 30)

            for t in list(self.treats):
                # Magnet: good treats drift toward the cat.
                if self.magnet_active and t.kind in ('good', 'golden'):
                    if t.pos_x < self.cat.pos_x:
                        t.pos_x = min(t.pos_x + MAGNET_PULL, self.cat.pos_x)
                    elif t.pos_x > self.cat.pos_x:
                        t.pos_x = max(t.pos_x - MAGNET_PULL, self.cat.pos_x)
                missed = t.update(speed_scale=self.speed_scale())
                if missed:
                    self.handle_near_miss(t)
                t.spawn()
            self.cat.spawn()

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    self.game_running = False
                    self.app_running = False

            key_pressed = self.game.key.get_pressed()

            if key_pressed[pygame.K_ESCAPE]:
                self.game_running = False

            if key_pressed[pygame.K_UP]:
                if self.cat.pos_y - self.cat.catbox_offset > self.velocity:
                    self.cat.pos_y -= self.velocity

            if key_pressed[pygame.K_DOWN]:
                if self.cat.pos_y < (self.wndw_h - self.cat.cat_H - self.velocity):
                    self.cat.pos_y += self.velocity

            if key_pressed[pygame.K_LEFT]:
                if self.cat.pos_x - self.cat.catbox_offset > self.velocity:
                    self.cat.pos_x -= self.velocity

            if key_pressed[pygame.K_RIGHT]:
                if self.cat.pos_x < (self.wndw_w - self.cat.cat_H - self.velocity):
                    self.cat.pos_x += self.velocity

            for t in list(self.treats):
                if self.cat.catrect.colliderect(t.treatrect):
                    self.handle_eat(t)
                    break

            if not self.player.is_alive():
                self.end_game('Out of lives!')
                return

            if tmr == 0:
                self.end_game("Time's up!")
                return

            self.game.display.update()
            self.clock.tick(60)
