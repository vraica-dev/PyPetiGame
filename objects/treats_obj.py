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


class TreatObj:
    """A treat that drops from the sky. Good = points, bad = lose a life."""

    def __init__(self, w=1920, h=1080):
        self.w = w
        self.h = h
        self.pos_x = self._fair_x(w)
        self.pos_y = -40  # start above the screen, falls in

        self.vy = 5  # fall speed, px per 60-FPS frame; raised as you score

        self.selected_skin = None
        self.kind = 'good'
        self.points = 1

        self.treatimg = None
        self.treatrect = None

    def _fair_x(self, w=None):
        w = self.w if w is None else w
        lo, hi = SPAWN_MARGIN, w - SPAWN_MARGIN
        if hi < lo:  # tiny playfield fallback
            lo, hi = 40, w - 40
        return random.randint(lo, hi)

    def set_treat_pic(self):
        rndm_pic, kind, points = random.choice(SKINS)
        treats_img = pygame.image.load(rndm_pic)
        treats_img = pygame.transform.scale(treats_img, (TREAT_SIZE, TREAT_SIZE))
        treats_img.convert()

        self.treatimg = treats_img
        self.selected_skin = rndm_pic.split('/')[-1]
        self.kind = kind
        self.points = points
        self.set_graph()
        self.spawn()

    def set_graph(self):
        treats_rect = self.treatimg.get_rect()
        self.treatrect = treats_rect

    def set_bounds(self, w, h):
        self.w = w
        self.h = h

    def rand_move(self):
        """Respawn at the top with a fair random x (treat drops from sky)."""
        self.pos_x = self._fair_x()
        self.pos_y = -40
        self.set_treat_pic()

    def update(self, dt=1.0):
        """Fall one dt-scaled step. Returns True if fell off-screen (missed)."""
        self.pos_y += self.vy * dt
        if self.pos_y > self.h + 60:
            self.rand_move()
            return True
        return False

    def spawn(self):
        self.treatrect.center = self.pos_x, self.pos_y
