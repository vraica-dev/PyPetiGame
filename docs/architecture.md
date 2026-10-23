# PyPetiGame — Architecture

Revived 2026-10-23 from the archived upstream
(`https://github.com/vraica-dev/PyPetiGame.git`, read-only).
Stack: Python 3 + pygame-ce (>= 2.5), SQLite (stdlib), no other dependencies.

## 1. Entry point & lifecycle

- `run_game.py` — creates `PetunaGame`, enters `game_start_screen()`,
  calls `pygame.quit()` once on exit.
- `game.py :: PetunaGame` owns the whole app: window, clock, DB handle,
  entities, and all screen loops.
- Screen flow (flat, return-based — no recursion):
  `game_start_screen()` → `run_game()` → `game_over()` → back to menu.
- Two flags drive every loop: `game_running` (in-match) and
  `app_running` (whole app; QUIT sets it `False` everywhere).
- Single `pygame.time.Clock`, 60 FPS (`clock.tick(60)`).

## 2. Module map

| File | Role |
|---|---|
| `run_game.py` | Bootstrap only |
| `game.py` | App controller: screens, HUD, timer, scoring, sounds, DB writes |
| `objects/petun_obj.py` | `PetunaObj` — the cat (player sprite): position, 60×60 scaled image, `spawn()` syncs rect |
| `objects/treats_obj.py` | `TreatObj` — the treat: random spawn, random skin, `rand_move()` respawn |
| `objects/player_obj.py` | `PlayerObj` — pure data: `player_name`, `points`, `add_point` / `add_special_points` / `reset_points` |
| `objects/cursor_obj.py` | `CursorObj` — menu cursor: `pos_x/pos_y` (120/170/220 rows), `font_size` |
| `scoreboard_db/scores_db` | SQLite file, table `scores(name TEXT, score INTEGER)` |
| `static/images/` | `cat.png`, `treats.png`, `treats_2.png` (golden/bonus) |
| `static/audio/` | `cat_eat.mp3`, `cat_go.mp3`, `cat_running.mp3` (unused) |
| `screenshots/` | Original JPGs + revival verification PNGs |

## 3. Working directory & paths

- `PetunaGame.__init__` does `os.chdir(BASE_DIR)` (dir of `game.py`),
  so all relative asset paths (`static/...`) and the DB path work
  regardless of launch cwd.
- `db_path` is absolute: `<BASE_DIR>/scoreboard_db/scores_db`.

## 4. Rendering

- Fixed 500×500 window (`set_mode([500, 500])`).
- Per frame: `screen.fill(...)` → blit cat + treat → HUD text → `display.update()`.
- All text via `pygame.font.SysFont('comicsans', size, bold)` with
  default-font fallback on systems without it.
- HUD: `Score: N` (top-left), `Player: NAME` (top-right, x=320),
  `Time: Ns` (below player) during matches.
- No sprite groups, no layers — direct blits each frame.

## 5. Game loop (`run_game`)

1. `reset_game()` — timer → 60.0s, points/score → 0.
2. `cat.set_graph()` / `treat.set_treat_pic()` load & scale images.
3. Each tick: `run_timmer()` (−1/60s, clamps at 0) → clear → blit →
   `treat.spawn()` + `cat.spawn()` (rect.center ← pos) → poll QUIT →
   read `key.get_pressed()` for movement → AABB collision check →
   score + `rand_move()` on eat → timer 0 → `write_scoreboard()` +
   `game_over()`.
4. Movement: 10 px/tick, clamped inside the window with
   `catbox_offset` margins. ESC exits the match.

## 6. Collision & scoring

- `catrect.colliderect(treatrect)` — cat 60×60, treat 40×40.
- Normal treat (`treats.png`): +1. Golden (`treats_2.png`): +3
  (`add_special_points`). Skin identity is the image basename
  (`selected_skin`), re-rolled randomly on every respawn.
- Treat respawn: uniform random x ∈ [1, 482], y ∈ [1, 388].

## 7. Timer

- `init_timer = 60`, `timer` float seconds, `run_timmer()` steps 1/60
  per frame and returns the remaining time (0 at expiry).
- Expiry ends the match exactly once: score persisted, then game-over screen.

## 8. Persistence (scoreboard)

- `init_db()` opens SQLite and `CREATE TABLE IF NOT EXISTS`.
- `read_scoreboard()` — top 5 by score DESC.
- `write_scoreboard(name, score)` — upsert by player name
  (UPDATE if name exists else INSERT), committed immediately.
- Screens: `show_scoreboard()` lists them; ESC returns.

## 9. Menu & input screens

- `game_start_screen()` — three rows (START 120 / NAME 170 / BOARD 220),
  UP/DOWN moves `menu_cursor.pos_y` ±50, ENTER dispatches.
- `change_player_name()` — keystroke accumulator; BACKSPACE trims,
  ENTER confirms (strip, upper, max 4 chars, keeps old name if empty),
  ESC cancels.
- `game_over()` — shows player + final score; SPACE replays
  (`run_game()`), ESC returns to menu.

## 10. Audio

- `mixer.init()` in try/except — game runs muted with a `[warn]` if no
  audio device (e.g. headless/CI).
- `_play_sound(path)` wraps `music.load + play` in try/except.
- `eatSound` on every eat, `goSound` on game over.
  `cat_running.mp3` ships but is not wired up.

## 11. Known limitations / tech debt

- Flat procedural screens inside one god class (`PetunaGame` ~350 lines);
  no separation of view/input/state.
- `event.get()` consumed in multiple places per frame; QUIT handled
  per-loop rather than centrally.
- Name length (4) and label x-position are hardcoded for the 500px window.
- No tests in-repo; verified via throwaway headless scripts (SDL dummy
  video/audio) — see revival notes, not committed.
- Font is best-effort (`comicsans` → default fallback on Linux).
- Scoreboard UPDATE overwrites a player's best with the latest score,
  even if lower.
