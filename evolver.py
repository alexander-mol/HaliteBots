import subprocess
import re
import logging
import copy
import random
import time
import _pickle
import scipy.stats
import sys

# evolutionary algorithm parameters
pop_size = 4
num_generations = 200
fitness_num_games = 50
mutation_rate = 0.25
mutation_magnitude = 0.25

# map parameters
map_width = 288  # 288
map_height = 192  # 192

# competing bots
rl_default_bot = 'micro-manager_rl_default.py'
evolving_bot = 'micro-manager_evolved.py'
comparison_bot = 'micro-manager.py'

# initialize pop
# base_params = {'defensive_action_radius': 34.6, 'max_response': 5, 'safe_docking_distance': 12.5,
#                'job_base_benefit': 81.3, 'attacking_relative_benefit': 1.5, 'defending_relative_benefit': 1.5,
#                'central_planet_relative_benefit': 1.0, 'available_ships_for_rogue_mission_trigger': 12,
#                'zone_dominance_factor_for_docking': 10, 'safety_check_radius': 10.0, 'support_radius': 10.0,
#                'attack_superiority_ratio': 1.5, 'rush_mode_proximity': 70.0, 'general_approach_dist': 3.7,
#                'dogfighting_approach_dist': 3.7, 'planet_approach_dist': 3.45, 'own_ship_approach_dist': 0.77,
#                'tether_dist': 1.81}
base_params = {'max_response': 8,
               'job_base_benefit': 71.6, 'attacking_relative_benefit': 1.5, 'defending_relative_benefit': 1.385,
               'central_planet_relative_benefit': 1.0,
               'zone_dominance_factor_for_docking': 4.0, 'safety_check_radius': 12.0, 'support_radius': 8.0,
               'attack_superiority_ratio': 1.13, 'rush_mode_proximity': 72.8,
               'own_ship_approach_dist': 0.77,
               'tether_dist': 1.81}

rl_new_params = {'defensive_action_radius': 56.189, 'max_response': 14, 'safe_docking_distance': 15.234,
                 'job_base_benefit': 70.755, 'attacking_relative_benefit': 1.193, 'defending_relative_benefit': 1.302,
                 'available_ships_for_rogue_mission_trigger': 10, 'zone_dominance_factor_for_docking': 2.847,
                 'safety_check_radius': 11.567, 'attack_superiority_ratio': 1.018, 'general_approach_dist': 3.367,
                 'dogfighting_approach_dist': 2.956, 'planet_approach_dist': 3.451, 'leader_approach_dist': 0.348,
                 'tether_dist': 1.324, 'padding': 0.079}

t0 = time.time()
logging.basicConfig(level=logging.INFO, filename='./evolver_log', filemode='w')
logger = logging.getLogger(__name__)


def message(text):
    logger.info(text)
    print(text)


def get_query(i, bot1=None, bot2=None, timeouts=True):
    path = '/Users/student/Desktop/Local Files/Projects/Halite2_Python3_MacOS/halite'
    if not bot1 and not bot2:
        bot1, bot2 = evolving_bot, comparison_bot
    elif not (bot1 and bot2):
        print('Only one bot given!')
        exit()
    if i % 2 == 1:
        bot1, bot2 = bot2, bot1
    query = ['-d', f'{map_width} {map_height}', f'python3 {bot1}', f'python3 {bot2}']
    if not timeouts:
        query.append('-t')
    return [path] + query, 0 if bot1 == evolving_bot else 1


def get_query_windows(i, bot1=None, bot2=None, timeouts=True):
    path = 'C:/Users/alexa/Documents/Halite2_Python3_Windows/halite.exe'
    if not bot1 and not bot2:
        bot1, bot2 = evolving_bot, comparison_bot
    elif not (bot1 and bot2):
        print('Only one bot given!')
        exit()
    if i % 2 == 1:
        bot1, bot2 = bot2, bot1
    query = ['-d', f'{map_width} {map_height}', f'python {bot1}', f'python {bot2}']
    if not timeouts:
        query.append('-t')
    return [path] + query, 0 if bot1 == evolving_bot else 1


def run_game(i, bot1, bot2):
    if sys.platform == 'win32':
        query, target_pos = get_query_windows(i, bot1, bot2)
    else:
        query, target_pos = get_query(i, bot1, bot2)
    result = subprocess.run(query, stdout=subprocess.PIPE).stdout.decode('utf-8')
    rank = re.findall(f'Player #{target_pos}, .*?, came in rank #(.*?) and', result)[0]
    ship_prod = re.findall(f'producing (\d*?) ships', result)
    logger.info(re.sub('Turn (.*?)\n', '', result))
    return rank == '1', int(ship_prod[i % 2]), int(ship_prod[(i + 1) % 2])


