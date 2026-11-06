# ADR — openclaw/falling-treats-lives · 2026-11-06T14:08:38Z

Gameplay upgrade: falling treats, rotten treats, lives, 1080p.

## Context

The revived game had treats spawning at random positions on a 500×500
window, no hazards, and the only fail state was the 60s timer. This PR
makes it an actual dodge-and-catch game on a modern 1080p window.

## Changes (this PR)

- **Treats drop from the sky**: `TreatObj` spawns at y=−40 with random x,
  falls `vy` px/frame (`update()`); falling off the bottom respawns
  silently — misses cost nothing.
- **Bad treats**: new `static/images/treats_bad.png` (rotten cookie + red X,
  generated with pygame, 120px source). Skin table is weighted
  (~3/7 good, ~2/7 golden, ~2/7 bad); outcome derives from `kind`/`points`
  via `PetunaGame.handle_eat()`.
- **Lives**: `PlayerObj.lives` (start 9), `lose_life()`, `is_alive()`,
  `reset()`. Bad treat → −1 life; 0 lives → `end_game('Out of lives!')`.
  Good/golden treats never touch lives. HUD shows `Lives: N` under Score.
- **Difficulty ramp**: fall speed 5 px/frame +0.15 per good eat, cap 12.
- **1080p default**: window 1920×1080; cat 140px, treats 90px, velocity 14;
  all hardcoded 500px bounds replaced with `wndw_w/h`; menu, scoreboard,
  name, and game-over screens recentered (`draw_centered()` helper);
  menu navigation is index-based instead of pixel-position matching.
- **Game-over reason**: `Time's up!` vs `Out of lives!` shown on the
  end screen.
- **Tests**: suite grows 10 → 14 (sky spawn bounds, falling/missed
  respawn, kind distribution incl. bad, good-eat scores + speeds up,
  bad-eat costs a life, last-life death, 1080p window). 14/14 green,
  `ruff check` clean.
- **Docs**: `README.md` (falling/bad/lives/1080p) and
  `docs/architecture.md` (§4/§5/§6/§7-adjacent HUD-loop-collision notes)
  updated; `screenshots/*_1080p.png` proofs (gameplay, game-over, menu).
- **ADR**: this file.

## Follow-up: funny font + alignment pass (same PR)

- **Inspection findings**: code requested `'comicsans'` via
  `pygame.font.SysFont`, but that font doesn't exist on most Linux
  systems — pygame silently fell back to its built-in default font, so
  text looked different on every machine. HUD right column
  (`Player:`/`Time:`) was blitted at a fixed x, so values changing width
  made the column jitter.
- **Fix**: bundled `static/fonts/LuckiestGuy-Regular.ttf`
  (SIL OFL 1.1, via Fontsource CDN) + cached `PetunaGame.font(size)`
  helper with SysFont fallback; all screens use it. New `draw_right()`
  pins `Player:`/`Time:` to the right margin. Menu/game-over titles
  bumped up (all-caps display face reads small otherwise).
- **Tests**: +1 (`test_funny_font_loads_and_renders` — file exists,
  cache works, width variance justifies right-alignment). 15/15 green.

## Alternatives considered

- Multiple simultaneous falling treats: rejected for this PR — single-treat
  loop keeps collision/scoring trivially correct; easy follow-up (treat list).
- Penalty for missing good treats: rejected — misses already cost time;
  only bad eats are punished, keeping the game friendly.
- Pixel-position menu matching kept: rejected — replaced with index-based
  selection, which survives the 1080p re-layout.

## Consequences

- Old 500×500 screenshots remain as history; new `_1080p.png` shots show
  the current layout.
- Cat/treat sizes, speeds, and menu coordinates are tuned for 1920×1080;
  smaller displays will letterbox/scale via the OS — no dynamic scaling yet.
- Scoreboard semantics unchanged (upsert by name, top 5).
