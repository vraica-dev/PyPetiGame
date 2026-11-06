import pygame
import random


class TreatObj:
    def __init__(self):
        self.pos_x = random.randint(1, 400)
        self.pos_y = random.randint(1, 400)

        self.treats_img_list = [
            'static/images/treats.png',
            'static/images/treats_2.png',
        ]

        self.selected_skin = None

        self.treatimg = None
        self.treatrect = None

        # self.set_graph()
    def set_treat_pic(self):
        rndm_pic = random.choice(self.treats_img_list)
        treats_img = pygame.image.load(rndm_pic)
        treats_img = pygame.transform.scale(treats_img, (40, 40))
        treats_img.convert()

        self.treatimg = treats_img
        self.selected_skin = rndm_pic.split('/')[-1]
        self.set_graph()
        self.spawn()

    def set_graph(self):
        treats_rect = self.treatimg.get_rect()
        self.treatrect = treats_rect

    def rand_move(self):
        self.pos_x = random.randint(1, 482)
        self.pos_y = random.randint(1, 388)
        self.set_treat_pic()

    def spawn(self):
        self.treatrect.center = self.pos_x, self.pos_y





