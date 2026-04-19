"""
prep_chennai.py
===============
Extract Chennai cell towers from india_spec/404.csv + 405.csv,
map every MNC to one of our four carriers (airtel / bsnl / jio / vi),
and write data/chennai_towers.csv in the exact format that
graph_builder.py + signal_model.py expect.

Geographic bounds (Kanchipuram edge → Marina Beach):
  lat  12.85 – 13.35
  lon  79.95 – 80.45
"""

import os
import pandas as pd
import numpy as np

# ── Geographic bounds ─────────────────────────────────────────────────────────
LAT_MIN, LAT_MAX = 12.85, 13.35
LON_MIN, LON_MAX = 79.95, 80.45

# ── Complete MNC → carrier mapping for every MNC found in Chennai ─────────────
# Format: (mcc, mnc) -> 'airtel' | 'bsnl' | 'jio' | 'vi' | None (defunct/skip)
MNC_TO_CARRIER = {
    # ── Airtel ────────────────────────────────────────────────────────────────
    (404, 10): 'airtel',   # Airtel (circle overlap)
    (404, 40): 'airtel',   # Airtel Chennai
    (404, 45): 'airtel',   # Airtel
    (404, 49): 'airtel',   # Airtel
    (404, 94): 'airtel',   # Airtel Tamil Nadu
    (404, 95): 'airtel',   # Airtel Kerala (border)
    (405, 25): 'airtel',   # Airtel (old Tata Docomo)
    (405, 34): 'airtel',   # Airtel (old Tata Docomo)
    (405, 44): 'airtel',   # Airtel Tamil Nadu incl Chennai

    # ── BSNL ─────────────────────────────────────────────────────────────────
    (404, 57): 'bsnl',     # BSNL
    (404, 64): 'bsnl',     # BSNL Chennai
    (404, 73): 'bsnl',     # BSNL
    (404, 80): 'bsnl',     # BSNL Tamil Nadu
    (404, 81): 'bsnl',     # BSNL

    # ── Jio ──────────────────────────────────────────────────────────────────
    (405, 840): 'jio',     # Jio West Bengal (border towers)
    (405, 854): 'jio',     # Jio Andhra Pradesh (border)
    (405, 856): 'jio',     # Jio Bihar (mis-placed / border)
    (405, 863): 'jio',     # Jio Madhya Pradesh (border)
    (405, 869): 'jio',     # Jio Tamil Nadu incl Chennai  ← PRIMARY
    (405, 871): 'jio',     # Jio UP East (border)
    (405, 20):  'jio',     # Old Reliance → Jio Tamil Nadu

    # ── Vi (Vodafone Idea) ────────────────────────────────────────────────────
    (404, 11): 'vi',       # Vi
    (404, 13): 'vi',       # Vi
    (404, 43): 'vi',       # Vi Tamil Nadu
    (404, 84): 'vi',       # Vi Chennai  ← PRIMARY
    (405, 753): 'vi',      # Vi Orissa (border)
    (405, 852): 'vi',      # Vi Tamil Nadu  ← PRIMARY

    # ── Defunct / skip ───────────────────────────────────────────────────────
    (404, 41): None,       # AIRCEL Chennai (shut down 2018)
    (404, 42): None,       # AIRCEL Tamil Nadu (shut down)
    (405,  4): None,       # Old Reliance (pre-Jio)
    (405, 801): None,      # AIRCEL defunct
}

# avgsignal = 0 means "not measured" in OpenCelliD; replace with realistic floor
DEFAULT_SIGNAL_DBM = -85.0  # reasonable urban signal floor

os.makedirs('data', exist_ok=True)

# ── Load raw CSVs ─────────────────────────────────────────────────────────────
print("Loading india_spec/404.csv ...")
df404 = pd.read_csv('india_spec/404.csv', low_memory=False)
print(f"  {len(df404):,} rows")

print("Loading india_spec/405.csv ...")
df405 = pd.read_csv('india_spec/405.csv', low_memory=False)
print(f"  {len(df405):,} rows")

df_all = pd.concat([df404, df405], ignore_index=True)
print(f"  Combined: {len(df_all):,} rows")

