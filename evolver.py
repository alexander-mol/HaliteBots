import subprocess
import re
import logging
import copy
import random
import time
import _pickle
import scipy.stats

# evolutionary algorithm parameters
pop_size = 12
num_generations = 100
fitness_num_games = 16
mutation_rate = 0.5
mutation_magnitude = 0.5

# map parameters
map_width = 300  # 288
map_height = 200  # 192

# competing bots
evolving_bot = 'micro-manager_evolved.py'
comparison_bot = 'micro-manager.py'

t0 = time.time()
logging.basicConfig(level=logging.INFO, filename='./evolver_log', filemode='w')
logger = logging.getLogger(__name__)


def get_query(i):
    path = '/Users/student/Desktop/Local Files/Projects/Halite2_Python3_MacOS/halite'
    bot1, bot2 = evolving_bot, comparison_bot
    if i % 2 == 1:
        bot1, bot2 = bot2, bot1
    query = ['-d', f'{map_width} {map_height}', f'python3 {bot1}', f'python3 {bot2}']
    return [path] + query, 0 if bot1 == evolving_bot else 1

def run_game(i):
    query, target_pos = get_query(i)
    result = subprocess.run(query, stdout=subprocess.PIPE).stdout.decode('utf-8')
    rank = re.findall(f'Player #{target_pos}, .*?, came in rank #(.*?) and', result)[0]
    logger.info(re.sub('Turn (.*?)\n', '', result))
    return rank == '1'

def get_fitness(num_games, id=None, feedback=False):
    win_count = 0
    for i in range(num_games):
        if id:
            i = id + str(i)
        if run_game(i):
            win_count += 1
        if feedback:
            print(f'At game {i+1} of {num_games}. Target won {win_count} / {i+1}, '
                  f'or {round(100*win_count/(i+1))}%. p(H0) = {get_p_null_hypothesis(win_count, i+1)}, '
                  f'running average time per game: {round((time.time() - t0)/(i+1), 1)}')
    return win_count / num_games

def get_p_null_hypothesis(successes, num_samples):
    p = 0
    for i in range(successes, num_samples + 1):
        p += scipy.stats.binom(num_samples, 0.5).pmf(i)
    return round(p, 3)

def set_params(params_dict, with_round=False):
    with open('micro-manager_evolved.py', 'r') as f:
        script = f.read()
    for param, value in params_dict.items():
        regex = f'\n{param} = [\d\.]*?\n'
        if with_round:
            replacement = f'\n{param} = {round(value, 2)}\n'
        else:
            replacement = f'\n{param} = {value}\n'
        script = re.sub(regex, replacement, script)
    with open('micro-manager_evolved.py', 'w') as f:
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

def run_evolution():
    # initialize pop
    base_params = {'defensive_action_radius': 33.22346939590352, 'max_response': 4, 'safe_docking_distance': 15.90991149809392, 'job_base_benefit': 79.7295501179922, 'fighting_relative_benefit': 1.572854795198809, 'available_ships_for_rogue_mission_trigger': 12, 'zone_dominance_factor_for_docking': 2.0, 'general_approach_dist': 2.842128273421315, 'planet_approach_dist': 2.427450916328799, 'leader_approach_dist': 0.7613118205454873, 'tether_dist': 2.3797253838512864, 'padding': 0.11081714461786406, 'motion_ghost_points': 6}
    with open('pop_cache.p', 'rb') as f:
        pop_cache = _pickle.load(f)
    pop = []
    for i in range(pop_size):
        if i < len(pop_cache):
            pop.append(pop_cache[i])
        else:
            pop.append((copy.copy(base_params), None))

    mid_point = round(pop_size / 2)

    t = time.time()
    for gen_i in range(num_generations):

        # mutate
        for ind in pop[mid_point:]:
            mutate(ind[0])

        # fitness
        for i, ind in enumerate(pop[mid_point:]):
            set_params(ind[0])
            pop[mid_point + i] = (ind[0], get_fitness(fitness_num_games))

        # sort
        pop.sort(key=lambda x: -x[1])

        # store results
        with open('pop_cache.p', 'wb') as f:
            _pickle.dump(pop, f)

        # generate new individuals
        for i in range(mid_point, len(pop)):
            father_i = random.randint(0, mid_point-1)
            mother_i = random.randint(0, mid_point-1)
            pop[i] = (combine(pop[father_i][0], pop[mother_i][0]), None)

        print(f'Gen {gen_i}, {round(time.time() - t)} s, max_fitness = {pop[0][1]} using: {pop[0][0]}')
        t = time.time()
    print(f'Finished in {round(t - t0)} s, or {round((t - t0)/(pop_size * num_generations * fitness_num_games), 1)} per game.')

# run_evolution()
print(get_fitness(100, feedback=True))