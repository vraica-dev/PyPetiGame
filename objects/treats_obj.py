import math
import random

import pygame

TREAT_SIZE = 90

# Fair spawn band: keeps treats away from screen edges so the cat can
# always reach them. Multi-treat spacing (no impossible rotten pairs)
# is deferred to Phase 2 when concurrent treats land.
SPAWN_MARGIN = 80

# (image, kind, points). Bad treats cost a life instead of scoring.
SKINS = [
    ('static/images/treats.png', 'good', 1),
    ('static/images/treats.png', 'good', 1),
    ('static/images/treats.png', 'good', 1),
    ('static/images/treats_2.png', 'golden', 3),
    ('static/images/treats_2.png', 'golden', 3),
    ('static/images/treats_bad.png', 'bad', 0),
    ('static/images/treats_bad.png', 'bad', 0),
]

# Phase 2 — Depth: power-ups, rotten variety.
# Power-ups reuse the golden sprite (treats_2.png) with a tint overlay,
# so no new assets are needed. They only appear in place of a golden roll
# (the "golden-only window").
POWERUP_TYPES = ('magnet', 'shield', 'slowmo', 'frenzy')
GOLDEN_TO_POWERUP_CHANCE = 0.30
FAST_ROTTEN_CHANCE = 0.30
DECOY_CHANCE = 0.25
DECOY_DISGUISE_TIME = 1.0  # seconds the decoy looks golden before revealing

# Minimum horizontal distance between concurrent treats so the player is
# never served an impossible rotten pair.
MIN_SPAWN_DISTANCE = 150

# Tint per power-up, drawn over the reused golden sprite.
POWERUP_TINTS = {
    'magnet': (255, 80, 80),      # red-ish: attracts good treats
    'shield': (80, 160, 255),     # blue: blocks rotten damage
    'slowmo': (140, 220, 255),    # ice-blue: halves fall speed
    'frenzy': (255, 200, 60),     # orange-gold: 2x points
}


