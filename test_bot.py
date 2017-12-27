import hlt
import logging

game = hlt.Game("Test-Bot")

t = 0
while True:
    game_map = game.update_map()

    command_queue = []

    target = hlt.entity.Position(game_map.width-1, game_map.height-1)

    for ship in game_map.get_me().all_ships():
        command = ship.navigate(target, game_map, 3)
        if command:
            command_queue.append(command)

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    t += 1
