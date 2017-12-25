import hlt
import bot_utils
import logging
import random
import copy

game = hlt.Game("Hunter-Builder")
logging.info("Starting my Settler bot!")

type_table = {}  # e.g. id -> string
hunter_targets = {}  # e.g. id -> enemy ships by id
builder_targets = {}  # e.g. id -> planets by id

t = 0
while True:
    game_map = game.update_map()
    command_queue = []

    # update type table
    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if
                         ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    all_my_ship_ids = [ship.id for ship in game_map.get_me().all_ships()]
    logging.info(f'all_my_ship_ids: {all_my_ship_ids}')
    logging.info(f'type_table before updates: {type_table}')
    # remove dead guys
    for ship_id in list(type_table.keys()):
        if ship_id not in all_my_ship_ids:
            del type_table[ship_id]
            try:
                del hunter_targets[ship_id]
            except:
                pass
            try:
                del builder_targets[ship_id]
            except:
                pass
    # add new guys
    for ship in my_fighting_ships:
        if ship.id not in type_table:
            type_table[ship.id] = random.choice(['hunter', 'builder'])

    logging.info(f'type_table after: {type_table}')
    # collect map information
    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    docked_enemy_ships = [enemy for enemy in enemy_ships if
                          enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING,
                                                   hlt.entity.Ship.DockingStatus.DOCKED]]

    ship_directory = {}
    for player in game_map.all_players():
        for ship in player.all_ships():
            ship_directory[ship.id] = ship

    all_planets = game_map.all_planets()
    non_full_friendly_planets = [planet for planet in all_planets if
                                 planet.owner in [None, game_map.get_me()] and not planet.is_full()]
    dockable_spots_list = []
    for planet in non_full_friendly_planets:
        for _ in range(planet.num_docking_spots):
            dockable_spots_list.append(planet)

    # remove already scheduled dockspots
    taken_ids = list(builder_targets.values())
    for taken_id in taken_ids:
        found = False
        for i in range(len(dockable_spots_list)):
            if dockable_spots_list[i].id == taken_id:
                dockable_spots_list.remove(dockable_spots_list[i])
                found = True
                break
        if not found:
            # if a previously scheduled dock spot is no longer available - remove the order
            for ship_id in list(builder_targets.keys()):
                if builder_targets[ship_id] == taken_id:
                    del builder_targets[ship_id]

    # remove already scheduled enemy ships
    # taken_ids = list(hunter_targets.values())
    # for taken_id in taken_ids:
    #     found = False
    #     for i in range(len(docked_enemy_ships)):
    #         if docked_enemy_ships[i].id == taken_id:
    #             docked_enemy_ships.remove(docked_enemy_ships[i])
    #             found = True
    #             break
    #     if not found:
    #         # if a previously scheduled enemy spot is no longer available - remove the order
    #         for ship_id in list(hunter_targets.keys()):
    #             if hunter_targets[ship_id] == taken_id:
    #                 del hunter_targets[ship_id]

    # need to assign targets here so that if the dockable spots list becomes empty we can then assign guys to be hunters
    orders = {}
    for ship in my_fighting_ships:
        ship_type = type_table[ship.id]
        if ship_type == 'builder':
            if ship.id in builder_targets:
                target_id = builder_targets[ship.id]
                target = game_map.get_planet(target_id)
                orders[ship] = target
            else:
                if len(dockable_spots_list) > 0:
                    target = bot_utils.pop_closest(ship, dockable_spots_list)
                    builder_targets[ship.id] = target.id
                    orders[ship] = target
                else:
                    # make this ship a hunter
                    type_table[ship.id] = 'hunter'

    # handle orders for hunters here
    docked_enemy_ships_full = copy.copy(docked_enemy_ships)
    for ship in my_fighting_ships:
        ship_type = type_table[ship.id]
        if ship_type == 'hunter':
            # if ship.id in hunter_targets:
            #     target_id = hunter_targets[ship.id]
            #     target = ship_directory[target_id]
            #     orders[ship] = target
            # else:
            if len(docked_enemy_ships) > 0:
                target = bot_utils.pop_closest(ship, docked_enemy_ships)
                hunter_targets[ship.id] = target.id
                orders[ship] = target
            elif len(docked_enemy_ships_full) > 0:
                target = bot_utils.get_closest(ship, docked_enemy_ships_full)
                hunter_targets[ship.id] = target.id
                orders[ship] = target
            else:
                # just wait
                pass

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
                ship.closest_point_to(target, min_distance=2),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=False)

        if command:
            command_queue.append(command)

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
