import hlt
import time


def get_all_enemy_ships(game_map):
    enemy_ships = []
    players = game_map.all_players()
    for player in players:
        if player == game_map.get_me():
            continue
        enemy_ships.extend(player.all_ships())
    return enemy_ships

def pop_closest(obj, obj_list):
    min_seen = 1e10
    min_obj = None
    for obj2 in obj_list:
        dist = obj.calculate_distance_between(obj2)
        if dist < min_seen:
            min_seen = dist
            min_obj = obj2
    obj_list.remove(min_obj)
    return min_obj

def get_closest(obj, obj_list):
    min_seen = 1e10
    min_obj = None
    for obj2 in obj_list:
        dist = obj.calculate_distance_between(obj2)
        if dist < min_seen:
            min_seen = dist
            min_obj = obj2
    return min_obj

def get_proximity(obj, obj_list):
    min_seen = 1e10
    for obj2 in obj_list:
        dist = obj.calculate_distance_between(obj2)
        if dist < min_seen:
            min_seen = dist
    return min_seen

def get_proximity_alerts(sensors, targets, trigger_dist):
    trigger_list = []
    for target in targets:
        for sensor in sensors:
            if target.calculate_distance_between(sensor) < trigger_dist:
                trigger_list.append(target)
                break
    return trigger_list

def get_attractive_dock_spot(game_map, ship, dock_spots):
    max_score_seen = -1e10
    max_score_dock_spot = None
    map_center = hlt.entity.Position(game_map.width/2, game_map.height/2)
    for dock_spot in dock_spots:
        dist_from_ship = ship.calculate_distance_between(ship.closest_point_to(dock_spot))
        dist_from_center = dock_spot.calculate_distance_between(map_center)
        planet_size = dock_spot.num_docking_spots
        score = planet_size + dist_from_center * 0.02 - dist_from_ship * 0.1
        if score > max_score_seen:
            max_score_seen = score
            max_score_dock_spot = dock_spot
    return max_score_dock_spot, max_score_seen

def get_most_attractive(game_map, ship, options, func, with_score=False):
    max_score_seen = -1e10
    best_option_seen = None
    for option in options:
        score = func(game_map, ship, option)
        if score > max_score_seen:
            max_score_seen = score
            best_option_seen = option
    if with_score:
        return best_option_seen, max_score_seen
    return best_option_seen

def is_under_attack(game_map, ship):
    enemies = get_all_enemy_ships(game_map)
    for enemy in enemies:
        if ship.calculate_distance_between(enemy) <= 5:
            return True
    return False

def get_attackers(game_map, ship):
    attackers = []
    enemies = get_all_enemy_ships(game_map)
    for enemy in enemies:
        if ship.calculate_distance_between(enemy) <= 5:
            attackers.append(enemy)
    return attackers

def get_object_to_object_proximity_list(game_map, obj, f=None):
    if f is None:
        f = lambda x: True
    entities_by_distance = game_map.nearby_entities_by_distance(obj)
    objects_in_distance_order = []
    for distance in sorted(entities_by_distance):
        objects_in_distance_order.extend([(entity, distance) for entity in entities_by_distance[distance] if f(entity)])
    return objects_in_distance_order

class Timer:
    def __init__(self):
        self.t = time.time()

    def get_time(self):
        dt = time.time() - self.t
        self.t = time.time()
        return round(dt*1000, 0)