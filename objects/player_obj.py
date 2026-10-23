
class PlayerObj:

    def __init__(self):
        self.points = 0
        self.player_name = 'Player1'

    def set_player_name(self):
        pass

    def add_point(self):
        self.points += 1

    def add_special_points(self):
        self.points += 3

    def reset_points(self):
        self.points = 0

