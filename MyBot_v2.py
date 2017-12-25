"""
Welcome to your first Halite-II bot!

This bot's name is Settler. It's purpose is simple (don't expect it to win complex games :) ):
1. Initialize game
2. If a ship is not docked and there are unowned planets
2.a. Try to Dock in the planet if close enough
2.b If not, go towards the planet

Note: Please do not place print statements here as they are used to communicate with the Halite engine. If you need
to log anything use the logging module.
"""
# Let's start by importing the Halite Starter Kit so we can interface with the Halite engine
import hlt
# Then let's import the logging module so we can print out information
import logging
import random

# parameters
prob_reinforce = 0.1


def get_non_owned_planets_proximity_list():
    ship_to_planet_proximity_list = {}
    for ship in game_map.get_me().all_ships():
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue
        entities_by_distance = game_map.nearby_entities_by_distance(ship)
        planets_in_distance_order = []
        for distance in sorted(entities_by_distance):
            planets_in_distance_order.extend([(entity, distance) for entity in entities_by_distance[distance] if
                                              isinstance(entity,
                                                         hlt.entity.Planet) and entity.owner != game_map.get_me()])
        ship_to_planet_proximity_list[ship] = planets_in_distance_order
    return ship_to_planet_proximity_list

# GAME START
# Here we define the bot's name as Settler and initialize the game, including communication with the Halite engine.
game = hlt.Game("Settler")
# Then we print our start message to the logs
logging.info("Starting my Settler bot!")

while True:
    # TURN START
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()
    mission_dict = {}
    for ship in game_map.get_me().all_ships():
        if ship in mission_dict:
            continue
        else:
            mission_dict[ship] = 'reinforce'
            


    # determine ship targets for rapid colonization
    ship_to_non_owned_planet_proximity_list = get_non_owned_planets_proximity_list()

    ship_to_target_map = {}
    for ship in game_map.get_me().all_ships():
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue
        for planet, distance in ship_to_non_owned_planet_proximity_list[ship]:
            if planet not in ship_to_target_map.values():
                ship_to_target_map[ship] = planet
                break
        if ship not in ship_to_target_map:
            try:
                ship_to_target_map[ship] = ship_to_non_owned_planet_proximity_list[ship][0][0]
            except:
                ship_to_target_map[ship] = random.choice(game_map.all_planets())



    # Here we define the set of commands to be sent to the Halite engine at the end of the turn
    command_queue = []
    my_non_full_planets = [planet for planets in game_map.all_planets() if
                           planet.owner == game_map.get_me() and not planet.is_full()]
    # For every ship that I control
    for ship in game_map.get_me().all_ships():
        # If the ship is docked
        command = None
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue

        target_planet = ship_to_target_map[ship]


        for planet in my_non_full_planets:
            if ship.can_dock(planet) and random.random() < prob_stay:
                command = ship.dock(planet)

        if command is None:
            if ship.can_dock(target_planet):
                if target_planet.owner is None or target_planet.owner == game_map.get_me():
                    command = ship.dock(target_planet)
                else:
                    enemy = target_planet.all_docked_ships()[0]
                    command = ship.navigate(
                        ship.closest_point_to(enemy),
                        game_map,
                        speed=int(hlt.constants.MAX_SPEED),
                        ignore_ships=False)

        if command is None:
            command = ship.navigate(
                ship.closest_point_to(target_planet),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=False)
        # If the move is possible, add it to the command_queue (if there are too many obstacles on the way
        # or we are trapped (or we reached our destination!), navigate_command will return null;
        # don't fret though, we can run the command again the next turn)
        if command:
            command_queue.append(command)

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
