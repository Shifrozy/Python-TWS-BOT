"""
Trading Strategy Module
Implements EMA 200 (1H) + SuperTrend (10M) strategy
"""
import pandas as pd
import numpy as np
from indicators import calculate_ema, calculate_supertrend, is_price_above_ema, is_supertrend_positive
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    EMA 200 (1H) + SuperTrend (10M) Trading Strategy
    
    *** LONG ONLY - NO SHORT TRADES ***
    
    Strategy Rules:
    ===============
    
    BUY ENTRY:
    - emaBull = 1H close > EMA 200
    - stBull = 10M close > SuperTrend
    - buyCond = position == 0 AND emaBull AND stBull
    
    EXIT:
    - Take Profit: price >= entry * (1 + tpPct/100)
    - Stop Loss: price <= entry * (1 - slPct/100)
    - SuperTrend Flip: stBear (close < supertrend) → EXIT
    
    CONTINUOUS TRADING:
    - After TP hit, if 10M becomes positive again → re-enter BUY
    - Continue trading as long as 1H bars > EMA 200
    """
    
    def __init__(self, 
                 ema_period=200,
                 st_atr_period=10,        # Default: Client spec (change to 55 for PineScript)
                 st_multiplier=3.0,       # Default: Client spec (change to 3.8 for PineScript)
                 tp_percent=1.2,          # Default: Client spec (change to 3.0 for PineScript)
                 sl_percent=0.4):         # Default: Client spec (change to 0.55 for PineScript)
        """
        Initialize strategy parameters
        
        Default values are from client verbal specification.
        PineScript uses: ATR=55, Mult=3.8, TP=3%, SL=0.55%
        
        Args:
            ema_period: EMA period (default 200)
            st_atr_period: SuperTrend ATR period (default 10, PineScript uses 55)
            st_multiplier: SuperTrend multiplier (default 3, PineScript uses 3.8)
            tp_percent: Take profit percentage (default 1.2, PineScript uses 3.0)
            sl_percent: Stop loss percentage (default 0.4, PineScript uses 0.55)
        """
        self.ema_period = ema_period
        self.st_atr_period = st_atr_period
        self.st_multiplier = st_multiplier
        self.tp_percent = tp_percent
        self.sl_percent = sl_percent
        
        self.position = 0  # 0: no position, 1: long, -1: short
        self.entry_price = 0
        self.tp_price = 0
        self.sl_price = 0
        
        # Track 1H trend state for continuous trading
        self.trend_confirmed = False
        self.last_exit_reason = None
    
    def prepare_data(self, df_1h, df_10m):
        """
        Prepare and align data from both timeframes
        
        Args:
            df_1h: DataFrame with 1H OHLCV data
            df_10m: DataFrame with 10M OHLCV data
        
        Returns:
            Tuple of (prepared_1h_df, prepared_10m_df)
        """
        # Calculate indicators on 1H data
        df_1h = calculate_ema(df_1h, period=self.ema_period)
        df_1h['above_ema'] = is_price_above_ema(df_1h)
        
        # Calculate indicators on 10M data
        df_10m = calculate_supertrend(df_10m, period=self.st_atr_period, multiplier=self.st_multiplier)
        df_10m['st_positive'] = is_supertrend_positive(df_10m)
        
        return df_1h, df_10m
    
    def is_1h_confirmed(self, df_1h, current_idx):
        """
        Check if 1H bar is confirmed above EMA 200
        Bar must close above EMA (not just touching or between)
        
        Args:
            df_1h: 1H DataFrame
            current_idx: Current index
        
        Returns:
            Boolean
        """
        if current_idx >= len(df_1h):
            return False
        
        current_bar = df_1h.iloc[current_idx]
        return current_bar['close'] > current_bar['ema']
    
    def get_10m_supertrend_status(self, df_10m, current_time):
        """
        Get SuperTrend status from 10M timeframe at given time
        
        SuperTrend is POSITIVE (bullish) when: close > supertrend value
        SuperTrend is NEGATIVE (bearish) when: close < supertrend value
        
        This matches TradingView logic:
        stBull = close10 > st10
        stBear = close10 < st10
        
        Args:
            df_10m: 10M DataFrame
            current_time: Timestamp to check
        
        Returns:
            Tuple of (is_positive, supertrend_value, close_price)
        """
        # Find the most recent 10M bar before or at current_time
        df_10m_filtered = df_10m[df_10m.index <= current_time]
        if df_10m_filtered.empty:
            return False, None, None
        
        latest_10m = df_10m_filtered.iloc[-1]
        st_value = latest_10m['supertrend']
        close_price = latest_10m['close']
        
        # SuperTrend is positive when close > supertrend (like TradingView)
        is_positive = close_price > st_value
        
        return is_positive, st_value, close_price
    
    def check_entry_signal(self, df_1h, df_10m, current_idx):
        """
        Check for BUY entry signal (LONG ONLY - no shorts)
        
        BUY Condition:
        buyCond = position_size == 0 AND emaBull AND stBull
        
        Where:
        emaBull = close > ema1h (1H close above EMA 200)
        stBull = close10 > st10 (10M close above SuperTrend)
        
        Args:
            df_1h: 1H DataFrame
            df_10m: 10M DataFrame
            current_idx: Current 1H bar index
        
        Returns:
            Tuple of (signal, price) where signal is 'BUY' or None
        """
        if current_idx >= len(df_1h):
            return None, None
        
        current_1h = df_1h.iloc[current_idx]
        current_time = df_1h.index[current_idx]
        close_1h = current_1h['close']
        ema_1h = current_1h['ema']
        
        # ===== EMA Condition (1H timeframe) =====
        # emaBull = close > ema1h
        ema_bull = close_1h > ema_1h
        
        # Update trend state
        self.trend_confirmed = ema_bull
        
        # ===== SuperTrend Condition (10M timeframe) =====
        # stBull = close10 > st10
        st_positive, st_value, close_10m = self.get_10m_supertrend_status(df_10m, current_time)
        st_bull = st_positive  # close > supertrend
        
        # ===== BUY ENTRY ONLY =====
        # buyCond = position_size == 0 AND emaBull AND stBull
        if self.position == 0 and ema_bull and st_bull:
            logger.info(f"BUY SIGNAL: 1H close > EMA ✓, 10M close > SuperTrend ✓")
            return 'BUY', close_1h
        
        # No entry signal
        return None, None
    
    def check_exit_signal(self, df_10m, df_1h, current_time, current_price, current_idx):
        """
        Check for exit signal (LONG ONLY)
        
        Exit Conditions:
        1. Take Profit: price >= entry * (1 + tpPct/100)
        2. Stop Loss: price <= entry * (1 - slPct/100)
        3. SuperTrend Flip: stBear (close < supertrend) → EXIT
        
        Args:
            df_10m: 10M DataFrame
            df_1h: 1H DataFrame
            current_time: Current timestamp
            current_price: Current price
            current_idx: Current 1H bar index
        
        Returns:
            Exit reason string or None
        """
        if self.position == 0:
            return None
        
        # Get current 10M SuperTrend status
        st_positive, st_value, close_10m = self.get_10m_supertrend_status(df_10m, current_time)
        st_bear = not st_positive if st_value is not None else False
        
        # ===== LONG POSITION EXIT ONLY =====
        if self.position == 1:
            
            # Check Take Profit: longTP = entry * (1 + tpPct/100)
            if current_price >= self.tp_price:
                self.last_exit_reason = 'TP_HIT'
                logger.info(f"TP hit at {current_price:.2f}")
                return 'TP_HIT'
            
            # Check Stop Loss: longSL = entry * (1 - slPct/100)
            if current_price <= self.sl_price:
                self.last_exit_reason = 'SL_HIT'
                logger.info(f"SL hit at {current_price:.2f}")
                return 'SL_HIT'
            
            # SuperTrend Flip: stBear → EXIT
            # "exit will always happen based on Super Trend"
            if st_bear:
                self.last_exit_reason = 'ST_FLIP'
                logger.info(f"SuperTrend flipped BEARISH → EXIT")
                return 'ST_FLIP'
        
        return None
    
    def can_reenter(self, df_1h, df_10m, current_idx):
        """
        Check if re-entry is possible after TP hit
        
        Re-entry Conditions:
        - Previous exit was TP_HIT
        - 1H bars still above EMA 200
        - 10M SuperTrend turns positive again
        
        Returns:
            Boolean
        """
        if self.last_exit_reason != 'TP_HIT':
            return False
        
        if current_idx >= len(df_1h):
            return False
        
        current_time = df_1h.index[current_idx]
        
        # Check 1H EMA confirmation
        ema_confirmed = self.is_1h_confirmed(df_1h, current_idx)
        
        # Check 10M SuperTrend
        st_positive, _, _ = self.get_10m_supertrend_status(df_10m, current_time)
        
        return ema_confirmed and st_positive
    
    def enter_position(self, action, price):
        """
        Enter a position
        
        Args:
            action: 'BUY' or 'SELL'
            price: Entry price
        """
        self.position = 1 if action == 'BUY' else -1
        self.entry_price = price
        
        if action == 'BUY':
            self.tp_price = price * (1 + self.tp_percent / 100)
            self.sl_price = price * (1 - self.sl_percent / 100)
        else:
            self.tp_price = price * (1 - self.tp_percent / 100)
            self.sl_price = price * (1 + self.sl_percent / 100)
        
        logger.info(f"Entered {action} position at {price:.2f}, TP: {self.tp_price:.2f}, SL: {self.sl_price:.2f}")
    
    def exit_position(self, price, reason='MANUAL'):
        """
        Exit current position
        
        Args:
            price: Exit price
            reason: Exit reason
        """
        if self.position == 0:
            return
        
        pnl = 0
        if self.position == 1:
            pnl = (price - self.entry_price) / self.entry_price * 100
        else:
            pnl = (self.entry_price - price) / self.entry_price * 100
        
        logger.info(f"Exited position at {price:.2f}, PnL: {pnl:.2f}%, Reason: {reason}")
        
        self.position = 0
        self.entry_price = 0
        self.tp_price = 0
        self.sl_price = 0
        
        return pnl
    
    def update_parameters(self, tp_percent=None, sl_percent=None, st_atr_period=None, st_multiplier=None):
        """Update strategy parameters"""
        if tp_percent is not None:
            self.tp_percent = tp_percent
        if sl_percent is not None:
            self.sl_percent = sl_percent
        if st_atr_period is not None:
            self.st_atr_period = st_atr_period
        if st_multiplier is not None:
            self.st_multiplier = st_multiplier

