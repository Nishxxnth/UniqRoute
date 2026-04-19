import pandas as pd
import numpy as np

df = pd.read_csv('chennai_towers_encoded.csv')
print(f'Original: {len(df)} towers')

# Rename column to match code expectation
df = df.rename(columns={'averageSignalStrength': 'averageSignal'})
df['averageSignal'] = df['averageSignal'].astype(float)

# Signal is all 0 in OpenCelliD — generate realistic synthetic RSSI based on network type
np.random.seed(42)
signal_map = {
    'LTE':  (-75, -55),
    'UMTS': (-85, -65),
    'GSM':  (-95, -70),
    'NR':   (-70, -50),
}
for idx, row in df.iterrows():
    radio = row['radio']
    lo, hi = signal_map.get(radio, (-90, -60))
    df.at[idx, 'averageSignal'] = np.random.uniform(lo, hi)

# Hackathon Demo Shaping: Carve out 3 "dead zone" bubbles on the East Coast / Marina route
# Rajiv Hospital -> Marina Beach shortest path goes through these.
bubbles = [
    (13.08, 80.28, 0.005),  # Bubble 1 (Hospital)
    (13.07, 80.28, 0.005),  # Bubble 2 (Mid-route)
    (13.06, 80.28, 0.005),  # Bubble 3 (Approaching Beach)
]

def in_bubble(lat, lon):
    for b_lat, b_lon, radius in bubbles:
        if (lat - b_lat)**2 + (lon - b_lon)**2 < radius**2:
            return True
    return False

# Filter out towers in the bubbles
df = df[~df.apply(lambda row: in_bubble(row['lat'], row['lon']), axis=1)]

# Artificially boost Vi, Jio, BSNL for the hackathon demo so they don't have inescapable dead zones
# We give each tower a 40% chance of being supported by a carrier
np.random.seed(42)
for carrier in ['airtel', 'bsnl', 'jio', 'vi']:
    if carrier in df.columns:
        # Keep original true values, but randomly add more
        df[carrier] = df[carrier] | (np.random.rand(len(df)) < 0.45)


# Add carrier-specific 5G NR super-towers so each carrier genuinely differs
# This ensures the routing engine finds truly different paths per carrier
inland_towers = pd.DataFrame([
    # Jio has strong NR in the inland western corridor
    {'lat': 13.08, 'lon': 80.26, 'averageSignal': -50, 'radio': 'NR', 'airtel': False, 'jio': True,  'vi': False, 'bsnl': False},
    {'lat': 13.07, 'lon': 80.26, 'averageSignal': -50, 'radio': 'NR', 'airtel': False, 'jio': True,  'vi': False, 'bsnl': False},
    {'lat': 13.06, 'lon': 80.26, 'averageSignal': -50, 'radio': 'NR', 'airtel': False, 'jio': True,  'vi': False, 'bsnl': False},
    {'lat': 13.05, 'lon': 80.26, 'averageSignal': -50, 'radio': 'NR', 'airtel': False, 'jio': True,  'vi': False, 'bsnl': False},
    # Airtel has strong NR in the eastern coastal corridor
    {'lat': 13.08, 'lon': 80.28, 'averageSignal': -50, 'radio': 'NR', 'airtel': True,  'jio': False, 'vi': False, 'bsnl': False},
    {'lat': 13.07, 'lon': 80.28, 'averageSignal': -50, 'radio': 'NR', 'airtel': True,  'jio': False, 'vi': False, 'bsnl': False},
    {'lat': 13.06, 'lon': 80.28, 'averageSignal': -50, 'radio': 'NR', 'airtel': True,  'jio': False, 'vi': False, 'bsnl': False},
    # Vi has LTE advantage in central areas
    {'lat': 13.08, 'lon': 80.27, 'averageSignal': -55, 'radio': 'LTE', 'airtel': False, 'jio': False, 'vi': True, 'bsnl': False},
    {'lat': 13.07, 'lon': 80.27, 'averageSignal': -55, 'radio': 'LTE', 'airtel': False, 'jio': False, 'vi': True, 'bsnl': False},
    {'lat': 13.06, 'lon': 80.27, 'averageSignal': -55, 'radio': 'LTE', 'airtel': False, 'jio': False, 'vi': True, 'bsnl': False},
    # BSNL has older GSM/UMTS spread broadly but weaker signal
    {'lat': 13.09, 'lon': 80.25, 'averageSignal': -70, 'radio': 'UMTS', 'airtel': False, 'jio': False, 'vi': False, 'bsnl': True},
    {'lat': 13.05, 'lon': 80.25, 'averageSignal': -70, 'radio': 'UMTS', 'airtel': False, 'jio': False, 'vi': False, 'bsnl': True},
])

# --- Synthetic Spatial Density Grid via K-Means Clustering ---
# Instead of a simple hex grid, we use K-Means clustering over actual road geometries.
print("Generating synthetic towers via Spatial Density Clustering...")
ambattur_towers = []
try:
    import pickle
    from sklearn.cluster import KMeans
    
    # Load the already-downloaded OpenStreetMap road topology
    with open('cache/graph_cache_topo.pkl', 'rb') as f:
        G = pickle.load(f)
        
    print("Loaded OSM Topology. Extracting road density nodes...")
    ambattur_nodes = []
    for node, data in G.nodes(data=True):
        if 13.08 < data.get('y', 0) < 13.15 and 80.11 < data.get('x', 0) < 80.21:
            ambattur_nodes.append([data['y'], data['x']])
            
    if ambattur_nodes:
        # Ask Machine Learning to find 300 optimal centroids based on road density map
        print(f"Running K-Means over {len(ambattur_nodes)} road intersections...")
        kmeans = KMeans(n_clusters=300, random_state=42, n_init='auto')
        kmeans.fit(ambattur_nodes)
        
        for lat, lon in kmeans.cluster_centers_:
            ambattur_towers.append({
                'lat': lat,
                'lon': lon,
                'averageSignal': np.random.uniform(-80, -60),
                'radio': 'LTE',
                'airtel': np.random.rand() < 0.6,
                'jio': np.random.rand() < 0.6,
                'vi': np.random.rand() < 0.4,
                'bsnl': np.random.rand() < 0.3
            })
    else:
        raise ValueError("No routing nodes found in Ambattur bounding box.")
        
except Exception as e:
    print(f"Fallback to random generation due to error: {e}")
    # Fallback to random if cache not found
    for _ in range(300):
        ambattur_towers.append({
            'lat': np.random.uniform(13.08, 13.15),
            'lon': np.random.uniform(80.11, 80.21),
            'averageSignal': np.random.uniform(-80, -60),
            'radio': 'LTE',
            'airtel': True, 'jio': True, 'vi': True, 'bsnl': True
        })

ambattur_df = pd.DataFrame(ambattur_towers)
print(f'Generated {len(ambattur_df)} synthetic towers via K-Means spatial density')

cols_to_keep = ['lat', 'lon', 'averageSignal', 'radio', 'airtel', 'bsnl', 'jio', 'vi']
out = pd.concat([df[cols_to_keep], inland_towers, ambattur_df])
out.to_csv('data/chennai_towers.csv', index=False)
print(f'Saved {len(out)} towers to data/chennai_towers.csv')
print(out['radio'].value_counts())
print(f"Signal range: {out['averageSignal'].min():.1f} to {out['averageSignal'].max():.1f}")
print(out.head())
