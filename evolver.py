import subprocess
import re
import logging
import copy
import random
import time
import _pickle

pop_size = 8
num_generations = 8
fitness_num_games = 25
mutation_rate = 0.4
mutation_magnitude = 0.3
map_width = 288
map_height = 192

logging.basicConfig(filename='./evolver_log')

path = '/Users/student/Desktop/Local Files/Projects/Halite2_Python3_MacOS/halite'
query = ['-d', f'{map_width} {map_height}', "python3 micro-manager_evolved.py", "python3 micro-manager.py"]
single_game_query = [path] + query

def run_game(id=None):
    result = subprocess.run(single_game_query, stdout=subprocess.PIPE).stdout.decode('utf-8')
    try:
        rank = re.findall('Player #0, .*?, came in rank #(.*?) and', result)[0]
        return rank == '1'
    except:
        if id:
            logging.info(f'id: {id}')
        print(re.sub('Turn (.*?)\n', '', result))
        return False

def get_fitness(num_games, id=None):
    win_count = 0
    for i in range(num_games):
        if id:
            i = id + str(i)
        if run_game(i):
            win_count += 1
    return win_count / num_games

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
    # evolution
    base_params = {'defensive_action_radius': 33.22346939590352, 'max_response': 4, 'safe_docking_distance': 15.90991149809392, 'job_base_benefit': 79.7295501179922, 'fighting_relative_benefit': 1.572854795198809, 'available_ships_for_rogue_mission_trigger': 12, 'general_approach_dist': 2.842128273421315, 'planet_approach_dist': 2.427450916328799, 'leader_approach_dist': 0.7613118205454873, 'tether_dist': 2.3797253838512864, 'padding': 0.11081714461786406, 'motion_ghost_points': 4}
    pop = [(copy.copy(base_params), None) for _ in range(pop_size)]

    mid_point = round(pop_size / 2)

    t0 = time.time()
    t = time.time()
    for gen_i in range(num_generations):

        # mutate
        for ind in pop[mid_point:]:
            mutate(ind[0])

        # fitness
        for i, ind in enumerate(pop):
            set_params(ind[0])
            pop[i] = (ind[0], get_fitness(fitness_num_games, str(ind[0])))

        # sort
        pop.sort(key=lambda x: -x[1])

        # generate new individuals
        for i in range(mid_point, len(pop)):
            father_i = random.randint(0, mid_point-1)
            mother_i = random.randint(0, mid_point-1)
            pop[i] = (combine(pop[father_i][0], pop[mother_i][0]), None)

        with open('pop_cache.p', 'wb') as f:
            _pickle.dump(pop, f)
        print(f'Gen {gen_i}, {round(time.time() - t)} s, max_fitness = {pop[0][1]} using: {pop[0][0]}')
        t = time.time()
    print(f'Finished in {round(t - t0)} s, or {round((t - t0)/(pop_size * num_generations * fitness_num_games), 1)} per game.')

run_evolution()
# set_params({'defensive_action_radius': 33.22346939590352, 'max_response': 4, 'safe_docking_distance': 10.905369014309452, 'job_base_benefit': 80.74621336507236, 'fighting_relative_benefit': 1.1943799665409098, 'available_ships_for_rogue_mission_trigger': 13, 'general_approach_dist': 4.18437790908138, 'planet_approach_dist': 3.4615527769250996, 'leader_approach_dist': 0.7759324752156381, 'tether_dist': 1.9767495471214407, 'padding': 0.14276624784331843, 'motion_ghost_points': 4},
#            with_round=True)