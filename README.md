[![CI](https://github.com/vraica-dev/pypetigame/actions/workflows/ci.yml/badge.svg)](https://github.com/vraica-dev/pypetigame/actions/workflows/ci.yml)

First attempt of creating a game in Python using the PyGame framework.

Tech used:
  - Python 3.12 (pinned via `.python-version`)
  - pygame-ce
  - uv for packaging (`pyproject.toml` + `uv.lock`)
  - pytest + ruff (dev), enforced by CI on the local runner `vmi3706455`

Game logic:
  - catch the treats as they drop from the sky while the clock is still ticking
  - dodge the rotten treats (red X) — each one eaten costs a life; you have 9

## How to run

With [uv](https://docs.astral.sh/uv/) (recommended — pinned Python + locked deps):

```bash
uv sync
uv run python run_game.py
```

Or with plain pip:

```bash
pip install -r requirements.txt
python3 run_game.py
```

A display is required (or `xvfb-run` on headless Linux).
Audio is optional — the game runs muted if no audio device is present.

## Controls

Menu (UP/DOWN + ENTER):
  - START GAME — begin playing
  - PLAYER NAME — type a name (max 4 chars), ENTER to confirm, ESC to cancel
  - SCOREBOARD — top 5 scores, ESC to go back

In game (arrow keys move the cat):
  - UP / DOWN / LEFT / RIGHT — move
  - ESC — quit to menu

Game over:
  - SPACE — play again
  - ESC — back to menu

Scoring: normal treat = 1 pt, golden treat = 3 pts, rotten treat = -1 life.
Treats fall faster the more you eat. Game length: 60 seconds or until all
9 lives are lost — whichever comes first. Window: 1920x1080 (1080p).
Scores are saved in `scoreboard_db/scores_db` (SQLite).

## Development

```bash
uv sync --group dev   # install runtime + dev deps
uv run ruff check .   # lint
uv run pytest -q      # tests (10 tests in tests/)
```

Every push / PR to `master` runs the same two commands as CI
(`.github/workflows/ci.yml`) on the local runner.

## Distribution (local build only, no publishing)

One-file Linux binary via PyInstaller — build locally only. Nothing is
published: no GitHub Releases, no tags, no store uploads.
See `.github/workflows/build.yml` (manual `workflow_dispatch` + PR checks
that only upload a CI artifact for inspection).

```bash
uv sync --group packaging
uv run pyinstaller pypetigame.spec  # -> dist/pypetigame
```

The frozen build bundles `static/` (images, audio, font) and stores the
SQLite scoreboard per-user (`~/.local/share/pypetigame/` on Linux) since
the bundle dir isn't a safe place for writable data.

Release flow: none — local builds only, the game is not published
and has never been published.

Please consider this is not the final version. Multiple finetunnings are still necessary.
