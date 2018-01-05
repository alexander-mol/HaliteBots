import hlt
import bot_utils
import logging
import copy

game = hlt.Game("Aggressive")

# PARAMETERS
# strategic parameters
defensive_action_radius = 34.6  # enemy distance from planet that triggers defensive action
max_response = 5    # maximum number of interceptors per enemy
safe_docking_distance = 1000.0  # minimum 'safe' distance from a planet to the nearest enemy
job_base_benefit = 81.3
attacking_relative_benefit = 1.5
defending_relative_benefit = 1.5
available_ships_for_rogue_mission_trigger = 12   # number of ships where loosing one isn't a disaster
zone_dominance_factor_for_docking = 10
safety_check_radius = 10.0
attack_superiority_ratio = 2.1

# micro movement parameters
general_approach_dist = 0.6
dogfighting_approach_dist = 3.7
planet_approach_dist = 3.45
leader_approach_dist = 0.6
tether_dist = 1.81
padding = 0.14   # standard padding added to obstacle radii (helps to prevent unwanted crashes)
max_horizon = 8

# navigation parameters
angular_step = 5
max_corrections = int(90 / angular_step) + 1
motion_ghost_points = 6
use_unassigned_ships = True

type_table = {}  # e.g. id -> string
enemy_tracking = {}
planet_ownership_changes = {}
planet_owners = {}
rogue_missions_id = {}

