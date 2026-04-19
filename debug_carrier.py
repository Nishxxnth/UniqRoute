import pandas as pd
from scipy.spatial import KDTree
from modules.signal_model import batch_score_segments

df = pd.read_csv('data/chennai_towers.csv')
df_airtel = df[df['airtel']]
df_bsnl = df[df['bsnl']]

kd_all = KDTree(df[['lat','lon']].values)
kd_airtel = KDTree(df_airtel[['lat','lon']].values)
kd_bsnl = KDTree(df_bsnl[['lat','lon']].values)

pts = [(13.0825, 80.2707), (13.0550, 80.2700), (13.0200, 80.2500)]
r_all = batch_score_segments(pts, df, kd_all, {}, 12)
r_airtel = batch_score_segments(pts, df_airtel, kd_airtel, {}, 12)
r_bsnl = batch_score_segments(pts, df_bsnl, kd_bsnl, {}, 12)

for i, pt in enumerate(pts):
    print(f"Pt {pt}: all={r_all[i]['score']:.1f} airtel={r_airtel[i]['score']:.1f} bsnl={r_bsnl[i]['score']:.1f}")

# Check distances at pt[0]
d_all, _ = kd_all.query(pts[0], k=1)
d_airtel, _ = kd_airtel.query(pts[0], k=1)
d_bsnl, _ = kd_bsnl.query(pts[0], k=1)
print(f"Distances (km): all={d_all*111:.2f} airtel={d_airtel*111:.2f} bsnl={d_bsnl*111:.2f}")

# Show RSSI of nearest towers
_, i_all = kd_all.query(pts[0], k=1)
_, i_airtel = kd_airtel.query(pts[0], k=1)
_, i_bsnl = kd_bsnl.query(pts[0], k=1)
print(f"RSSI: all={df.iloc[i_all]['averageSignal']:.1f} airtel={df_airtel.iloc[i_airtel]['averageSignal']:.1f} bsnl={df_bsnl.iloc[i_bsnl]['averageSignal']:.1f}")
print(f"Radio: all={df.iloc[i_all]['radio']} airtel={df_airtel.iloc[i_airtel]['radio']} bsnl={df_bsnl.iloc[i_bsnl]['radio']}")
