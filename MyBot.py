import hlt
import bot_utils
import logging
import copy

game = hlt.Game("Micro-Manager-Scan-Nav")
game_map = game.update_map()
four_players = len(game_map.all_players()) == 4

# PARAMETERS
# strategic parameters
defensive_action_radius = 40.4
max_response = 15
safe_docking_distance = 15.2
job_base_benefit = 73.4
attacking_relative_benefit = 1.5
defending_relative_benefit = 1.586
central_planet_relative_benefit = 1.04
available_ships_for_rogue_mission_trigger = 17
zone_dominance_factor_for_docking = 3.55
safety_check_radius = 10.59
support_radius = 9.54
attack_superiority_ratio = 0.843
rush_mode_proximity = 82.37
benefit_per_extra_dock_spot = 0.1

# micro movement parameters
fighting_opportunity_merge_distance = 7.3
general_approach_dist = 3.06
dogfighting_approach_dist = 4.89
planet_approach_dist = 2.42
own_ship_approach_dist = 0.02
tether_dist = 0
padding = 0.1
max_horizon = 8.47

if four_players:
    max_response = 4
    central_planet_relative_benefit = 0.9
    safety_check_radius = 17
    attack_superiority_ratio = 1.2

# navigation parameters
angular_step = 5
motion_ghost_points = 6
use_unassigned_ships = True

# cheeky params
health_reduction_for_survival_mode = 0.6

enemy_tracking = {}
planet_ownership_changes = {}
planet_owners = {}
rogue_missions_id = {}
total_health_high_water_mark = 0
collection_points = []

# important lists to keep up-to-date:
# - my_unassigned_ships
# - packs
# - my_free_navigation_ships
# - tethered_followers

