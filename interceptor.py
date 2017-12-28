import hlt
import bot_utils
import logging
import benefit_calculator
import numpy as np

game = hlt.Game("Investment-Manager")

# parameters
defensive_action_radius = 40  # radius around a planet within which interceptors will attack enemies (also longest distance interceptor will travel to intercept)
max_response = 4  # maximum number of interceptors per enemy
safe_docking_distance = 20  # minimum 'safe' distance from a planet to the nearest enemy

approach_dist = 2  # 'closest point to' offset
padding = 1  # standard padding added to obstacle radii (helps to prevent unwanted crashes)

type_table = {}  # e.g. id -> string
enemy_tracking = {}

angular_step = 5
max_corrections = int(180 / angular_step) + 1

t = 0
while True:
    game_map = game.update_map()
    logging.info(f't = {t}')
    timer = bot_utils.Timer()

    command_queue = []

    # collect map information
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]

    my_planets = [planet for planet in game_map.all_planets() if planet.owner == game_map.get_me()]
    all_planets = game_map.all_planets()
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]
    enemy_planets = [planet for planet in all_planets if planet.owner not in [None, game_map.get_me()]]
    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    docked_enemy_ships = [enemy for enemy in enemy_ships if
                          enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING,
                                                   hlt.entity.Ship.DockingStatus.DOCKED]]

    enemy_tracking_new = {enemy.id: hlt.entity.Position(enemy.x, enemy.y) for enemy in enemy_ships}
    enemy_location_prediction = {}
    for enemy_id in enemy_tracking_new:
        if enemy_id in enemy_tracking:
            enemy_location_prediction[enemy_id] = (2 * enemy_tracking_new[enemy_id] - enemy_tracking[enemy_id])
    enemy_tracking = enemy_tracking_new
    logging.info(f'Time used for enemy ship tracking: {timer.get_time()} ms')

    planet_defense_radii = [planet.radius + defensive_action_radius for planet in my_planets]
    proximal_enemy_ships = bot_utils.get_proximity_alerts(my_planets, planet_defense_radii, enemy_ships)

    if len(proximal_enemy_ships) > 0:
        logging.info(f'Enemy ships nearby: {[ship.id for ship in proximal_enemy_ships]}')

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

    good_opportunities = docked_enemy_ships + good_dock_spots + proximal_enemy_ships
    # build opportunity matrix
    orders = {}
    for i, ship in enumerate(my_fighting_ships):
        best_opportunity = bot_utils.get_closest(ship, enemy_ships)
        score = 0
        for j, opportunity in enumerate(good_opportunities):
            benefit = benefit_calculator.get_benefit(ship, opportunity, t, orders, game_map)
            if benefit > score:
                score = benefit
                best_opportunity = opportunity
        orders[ship] = best_opportunity
        good_opportunities.remove(best_opportunity)

    # if t < 2:
    #     main_ship = my_fighting_ships[0]
    #     for ship in orders:
    #         orders[ship] = orders[main_ship]



    # create abbreviated order dict for logging
    logging_orders = {}
    for ship, order in orders.items():
        logging_orders[ship.id] = f'S{order.id}' if isinstance(order, hlt.entity.Ship) else f'P{order.id}'
    logging.info(f'orders: {logging_orders}')

    for ship, target in list(orders.items()):
        if isinstance(target, hlt.entity.Ship):
            if target.id in enemy_location_prediction:
                orders[ship] = enemy_location_prediction[target.id]

    for ship in orders:
        if isinstance(orders[ship], hlt.entity.Planet) and ship.can_dock(orders[ship]):
            command_queue.append(ship.dock(orders[ship]))
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

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
