import hlt
import bot_utils
import logging
import copy

game = hlt.Game("Micro-Manager")

# PARAMETERS
# strategic parameters
defensive_action_radius = 40  # enemy distance from planet that triggers defensive action
max_response = 4  # maximum number of interceptors per enemy
safe_docking_distance = 20  # minimum 'safe' distance from a planet to the nearest enemy

# dogfighting parameters
general_approach_dist = 2  # 'closest point to' offset
leader_approach_dist = 2
tether_dist = 3
padding = 0.2  # standard padding added to obstacle radii (helps to prevent unwanted crashes)

# navigation parameters
angular_step = 1
horizon_reduction_factor = 0.95
max_corrections = int(90 / angular_step) + 1

type_table = {}  # e.g. id -> string
enemy_tracking = {}

t = 0
while True:
    game_map = game.update_map()
    logging.info(f't = {t}')
    timer = bot_utils.Timer()

    # 1 DATA COLLECTION
    # collect general map information
    all_planets = game_map.all_planets()
    all_docked_ships = [ship for player in game_map.all_players() for ship in player.all_ships() if
                        ship.docking_status != hlt.entity.Ship.DockingStatus.UNDOCKED]

    # collect my stuff
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    my_unassigned_ships = copy.copy(my_fighting_ships)
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]

    my_planets = [planet for planet in game_map.all_planets() if planet.owner == game_map.get_me()]
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]

    # update type table
    logging.info(f'all my ships: {all_my_ship_ids}')
    # remove dead guys
    for ship_id in list(type_table.keys()):
        if ship_id not in all_my_ship_ids:
            del type_table[ship_id]
    # add new guys
    for ship in my_fighting_ships:
        if ship.id not in type_table:
            type_table[ship.id] = 'interceptor'
    # logging.info(f'type_table: {type_table}')

    # collect enemy stuff
    enemy_planets = [planet for planet in all_planets if planet.owner not in [None, game_map.get_me()]]
    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    flying_enemies = [enemy for enemy in enemy_ships if enemy.docking_status != hlt.entity.Ship.DockingStatus.UNDOCKED]

    docked_enemy_ships = [enemy for enemy in enemy_ships if
                          enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING,
                                                   hlt.entity.Ship.DockingStatus.DOCKED]]

    enemy_tracking_new = {enemy.id: hlt.entity.Position(enemy.x, enemy.y) for enemy in enemy_ships}
    enemy_location_prediction = {}
    for enemy_id in enemy_tracking_new:
        if enemy_id in enemy_tracking:
            enemy_location_prediction[enemy_id] = (2 * enemy_tracking_new[enemy_id] - enemy_tracking[enemy_id])
    enemy_tracking = enemy_tracking_new

    planet_defense_radii = [planet.radius + defensive_action_radius for planet in my_planets]
    proximal_enemy_ships = bot_utils.get_proximity_alerts(my_planets, planet_defense_radii, enemy_ships)

    if len(proximal_enemy_ships) > 0:
        logging.info(f'Enemy ships nearby: {[ship.id for ship in proximal_enemy_ships]}')

    # 2 STRATEGIC CALCULATIONS & JOB CREATION - output: list good_opportunities
    good_to_dock_planets = \
        [planet for planet in non_full_friendly_planets
         if bot_utils.get_proximity(planet, enemy_ships) > safe_docking_distance + planet.radius

         or (planet.owner == game_map.get_me() and len(
            bot_utils.get_proximity_alerts([planet], [defensive_action_radius + planet.radius], enemy_ships)) < len(
            bot_utils.get_proximity_alerts([planet], [defensive_action_radius + planet.radius], my_unassigned_ships)))

         or len(bot_utils.get_proximity_alerts([planet], [defensive_action_radius + planet.radius],
                                               my_unassigned_ships + my_planets))
         > 2 * len(bot_utils.get_proximity_alerts([planet], [safe_docking_distance + planet.radius], enemy_ships))]
    logging.info(f'Good planets: {["P"+str(planet.id) for planet in good_to_dock_planets]}')
    logging.info(f'Time used for good planet determination: {timer.get_time()}')

    good_dock_spots = []
    for planet in good_to_dock_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            good_dock_spots.append(planet)

    good_opportunities = docked_enemy_ships + good_dock_spots

    # 3 JOB ALLOCATION - output: dict orders
    # planet defense calculations
    # TODO: make this part of the strategic calculations and then let the allocation algorithm decide who does it
    interceptors = {enemy: [] for enemy in proximal_enemy_ships}
    orders = {}
    for ship in list(my_unassigned_ships):
        if len(proximal_enemy_ships) > 0:
            enemy = bot_utils.get_closest(ship, proximal_enemy_ships)
            if ship.calculate_distance_between(enemy) < defensive_action_radius \
                    and len(interceptors[enemy]) < max_response:
                interceptors[enemy].append(ship)
                my_unassigned_ships.remove(ship)
                if len(interceptors[enemy]) >= max_response:
                    proximal_enemy_ships.remove(enemy)

    defensive_packs = {}
    for enemy in interceptors:
        if len(interceptors[enemy]) > 0:
            pack_leader = bot_utils.get_central_entity(interceptors[enemy])
            defensive_packs[pack_leader] = []
            for ship in interceptors[enemy]:
                if ship is pack_leader:
                    orders[ship] = enemy
                else:
                    defensive_packs[pack_leader].append(ship)
    tethered_followers = {leader: [] for leader in defensive_packs}
    for leader in defensive_packs:
        for follower in defensive_packs[leader]:
            if leader.calculate_distance_between(follower) < tether_dist:
                tethered_followers[leader].append(follower)
    for leader, followers in tethered_followers.items():
        if len(followers) > 0:
            leader.radius = leader.calculate_distance_between(bot_utils.get_furthest(leader, followers)) + 0.5

    minimal_dist_alloc = bot_utils.get_minimal_distance_allocation(my_unassigned_ships, good_opportunities)
    logging.info(f'Time to calculate minimal distance job allocation: {timer.get_time()} ms')
    for ship in list(my_unassigned_ships):
        if ship in minimal_dist_alloc:
            orders[ship] = minimal_dist_alloc[ship]
        else:
            enemy = bot_utils.get_closest(ship, enemy_ships)
            orders[ship] = enemy
        my_unassigned_ships.remove(ship)

    # 4 LOGGING
    logging_orders = {}
    for ship, order in orders.items():
        logging_orders[ship.id] = f'S{order.id}' if isinstance(order, hlt.entity.Ship) else f'P{order.id}'
    logging.info(f'orders: {logging_orders}')
    defensive_packs_logging = {}
    for leader, followers in defensive_packs.items():
        defensive_packs_logging[leader.id] = [ship.id for ship in followers]
    logging.info(f'defensive_packs: {defensive_packs_logging}')

    # update orders to account for location prediction
    for ship, target in list(orders.items()):
        if isinstance(target, hlt.entity.Ship):
            if target.id in enemy_location_prediction:
                orders[ship] = enemy_location_prediction[target.id]

    # 5 COMMAND GENERATION
    # prepare avoid_entities list
    all_tethered_ships = [ship for leader in tethered_followers for ship in tethered_followers[leader]]
    all_my_flying_obstacles = [ship for ship in my_fighting_ships if ship not in all_tethered_ships]
    avoid_entities = all_planets + all_docked_ships + all_my_flying_obstacles
    for enemy in flying_enemies:
        if enemy.id in enemy_location_prediction:
            avoid_entities.append(enemy_location_prediction[enemy.id])
        else:
            avoid_entities.append(enemy)

    command_queue = []
    # handle navigation of pack leaders and tethered followers
    for leader in list(defensive_packs):
        avoid_entities.remove(leader)
        command = leader.smart_navigate(
            leader.closest_point_to(orders[leader], min_distance=general_approach_dist),
            game_map,
            hlt.constants.MAX_SPEED,
            angular_step=angular_step,
            max_corrections=max_corrections,
            horizon_reduction_factor=horizon_reduction_factor,
            padding=padding,
            avoid_entities=avoid_entities)

        if command:
            command_queue.append(command)
            delta = bot_utils.convert_command_to_position_delta(leader, command)
            new_position = delta + leader
            avoid_entities.append(new_position)
            for follower in defensive_packs[leader]:
                if follower in tethered_followers[leader]:
                    command_queue.append(f't {follower.id} {command.split(" ")[2]} {command.split(" ")[3]}')
                else:
                    orders[follower] = new_position
        else:
            # if command fails, keep the previous position
            avoid_entities.append(leader)
        del orders[leader]

    # handle navigation for other ships
    for ship in list(orders):
        if isinstance(orders[ship], hlt.entity.Planet) and ship.can_dock(orders[ship]):
            command_queue.append(ship.dock(orders[ship]))
        else:
            avoid_entities.remove(ship)
            if orders[ship] in defensive_packs:
                approach_dist = leader_approach_dist
            else:
                approach_dist = general_approach_dist
            command = ship.smart_navigate(
                ship.closest_point_to(orders[ship], min_distance=approach_dist),
                game_map,
                hlt.constants.MAX_SPEED,
                angular_step=angular_step,
                max_corrections=max_corrections,
                horizon_reduction_factor=horizon_reduction_factor,
                padding=padding,
                avoid_entities=avoid_entities)

            if command:
                command_queue.append(command)

            del orders[ship]
            new_position = bot_utils.convert_command_to_position_delta(ship, command) + ship
            avoid_entities.append(new_position)

    delta_time = timer.get_time()
    logging.info(f'Time to calculate trajectories: {delta_time} ms,'
                 f'time per ship: {round(delta_time / (len(my_fighting_ships)+1), 0)} ms')
    # if delta_time > 1000:
    #     angular_step = min(angular_step + 5, 45)
    #     max_corrections = int(180 / angular_step) + 1
    #     logging.info(f'Increased angular step to {angular_step}, with max corrections {max_corrections}')

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