t = 0
while True:
    if t > 0:
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

        w = game_map.width
        h = game_map.height
        collection_points = [hlt.entity.Position(1, 1), hlt.entity.Position(w - 1, 1), hlt.entity.Position(1, h - 1),
                             hlt.entity.Position(w - 1, h - 1)]

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
    total_health = 0
    for ship in game_map.get_me().all_ships():
        total_health += ship.health
    if total_health > total_health_high_water_mark:
        total_health_high_water_mark = total_health

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
    dock_spot_relative_benefits = []
    for planet in good_to_dock_planets:
        for _ in range(planet.num_docking_spots - len(planet.all_docked_ships())):
            good_dock_spots.append(planet)
            base_benefit = (max(planet.num_docking_spots, 3) - 3) * benefit_per_extra_dock_spot + 1
            if planet.id in [0, 1, 2, 3]:
                dock_spot_relative_benefits.append(base_benefit * central_planet_relative_benefit)
            else:
                dock_spot_relative_benefits.append(base_benefit)

    fighting_opportunities = (docked_enemy_ships + proximal_enemy_ships) * max_response
    good_opportunities = good_dock_spots + fighting_opportunities
    relative_benefit_factors = dock_spot_relative_benefits \
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

    alloc = bot_utils.get_maximal_benefit_allocation(my_unassigned_ships, good_opportunities, relative_benefit_factors,
                                                     job_base_benefit)
    logging_alloc = {f'S{ship.id}': f'P{target.id}' if isinstance(target, hlt.entity.Planet) else f'S{target.id}' for
                     ship, target in alloc.items()}
    logging.info(f'Minimal dist alloc: {logging_alloc}')
    logging.info(f'Time to calculate minimal distance job allocation: {timer.get_time()} ms')

    # rushing
    if len(my_docked_ships) == 0 and len(my_fighting_ships) <= 3 and len(game_map.all_players()) == 2:
        if len(bot_utils.get_proximity_alerts(my_fighting_ships, [rush_mode_proximity] * len(my_fighting_ships),
                                              enemy_ships)) > 1:
            closest_enemy = bot_utils.get_closest(my_fighting_ships[0], enemy_ships)
            fighting_opportunities.append(closest_enemy)
            alloc = {}
            for ship in my_fighting_ships:
                alloc[ship] = closest_enemy

    # merge fighting opportunities if they are close
    merged_fighting_opp_map = {}
    for i, ship1 in enumerate(fighting_opportunities):
        for j, ship2 in enumerate(fighting_opportunities):
            if i >= j:
                continue
            if ship1.calculate_distance_between(ship2) < fighting_opportunity_merge_distance:
                if len([ship for ship in alloc.values() if ship is ship1]) > \
                        len([ship for ship in alloc.values() if ship is ship2]):
                    merged_fighting_opp_map[ship2] = ship1
                else:
                    merged_fighting_opp_map[ship1] = ship2
    for ship in fighting_opportunities:
        if ship not in merged_fighting_opp_map:
            merged_fighting_opp_map[ship] = ship

    # sort ships by type of objective
    potential_packs = {fighting_opportunity: [] for fighting_opportunity in merged_fighting_opp_map.values()}
    for ship, target in alloc.items():
        if target in fighting_opportunities:
            potential_packs[merged_fighting_opp_map[target]].append(ship)
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
    followers = []
    for target, pack in potential_packs.items():
        if len(pack) > 1:
            leader = bot_utils.get_closest(target, pack)  # bot_utils.get_central_entity(pack)
            pack_followers = [ship for ship in pack if ship != leader]
            followers.extend(pack_followers)
            packs[leader] = pack_followers
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
            new_radius = leader.calculate_distance_between(bot_utils.get_furthest(leader, followers)) + 0.5
            planet_too_close = False
            for planet in all_planets:
                if planet.radius + new_radius > planet.calculate_distance_between(leader):
                    planet_too_close = True
            if not planet_too_close:
                leader.radius = new_radius
            else:
                for ship in tethered_followers[leader]:
                    my_free_navigation_ships.append(ship)
                tethered_followers[leader] = []

    # survival mode overwrites
    if total_health <= int(total_health_high_water_mark * (1 - health_reduction_for_survival_mode)) and \
            len(game_map.all_players()) == 4:
        for ship in my_fighting_ships:
            orders[ship] = bot_utils.get_closest(ship, collection_points)

    # mission overwrite for safety
    for ship in my_free_navigation_ships:
        if ship in followers:
            continue
        nearby_mobile_enemies = bot_utils.get_proximity_alerts([ship], [safety_check_radius], mobile_enemies)
        if len(nearby_mobile_enemies) > 0:
            nearest_enemy = bot_utils.get_closest(ship, nearby_mobile_enemies)
            enemy_att = len(bot_utils.get_proximity_alerts([nearest_enemy], [support_radius], mobile_enemies))
            enemy_def = len(bot_utils.get_proximity_alerts([nearest_enemy], [support_radius], enemy_ships))
            my_att = len(bot_utils.get_proximity_alerts([ship], [support_radius], my_fighting_ships))
            if enemy_att / my_att * attack_superiority_ratio > my_att / enemy_def:
                # target the nearest docked ship
                closest_docked_ship = bot_utils.get_closest(ship, my_docked_ships)
                if closest_docked_ship:
                    orders[ship] = closest_docked_ship
                else:
                    friendlies = [friendly for friendly in game_map.get_me().all_ships() if friendly is not ship]
                    if len(friendlies) == 0:
                        orders[ship] = bot_utils.extend_ray(nearest_enemy, ship, 10)
                    else:
                        orders[ship] = bot_utils.get_closest(ship, friendlies)

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
    queue_entities = copy.copy(my_fighting_ships)

    # determine execution order
    leaders = sorted(packs.keys(), key=lambda x: x.calculate_distance_between(location_prediction[orders[x]]) \
                     if orders[x] in location_prediction else x.calculate_distance_between(orders[x]))
    other_ships = [ship for ship in my_free_navigation_ships if ship not in leaders]
    others = sorted(other_ships, key=lambda x: x.calculate_distance_between(location_prediction[orders[x]]) \
                    if orders[x] in location_prediction else x.calculate_distance_between(orders[x]))
    execution_order = leaders + others

    command_queue = []
    for ship in execution_order:  # types of orders to expect: docking, go to enemy, go to leader, mimic leader
        if isinstance(orders[ship], hlt.entity.Planet) and ship.can_dock(orders[ship]):
            command_queue.append(ship.dock(orders[ship]))
            if ship.id in rogue_missions_id:
                del rogue_missions_id[ship.id]
        else:
            avoid_entities.remove(ship)
            queue_entities.remove(ship)
            if orders[ship] in game_map.get_me().all_ships():
                approach_dist = own_ship_approach_dist
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
            command = ship.scan_navigate(
                ship.closest_point_to(target, min_distance=approach_dist),
                game_map,
                angular_step=angular_step,
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
                ghost_point_pos.radius = ship.radius + own_ship_approach_dist
                avoid_entities.append(ghost_point_pos)
                queue_entities.append(ghost_point_pos)
            avoid_entities.append(new_position)
            queue_entities.append(new_position)
            location_prediction[ship] = new_position

    delta_time = timer.get_time()
    logging.info(f'Time to calculate trajectories: {delta_time} ms,'
                 f'time per ship: {round(delta_time / (len(my_fighting_ships)+1), 0)} ms')

    # calculation speed throttling
    if delta_time > 1000:
        if motion_ghost_points > 4:
            motion_ghost_points -= 1
            logging.info(f'Throttling: Decreased motion ghosting to {motion_ghost_points}')
        elif angular_step < 45:
            angular_step += 5
            logging.info(f'Throttling: Increased angular step to {angular_step}')
        elif use_unassigned_ships:
            use_unassigned_ships = False
            logging.info(f'Throttling: Set use_unassigned_ships to FALSE')

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
