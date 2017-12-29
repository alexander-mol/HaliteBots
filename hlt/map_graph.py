import math
import networkx as nx
import logging
import bot_utils

# timer = bot_utils.Timer()

class MapGraph:

    def __init__(self):
        self.core_graph = None
        self.heuristic = lambda n1, n2: math.sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2)
        self.planet_nodes = {}
        self.planet_edge_nodes = {}
        self.width = None
        self.height = None

    def build_core_graph(self, game_map, granularity=1, padding=0.1):
        self.core_graph = nx.Graph()

        self.width = game_map.width
        self.height = game_map.height
        # add initial nodes
        for x in range(self.width):
            for y in range(self.height):
                node = Position(x, y)
                self.core_graph.add_node(node)
        # logging.info(f'Time to make node set {timer.get_time()}')

        def in_bounds(pos):
            return pos.x >= 0 and pos.x < game_map.width and pos.y >= 0 and pos.y < game_map.height

        # add initial edges
        for node in self.core_graph.nodes():
            neighbour = Position(node.x - 1, node.y)
            if in_bounds(neighbour):
                self.core_graph.add_edge(node, neighbour, weight=1)
            neighbour = Position(node.x, node.y - 1)
            if in_bounds(neighbour):
                self.core_graph.add_edge(node, neighbour, weight=1)
            neighbour = Position(node.x - 1, node.y - 1)
            if in_bounds(neighbour):
                self.core_graph.add_edge(node, neighbour, weight=math.sqrt(2))
            neighbour = Position(node.x - 1, node.y + 1)
            if in_bounds(neighbour):
                self.core_graph.add_edge(node, neighbour, weight=math.sqrt(2))

        # logging.info(f'Time to add edges {timer.get_time()}')

        all_planets = game_map.all_planets()
        self.planet_edge_nodes = {Position(planet.x, planet.y): [] for planet in all_planets}

        # remove nodes that are 'inside' planets
        for node in self.core_graph.nodes():
            for planet in all_planets:
                dist = planet.calculate_distance_between(node)
                if dist < planet.radius + 0.5 + padding:
                    self.core_graph.remove_node(node)
                    self.planet_nodes[node] = Position(planet.x, planet.y)
                elif dist < planet.radius + 0.5 + granularity + padding:
                    self.planet_edge_nodes[Position(planet.x, planet.y)].append(node)

        # logging.info(f'Time to remove nodes in planets {timer.get_time()}')

    def get_closest_node(self, pos):
        x = round(pos.x)
        y = round(pos.y)
        grid_pos = Position(x, y)
        if grid_pos in self.core_graph.nodes():
            return grid_pos
        # inside a planet
        planet_center = self.planet_nodes[grid_pos]
        closest_node = "couldn't find closest node"
        min_dist = math.inf
        for node in self.planet_edge_nodes[planet_center]:
            this_dist = self.heuristic(pos, node)
            if this_dist < min_dist:
                closest_node = node
                min_dist = this_dist
        return closest_node


    def get_path_length(self, pos1, pos2):
        node1 = self.get_closest_node(pos1)
        node2 = self.get_closest_node(pos2)
        return nx.astar_path_length(self.core_graph, node1, node2, self.heuristic)

    def get_waypoint(self, source, target, points_along=7):
        node1 = self.get_closest_node(source)
        node2 = self.get_closest_node(target)
        path = nx.astar_path(self.core_graph, node1, node2, self.heuristic)
        waypoint_index = min(len(path)-1, points_along)
        return path[waypoint_index]

class Position:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        try:
            return self.x == other.x and self.y == other.y
        except:
            return False

    def __hash__(self):
        return int(self.x + self.y * 360)

    def __repr__(self):
        return f'({self.x}, {self.y})'


if __name__ == '__main__':
    class Temp:
        def __init__(self):
            self.width = 3
            self.height = 3
        def all_planets(self):
            return []

    game_map = Temp()
    m = MapGraph()
    m.build_core_graph(game_map)
    print(f'nodes: ({len(m.core_graph.nodes())}) {m.core_graph.nodes()}')
    print(f'edges: ({len(m.core_graph.edges())}) {m.core_graph.edges()}')
    print(m.get_path_length(Position(0, 0), Position(2, 2)))
    print(m.get_path_length(Position(0, 0), Position(2, 1)))
    target = m.get_waypoint(Position(0, 0), Position(2, 2))
    print(target)
