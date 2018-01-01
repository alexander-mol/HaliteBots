import hlt
import bot_utils
import logging
import copy

game = hlt.Game("Settler-Improved")

"""
TO TEST IF A MORE EXPANSIVE SETTLING STRATEGY IS USEFUL - RESULT: NO
"""

# PARAMETERS
# strategic parameters
defensive_action_radius = 33.2
max_response = 5
safe_docking_distance = 10.9
job_base_benefit = 80.7
fighting_relative_benefit = 1.5
available_ships_for_rogue_mission_trigger = 12

# micro movement parameters
general_approach_dist = 3.7
planet_approach_dist = 3.46
leader_approach_dist = 0.8
tether_dist = 2.0
padding = 0.14
motion_ghost_points = 4

# navigation parameters
angular_step = 5
horizon_reduction_factor = 0.99
max_corrections = int(90 / angular_step) + 1
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
    location_prediction = {}
    for enemy_id in enemy_tracking_new:
        if enemy_id in enemy_tracking:
            enemy = [enemy for enemy in enemy_ships if enemy.id == enemy_id][0]
            location_prediction[enemy] = (2 * enemy_tracking_new[enemy_id] - enemy_tracking[enemy_id])
    enemy_tracking = enemy_tracking_new

    planet_defense_radii = [planet.radius + defensive_action_radius for planet in my_planets]
    proximal_enemy_ships = bot_utils.get_proximity_alerts(my_planets, planet_defense_radii, enemy_ships)

    if len(proximal_enemy_ships) > 0:
        logging.info(f'Enemy ships nearby: {[ship.id for ship in proximal_enemy_ships]}')

    # 2 STRATEGIC CALCULATIONS & JOB CREATION - output: list good_opportunities
    good_to_dock_planets = \
        [planet for planet in non_full_friendly_planets
         if bot_utils.get_proximity(planet, enemy_ships) > safe_docking_distance + planet.radius]
    logging.info(f'Good planets: {["P"+str(planet.id) for planet in good_to_dock_planets]}')
    logging.info(f'Time used for good planet determination: {timer.get_time()}')

    good_dock_spots = []
    for planet in good_to_dock_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            good_dock_spots.append(planet)

    # 3 JOB ALLOCATION - output: dict orders
    # All orders are placed here - the eventual position may change later on due to position prediction
    orders = {}
    alloc = bot_utils.get_minimal_distance_allocation(my_unassigned_ships, good_to_dock_planets)
    for ship in my_unassigned_ships:
        if ship in alloc:
            orders[ship] = alloc[ship]
        else:
            orders[ship] = ship

    # 5 COMMAND GENERATION
    # prepare avoid_entities list
    all_my_flying_obstacles = [ship for ship in my_fighting_ships]
    avoid_entities = all_planets + all_docked_ships + all_my_flying_obstacles
    for enemy in flying_enemies:
        if enemy in location_prediction:
            avoid_entities.append(location_prediction[enemy])
        else:
            avoid_entities.append(enemy)

    # determine execution order
    execution_order = []
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
            if orders[ship] in all_planets:
                approach_dist = planet_approach_dist
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
                horizon_reduction_factor=horizon_reduction_factor,
                padding=padding,
                avoid_entities=avoid_entities)
            if command:
                command_queue.append(command)

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

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
