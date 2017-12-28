import hlt


class DataCapture:

    def __init__(self, game_map):
        self.game_map = game_map
        self.last_alive = []
        self.docked_ships = []
        self.dock_events = {}
        self.death_events = {}
        self.birth_events = {}
        self.t = 0

    def update(self):
        currently_alive = [ship for player in self.game_map.all_players() for ship in player.all_ships()]
        for ship in currently_alive:
            if ship.id not in self.last_alive:
                self.birth_events[ship.id] = {'t': self.t, 'owner': ship.owner, 'x': ship.x, 'y': ship.y}
        for ship in self.last_alive:
            if ship.id not in [ship.id for ship in currently_alive]:
                self.death_events[ship.id] = {'t': self.t, 'owner': ship.owner, 'x': ship.x, 'y': ship.y}
        for ship in currently_alive:
            if ship.docking_status != hlt.entity.Ship.DockingStatus.UNDOCKED:
                if ship.id in self.docked_ships:
                    continue
                # UNFINISHED

        self.last_alive = currently_alive
        self.t += 1

    def initialize(self):
        # log map details
        pass