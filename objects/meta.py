"""Phase 4 meta & polish: settings, cat skins, lifetime stats.

Additive module — the classic game loop is untouched. ``game.py`` calls
into these helpers for persistence and unlock rules so the logic stays
testable without a display.
"""

import json
import os

# Where player settings live (next to the game root, not in the DB, so a
# settings wipe never touches the scoreboard).
SETTINGS_FILENAME = 'settings.json'

RESOLUTIONS = {
    '720p': (1280, 720),
    '1080p': (1920, 1080),
}

DIFFICULTIES = ('Easy', 'Normal', 'Hard')

# Difficulty presets: starting lives + base treat fall speed (px/frame).
# Classic loop assumes 60 FPS, same as the rest of the game.
DIFFICULTY_PRESETS = {
    'Easy': {'lives': 12, 'fall_speed': 4.0},
    'Normal': {'lives': 9, 'fall_speed': 5.0},
    'Hard': {'lives': 6, 'fall_speed': 7.0},
}

DEFAULT_SETTINGS = {
    'volume': 7,  # 0-10, mapped to mixer 0.0-1.0
    'resolution': '1080p',  # '720p' (1280x720) or '1080p' (1920x1080)
    'difficulty': 'Normal',  # Easy / Normal / Hard
    'skin': 'classic',  # selected cat skin id
}

VOLUME_MIN = 0
VOLUME_MAX = 10

# Unlockable cat skins. ``treats`` is the lifetime-treats milestone that
# unlocks the skin; ``tint`` is an RGB multiply applied over cat.png
# (None = original colours) and ``scale`` resizes the sprite.
CAT_SKINS = [
    {
        'id': 'classic',
        'name': 'Classic Petunia',
        'treats': 0,
        'tint': None,
        'scale': 1.0,
    },
    {
        'id': 'honey',
        'name': 'Honey Tabby',
        'treats': 50,
        'tint': (255, 210, 140),
        'scale': 1.0,
    },
    {
        'id': 'midnight',
        'name': 'Midnight Hunter',
        'treats': 150,
        'tint': (150, 160, 255),
        'scale': 1.15,
    },
]

# Lifetime stat keys stored in the ``stats`` table (single-row key/value).
STAT_KEYS = ('lifetime_treats', 'rottens_dodged', 'best_combo')


def settings_path(base_dir):
    return os.path.join(base_dir, SETTINGS_FILENAME)


def load_settings(base_dir):
    """Return persisted settings merged over defaults (never raises)."""
    merged = dict(DEFAULT_SETTINGS)
    try:
        with open(settings_path(base_dir), encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return merged
    if not isinstance(data, dict):
        return merged
    if isinstance(data.get('volume'), int):
        merged['volume'] = max(VOLUME_MIN, min(VOLUME_MAX, data['volume']))
    if data.get('resolution') in RESOLUTIONS:
        merged['resolution'] = data['resolution']
    if data.get('difficulty') in DIFFICULTIES:
        merged['difficulty'] = data['difficulty']
    if isinstance(data.get('skin'), str) and any(
        s['id'] == data['skin'] for s in CAT_SKINS
    ):
        merged['skin'] = data['skin']
    return merged


def save_settings(base_dir, settings):
    """Persist settings to JSON. Returns True on success."""
    clean = dict(DEFAULT_SETTINGS)
    clean.update({k: v for k, v in settings.items() if k in clean})
    try:
        with open(settings_path(base_dir), 'w', encoding='utf-8') as fh:
            json.dump(clean, fh, indent=2)
        return True
    except OSError:
        return False


def volume_to_mixer(volume):
    """Map 0-10 volume to a 0.0-1.0 mixer level."""
    return max(0.0, min(1.0, volume / 10.0))


def difficulty_preset(name):
    return DIFFICULTY_PRESETS.get(name, DIFFICULTY_PRESETS['Normal'])


def unlocked_skins(lifetime_treats):
    """Return the skins unlocked at the given lifetime treat count."""
    return [s for s in CAT_SKINS if lifetime_treats >= s['treats']]


def skin_by_id(skin_id):
    for skin in CAT_SKINS:
        if skin['id'] == skin_id:
            return skin
    return CAT_SKINS[0]


def ensure_stats_table(conn):
    """Create the lifetime-stats table (additive; scores table untouched)."""
    conn.execute(
        'CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)'
    )
    for key in STAT_KEYS:
        conn.execute(
            'INSERT OR IGNORE INTO stats (key, value) VALUES (?, 0)', (key,)
        )
    conn.commit()


def get_stats(conn):
    ensure_stats_table(conn)
    cur = conn.cursor()
    cur.execute('SELECT key, value FROM stats')
    rows = dict(cur.fetchall())
    return {key: int(rows.get(key, 0)) for key in STAT_KEYS}


def bump_stat(conn, key, delta=1):
    ensure_stats_table(conn)
    conn.execute(
        'INSERT INTO stats (key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = value + ?',
        (key, delta, delta),
    )
    conn.commit()


def set_stat_max(conn, key, value):
    """Store value only if it beats the stored max (for best_combo)."""
    ensure_stats_table(conn)
    conn.execute(
        'INSERT INTO stats (key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = max(value, ?)',
        (key, value, value),
    )
    conn.commit()


def is_new_best(conn, player_name, score):
    """True when score beats the player's stored scoreboard best.

    A first-time player with no row counts as a new best when score > 0.
    """
    cur = conn.cursor()
    try:
        cur.execute('SELECT score FROM scores WHERE name = ?', (player_name,))
        row = cur.fetchone()
    except Exception:
        return False
    if row is None:
        return score > 0
    try:
        return score > int(row[0])
    except (TypeError, ValueError):
        return False
