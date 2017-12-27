import hlt
import bot_utils
import logging
import random
import copy
import time

game = hlt.Game("Formation-fighter")

# parameters
defensive_action_radius = 40  # radius around a planet within which interceptors will attack enemies (also longest distance interceptor will travel to intercept)
max_response = 4  # maximum number of interceptors per enemy
safe_docking_distance = 20  # minimum 'safe' distance from a planet to the nearest enemy

approach_dist = 0.01  # 'closest point to' offset
padding = 0.01  # standard padding added to obstacle radii (helps to prevent unwanted crashes)

type_table = {}  # e.g. id -> string
enemy_tracking = {}

angular_step = 5
max_corrections = int(180 / angular_step) + 1
formations = []

t = 0
while True:
    game_map = game.update_map()
    logging.info(f't = {t}')
    timer = bot_utils.Timer()

    command_queue = []

    # collect map information
    all_planets = game_map.all_planets()
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]
    # collect my stuff
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]
    my_planets = [planet for planet in game_map.all_planets() if planet.owner == game_map.get_me()]

    # collect enemy stuff
    enemy_planets = [planet for planet in all_planets if planet.owner not in [None, game_map.get_me()]]
    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    docked_enemy_ships = [enemy for enemy in enemy_ships if
                          enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING,
                                                   hlt.entity.Ship.DockingStatus.DOCKED]]

    # find attacking enemies
    planet_defense_radii = [planet.radius + defensive_action_radius for planet in my_planets]
    proximal_enemy_ships = bot_utils.get_proximity_alerts(my_planets, planet_defense_radii, enemy_ships)
    if len(proximal_enemy_ships) > 0:
        logging.info(f'Enemy ships nearby: {[ship.id for ship in proximal_enemy_ships]}')

    # update enemy trajectory tracking
    enemy_tracking_new = {enemy.id: hlt.entity.Position(enemy.x, enemy.y) for enemy in enemy_ships}
    enemy_location_prediction = {}
    for enemy_id in enemy_tracking_new:
        if enemy_id in enemy_tracking:
            enemy_location_prediction[enemy_id] = (2 * enemy_tracking_new[enemy_id] - enemy_tracking[enemy_id])
    enemy_tracking = enemy_tracking_new
    logging.info(f'Time used for enemy ship tracking: {timer.get_time()} ms')

    # find good dock spots
    good_to_dock_planets = \
        [planet for planet in non_full_friendly_planets
         if bot_utils.get_proximity(planet, enemy_ships) > safe_docking_distance + planet.radius

         or (planet.owner == game_map.get_me() and len(
            bot_utils.get_proximity_alerts([planet], [defensive_action_radius + planet.radius], enemy_ships)) < len(
            bot_utils.get_proximity_alerts([planet], [defensive_action_radius + planet.radius], my_fighting_ships)))

         or len(bot_utils.get_proximity_alerts([planet], [defensive_action_radius + planet.radius],
                                               my_fighting_ships + my_planets))
         > 2 * len(bot_utils.get_proximity_alerts([planet], [safe_docking_distance + planet.radius], enemy_ships))]
    logging.info(f'Time used for good planet determination: {timer.get_time()}')

    other_dockable_planets = [planet for planet in non_full_friendly_planets if planet not in good_to_dock_planets]

    good_dock_spots = []
    for planet in good_to_dock_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            good_dock_spots.append(planet)

    other_dock_spots = []
    for planet in other_dockable_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            other_dock_spots.append(planet)

    # update type table
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

    # formation handling
    for formation in formations:
        formation.update(my_fighting_ships)
        for ship in formation.ships:
            my_fighting_ships.remove(ship)

    if len(formations) == 0 and len(my_fighting_ships) > 7:
        central_ship = bot_utils.get_central_point(my_fighting_ships)
        formations.append(hlt.entity.Formation(central_ship))
        my_fighting_ships.remove(central_ship)

    available_formation_spots = []
    for formation in formations:
        available_formation_spots.extend(formation.available_spots)

    good_opportunities = good_dock_spots + available_formation_spots

    # intercept attackers
    interceptors = {enemy: [] for enemy in proximal_enemy_ships}
    # can also join all action lists (dock spots and proximal enemies) and then let each ship do the closest action
    orders = {}
    # # attack any proximal enemies
    # for ship in copy.copy(my_fighting_ships):
    #     if len(proximal_enemy_ships) > 0:
    #         enemy = bot_utils.get_closest(ship, proximal_enemy_ships)
    #         if ship.calculate_distance_between(enemy) < defensive_action_radius \
    #                 and len(interceptors[enemy]) < max_response:
    #             orders[ship] = enemy
    #             interceptors[enemy].append(ship)
    #             my_fighting_ships.remove(ship)
    #             if len(interceptors[enemy]) >= max_response:
    #                 proximal_enemy_ships.remove(enemy)


    minimal_dist_alloc = bot_utils.get_minimal_distance_allocation(my_fighting_ships, good_opportunities)

    logging.info(f'Time to calculate minimal distance job allocation: {timer.get_time()} ms')
    for ship in my_fighting_ships:
        if ship in minimal_dist_alloc:
            orders[ship] = minimal_dist_alloc[ship]
        else:
            enemy = bot_utils.get_closest(ship, enemy_ships)
            orders[ship] = enemy

    # create abbreviated order dict for logging
    logging_orders = {}
    for ship, order in orders.items():
        logging_orders[ship.id] = bot_utils.get_order_string(order)
    logging.info(f'orders: {logging_orders}')

    for ship, target in list(orders.items()):
        if isinstance(target, hlt.entity.Ship):
            if target.id in enemy_location_prediction:
                orders[ship] = enemy_location_prediction[target.id]

    corner = hlt.entity.Position(game_map.width, game_map.height)
    if len(formations) > 0:
        command = formations[0].smart_navigate(corner, game_map, hlt.constants.MAX_SPEED/3)
        if command:
            command_queue.append(command)

    for ship in orders:
        if isinstance(orders[ship], hlt.entity.Planet) and ship.can_dock(orders[ship]):
            command_queue.append(ship.dock(orders[ship]))
        elif isinstance(orders[ship], hlt.entity.FormationSpot) and orders[ship].can_add(ship):
            orders[ship].add(ship)
        else:
            command = ship.smart_navigate(
                ship.closest_point_to(orders[ship], min_distance=approach_dist),
                game_map,
                hlt.constants.MAX_SPEED,
                angular_step=angular_step,
                max_corrections=max_corrections,
                padding=padding)
            if command:
                command_queue.append(command)

    delta_time = timer.get_time()
    logging.info(f'Time to calculate trajectories: {delta_time} ms,'
                 f'time per ship: {round(delta_time / (len(my_fighting_ships)+1), 0)} ms')
    if delta_time > 1000:
        angular_step = min(angular_step + 5, 45)
        max_corrections = int(180 / angular_step) + 1
        logging.info(f'Increased angular step to {angular_step}, with max corrections {max_corrections}')

    logging.info(f'command_queue {command_queue}')

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
