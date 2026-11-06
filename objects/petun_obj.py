
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

    def set_graph(self):
        peti_img = pygame.image.load('static/images/cat.png')
        peti_img = pygame.transform.scale(peti_img, (self.cat_H, self.cat_W))
        peti_img.convert()
        peti_rect = peti_img.get_rect()
        self.catimg = peti_img
        self.catrect = peti_rect

    def spawn(self):
        self.catrect.center = self.pos_x, self.pos_y