# important lists to keep up-to-date:
# - my_unassigned_ships
# - packs
# - my_free_navigation_ships
# - tethered_followers

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
    if t == 0:
        for planet in all_planets:
            planet_ownership_changes[planet.id] = 0
            planet_owners[planet.id] = planet.owner

    for planet in all_planets:
        if planet.owner != planet_owners[planet.id]:
            planet_owners[planet.id] = planet.owner
            planet_ownership_changes[planet.id] += 1

    # collect my stuff
    my_docked_ships = [ship for ship in game_map.get_me().all_ships() if
                       ship.docking_status != hlt.entity.Ship.DockingStatus.UNDOCKED]
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    my_unassigned_ships = copy.copy(my_fighting_ships)
    my_free_navigation_ships = copy.copy(my_fighting_ships)
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]

    my_planets = [planet for planet in game_map.all_planets() if planet.owner == game_map.get_me()]
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]

    # update type table
    logging.info(f'my unassigned ships: ({len(my_unassigned_ships)}) {[ship.id for ship in my_unassigned_ships]}')
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
    mobile_enemies = []
    location_prediction = {}
    for enemy_id in enemy_tracking_new:
        if enemy_id in enemy_tracking:
            enemy = [enemy for enemy in enemy_ships if enemy.id == enemy_id][0]
            location_prediction[enemy] = (2 * enemy_tracking_new[enemy_id] - enemy_tracking[enemy_id])
            if (location_prediction[enemy] - enemy).calculate_distance_between(hlt.entity.Position(0, 0)) > 0.1:
                mobile_enemies.append(enemy)
    enemy_tracking = enemy_tracking_new

    planet_defense_radii = [planet.radius + defensive_action_radius for planet in my_planets]
    proximal_enemy_ships = bot_utils.get_proximity_alerts(my_planets, planet_defense_radii, enemy_ships)

    if len(proximal_enemy_ships) > 0:
        logging.info(f'Enemy ships nearby: {[ship.id for ship in proximal_enemy_ships]}')

    # 2 STRATEGIC CALCULATIONS & JOB CREATION - output: list good_opportunities
    good_to_dock_planets = \
        [planet for planet in non_full_friendly_planets
         if bot_utils.get_proximity(planet, enemy_ships) > safe_docking_distance + planet.radius
         or len(bot_utils.get_proximity_alerts([planet], [safe_docking_distance + planet.radius],
                                               my_unassigned_ships + my_planets))
         > len(bot_utils.get_proximity_alerts([planet], [safe_docking_distance + planet.radius],
                                              enemy_ships)) * zone_dominance_factor_for_docking]
    logging.info(f'Good planets: {["P"+str(planet.id) for planet in good_to_dock_planets]}')
    logging.info(f'Time used for good planet determination: {timer.get_time()}')

    potential_rogue_missions = []
    if len(my_unassigned_ships) >= available_ships_for_rogue_mission_trigger:
        for planet_id, changes in planet_ownership_changes.items():
            if changes == 0:
                potential_rogue_missions.append(game_map.get_planet(planet_id))

    good_dock_spots = []
    for planet in good_to_dock_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            good_dock_spots.append(planet)

    fighting_opportunities = (docked_enemy_ships + proximal_enemy_ships) * max_response
    good_opportunities = good_dock_spots + fighting_opportunities
    relative_benefit_factors = [1] * len(good_dock_spots) \
                               + [attacking_relative_benefit] * len(docked_enemy_ships) * max_response \
                               + [defending_relative_benefit] * len(proximal_enemy_ships) * max_response
    opportunities_logging = [f'P{op.id}' if isinstance(op, hlt.entity.Planet) else f'S{op.id}' for op in
                             good_opportunities]
    logging.info(f'opportunities: {opportunities_logging}')

    # 3 JOB ALLOCATION - output: dict orders
    # All orders are placed here - the eventual position may change later on due to position prediction
    orders = {}

    # handle rogue missions
    if len(rogue_missions_id) > 0:
        for ship_id, target in list(rogue_missions_id.items()):
            ship = game_map.get_me().get_ship(ship_id)
            if ship in my_unassigned_ships:
                orders[ship] = target
                my_unassigned_ships.remove(ship)
            else:
                # the ship died
                planet_ownership_changes[rogue_missions_id[ship_id].id] += 1
                del rogue_missions_id[ship_id]
    elif len(potential_rogue_missions) > 0:
        min_dist_alloc = bot_utils.get_minimal_distance_allocation(my_unassigned_ships, potential_rogue_missions)
        rogue_ship = bot_utils.get_shortest_alloc(min_dist_alloc)
        orders[rogue_ship] = min_dist_alloc[rogue_ship]
        my_unassigned_ships.remove(rogue_ship)
        rogue_missions_id[rogue_ship.id] = min_dist_alloc[rogue_ship]
    if len(rogue_missions_id) > 0:
        logging.info(f'rogue_missions: {dict([(ship_id, planet.id) for ship_id, planet in rogue_missions_id.items()])}')

    # minimal_dist_alloc = bot_utils.get_minimal_distance_allocation(my_unassigned_ships, good_opportunities)
    alloc = bot_utils.get_maximal_benefit_allocation(my_unassigned_ships, good_opportunities, relative_benefit_factors,
                                                     job_base_benefit)
    logging_alloc = {f'S{ship.id}': f'P{target.id}' if isinstance(target, hlt.entity.Planet) else f'S{target.id}' for
                     ship, target in alloc.items()}
    logging.info(f'Minimal dist alloc: {logging_alloc}')
    logging.info(f'Time to calculate minimal distance job allocation: {timer.get_time()} ms')

    # sort ships by type of objective
    potential_packs = {fighting_opportunity: [] for fighting_opportunity in fighting_opportunities}
    for ship, target in alloc.items():
        if target in fighting_opportunities:
            potential_packs[target].append(ship)
        elif target in good_dock_spots:
            orders[ship] = target
        my_unassigned_ships.remove(ship)
    for ship in my_unassigned_ships:
        if use_unassigned_ships:
            enemy = bot_utils.get_closest(ship, enemy_ships)
            orders[ship] = enemy
        else:
            my_free_navigation_ships.remove(ship)

    if len(my_unassigned_ships) > 0:
        logging.info(f'Some ships were left unassigned: {[ship.id for ship in my_unassigned_ships]}')

    # create packs from ships with the same objective
    packs = {}
    for target, pack in potential_packs.items():
        if len(pack) > 1:
            leader = bot_utils.get_central_entity(pack)
            packs[leader] = [ship for ship in pack if ship != leader]
            orders[leader] = target
            for ship in packs[leader]:
                orders[ship] = leader
        elif len(pack) == 1:
            orders[pack[0]] = target

    # determine which members of the pack should be tethered
    tethered_followers = {leader: [] for leader in packs}
    for leader in packs:
        for follower in packs[leader]:
            if leader.calculate_distance_between(follower) < tether_dist:
                tethered_followers[leader].append(follower)
                my_free_navigation_ships.remove(follower)
    for leader, followers in tethered_followers.items():
        if len(followers) > 0:
            leader.radius = leader.calculate_distance_between(bot_utils.get_furthest(leader, followers)) + 0.5

    # mission overwrite for safety
    for ship in my_free_navigation_ships:
        number_of_nearby_enemies = len(bot_utils.get_proximity_alerts([ship], [safety_check_radius], mobile_enemies))
        number_of_nearby_friendlies = len(bot_utils.get_proximity_alerts([ship], [safety_check_radius], my_fighting_ships))
        if number_of_nearby_enemies * attack_superiority_ratio > number_of_nearby_friendlies:
            # target the nearest docked ship
            closest_docked_ship = bot_utils.get_closest(ship, my_docked_ships)
            if closest_docked_ship:
                orders[ship] = closest_docked_ship
            else:
                orders[ship] = bot_utils.get_closest(ship, game_map.get_me().all_ships())

    # 4 LOGGING
    logging_orders = {}
    for ship, order in orders.items():
        logging_orders[f'S{ship.id}'] = f'S{order.id}' if isinstance(order, hlt.entity.Ship) else f'P{order.id}'
    logging.info(f'orders: {logging_orders}')
    packs_logging = {}
    for leader, followers in packs.items():
        packs_logging[f'S{leader.id}'] = [f'(S{ship.id})' if ship in tethered_followers[leader] else f'S{ship.id}' for
                                          ship in followers]
    logging.info(f'packs: {packs_logging}')

    # 5 COMMAND GENERATION
    # prepare avoid_entities list
    all_tethered_ships = [ship for leader in tethered_followers for ship in tethered_followers[leader]]
    all_my_flying_obstacles = [ship for ship in my_fighting_ships if ship not in all_tethered_ships]
    avoid_entities = all_planets + all_docked_ships + all_my_flying_obstacles
    for enemy in flying_enemies:
        if enemy in location_prediction:
            avoid_entities.append(location_prediction[enemy])
        else:
            avoid_entities.append(enemy)

    # determine execution order
    execution_order = []
    for ship in packs:
        execution_order.append(ship)
    for ship in my_free_navigation_ships:
        if ship not in execution_order:
            execution_order.append(ship)

    command_queue = []
    for ship in execution_order:  # types of orders to expect: docking, go to enemy, go to leader, mimic leader
        if isinstance(orders[ship], hlt.entity.Planet) and ship.can_dock(orders[ship]):
            command_queue.append(ship.dock(orders[ship]))
            if ship.id in rogue_missions_id:
                del rogue_missions_id[ship.id]
        else:
            avoid_entities.remove(ship)
            if orders[ship] in packs.keys():
                approach_dist = leader_approach_dist
            elif isinstance(orders[ship], hlt.entity.Planet):
                approach_dist = planet_approach_dist
            elif orders[ship] in mobile_enemies:
                approach_dist = dogfighting_approach_dist
            else:
                approach_dist = general_approach_dist
            if orders[ship] in location_prediction:
                target = location_prediction[orders[ship]]
            else:
                target = orders[ship]
            command = ship.smart_navigate(
                ship.closest_point_to(target, min_distance=approach_dist),
                game_map,
                hlt.constants.MAX_SPEED,
                angular_step=angular_step,
                max_corrections=max_corrections,
                max_horizon=max_horizon,
                padding=padding,
                avoid_entities=avoid_entities)
            if command:
                command_queue.append(command)

                if ship in packs.keys():
                    for follower in packs[ship]:
                        if follower in tethered_followers[ship]:
                            command_queue.append(f't {follower.id} {command.split(" ")[2]} {command.split(" ")[3]}')

                new_position = bot_utils.convert_command_to_position_delta(ship, command) + ship
                new_position.radius = ship.radius
            else:
                new_position = ship
            # add motion ghost points
            for i in range(1, motion_ghost_points + 1):
                ghost_point_pos = (ship * (motion_ghost_points + 1 - i) + new_position * i) / (motion_ghost_points + 1)
                ghost_point_pos.radius = ship.radius
                avoid_entities.append(ghost_point_pos)
            avoid_entities.append(new_position)
            location_prediction[ship] = new_position

    delta_time = timer.get_time()
    logging.info(f'Time to calculate trajectories: {delta_time} ms,'
                 f'time per ship: {round(delta_time / (len(my_fighting_ships)+1), 0)} ms')

    # calculation speed throttling
    if delta_time > 1000:
        if motion_ghost_points > 2:
            motion_ghost_points -= 1
            logging.info(f'Decreased motion ghosting to {motion_ghost_points}')
        elif angular_step < 45:
            angular_step += 5
            max_corrections = int(90 / angular_step) + 1
            logging.info(f'Increased angular step to {angular_step}, with max corrections {max_corrections}')
        elif use_unassigned_ships:
            use_unassigned_ships = False
            logging.info(f'Set use_unassigned_ships to FALSE')

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
