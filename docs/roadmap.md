# PyPetiGame Roadmap — Taking It to the Next Level

Written 2026-11-06. Goal: fix the core fun deficit (low intensity, no
progression — a playtest caught ~1 treat per 6 seconds) so the game offers
more interesting decisions per minute.

Inspirations: Atari's *Avalanche/Kaboom!* (the genre), *Vampire Survivors*
(escalation + variety), Vlambeer's "Juice It or Lose It" (game feel).

## Phase 0 — Foundation fixes (small PR, do first)

- [ ] Pause (`P`/overlay + resume) — currently no way to stop mid-run
- [ ] Mute toggle (`M`)
- [ ] Scoreboard stores best per player (currently overwrites best with latest)
- [ ] Delta-time movement (game assumes 60 FPS everywhere)
- [ ] Treat spawn fairness (no impossible rotten pairs once multi-treat lands)

## Phase 1 — Juice: make it *feel* good (1 PR, highest fun-per-effort)

No rule changes, all feel (the Vlambeer lesson):

- [ ] Catch particles (crumb bursts, 0.4s life)
- [ ] Squash & stretch (cat leans/squashes on move, treats pulse while falling)
- [ ] Combo system (consecutive good catches build ×2/×3/×4; miss or rotten resets)
- [ ] Screen shake + red flash on rotten eat; golden flash + higher tone on golden
- [ ] Cat animation (tail wag / lean — kill the static-photo look)
- [ ] Distinct SFX per event (normal/golden/rotten/combo-up/game-over)

## Phase 2 — Depth: more decisions per minute (1–2 PRs)

- [ ] Multiple concurrent treats (3–5, scaling) — THE structural intensity fix;
  requires treat list instead of single `TreatObj`
- [ ] Power-up treats: Magnet, Shield, Slow-mo, Frenzy (golden-only window)
- [ ] Rotten variety: fast rotten (2× fall), decoy (looks golden for 1s)
- [ ] Near-miss bonus (+1 when a rotten passes within ~50px untouched)

## Phase 3 — Progression: runs with chapters (1–2 PRs)

- [ ] 3 waves × 20s: Tea Time → Sugar Rush → Rotten Storm (speed/mix/palette shift)
- [ ] Wave-clear bonus: +1 life refill (up to 9)
- [ ] Endless mode (escalating score-chase) + classic timed mode on menu
- [ ] Persistent bests per player (best score, longest combo, treats caught)

## Phase 4 — Meta & polish (ongoing small PRs)

- [ ] Settings screen (volume, windowed, difficulty presets)
- [ ] Unlockable cat skins (milestones, asset swaps)
- [ ] Stats screen (lifetime treats, rottens dodged, best combo — new DB table)
- [ ] Pause menu, "new best!" game-over celebration

## Phase 5 — Distribution (local build only, no publishing)

- [ ] PyInstaller one-file build, run locally (`pyinstaller pypetigame.spec`)
- [ ] CI build check only (artifact upload for inspection, no releases)

## Explicitly out of scope

- No multiplayer (doubles complexity, halves polish)
- No engine change (pygame-ce is fine at this scope)
- No dynamic resolution scaling before the fun is proven (tuned for 1080p)

## Suggested order

**0 → 1 → 2** — each shippable alone; Phase 1's combo already transforms
the feel before any structural refactor.
