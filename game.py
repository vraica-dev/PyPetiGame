import os
import sqlite3

import pygame

from objects.cursor_obj import CursorObj
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
from objects.treats_obj import TreatObj

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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
        self.apply_difficulty()
        self.score_value = 0
        self.game_over_reason = ''

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

    def apply_volume(self):
        try:
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
        if self.is_new_best:
            self.draw_centered('*** NEW BEST! ***', 300, 48)
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
        self.apply_difficulty()
        self.player.reset()
        self.player.lives = self.start_lives
        self.combo = 0
        self.is_new_best = False
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
        # Celebration flag must be computed BEFORE the scoreboard update.
        self.is_new_best = is_new_best(
            self.db_conn, self.player.player_name, self.player.points
        )
        try:
            set_stat_max(self.db_conn, 'best_combo', self.combo)
        except Exception:
            pass
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
        rows = [400, 470, 540, 610, 680, 750]
        items = [
            'START GAME', 'PLAYER NAME', 'SCOREBOARD',
            'STATS', 'SKINS', 'SETTINGS',
        ]
        sel = 0
        fs = True
        while fs and self.app_running:
            self.screen.fill((60, 60, 60))

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
                            self.change_player_name()
                        elif sel == 2:
                            self.show_scoreboard()
                        elif sel == 3:
                            self.show_stats()
                        elif sel == 4:
                            self.show_skins()
                        elif sel == 5:
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

    def handle_eat(self):
        """Score (or lose a life for) the treat currently touching the cat."""
        if self.treat.kind == 'bad':
            self.badSound()
            self.player.lose_life()
            self.combo = 0  # rotten breaks the streak
        else:
            self.eatSound()
            self.player.add_points(self.treat.points)
            self.combo += 1
            try:
                bump_stat(self.db_conn, 'lifetime_treats', 1)
                set_stat_max(self.db_conn, 'best_combo', self.combo)
            except Exception:
                pass
            # treats fall faster as you score — gentle difficulty ramp
            self.fall_speed = min(self.fall_speed + 0.15, 12)
            self.treat.vy = self.fall_speed
        self.score_value = self.player.points
        self.treat.rand_move()
        self.treat.vy = self.fall_speed

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
        self.treat.set_treat_pic()

        while self.game_running and self.app_running:

            tmr = self.run_timmer()
            self.game.display.update()
            self.screen.fill((52, 106, 107))
            self.screen.blit(self.cat.catimg, self.cat.catrect)
            self.screen.blit(self.treat.treatimg, self.treat.treatrect)
            self.drawing()

            self.draw_right(f'Time: {int(self.timer)}', self.wndw_w - 20, 50, 30)

            missed_kind = self.treat.kind
            if self.treat.update():  # treats drop from the sky
                self.handle_miss(missed_kind)
            self.treat.spawn()
            self.cat.spawn()

            for event in self.game.event.get():
                if event.type == pygame.QUIT:
                    self.game_running = False
                    self.app_running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        if self.pause_menu() == 'quit':
                            self.game_running = False
                            return

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
