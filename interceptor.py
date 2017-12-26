import hlt
import bot_utils
import logging
import random
import copy
import time

game = hlt.Game("Interceptor")

# parameters
defensive_action_radius = 40  # radius around a planet within which interceptors will attack enemies (also longest distance interceptor will travel to intercept)
max_response = 4  # maximum number of interceptors per enemy
safe_docking_distance = 50  # minimum 'safe' distance from a planet to the nearest enemy planet

type_table = {}  # e.g. id -> string
enemy_tracking = {}

t = 0
while True:
    game_map = game.update_map()
    logging.info(f't = {t}')
    timer = bot_utils.Timer()

    command_queue = []

    # update type table
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]

    my_planets = [planet for planet in game_map.all_planets() if planet.owner == game_map.get_me()]
    all_planets = game_map.all_planets()
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]
    enemy_planets = [planet for planet in all_planets if planet.owner not in [None, game_map.get_me()]]

    # collect map information
    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    docked_enemy_ships = [enemy for enemy in enemy_ships if
                          enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING,
                                                   hlt.entity.Ship.DockingStatus.DOCKED]]

    proximal_enemy_ships = bot_utils.get_proximity_alerts(my_planets, enemy_ships, defensive_action_radius)

    if len(proximal_enemy_ships) > 0:
        logging.info(f'Enemy ships nearby: {[ship.id for ship in proximal_enemy_ships]}')

    good_to_dock_planets = [planet for planet in non_full_friendly_planets
                            if bot_utils.get_proximity(planet, enemy_planets) > safe_docking_distance]
    other_dockable_planets = [planet for planet in non_full_friendly_planets if planet not in good_to_dock_planets]

    good_dock_spots = []
    for planet in good_to_dock_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            good_dock_spots.append(planet)

    other_dock_spots = []
    for planet in other_dockable_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            other_dock_spots.append(planet)

    good_opportunities = docked_enemy_ships + good_dock_spots

    logging.info(f'all_my_ship_ids: {all_my_ship_ids}')
    # remove dead guys
    for ship_id in list(type_table.keys()):
        if ship_id not in all_my_ship_ids:
            del type_table[ship_id]
    # add new guys
    for ship in my_fighting_ships:
        if ship.id not in type_table:
            type_table[ship.id] = 'interceptor'

    logging.info(f'type_table: {type_table}')

    interceptors = {enemy: [] for enemy in proximal_enemy_ships}
    # can also join all action lists (dock spots and proximal enemies) and then let each ship do the closest action
    orders = {}
    # attack any proximal enemies
    for ship in my_fighting_ships:
        if len(proximal_enemy_ships) > 0:
            enemy = bot_utils.get_closest(ship, proximal_enemy_ships)
            if ship.calculate_distance_between(enemy) < defensive_action_radius \
                    and len(interceptors[enemy]) < max_response:
                orders[ship] = enemy
                interceptors[enemy].append(ship)
                my_fighting_ships.remove(ship)
                if len(interceptors[enemy]) >= max_response:
                    proximal_enemy_ships.remove(enemy)

    # the rest can build or hunt good opportunities
    for ship in my_fighting_ships:
        if ship not in orders:
            if len(good_opportunities) > 0:
                closest_opportunity = bot_utils.pop_closest(ship, good_opportunities)
                orders[ship] = closest_opportunity
            else:
                enemy = bot_utils.get_closest(ship, enemy_ships)
                orders[ship] = enemy

    for ship in orders:
        if isinstance(orders[ship], hlt.entity.Planet) and ship.can_dock(orders[ship]):
            command_queue.append(ship.dock(orders[ship]))
        else:
            command = ship.smart_navigate(
                ship.closest_point_to(orders[ship], min_distance=2),
                game_map,
                hlt.constants.MAX_SPEED,
                angular_step=20)
            if command:
                command_queue.append(command)

    delta_time = timer.get_time()
    logging.info(f'Time to calculate trajectories: {delta_time} ms,'
                 f'time per ship: {delta_time / (len(my_fighting_ships)+1)} ms')

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
