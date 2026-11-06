import pygame


class PetunaObj:
    # 2-frame wag: alternate tilt each half-period (time-based, no assets).
    WAG_PERIOD = 0.5  # seconds per full wag cycle
    WAG_ANGLE = 4.0  # degrees of tail-wag tilt per frame
    LEAN_ANGLE = 9.0  # extra tilt while moving sideways
    MOVE_SQUASH = (1.08, 0.94)  # (x-stretch, y-squash) while moving

    def __init__(self, w=1920, h=1080):
        self.pos_x = w // 2
        self.pos_y = h - 130
        self.catimg = None
        self.catrect = None
        self.catbox_offset = 40

        self.cat_H = 140
        self.cat_W = 140

        self.base_img = None  # untransformed sprite; transforms derive from it
        self.lean = 0.0  # -1 (left) .. 0 (idle) .. +1 (right)

        # self.set_graph()

    def set_graph(self):
        peti_img = pygame.image.load('static/images/cat.png')
        peti_img = pygame.transform.scale(peti_img, (self.cat_H, self.cat_W))
        peti_img.convert()
        self.base_img = peti_img
        self.catimg = peti_img
        self.catrect = peti_img.get_rect()
        self.spawn()

    def animate(self, time_s, moving=0):
        """Rebuild catimg from the base sprite: 2-frame wag + move lean.

        `moving`: -1/0/+1 for left/idle/right. Headless-safe: pure
        rotozoom/scale on an in-memory surface, no display needed.
        """
        if self.base_img is None:
            return
        self.lean = float(moving)
        frame = int(time_s / (self.WAG_PERIOD / 2)) % 2
        wag = -self.WAG_ANGLE if frame == 0 else self.WAG_ANGLE
        angle = wag - self.lean * self.LEAN_ANGLE
        try:
            img = pygame.transform.rotate(self.base_img, angle)
            if moving != 0:
                sx, sy = self.MOVE_SQUASH
                w = max(1, int(img.get_width() * sx))
                h = max(1, int(img.get_height() * sy))
                img = pygame.transform.scale(img, (w, h))
            center = self.catrect.center if self.catrect is not None else None
            self.catimg = img
            self.catrect = img.get_rect()
            if center is not None:
                self.catrect.center = center
        except pygame.error:
            self.catimg = self.base_img  # cosmetic only — never break the game

    def spawn(self):
        self.catrect.center = self.pos_x, self.pos_y
