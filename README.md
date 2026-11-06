First attempt of creating a game in Python using the PyGame framework.

Tech used:
  - Python 3
  - PyGame (pygame-ce works too)

Game logic:
  - catch as many treats as you can while the clock is still ticking

## How to run

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

Scoring: normal treat = 1 pt, golden treat (`treats_2.png`) = 3 pts.
Game length: 60 seconds. Scores are saved in `scoreboard_db/scores_db` (SQLite).

Please consider this is not the final version. Multiple finetunnings are still necessary.