# ── Geo-filter for Chennai ────────────────────────────────────────────────────
chennai = df_all[
    (df_all['lat'] >= LAT_MIN) & (df_all['lat'] <= LAT_MAX) &
    (df_all['long'] >= LON_MIN) & (df_all['long'] <= LON_MAX)
].copy()
print(f"\nChennai geo-filter: {len(chennai):,} towers")

# ── Map MNC → carrier booleans ───────────────────────────────────────────────
def get_carrier(row):
    return MNC_TO_CARRIER.get((int(row['mcc']), int(row['mnc'])), 'unknown')

chennai['_carrier'] = chennai.apply(get_carrier, axis=1)

# Drop defunct and truly unknown (not mapped to any carrier at all)
before = len(chennai)
chennai = chennai[chennai['_carrier'].notna()]  # removes None (defunct)
print(f"After dropping defunct operators: {len(chennai):,} towers (removed {before - len(chennai):,})")

# For rows mapped to 'unknown' - assign to 'airtel' as default for known Indian towers
# that fall outside our explicit MNC list (they're valid towers, just outside Tamil Nadu circle)
chennai.loc[chennai['_carrier'] == 'unknown', '_carrier'] = 'airtel'

# ── Build carrier boolean columns ─────────────────────────────────────────────
chennai['airtel'] = chennai['_carrier'] == 'airtel'
chennai['bsnl']   = chennai['_carrier'] == 'bsnl'
chennai['jio']    = chennai['_carrier'] == 'jio'
chennai['vi']     = chennai['_carrier'] == 'vi'

# ── Fix averageSignal ─────────────────────────────────────────────────────────
# OpenCelliD stores 0 when signal is unmeasured. Replace with realistic floor.
# Also, LTE typically ranges -70 to -100 dBm; GSM -60 to -110 dBm
chennai['averageSignal'] = chennai['avgsignal'].astype(float)
# Assign realistic defaults based on radio type where signal = 0
mask_zero = chennai['averageSignal'] == 0
radio_signal_defaults = {
    'LTE':  -78.0,
    'UMTS': -82.0,
    'GSM':  -85.0,
    'NR':   -75.0,
}
for radio_type, default_sig in radio_signal_defaults.items():
    m = mask_zero & (chennai['radio'] == radio_type)
    chennai.loc[m, 'averageSignal'] = default_sig
# Any remaining zeros
chennai.loc[mask_zero & (chennai['averageSignal'] == 0), 'averageSignal'] = DEFAULT_SIGNAL_DBM

# ── Rename to match graph_builder expected schema ─────────────────────────────
# Expected: lat, lon, averageSignal, radio, airtel, bsnl, jio, vi
out = chennai[['lat', 'long', 'averageSignal', 'radio', 'airtel', 'bsnl', 'jio', 'vi']].copy()
out = out.rename(columns={'long': 'lon'})

# Drop rows with bad coordinates
out = out.dropna(subset=['lat', 'lon'])
out = out[(out['lat'] > 0) & (out['lon'] > 0)]

print(f"\nFinal output: {len(out):,} towers")
print(f"\nCarrier breakdown:")
print(f"  Airtel : {out['airtel'].sum():>6,}")
print(f"  BSNL   : {out['bsnl'].sum():>6,}")
print(f"  Jio    : {out['jio'].sum():>6,}")
print(f"  Vi     : {out['vi'].sum():>6,}")
print(f"\nRadio breakdown:")
print(out['radio'].value_counts().to_string())
print(f"\nSignal stats (dBm):")
print(out['averageSignal'].describe())
print(f"\nGeo bounds of output:")
print(f"  lat: {out['lat'].min():.4f} – {out['lat'].max():.4f}")
print(f"  lon: {out['lon'].min():.4f} – {out['lon'].max():.4f}")

# ── Save ──────────────────────────────────────────────────────────────────────
out_path = 'data/chennai_towers.csv'
out.to_csv(out_path, index=False)
print(f"\n✅ Saved {len(out):,} towers → {out_path}")
print("   Next: delete cache/graph_cache.pkl and cache/graph_cache_topo.pkl")
print("   then restart the backend to rebuild with real tower data.")
