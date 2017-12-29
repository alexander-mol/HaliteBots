import hlt
import logging
import bot_utils

game = hlt.Game("Settler-with-graph")

map_graph = hlt.map_graph.MapGraph()

timer = bot_utils.Timer()
t = 0
while True:
    game_map = game.update_map()
    if t == 0:
        map_graph.build_core_graph(game_map)
        logging.info(f'Time to build graph: {timer.get_time()} ms')

    command_queue = []
    for ship in game_map.get_me().all_ships():
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            continue

        for planet in game_map.all_planets():
            if planet.is_owned():
                continue

            if ship.can_dock(planet):
                command_queue.append(ship.dock(planet))
            else:
                navigate_command = ship.smart_navigate(
                    ship.closest_point_to(planet),
                    game_map,
                    speed=int(hlt.constants.MAX_SPEED))
                if t < 10:
                    logging.info(f'Old navigation for {ship.id}: {timer.get_time()} ms, dist: {ship.calculate_distance_between(planet)}')
                    logging.info(f'{ship, planet}')
                    map_graph.get_waypoint(ship, planet)
                    logging.info(f'A* navigation for {ship.id}: {timer.get_time()} ms')
                if navigate_command:
                    command_queue.append(navigate_command)
            break

    game.send_command_queue(command_queue)
    t += 1

