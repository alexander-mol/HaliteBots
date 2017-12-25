import hlt

# functions to check if it is safe to dock
# and to kill oncoming enemy as they dock
# function to crash ships

def get_ship_to_object_proximity_lists(game_map, f=None):
    ship_to_object_proximity_lists = {}
    for ship in game_map.get_me().all_ships():
        ship_to_object_proximity_lists[ship] = get_object_to_object_proximity_list(game_map, ship, f)
    return ship_to_object_proximity_lists

def get_object_to_object_proximity_list(game_map, obj, f=None):
    if f is None:
        f = lambda x: True
    entities_by_distance = game_map.nearby_entities_by_distance(obj)
    objects_in_distance_order = []
    for distance in sorted(entities_by_distance):
        objects_in_distance_order.extend([(entity, distance) for entity in entities_by_distance[distance] if f(entity)])
    return objects_in_distance_order

def check_safe_to_dock(game_map, ship, planet):
    # not sure this really works
    dist = ship.calculate_distance_between(planet)
    estimated_time_to_dock = (dist - planet.radius) / 7 + 5
    net_time_to_create_a_ship = 6
    distance_needed_from_dock_spot = (estimated_time_to_dock + net_time_to_create_a_ship) * 7
    estimated_dock_spot = hlt.entity.Position((ship.x - planet.x) * planet.radius / dist,
                                              (ship.y - planet.y) * planet.radius / dist)
    near_enemies = get_object_to_object_proximity_list(game_map, estimated_dock_spot,
                                                       f=lambda x: x.owner != game_map.get_me()
                                                                   and isinstance(x, hlt.entity.Ship)
                                                                   and x.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED)
    threats = []
    for near_enemy, distance in near_enemies:
        if distance < distance_needed_from_dock_spot:
            threats.append((near_enemy, distance))

    any_real_threats = False
    for threat, distance in threats:
        if abs(planet.calculate_angle_between(threat)) < 180:
            any_real_threats = True
            break

    return not any_real_threats

def get_all_enemy_ships(game_map):
    ship = game_map.get_me().all_ships()[0]
    f = lambda x: x.owner != game_map.get_me() and isinstance(x, hlt.entity.Ship)
    enemy_ships = [ship for ship, distance in get_object_to_object_proximity_list(game_map, ship, f)]
    return enemy_ships

def determine_optimal_allocation(game_map, from_set, to_set):
    # determine an allocation assigning to each element of the from set a 'closest' element in to to_set, such that
    # the total length is minimized and each gets a unique target where possible
    # heuristic: assign the closest two to each other, then the next closest etc.
    from_set_proximity_list = {}
    for obj1 in from_set:
        from_set_proximity_list[obj1] = get_object_to_object_proximity_list(game_map, obj1, f=lambda x: x in to_set)

# def _pop_lowest(dict):
#     min_seen = 1e10
#     min_from = None
#     min_to = None
#     for from_obj, proximity_list in dict.items():
#         if proximity_list[0][1] < min_seen:
#             min_seen = proximity_list[0][1]
#             min_from = from_obj
#             min_to = proximity_list[0][0]
#     for key, value in dict.items():

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

def get_nearest_friendly_non_full_planet(game_map, ship):
    targets = get_object_to_object_proximity_list(game_map, ship, f=lambda x: isinstance(x, hlt.entity.Planet) and x.owner in [game_map.get_me(), None] and not x.is_full())
    if len(targets) > 0:
        return targets[0][0]
    else: # fail safe for if all planets are taken
        return game_map.all_planets()[0]

def get_nearest_docked_enemy(game_map, ship):
    targets = get_object_to_object_proximity_list(game_map, ship, f=lambda x: isinstance(x, hlt.entity.Ship) and x.owner != game_map.get_me())
    if len(targets) > 0:
        return targets[0][0]
    else:
        return None