class TreatObj:
    """A treat that drops from the sky. Good = points, bad = lose a life.

    Phase 2 kinds: 'good', 'golden', 'bad', 'powerup'.
    Power-up treats carry ``power`` in POWERUP_TYPES and grant a timed
    effect instead of plain points. Rotten variety: ``fast`` rottens fall
    at 2x speed; ``decoy`` rottens wear the golden sprite for
    DECOY_DISGUISE_TIME seconds before revealing as bad.
    """

    def __init__(self, w=1920, h=1080):
        self.w = w
        self.h = h
        self.pos_x = self._fair_x(w)
        self.pos_y = -40  # start above the screen, falls in

        self.vy = 5  # fall speed, px per 60-FPS frame; raised as you score

        self.pool = None  # optional skin pool (per-wave mix); None = SKINS

        self.selected_skin = None
        self.kind = 'good'
        self.points = 1

        # Phase 2 state
        self.power = None       # None or one of POWERUP_TYPES
        self.fast = False       # fast rotten: 2x fall speed
        self.decoy = False      # decoy rotten: disguised as golden first
        self.disguised = False  # True while the decoy still looks golden
        self.decoy_timer = 0.0  # seconds of disguise remaining
        self.touched = False    # True once the cat has collided with it

        # Snapshot of the treat that just fell off-screen (update() respawns
        # immediately, so the game reads these for the near-miss bonus).
        self.last_miss_x = None
        self.last_miss_kind = None
        self.last_miss_touched = False

        self.treatimg = None
        self.treatrect = None
        self.base_img = None  # untransformed sprite; pulse scales from it
        self.missed_kind = None  # kind of the treat that last fell off-screen

    def _fair_x(self, w=None):
        w = self.w if w is None else w
        lo, hi = SPAWN_MARGIN, w - SPAWN_MARGIN
        if hi < lo:  # tiny playfield fallback
            lo, hi = 40, w - 40
        return random.randint(lo, hi)

    # -- sprites ------------------------------------------------------

    def _load_image(self, path, tint=None):
        img = pygame.image.load(path)
        img = pygame.transform.scale(img, (TREAT_SIZE, TREAT_SIZE))
        img.convert()
        if tint is not None:
            overlay = pygame.Surface((TREAT_SIZE, TREAT_SIZE)).convert_alpha()
            overlay.fill((*tint, 90))
            img.blit(overlay, (0, 0), special_flags=pygame.BLEND_ADD)
        # Untransformed sprite: pulse() scales from this each frame.
        self.base_img = img
        return img

    def set_treat_pic(self, force_kind=None, force_power=None, pool=None):
        """Roll a new skin. Keeps the original no-arg behaviour.

        ``pool`` selects the skin mix (per-wave pool); defaults to this
        treat's own pool, falling back to SKINS. Golden rolls in any pool
        can still convert to power-ups (golden-only window)."""
        source = pool if pool is not None else (self.pool or SKINS)
        if force_kind is not None:
            matches = [s for s in source if s[1] == force_kind]
            rndm_pic, kind, points = random.choice(matches or SKINS)
        elif force_power is not None:
            self.set_powerup(force_power)
            return
        else:
            rndm_pic, kind, points = random.choice(source)

        # Reset Phase 2 flags, then roll variety.
        self.power = None
        self.fast = False
        self.decoy = False
        self.disguised = False
        self.decoy_timer = 0.0

        if kind == 'golden' and random.random() < GOLDEN_TO_POWERUP_CHANCE:
            self.set_powerup(random.choice(POWERUP_TYPES))
            return

        if kind == 'bad':
            roll = random.random()
            if roll < FAST_ROTTEN_CHANCE:
                self.fast = True
            elif roll < FAST_ROTTEN_CHANCE + DECOY_CHANCE:
                self.make_decoy()
                return

        self.treatimg = self._load_image(rndm_pic)
        self.selected_skin = rndm_pic.split('/')[-1]
        self.kind = kind
        self.points = points
        self.set_graph()
        self.spawn()

    def set_powerup(self, power):
        """Turn this treat into a power-up (reuses the golden sprite)."""
        self.power = power
        self.fast = False
        self.decoy = False
        self.disguised = False
        self.decoy_timer = 0.0
        self.treatimg = self._load_image(
            'static/images/treats_2.png', tint=POWERUP_TINTS.get(power)
        )
        self.selected_skin = 'treats_2.png'
        self.kind = 'powerup'
        self.points = 0
        self.set_graph()
        self.spawn()

    def make_decoy(self, duration=DECOY_DISGUISE_TIME):
        """Turn this treat into a decoy: looks golden, reveals as bad."""
        self.decoy = True
        self.disguised = True
        self.decoy_timer = duration
        self.fast = False
        self.power = None
        self.treatimg = self._load_image('static/images/treats_2.png')
        self.selected_skin = 'treats_2.png'
        self.kind = 'bad'
        self.points = 0
        self.set_graph()
        self.spawn()

    def reveal_decoy(self):
        """Drop the golden disguise — this was rotten all along."""
        if not self.decoy or not self.disguised:
            return
        self.disguised = False
        self.decoy_timer = 0.0
        self.treatimg = self._load_image('static/images/treats_bad.png')
        self.selected_skin = 'treats_bad.png'
        self.set_graph()
        self.spawn()

    # -- helpers ------------------------------------------------------

    def is_rotten(self):
        """True for bad treats, including disguised decoys."""
        return self.kind == 'bad'

    def looks_golden(self):
        """What the player sees: golden, disguised decoy, or power-up."""
        return (
            self.kind == 'golden'
            or self.kind == 'powerup'
            or (self.decoy and self.disguised)
        )

    def effective_vy(self, speed_scale=1.0):
        vy = self.vy * speed_scale
        if self.fast:
            vy *= 2
        return vy

    def check_near_miss(self, cat_x, threshold=50):
        """Rotten treat dodged within ~50px horizontally, untouched."""
        return (
            self.is_rotten()
            and not self.touched
            and abs(self.pos_x - cat_x) <= threshold
        )

    # -- core API (unchanged signatures) -------------------------------

    def set_graph(self):
        treats_rect = self.treatimg.get_rect()
        self.treatrect = treats_rect

    def set_bounds(self, w, h):
        self.w = w
        self.h = h

    def rand_move(self, others=None, min_dist=MIN_SPAWN_DISTANCE):
        """Respawn at the top with a fair random x (treat drops from sky).

        ``others`` is an optional list of sibling treats; the new x is kept
        at least ``min_dist`` px away from each of them so concurrent treats
        never form an impossible pair. Retries a bounded number of times,
        then keeps the best candidate found. Candidates come from
        ``_fair_x`` so the SPAWN_MARGIN edge guarantee always holds.
        """
        others = [t for t in (others or []) if t is not self]
        best_x = self._fair_x()
        if others:
            best_score = -1
            for _ in range(20):
                cand = self._fair_x()
                nearest = min(abs(cand - t.pos_x) for t in others)
                if nearest >= min_dist:
                    best_x = cand
                    break
                if nearest > best_score:
                    best_score = nearest
                    best_x = cand
        self.pos_x = best_x
        self.pos_y = -40
        self.touched = False
        self.set_treat_pic(pool=self.pool)

    def update(self, dt=1.0, speed_scale=1.0):
        """Fall one dt-scaled step (dt in 60-FPS frames, slowmo via
        ``speed_scale``). Returns True if it fell off-screen (missed)."""
        # Decoy disguise ticks down in real seconds, then reveals as bad.
        if self.decoy and self.disguised:
            self.decoy_timer -= dt / 60.0  # dt frames -> seconds
            if self.decoy_timer <= 0:
                self.reveal_decoy()
        self.pos_y += self.effective_vy(speed_scale) * dt
        if self.pos_y > self.h + 60:
            self.missed_kind = self.kind  # game reads this to reset combo
            # Snapshot for the near-miss bonus before respawning.
            self.last_miss_x = self.pos_x
            self.last_miss_kind = self.kind
            self.last_miss_touched = self.touched
            self.rand_move()
            return True
        return False

    def pulse(self, time_s):
        """Squash & stretch: gentle scale pulse while falling.

        Headless-safe: pure transform.scale on an in-memory surface."""
        if self.base_img is None or self.treatrect is None:
            return
        try:
            s = 1.0 + 0.08 * math.sin(time_s * 6.0 + self.pos_x * 0.01)
            w = max(1, int(TREAT_SIZE * s))
            h = max(1, int(TREAT_SIZE * s))
            center = self.treatrect.center
            self.treatimg = pygame.transform.scale(self.base_img, (w, h))
            self.treatrect = self.treatimg.get_rect()
            self.treatrect.center = center
        except pygame.error:
            pass  # cosmetic only — never break the game

    def spawn(self):
        self.treatrect.center = self.pos_x, self.pos_y
