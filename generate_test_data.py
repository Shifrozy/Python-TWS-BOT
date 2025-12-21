"""
Generate Realistic Test Data for Backtesting
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Seed for reproducibility
np.random.seed(42)

# Starting price
start_price = 21500

# ===== GENERATE 1H DATA =====
print("Generating 1H data...")

dates_1h = []
base = datetime(2025, 12, 15)  # Start from Dec 15

for i in range(168):  # 7 days * 24 hours
    dt = base + timedelta(hours=i)
    # Skip weekends
    if dt.weekday() < 5:  # Mon-Fri
        dates_1h.append(dt)

# Generate realistic price movement (random walk with trend)
prices_1h = [start_price]
for i in range(len(dates_1h) - 1):
    # Random change + subtle trend
    change = np.random.normal(0, 25)  
    trend = np.sin(i / 15) * 40  # Sine wave trend
    new_price = prices_1h[-1] + change + trend
    prices_1h.append(new_price)

# Create DataFrame
df_1h = pd.DataFrame(index=dates_1h[:len(prices_1h)])
df_1h['close'] = prices_1h
df_1h['open'] = df_1h['close'].shift(1).fillna(df_1h['close'].iloc[0])

# Generate high/low properly (high > open/close, low < open/close)
for idx in df_1h.index:
    o = df_1h.loc[idx, 'open']
    c = df_1h.loc[idx, 'close']
    max_oc = max(o, c)
    min_oc = min(o, c)
    
    df_1h.loc[idx, 'high'] = max_oc + abs(np.random.normal(15, 8))
    df_1h.loc[idx, 'low'] = min_oc - abs(np.random.normal(15, 8))

df_1h['volume'] = np.random.randint(500, 3000, len(df_1h))

# Save to CSV
df_1h.to_csv('./data_cache/MNQ_1H.csv')
print(f"1H Data: {len(df_1h)} bars saved")
print(f"Price range: {df_1h['close'].min():.0f} - {df_1h['close'].max():.0f}")

# ===== GENERATE 10M DATA =====
print("\nGenerating 10M data...")

dates_10m = []
for i in range(720):  # More granular
    dt = base + timedelta(minutes=i * 10)
    if dt.weekday() < 5:
        dates_10m.append(dt)

prices_10m = [start_price]
for i in range(len(dates_10m) - 1):
    change = np.random.normal(0, 8)
    trend = np.sin(i / 50) * 15
    prices_10m.append(prices_10m[-1] + change + trend)

df_10m = pd.DataFrame(index=dates_10m[:len(prices_10m)])
df_10m['close'] = prices_10m
df_10m['open'] = df_10m['close'].shift(1).fillna(df_10m['close'].iloc[0])

for idx in df_10m.index:
    o = df_10m.loc[idx, 'open']
    c = df_10m.loc[idx, 'close']
    max_oc = max(o, c)
    min_oc = min(o, c)
    
    df_10m.loc[idx, 'high'] = max_oc + abs(np.random.normal(5, 3))
    df_10m.loc[idx, 'low'] = min_oc - abs(np.random.normal(5, 3))

df_10m['volume'] = np.random.randint(100, 1000, len(df_10m))

df_10m.to_csv('./data_cache/MNQ_10M.csv')
print(f"10M Data: {len(df_10m)} bars saved")
print(f"Price range: {df_10m['close'].min():.0f} - {df_10m['close'].max():.0f}")

print("\n=== Realistic Test Data Generated! ===")
print("Now run backtest with CSV option")
