# ADR — openclaw/pypetigame-revival · 2026-10-23T14:52:50Z

Revival of the archived PyPetiGame (Python/pygame cat-and-treats game).
PR: revive the game so it launches, plays end-to-end, and persists scores.

## Context

Upstream `vraica-dev/pypetigame` was archived and did not run as-is:
menu crashed on QUIT, starting a match killed the app, the bonus treat never
registered, no dependency manifest, no run docs. Repo has since been
unarchived by the owner.

## Changes (this PR)

- **`game.py`** — core revival (~80-line net rework):
  - Fixed `NameError` (`go = 0`) on QUIT in the start screen.
  - Removed `pygame.quit()` from screen transitions (killed the app on START);
    single `quit()` at exit, flat return-based flow
    (`start → run_game → game_over → menu`).
  - Un-recursed menu/scoreboard/name screens; `game_running` + `app_running`
    flags drive all loops.
  - Timer initialized in `__init__`, framerate-independent (1/60s steps);
    match length 5s → 60s.
  - `score_value` reset per match; removed per-frame `print()` spam;
    ESC exits the match.
  - `init_db()` ensures `CREATE TABLE IF NOT EXISTS`; absolute DB path;
    `os.chdir(BASE_DIR)` so assets resolve from any launch cwd.
  - Audio optional (`mixer.init` / `_play_sound` guarded) for headless/CI.
  - Name entry: fixed `\r` appended on ENTER, empty input keeps old name.
  - Player HUD label moved to x=320 (was clipped).
- **`objects/treats_obj.py`** — `selected_skin` stores basename, so the
  golden-treat comparison matches (bonus was previously unreachable).
- **`objects/player_obj.py`** — golden treat +3 (was +1, same as normal).
- **`run_game.py`** — final `pygame.quit()` on exit.
- **New files** — `requirements.txt` (`pygame-ce>=2.5`, `pytest>=8`),
  `README.md` (run/controls/scoring), `docs/architecture.md` (full reference),
  `tests/` (10 pytest tests, all passing), `screenshots/*.png` (proofs),
  this ADR.

## Alternatives considered

- Plain `pygame` instead of `pygame-ce`: rejected — no Python 3.14 ARM wheel
  available in this environment; `pygame-ce` is API-compatible.
- Minimal crash-only fix vs full revival: chose revival (timer, scoring,
  audio fallback, docs, tests) since the game was unplayable, not just
  crashy. Match duration raised to 60s as 5s was not a real game.

## Consequences

- Game runs via `pip install -r requirements.txt && python3 run_game.py`.
- Bonus-treat gameplay now reachable; scoring changed (golden = 3 pts).
- Match length changed (5s → 60s) — affects existing scoreboard comparability.
- No asset changes; existing scoreboard rows preserved.
