"""
Technical Indicators Module
Implements SuperTrend and EMA calculations
"""
import pandas as pd
import numpy as np


def calculate_supertrend(df, period=10, multiplier=3.0):
    """
    Calculate SuperTrend indicator
    
    Uses TradingView logic:
    - Bullish: close > supertrend
    - Bearish: close < supertrend
    
    Args:
        df: DataFrame with columns ['high', 'low', 'close']
        period: ATR period (default 10 - client spec)
        multiplier: ATR multiplier (default 3 - client spec)
    
    Returns:
        DataFrame with 'supertrend', 'st_direction', and 'st_positive' columns
    """
    df = df.copy()
    
    # Calculate ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(window=period).mean()
    
    # Calculate basic bands
    hl_avg = (df['high'] + df['low']) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)
    
    # Initialize SuperTrend
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    for i in range(len(df)):
        if i == 0:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = 1
        else:
            # Upper band
            if upper_band.iloc[i] < supertrend.iloc[i-1] or df['close'].iloc[i-1] > supertrend.iloc[i-1]:
                upper_band.iloc[i] = upper_band.iloc[i]
            else:
                upper_band.iloc[i] = supertrend.iloc[i-1]
            
            # Lower band
            if lower_band.iloc[i] > supertrend.iloc[i-1] or df['close'].iloc[i-1] < supertrend.iloc[i-1]:
                lower_band.iloc[i] = lower_band.iloc[i]
            else:
                lower_band.iloc[i] = supertrend.iloc[i-1]
            
            # SuperTrend value
            if direction.iloc[i-1] == 1 and df['close'].iloc[i] <= upper_band.iloc[i]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            elif direction.iloc[i-1] == -1 and df['close'].iloc[i] >= lower_band.iloc[i]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            elif direction.iloc[i-1] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            else:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
    
    df['supertrend'] = supertrend
    df['st_direction'] = direction  # 1 for bullish, -1 for bearish
    
    # TradingView style: positive when close > supertrend
    df['st_positive'] = df['close'] > df['supertrend']
    
    return df


def calculate_ema(df, period=200):
    """
    Calculate Exponential Moving Average
    
    Args:
        df: DataFrame with 'close' column
        period: EMA period (default 200)
    
    Returns:
        DataFrame with 'ema' column added
    """
    df = df.copy()
    df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
    return df


def is_price_above_ema(df):
    """
    Check if current close is above EMA
    
    Returns:
        Boolean Series
    """
    return df['close'] > df['ema']


def is_supertrend_positive(df):
    """
    Check if SuperTrend is positive (bullish)
    
    Uses TradingView logic: close > supertrend
    
    Returns:
        Boolean Series
    """
    # TradingView style: bullish when close > supertrend
    return df['close'] > df['supertrend']

