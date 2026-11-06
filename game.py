import os
import sqlite3
import sys

import pygame

from objects.cursor_obj import CursorObj
from objects.petun_obj import PetunaObj
from objects.player_obj import PlayerObj
from objects.treats_obj import TreatObj


def _base_dir():
    # PyInstaller one-file extracts bundled data to sys._MEIPASS at runtime.
    # Unfrozen: the directory containing this file (the game root).
    bundled = getattr(sys, '_MEIPASS', None)
    if bundled:
        return bundled
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()


def _user_data_dir():
    # Writable per-user dir for the frozen build (the bundle dir may be
    # read-only or ephemeral, so the SQLite scoreboard lives outside it).
    home = os.path.expanduser('~')
    if sys.platform == 'win32':
        root = os.environ.get('APPDATA', home)
        return os.path.join(root, 'PyPetiGame')
    if sys.platform == 'darwin':
        return os.path.join(home, 'Library', 'Application Support', 'PyPetiGame')
    xdg = os.environ.get('XDG_DATA_HOME', os.path.join(home, '.local', 'share'))
    return os.path.join(xdg, 'pypetigame')


def _default_db_path():
    if getattr(sys, 'frozen', False):
        data_dir = _user_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'scores_db')
    return os.path.join(BASE_DIR, 'scoreboard_db', 'scores_db')


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

        self.db_path = _default_db_path()
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
        self.treat.set_bounds(self.wndw_w, self.wndw_h)
        self.treat.vy = self.fall_speed

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

    def handle_eat(self):
        """Score (or lose a life for) the treat currently touching the cat."""
        if self.treat.kind == 'bad':
            self.badSound()
            self.player.lose_life()
        else:
            self.eatSound()
            self.player.add_points(self.treat.points)
            # treats fall faster as you score — gentle difficulty ramp
            self.fall_speed = min(self.fall_speed + 0.15, 12)
            self.treat.vy = self.fall_speed
        self.score_value = self.player.points
        self.treat.rand_move()
        self.treat.vy = self.fall_speed

    def run_game(self):
        """
        main screen; game itself — treats drop from the sky;
        :return: na
        """

        self.reset_game()
        self.cat.set_graph()
        self.treat.set_treat_pic()

        while self.game_running and self.app_running:

            tmr = self.run_timmer()
            self.game.display.update()
            self.screen.fill((52, 106, 107))
            self.screen.blit(self.cat.catimg, self.cat.catrect)
            self.screen.blit(self.treat.treatimg, self.treat.treatrect)
            self.drawing()

            self.draw_right(f'Time: {int(self.timer)}', self.wndw_w - 20, 50, 30)

            self.treat.update()  # treats drop from the sky
            self.treat.spawn()
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

            if self.cat.catrect.colliderect(self.treat.treatrect):
                self.handle_eat()

            if not self.player.is_alive():
                self.end_game('Out of lives!')
                return

            if tmr == 0:
                self.end_game("Time's up!")
                return

            self.game.display.update()
            self.clock.tick(60)
