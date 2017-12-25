import hlt
import logging
import bot_utils


game = hlt.Game("Killer")
logging.info("Starting my Settler bot!")

t = 0
while True:
    game_map = game.update_map()
    command_queue = []

    enemy_ships = bot_utils.get_all_enemy_ships(game_map)
    docked_enemy_ships = [enemy for enemy in enemy_ships if enemy.docking_status in [hlt.entity.Ship.DockingStatus.DOCKING, hlt.entity.Ship.DockingStatus.DOCKED]]

    my_fighting_ships = [ship for ship in game_map.get_me().all_ships() if ship.docking_status == hlt.entity.Ship.DockingStatus.UNDOCKED]
    # logging.info(f'fighting ships: {my_fighting_ships}')

    logging.info(f'{game_map.all_planets(), game_map.all_players()[0].all_ships(), game_map.all_players()[1].all_ships()}')

    for i, ship in enumerate(my_fighting_ships):
        command = None
        if len(docked_enemy_ships) > i:
            target = docked_enemy_ships[i]

            command = ship.navigate(
                ship.closest_point_to(target),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=False)
        # nearest_planet = bot_utils.get_nearest_friendly_non_full_planet(game_map, ship)
        #
        # if ship.can_dock(nearest_planet):
        #     command = ship.dock(nearest_planet)
        # else:
        #     command = ship.navigate(
        #         ship.closest_point_to(nearest_planet),
        #         game_map,
        #         speed=int(hlt.constants.MAX_SPEED),
        #         ignore_ships=False)


        if command:
            command_queue.append(command)

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
    t += 1
# GAME END
