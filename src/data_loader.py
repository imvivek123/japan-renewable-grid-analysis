"""
Data loading and synthetic generation for Japan renewable energy grid analysis.
Provides functions to load real OCCTO/JEPX data or generate realistic synthetic grid data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path


# Regional data configurations
REGIONS = ["Hokkaido", "Tohoku", "Tokyo", "Chubu", "Hokuriku", 
           "Kansai", "Chugoku", "Shikoku", "Kyushu", "Okinawa"]

SOLAR_CAPACITY = {
    "Kyushu": 1.0, 
    "Kansai": 0.85, 
    "Chugoku": 0.8,
    "Chubu": 0.75, 
    "Tokyo": 0.7, 
    "Tohoku": 0.6,
    "Hokkaido": 0.5, 
    "Shikoku": 0.65, 
    "Hokuriku": 0.45, 
    "Okinawa": 0.9
}

WIND_CAPACITY = {
    "Hokkaido": 1.0,
    "Tohoku": 0.95,
    "Hokuriku": 0.7,
    "Kyushu": 0.6,
    "Chugoku": 0.5,
    "Shikoku": 0.45,
    "Kansai": 0.4,
    "Chubu": 0.35,
    "Tokyo": 0.2,
    "Okinawa": 0.3
}

DEMAND_BASELINE = {
    "Tokyo": 1.0,
    "Kansai": 0.7,
    "Chubu": 0.65,
    "Tohoku": 0.55,
    "Kyushu": 0.50,
    "Hokkaido": 0.35,
    "Chugoku": 0.30,
    "Hokuriku": 0.20,
    "Shikoku": 0.18,
    "Okinawa": 0.10
}


def load_occto_supply_demand(filepath: str) -> pd.DataFrame:
    """
    Load OCCTO monthly supply-demand CSV.
    
    Expected columns: datetime, region, total_demand_mw, solar_mw, wind_mw, 
                     hydro_mw, thermal_mw, nuclear_mw
    
    Args:
        filepath: Path to OCCTO CSV file
        
    Returns:
        Cleaned DataFrame with datetime index
    """
    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    return df


def load_jepx_prices(filepath: str) -> pd.DataFrame:
    """
    Load JEPX hourly spot price CSV.
    
    Expected columns: datetime, price_jpy_kwh, area
    
    Args:
        filepath: Path to JEPX CSV file
        
    Returns:
        Cleaned DataFrame
    """
    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df


def generate_synthetic_japan_grid(days: int = 365, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic 1 year of hourly data for 10 Japanese regions.
    
    Creates realistic renewable generation + demand patterns including:
    - Solar: diurnal + seasonal variation  
    - Wind: regional characteristics, random variation
    - Demand: daily load curve patterns
    - Price: inversely correlated with surplus
    
    Args:
        days: Number of days to simulate (default 365 = 1 year)
        seed: Random seed for reproducibility
        
    Returns:
        DataFrame with columns: datetime, region, solar_mw, wind_mw, demand_mw, 
                               surplus_mw, price_jpy_kwh, is_curtailment_risk
    """
    np.random.seed(seed)
    
    # Create datetime index
    start_date = datetime(2023, 1, 1)
    hours = days * 24
    date_range = [start_date + timedelta(hours=i) for i in range(hours)]
    
    # Pre-calculate seasonal factors
    day_of_year = np.array([(d - start_date).days for d in date_range])
    seasonal_factor = 0.5 + 0.5 * np.sin(2 * np.pi * day_of_year / 365)  # 0.5 to 1.5
    
    data_rows = []
    
    for region in REGIONS:
        solar_capacity = SOLAR_CAPACITY[region] * 5000  # Base 5000 MW * regional multiplier
        wind_capacity = WIND_CAPACITY[region] * 3000    # Base 3000 MW * regional multiplier
        demand_baseline = DEMAND_BASELINE[region] * 15000  # Base 15000 MW * regional multiplier
        
        for hour_idx, timestamp in enumerate(date_range):
            hour_of_day = timestamp.hour
            
            # Solar: sine wave pattern + seasonal variation + randomness
            solar_pattern = max(0, np.sin((hour_of_day - 6) * np.pi / 12))
            solar_mw = solar_capacity * solar_pattern * seasonal_factor[hour_idx] * np.random.uniform(0.85, 1.15)
            solar_mw = max(0, solar_mw)
            
            # Wind: random with regional characteristics
            wind_base = wind_capacity * np.random.uniform(0.3, 0.7)
            wind_variability = np.random.normal(0, wind_capacity * 0.1)
            wind_mw = max(0, wind_base + wind_variability)
            
            # Demand: daily load curve (low night, peak morning/evening)
            if 0 <= hour_of_day < 6:
                load_factor = 0.4
            elif 6 <= hour_of_day < 9:
                load_factor = 0.85
            elif 9 <= hour_of_day < 12:
                load_factor = 0.75
            elif 12 <= hour_of_day < 14:
                load_factor = 0.70
            elif 14 <= hour_of_day < 18:
                load_factor = 0.80
            elif 18 <= hour_of_day < 21:
                load_factor = 0.95
            else:
                load_factor = 0.55
            
            # Add day-of-week variation (lower on weekends)
            is_weekend = timestamp.weekday() >= 5
            if is_weekend:
                load_factor *= 0.9
            
            demand_mw = demand_baseline * load_factor * np.random.uniform(0.95, 1.05)
            
            # Surplus: renewable generation minus demand
            surplus_mw = solar_mw + wind_mw - demand_mw
            
            # Price: inversely correlated with surplus (simplified JEPX model)
            # High surplus = low price (curtailment risk)
            base_price = 12.0
            if surplus_mw > 0:
                price_discount = min(0.95, surplus_mw / (solar_capacity + wind_capacity))
                price_jpy_kwh = base_price * (1 - price_discount) + np.random.normal(0, 1)
            else:
                price_jpy_kwh = base_price + np.random.normal(0, 1.5)
            
            price_jpy_kwh = max(0.5, price_jpy_kwh)
            
            # Curtailment risk flag
            is_curtailment_risk = 1 if surplus_mw > 0 else 0
            
            data_rows.append({
                'datetime': timestamp,
                'region': region,
                'solar_mw': round(solar_mw, 1),
                'wind_mw': round(wind_mw, 1),
                'demand_mw': round(demand_mw, 1),
                'surplus_mw': round(surplus_mw, 1),
                'price_jpy_kwh': round(price_jpy_kwh, 2),
                'is_curtailment_risk': is_curtailment_risk
            })
    
    df = pd.DataFrame(data_rows)
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    return df


if __name__ == "__main__":
    # Quick test
    print("Generating synthetic Japan grid data...")
    df = generate_synthetic_japan_grid(days=7)  # 1 week sample
    print(f"\nGenerated {len(df)} rows across {df['region'].nunique()} regions")
    print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"\nFirst few rows:\n{df.head(10)}")
    print(f"\nSummary stats by region:\n{df.groupby('region')[['solar_mw', 'wind_mw', 'demand_mw', 'surplus_mw']].mean()}")
