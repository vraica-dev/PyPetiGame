import os
import pygame

from objects.petun_obj import PetunaObj
from objects.treats_obj import TreatObj
from objects.player_obj import PlayerObj
from objects.cursor_obj import CursorObj
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class PetunaGame:
    def __init__(self):
        # Run all relative asset paths from the game root no matter
        # where the player launches the script from.
        os.chdir(BASE_DIR)

        self.game = pygame
        self.game_running = False
        self.app_running = True
        self.wndw_h = 500
        self.wndw_w = 500

        self.db_path = os.path.join(BASE_DIR, 'scoreboard_db', 'scores_db')
        self.db_conn = self.init_db()

        self.game.init()
        try:
            self.game.mixer.init()
        except pygame.error as e:
            print(f'[warn] mixer init failed (no audio device?): {e}')
        self.game.display.set_caption('Petunia Game')

        self.clock = self.game.time.Clock()
        self.screen = self.game.display.set_mode([self.wndw_h, self.wndw_w])

        self.cat = PetunaObj()
        self.treat = TreatObj()
        self.player = PlayerObj()
        self.menu_cursor = CursorObj()

        self.init_timer = 60
        self.timer = float(self.init_timer)

        self.velocity = 10
        self.score_value = 0

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

    def draw_info(self, text_line=None, x=None, y=None, font_size=25):
        font = self.game.font.SysFont('comicsans', font_size, 1)
        if text_line is None and x is None and y is None:
            render = font.render(f'Score: {self.score_value}', True, (255, 255, 255))
            self.screen.blit(render, (7, 7))
        else:
            render = font.render(text_line, True, (255, 255, 255))
            self.screen.blit(render, (x, y))

    def draw_cursor(self, txt):
        font = self.game.font.SysFont('comicsans', self.menu_cursor.font_size, 1)
        render_font = font.render(txt, True, (255, 255, 255))
        self.screen.blit(render_font, (self.menu_cursor.pos_x, self.menu_cursor.pos_y))

    def draw_game_over(self):
        font = self.game.font.SysFont('comicsans', 36, 1)
        render_go = font.render('* G A M E O V E R *', True, (255, 255, 255))
        render_player = font.render(f'Player:  {self.player.player_name}', True, (255, 255, 255))
        render_final_score = font.render(f'Final Score: {self.player.points}', True, (255, 255, 255))

        self.screen.blit(render_go, (110, 90))
        self.screen.blit(render_player, (160, 190))
        self.screen.blit(render_final_score, (140, 140))

    def drawing(self):
        self.draw_info()
        self.draw_info(f'Player: {self.player.player_name}', 320, 10)

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

    def goSound(self):
        self._play_sound('static/audio/cat_go.mp3')

    def reset_game(self):
        self.timer = float(self.init_timer)
        self.player.points = 0
        self.score_value = 0

    def show_scoreboard(self):
        showing_score = True
        while showing_score and self.app_running:
            self.screen.fill((255, 124, 100))
            self.draw_info(' *** SCOREBOARD *** ', 150, 100)

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    showing_score = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        showing_score = False

            player_details = self.read_scoreboard()
            self.draw_info('Player -- Score', 180, 140)

            x, y = 180, 180
            for p, s in player_details:
                self.draw_info(f'{p}     --      {s}', x, y)
                y += 30

            self.game.display.update()
            self.clock.tick(60)

    def change_player_name(self):
        """
        new player name screen
        :return: player name
        """
        inserting_new_name = True
        new_name = ''
        while inserting_new_name and self.app_running:
            self.screen.fill((255, 124, 100))
            self.draw_info('Insert new player name: ', 150, 150)

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

            self.draw_info(f'{new_name}', 150, 180)
            self.game.display.update()

    def game_start_screen(self):
        """
        represents the start screen where user can select START/Change Player Name/SCOREBOARD
        :return: na
        """
        fs = True
        while fs and self.app_running:
            self.screen.fill((60, 60, 60))

            self.draw_info(' * Welcome To Petunia Game * ', 40, 25, 35)
            self.draw_info(' ************************************* ', 40, 70, 35)
            self.draw_info('  START GAME ', 150, 120, 30)
            self.draw_info('  PLAYER NAME ', 145, 170, 30)
            self.draw_info('  SCOREBOARD ', 144, 220, 30)

            self.draw_cursor('>>')

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    fs = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        if self.menu_cursor.pos_y < 200:
                            self.menu_cursor.pos_y += 50

                    if event.key == pygame.K_UP:
                        if self.menu_cursor.pos_y > 120:
                            self.menu_cursor.pos_y -= 50

                    if event.key == pygame.K_RETURN:
                        if self.menu_cursor.pos_y == 120:
                            fs = False
                            self.game_running = True
                            self.run_game()

                        elif self.menu_cursor.pos_y == 170:
                            self.change_player_name()

                        elif self.menu_cursor.pos_y == 220:
                            self.show_scoreboard()

            self.game.display.update()
            self.clock.tick(60)

    def game_over(self):
        """
        screen used when the game is done - when the timer is done;
        :return: na
        """

        self.goSound()
        go = True
        while go and self.app_running:
            self.game.display.update()
            self.screen.fill((60, 60, 60))
            self.draw_game_over()
            self.draw_info('SPACE: play again   ESC: menu', 90, 260, 22)

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

    def run_game(self):
        """
        main screen; game itself;
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

            self.draw_info(f'Time: {str(int(self.timer))}', 390, 30)

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
                if self.cat.pos_y - self.cat.catbox_offset * 2 < (500 - self.cat.cat_H - self.velocity):
                    self.cat.pos_y += self.velocity

            if key_pressed[pygame.K_LEFT]:
                if self.cat.pos_x - self.cat.catbox_offset > self.velocity:
                    self.cat.pos_x -= 10

            if key_pressed[pygame.K_RIGHT]:
                if self.cat.pos_x - self.cat.catbox_offset * 2 < (500 - self.cat.cat_H - self.velocity):
                    self.cat.pos_x += 10

            if self.cat.catrect.colliderect(self.treat.treatrect):
                self.eatSound()
                if self.treat.selected_skin == 'treats_2.png':
                    self.player.add_special_points()
                    self.treat.rand_move()
                else:
                    self.player.add_point()
                    self.treat.rand_move()
                self.score_value = self.player.points

            if tmr == 0:
                self.game_running = False
                self.write_scoreboard(self.player.player_name, self.player.points)
                self.game_over()
                return

            self.game.display.update()
            self.clock.tick(60)
