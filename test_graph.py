import osmnx as ox
import networkx as nx
from modules.graph_builder import build_graph
import math

G = build_graph()[0]
orig = (13.0805, 80.276) # Roughly Rajiv Gandhi Hospital
dest = (13.050, 80.282) # Marina Beach

o_node = ox.nearest_nodes(G, orig[1], orig[0])
d_node = ox.nearest_nodes(G, dest[1], dest[0])

# Fastest path
path_fast = nx.shortest_path(G, o_node, d_node, weight='length')
fast_len = sum(G.get_edge_data(path_fast[i], path_fast[i+1])[0].get('length', 100) for i in range(len(path_fast)-1))
fast_dead = sum(1 for i in range(len(path_fast)-1) if G.get_edge_data(path_fast[i], path_fast[i+1])[0].get('is_dead_zone', False))

# Most connected path
def weight_fn(a):
    def w(u, v, d):
        min_w = float('inf')
        for k, data in d.items():
            l = data.get('length', 100)
            score = data.get('connectivity_score', 50)
            l_norm = l / 100.0
            penalty = math.exp((100 - score) / 15.0)
            score_term = penalty * l_norm
            w_val = a * l_norm + (1 - a) * score_term
            if w_val < min_w: min_w = w_val
        return min_w
    return w

path_conn = nx.shortest_path(G, o_node, d_node, weight=weight_fn(0.0))
conn_len = sum(G.get_edge_data(path_conn[i], path_conn[i+1])[0].get('length', 100) for i in range(len(path_conn)-1))
conn_dead = sum(1 for i in range(len(path_conn)-1) if G.get_edge_data(path_conn[i], path_conn[i+1])[0].get('is_dead_zone', False))

print(f"Fastest: ETA {fast_len/1000/30*60:.1f} min, Dead Zones: {fast_dead}")
print(f"Connected: ETA {conn_len/1000/30*60:.1f} min, Dead Zones: {conn_dead}")