def get_fitness(num_games, id=None, feedback=False, early_stop_bad=False, early_stop_good=False,
                early_stop_trigger=0.05, bot1=None, bot2=None):
    win_count = 0
    ships_target, ships_opponent = 0, 0
    for i in range(num_games):
        if id:
            i = id + str(i)
        outcome, ships_t, ships_o = run_game(i, bot1, bot2)
        win_count += outcome
        ships_target += ships_t
        ships_opponent += ships_o
        ph0 = get_p_null_hypothesis(win_count, i + 1)
        log_message = f'At game {i+1} of {num_games}. Target won {win_count} / {i+1}, or' \
                      f' {round(100*win_count/(i+1))}%. p(H0) = {ph0}, running average time per game:' \
                      f' {round((time.time() - t0)/(i+1), 1)}. Ships produced by target {ships_target} vs ' \
                      f'{ships_opponent} for opponent, ' \
                      f'proportion: {round(ships_target / (ships_opponent + ships_target + 1), 2)}'
        if feedback:
            print(log_message)
        logger.info(log_message)
        if (ph0 > 1 - early_stop_trigger) and early_stop_bad or (ph0 < early_stop_trigger) and early_stop_good:
            logging.info(
                f'Made early stop after {i} games (target won {win_count}). Probability of null hypothesis: {ph0}')
            num_games = i + 1
            break
    return win_count / num_games, ships_target / (ships_opponent + ships_target + 1)


def get_p_null_hypothesis(successes, num_samples):
    p = scipy.stats.binom(num_samples, 0.5).pmf(successes) / 2
    for i in range(successes + 1, num_samples + 1):
        p += scipy.stats.binom(num_samples, 0.5).pmf(i)
    return round(p, 3)


def set_params(params_dict, script_name=None):
    if not script_name:
        script_name = 'micro-manager_evolved.py'
    with open(script_name, 'r') as f:
        script = f.read()
    for param, value in params_dict.items():
        regex = f'\n{param} = [\d\.]*?\n'
        replacement = f'\n{param} = {value}\n'
        script = re.sub(regex, replacement, script)
    with open(script_name, 'w') as f:
        f.write(script)


def mutate(dna):
    for key, value in dna.items():
        if random.random() < mutation_rate:
            if isinstance(value, int):
                value += random.choice([-1, 1])
            else:
                value *= 1 + (2 * random.random() - 1) * mutation_magnitude
        dna[key] = value


def combine(dna1, dna2):
    dna_new = {}
    for key, value in dna1.items():
        if random.random() < 0.5:
            dna_new[key] = value
        else:
            dna_new[key] = dna2[key]
    return dna_new


def run_reinforcement_learning():
    default_player = base_params
    set_params(default_player, rl_default_bot)
    swaps = 0
    t = time.time()
    for gen_i in range(num_generations):
        augmented_player = copy.copy(default_player)
        mutate(augmented_player)
        set_params(augmented_player, evolving_bot)
        logging.info(f'------------------------------------------------------------------------------------------------'
                     f'-------------')
        logging.info(f'default_player: {default_player}')
        logging.info(f'augmented_player: {augmented_player}')
        fitness = get_fitness(fitness_num_games, early_stop_bad=True, early_stop_good=True, bot1=rl_default_bot,
                              bot2=evolving_bot)[0]
        if fitness > 0.5:
            default_player = augmented_player
            set_params(augmented_player, rl_default_bot)
            swaps += 1
            message(f'-- Default player was replaced by augmented player, swaps: {swaps}.')
        dp_print_dict = {key: round(value, 3) for key, value in default_player.items()}
        ap_print_dict = {key: round(value, 3) for key, value in augmented_player.items()}
        message(f'Gen {gen_i}, {round(time.time() - t)} s, default_player: {dp_print_dict}, '
                f'augmented_player: {ap_print_dict}')
        t = time.time()


def run_evolution(use_cache=False):
    # if use_cache:
    #     with open('pop_cache.p', 'rb') as f:
    #         pop_cache = _pickle.load(f)
    # else:
    #     pop_cache = []
    # pop = []
    # for i in range(pop_size):
    #     if i < len(pop_cache):
    #         pop.append(pop_cache[i])
    #     else:
    #         pop.append((copy.copy(base_params), None))
    #
    # for i, ind in enumerate(pop):
    #     set_params(ind[0])
    #     pop[i] = (ind[0], get_fitness(fitness_num_games)[0])
    pop = [(copy.copy(base_params), 0.0) for _ in range(pop_size)]

    mid_point = round(pop_size / 2)

    t = time.time()
    for gen_i in range(num_generations):

        # mutate
        for ind in pop[mid_point:]:
            mutate(ind[0])

        # fitness
        for i, ind in enumerate(pop[mid_point:]):
            set_params(ind[0])
            pop[mid_point + i] = (ind[0], get_fitness(fitness_num_games, early_stop_bad=True)[0])

        # sort
        pop.sort(key=lambda x: -x[1])

        # store results
        with open('pop_cache.p', 'wb') as f:
            _pickle.dump(pop, f)

        # generate new individuals
        for i in range(mid_point, len(pop)):
            father_i = random.randint(0, mid_point - 1)
            mother_i = random.randint(0, mid_point - 1)
            pop[i] = (combine(pop[father_i][0], pop[mother_i][0]), None)

        print(f'Gen {gen_i}, {round(time.time() - t)} s, max_fitness = {pop[0][1]} using: {pop[0][0]}')
        t = time.time()
    print(
        f'Finished in {round(t - t0)} s, or {round((t - t0)/(pop_size * num_generations * fitness_num_games), 1)} per game.')


# set_params(rl_new_params, 'micro-manager_evolved.py')
# run_reinforcement_learning()
# run_evolution()
print(get_fitness(200, feedback=True))
