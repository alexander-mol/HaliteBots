import hlt
import bot_utils
import logging
import random
import copy

game = hlt.Game("Aggressive-Hunter")

# parameters
defensive_action_radius = 14

type_table = {}  # e.g. id -> string

t = 0
while True:
    game_map = game.update_map()
    logging.info(f't = {t}')

    if t == 0:
        # initialize ships - 2 builders, 1 hunter
        my_starting_ships = game_map.get_me().all_ships()
        type_table[my_starting_ships[0].id] = 'hunter'
        type_table[my_starting_ships[1].id] = 'hunter'
        type_table[my_starting_ships[2].id] = 'hunter'

    command_queue = []

    # update type table
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]
    logging.info(f'all_my_ship_ids: {all_my_ship_ids}')
    # remove dead guys
    for ship_id in list(type_table.keys()):
        if ship_id not in all_my_ship_ids:
            del type_table[ship_id]
    # add new guys
    for ship in my_fighting_ships:
        if ship.id not in type_table:
            type_table[ship.id] = random.choice(['hunter', 'builder'])

    logging.info(f'type_table: {type_table}')
    # collect map information
    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    docked_enemy_ships = [enemy for enemy in enemy_ships if
                          enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING,
                                                   hlt.entity.Ship.DockingStatus.DOCKED]]

    my_docked_ships = [ship for ship in game_map.get_me().all_ships() if
                       ship.docking_status in [hlt.entity.Ship.DockingStatus.DOCKED,
                                               hlt.entity.Ship.DockingStatus.DOCKING]]

    my_docked_ships_under_attack = [ship for ship in my_docked_ships if bot_utils.is_under_attack(game_map, ship)]
    belligerent_enemies = [e for ship in my_docked_ships_under_attack for e in bot_utils.get_attackers(game_map, ship)]
    if len(my_docked_ships_under_attack) > 0:
        logging.info(f'Docked ships {[ship.id for ship in my_docked_ships_under_attack]} are being attacked!')
        logging.info(f'The attackers are: {[ship.id for ship in belligerent_enemies]}')


    all_planets = game_map.all_planets()
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]
    dockable_spots_list = []
    for planet in non_full_friendly_planets:
        for _ in range(planet.num_docking_spots):
            dockable_spots_list.append(planet)

    # need to assign targets here so that if the dockable spots list becomes empty we can then assign guys to be hunters
    orders = {}
    for ship in my_fighting_ships:
        ship_type = type_table[ship.id]
        if ship_type == 'builder':
            if len(dockable_spots_list) > 0:
                target = bot_utils.pop_closest(ship, dockable_spots_list)
                orders[ship] = target
            else:
                # make this ship a hunter
                type_table[ship.id] = 'hunter'

    # handle orders for hunters here
    # usual hunting tactics
    docked_enemy_ships_full = copy.copy(docked_enemy_ships)
    for ship in my_fighting_ships:
        if ship in orders:
            continue
        ship_type = type_table[ship.id]
        if ship_type == 'hunter':
            if len(docked_enemy_ships) > 0:
                target = bot_utils.pop_closest(ship, docked_enemy_ships)
                orders[ship] = target
            elif len(docked_enemy_ships_full) > 0:
                target = bot_utils.get_closest(ship, docked_enemy_ships_full)
                orders[ship] = target
            else:
                target = bot_utils.get_closest(ship, enemy_ships)
                orders[ship] = target

    # special case - docked ships under attack
    if len(belligerent_enemies) > 0:
        my_hunters = [ship for ship in my_fighting_ships if type_table[ship.id] == 'hunter']
        for enemy in belligerent_enemies:
            if len(my_hunters) > 0:
                closest_hunter = bot_utils.get_closest(enemy, my_hunters)
                if closest_hunter.calculate_distance_between(enemy) < defensive_action_radius:
                    orders[closest_hunter] = enemy
                    my_hunters.remove(closest_hunter)

    # create abbreviated order dict for logging
    logging_orders = {}
    for ship, order in orders.items():
        logging_orders[ship.id] = f'S{order.id}' if isinstance(order, hlt.entity.Ship) else f'P{order.id}'
    logging.info(f'orders: {logging_orders}')

    for ship in orders:
        command = None
        ship_type = type_table[ship.id]
        target = orders[ship]
        if ship_type == 'builder':
            if ship.can_dock(target):
                command = ship.dock(target)
            else:
                command = ship.navigate(
                    ship.closest_point_to(target),
                    game_map,
                    speed=int(hlt.constants.MAX_SPEED),
                    ignore_ships=False)
        elif ship_type == 'hunter':
            command = ship.navigate(
                ship.closest_point_to(target, min_distance=4),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                angular_step=2,
                ignore_ships=False)

        if command:
            command_queue.append(command)

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
