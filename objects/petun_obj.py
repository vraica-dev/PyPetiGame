
import pygame


class PetunaObj:
    def __init__(self, w=1920, h=1080):
        self.pos_x = w // 2
        self.pos_y = h - 130
        self.catimg = None
        self.catrect = None
        self.catbox_offset = 40

        self.cat_H = 140
        self.cat_W = 140

        # self.set_graph()

    def set_graph(self, skin=None):
        """Load the cat sprite, optionally tinted/scaled per skin dict."""
        peti_img = pygame.image.load('static/images/cat.png')
        scale = 1.0
        tint = None
        if skin is not None:
            scale = float(skin.get('scale', 1.0))
            tint = skin.get('tint')
        size = (int(self.cat_H * scale), int(self.cat_W * scale))
        peti_img = pygame.transform.scale(peti_img, size)
        if tint is not None:
            glow = pygame.Surface(peti_img.get_size()).convert_alpha()
            glow.fill((*tint, 0))
            peti_img.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        peti_img.convert()
        peti_rect = peti_img.get_rect()
        self.catimg = peti_img
        self.catrect = peti_rect

    def spawn(self):
        self.catrect.center = self.pos_x, self.pos_y



