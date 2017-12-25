import hlt


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