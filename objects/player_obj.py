START_LIVES = 9


class PlayerObj:

    def __init__(self):
        self.points = 0
        self.lives = START_LIVES
        self.player_name = 'Player1'

    def set_player_name(self):
        pass

    def add_point(self):
        self.points += 1

    def add_special_points(self):
        self.points += 3

    def add_points(self, n):
        self.points += n

    def lose_life(self):
        self.lives = max(0, self.lives - 1)

    def is_alive(self):
        return self.lives > 0

    def reset_points(self):
        self.points = 0

    def reset(self):
        self.points = 0
        self.lives = START_LIVES
