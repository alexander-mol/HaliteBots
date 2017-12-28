import hlt
import numpy as np
import bot_utils

discount_rate = 0.08
killspot_success_rate = 0.5


def get_benefit(ship, target, t, existing_orders, game_map):
    if isinstance(target, hlt.entity.Planet):
        return get_benefit_dockspot(ship, target, t, existing_orders)
    elif target.docking_status != hlt.entity.Ship.DockingStatus.UNDOCKED:
        return get_benefit_killspot(ship, target, t, existing_orders)
    else:
        return get_benefit_planet_defense(ship, target, t, existing_orders, game_map)


def get_benefit_dockspot(ship, planet, t, existing_orders):
    dist = ship.calculate_distance_between(ship.closest_point_to(planet))
    time_to_payoff = int(np.ceil(dist / 7)) + 5
    dock_spots = planet.num_docking_spots
    # if planet not in existing_orders.values():
    #     payoffs = np.zeros(300 - t)
    #     payoffs[time_to_payoff:] = 1
    #     for i in range(dock_spots - 1):
    #         t_increase = int(np.ceil(12 / (i + 1)))
    #         payoffs[time_to_payoff + t_increase:] += 1
    #     return np.npv(discount_rate, payoffs)
    # else:
    payoffs = np.zeros(300 - t)
    payoffs[time_to_payoff:] = 1
    return np.npv(discount_rate, payoffs)


def get_benefit_killspot(ship, enemy, t, existing_orders):
    dist = ship.calculate_distance_between(ship.closest_point_to(enemy))
    time_to_payoff = int(np.ceil(dist / 7)) + 4
    payoffs = np.zeros(300 - t)
    payoffs[time_to_payoff:] = 1
    # support = len([supporter for supporter in existing_orders if existing_orders[supporter] is enemy])
    return np.npv(discount_rate, payoffs) * killspot_success_rate


def get_benefit_planet_defense(ship, enemy, t, existing_orders, game_map):
    dist = ship.calculate_distance_between(ship.closest_point_to(enemy))
    time_to_payoff = int(np.ceil(dist / 7)) + 4
    my_planets = [planet for planet in game_map.all_planets() if planet.owner == game_map.get_me()]
    this_planet = bot_utils.get_closest(enemy, my_planets)
    num_builders_in_jeopardy = len(this_planet._docked_ships)
    payoffs = np.zeros(300 - t)
    payoffs[time_to_payoff:] = 1
    for i in range(num_builders_in_jeopardy - 1):
        payoffs[:time_to_payoff + i * 4] += 1
    return np.npv(discount_rate, payoffs)
