"""
Trading Strategy Module
Implements EMA 200 (1H) + SuperTrend (10M) strategy
Matches script.pine strategy logic
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
    Matches script.pine strategy logic
    
    Strategy Rules (from script.pine):
    ==================================
    
    BUY ENTRY:
    - ST flips green (stBullFlip) AND 1H candle is above EMA, OR
    - ST is green AND 1H candle just closed above EMA (on new 1H candle start)
    - Not already traded in current ST trend
    
    SELL ENTRY:
    - ST flips red (stBearFlip) AND 1H candle is below EMA, OR
    - ST is red AND 1H candle just closed below EMA (on new 1H candle start)
    - Not already traded in current ST trend
    
    LONG EXIT:
    - Take Profit: price >= entry * (1 + tpPct/100)
    - Stop Loss: price <= entry * (1 - slPct/100)
    - SuperTrend Flip: stBear → EXIT
    
    SHORT EXIT:
    - Take Profit: price <= entry * (1 - tpPct/100)
    - Stop Loss: price >= entry * (1 + slPct/100)
    - SuperTrend Flip: stBull → EXIT
    
    TRADE TRACKING:
    - Same ST trend mein ek baar trade ke baad phir signal nahi aayega
    - Jab tak ST red hokar green na ho, tab tak buy signal nahi aayega
    """
    
    def __init__(self, 
                 ema_period=200,
                 st_atr_period=55,        # PineScript default: 55
                 st_multiplier=3.8,       # PineScript default: 3.8
                 tp_percent=3.0,          # PineScript default: 3.0
                 sl_percent=0.55):         # PineScript default: 0.55
        """
        Initialize strategy parameters
        
        Default values match script.pine: ATR=55, Mult=3.8, TP=3.0%, SL=0.55%
        
        Args:
            ema_period: EMA period (default 200)
            st_atr_period: SuperTrend ATR period (default 55)
            st_multiplier: SuperTrend multiplier (default 3.8)
            tp_percent: Take profit percentage (default 3.0)
            sl_percent: Stop loss percentage (default 0.55)
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
        
        # Track if already traded in current ST trend (matches script.pine)
        self.traded_in_bull_trend = False
        self.traded_in_bear_trend = False
        
        # Track previous ST state to detect flips
        self.prev_st_bull = None
        self.prev_st_bear = None
        
        # Track previous 1H candle state for crossover detection
        self.prev_1h_idx = None
        self.prev_ema_bull = None
        
        # Track last signal bar index to prevent same bar multiple signals
        self.last_signal_bar_idx = None
        self.last_signal_direction = None  # 'BUY' or 'SELL'
    
    def prepare_data(self, df_1h, df_10m):
        """
        Prepare and align data from both timeframes
        
        Note: This method recalculates indicators, which happens when parameters change.
        Trade flags are NOT reset here - they should only reset on ST flip or EMA cross.
        If you need to reset flags when parameters change, call reset_trade_flags() separately.
        
        Args:
            df_1h: DataFrame with 1H OHLCV data
            df_10m: DataFrame with 10M OHLCV data
        
        Returns:
            Tuple of (prepared_1h_df, prepared_10m_df)
        """
        # Validate input data
        if df_1h is None or df_1h.empty:
            logger.error("prepare_data: df_1h is None or empty")
            return pd.DataFrame(), pd.DataFrame()
        
        if df_10m is None or df_10m.empty:
            logger.error("prepare_data: df_10m is None or empty")
            return pd.DataFrame(), pd.DataFrame()
        
        try:
            # Calculate indicators on 1H data
            df_1h = calculate_ema(df_1h, period=self.ema_period)
            df_1h['above_ema'] = is_price_above_ema(df_1h)
            
            # Calculate indicators on 10M data
            df_10m = calculate_supertrend(df_10m, period=self.st_atr_period, multiplier=self.st_multiplier)
            df_10m['st_positive'] = is_supertrend_positive(df_10m)
            
            return df_1h, df_10m
        except Exception as e:
            logger.error(f"Error in prepare_data: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return pd.DataFrame(), pd.DataFrame()
    
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
    
    def is_1h_bearish(self, df_1h, current_idx):
        """
        Check if 1H bar is confirmed below EMA 200
        Bar must close below EMA (not just touching or between)
        
        Args:
            df_1h: 1H DataFrame
            current_idx: Current index
        
        Returns:
            Boolean
        """
        if current_idx >= len(df_1h):
            return False
        
        current_bar = df_1h.iloc[current_idx]
        return current_bar['close'] < current_bar['ema']
    
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
        # OPTIMIZED: Use searchsorted for O(log n) instead of O(n) filter
        # Find the most recent 10M bar before or at current_time
        if len(df_10m) == 0:
            return False, None, None
        
        # Binary search for position
        idx = df_10m.index.searchsorted(current_time, side='right') - 1
        
        if idx < 0:
            return False, None, None
        
        latest_10m = df_10m.iloc[idx]
        st_value = latest_10m['supertrend']
        close_price = latest_10m['close']
        
        # SuperTrend is positive when close > supertrend (like TradingView)
        is_positive = close_price > st_value
        
        return is_positive, st_value, close_price
    
    def check_entry_signal(self, df_1h, df_10m, current_idx):
        """
        Check for BUY or SELL entry signal (matches script.pine logic)
        
        BUY Condition (from script.pine):
        buyCond = position_size == 0 AND stBull AND emaBull_1h AND not tradedInBullTrend 
                  AND (stBullFlip OR emaBullCross_1h)
        
        Where:
        - stBull = 10M close > SuperTrend
        - stBullFlip = ST just turned bullish (was bearish, now bullish)
        - emaBull_1h = 1H close > EMA 200
        - emaBullCross_1h = 1H candle just closed above EMA (new 1H candle or crossover)
        
        SELL Condition (from script.pine):
        sellCond = position_size == 0 AND stBear AND emaBear_1h AND not tradedInBearTrend 
                   AND (stBearFlip OR emaBearCross_1h)
        
        Args:
            df_1h: 1H DataFrame
            df_10m: 10M DataFrame
            current_idx: Current 1H bar index
        
        Returns:
            Tuple of (signal, price) where signal is 'BUY', 'SELL', or None
        """
        if current_idx >= len(df_1h):
            return None, None
        
        current_1h = df_1h.iloc[current_idx]
        current_time = df_1h.index[current_idx]
        close_1h = current_1h['close']
        ema_1h = current_1h['ema']
        
        # ===== EMA Condition (1H timeframe) =====
        # emaBull_1h = close_1h > ema200_1h
        # emaBear_1h = close_1h < ema200_1h
        ema_bull_1h = close_1h > ema_1h
        ema_bear_1h = close_1h < ema_1h
        
        # Detect 1H EMA crossover (for immediate signal trigger)
        # emaBullCross_1h = emaBull_1h AND (previous close was <= EMA OR new 1H candle started)
        is_new_1h_candle = (self.prev_1h_idx is None or self.prev_1h_idx != current_idx)
        prev_close_1h = df_1h.iloc[current_idx - 1]['close'] if current_idx > 0 else close_1h
        prev_ema_1h = df_1h.iloc[current_idx - 1]['ema'] if current_idx > 0 else ema_1h
        
        ema_bull_cross_1h = ema_bull_1h and (prev_close_1h <= prev_ema_1h or is_new_1h_candle)
        ema_bear_cross_1h = ema_bear_1h and (prev_close_1h >= prev_ema_1h or is_new_1h_candle)
        
        # ===== SuperTrend Condition (10M timeframe) =====
        # stBull = close10 > st10 (stDir < 0 means bullish)
        # stBear = close10 < st10 (stDir > 0 means bearish)
        st_positive, st_value, close_10m = self.get_10m_supertrend_status(df_10m, current_time)
        st_bull = st_positive  # close > supertrend
        st_bear = not st_positive if st_value is not None else False  # close < supertrend
        
        # Detect ST flip (direction change) - matches script.pine line 52-53
        # stBullFlip = stBull AND stDir[1] > 0 (previous was bearish)
        # stBearFlip = stBear AND stDir[1] < 0 (previous was bullish)
        # In our case: stBull = st_positive, so prev was bearish = prev_st_bull was False
        st_bull_flip = st_bull and (self.prev_st_bull is False)
        st_bear_flip = st_bear and (self.prev_st_bull is True)
        
        # Update previous ST state
        self.prev_st_bull = st_bull
        self.prev_st_bear = st_bear
        self.prev_1h_idx = current_idx
        self.prev_ema_bull = ema_bull_1h
        
        # Reset trade flags when ST flips direction (matches script.pine)
        if st_bull_flip:
            self.traded_in_bull_trend = False
        if st_bear_flip:
            self.traded_in_bear_trend = False
        
        # Reset trade flags when 1H EMA crossover happens within same ST trend (matches script.pine)
        if st_bull and ema_bull_cross_1h:
            self.traded_in_bull_trend = False
        if st_bear and ema_bear_cross_1h:
            self.traded_in_bear_trend = False
        
        # ===== BUY ENTRY (matches script.pine line 93) =====
        # buyCond = position_size == 0 AND stBull AND emaBull_1h AND not tradedInBullTrend 
        #           AND (stBullFlip OR emaBullCross_1h)
        # Also prevent same bar multiple signals
        if (self.position == 0 and st_bull and ema_bull_1h and not self.traded_in_bull_trend 
            and (st_bull_flip or ema_bull_cross_1h)
            and not (self.last_signal_bar_idx == current_idx and self.last_signal_direction == 'BUY')):
            logger.info(f"BUY SIGNAL: ST green {'(flip)' if st_bull_flip else ''}, 1H close > EMA ✓, {'EMA cross' if ema_bull_cross_1h else ''}")
            self.traded_in_bull_trend = True
            self.last_signal_bar_idx = current_idx
            self.last_signal_direction = 'BUY'
            return 'BUY', close_1h
        
        # ===== SELL ENTRY (matches script.pine line 94) =====
        # sellCond = position_size == 0 AND stBear AND emaBear_1h AND not tradedInBearTrend 
        #            AND (stBearFlip OR emaBearCross_1h)
        # Also prevent same bar multiple signals
        if (self.position == 0 and st_bear and ema_bear_1h and not self.traded_in_bear_trend 
            and (st_bear_flip or ema_bear_cross_1h)
            and not (self.last_signal_bar_idx == current_idx and self.last_signal_direction == 'SELL')):
            logger.info(f"SELL SIGNAL: ST red {'(flip)' if st_bear_flip else ''}, 1H close < EMA ✓, {'EMA cross' if ema_bear_cross_1h else ''}")
            self.traded_in_bear_trend = True
            self.last_signal_bar_idx = current_idx
            self.last_signal_direction = 'SELL'
            return 'SELL', close_1h
        
        # No entry signal
        return None, None
    
    def check_exit_signal(self, df_10m, df_1h, current_time, current_price, current_idx):
        """
        Check for exit signal (LONG and SHORT positions)
        
        LONG Exit Conditions:
        1. Take Profit: price >= entry * (1 + tpPct/100)
        2. Stop Loss: price <= entry * (1 - slPct/100)
        3. SuperTrend Flip: stBear (close < supertrend) → EXIT
        
        SHORT Exit Conditions:
        1. Take Profit: price <= entry * (1 - tpPct/100)
        2. Stop Loss: price >= entry * (1 + slPct/100)
        3. SuperTrend Flip: stBull (close > supertrend) → EXIT
        
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
        st_bull = st_positive  # close > supertrend
        st_bear = not st_positive if st_value is not None else False  # close < supertrend
        
        # ===== LONG POSITION EXIT =====
        if self.position == 1:
            
            # Check Take Profit: longTP = entry * (1 + tpPct/100)
            if current_price >= self.tp_price:
                self.last_exit_reason = 'TP_HIT'
                logger.info(f"LONG TP hit at {current_price:.2f}")
                return 'TP_HIT'
            
            # Check Stop Loss: longSL = entry * (1 - slPct/100)
            if current_price <= self.sl_price:
                self.last_exit_reason = 'SL_HIT'
                logger.info(f"LONG SL hit at {current_price:.2f}")
                return 'SL_HIT'
            
            # SuperTrend Flip: stBear → EXIT
            # "exit will always happen based on Super Trend"
            if st_bear:
                self.last_exit_reason = 'ST_FLIP'
                logger.info(f"LONG: SuperTrend flipped BEARISH → EXIT")
                return 'ST_FLIP'
        
        # ===== SHORT POSITION EXIT =====
        elif self.position == -1:
            
            # Check Take Profit: shortTP = entry * (1 - tpPct/100)
            if current_price <= self.tp_price:
                self.last_exit_reason = 'TP_HIT'
                logger.info(f"SHORT TP hit at {current_price:.2f}")
                return 'TP_HIT'
            
            # Check Stop Loss: shortSL = entry * (1 + slPct/100)
            if current_price >= self.sl_price:
                self.last_exit_reason = 'SL_HIT'
                logger.info(f"SHORT SL hit at {current_price:.2f}")
                return 'SL_HIT'
            
            # SuperTrend Flip: stBull → EXIT
            # "exit will always happen based on Super Trend"
            if st_bull:
                self.last_exit_reason = 'ST_FLIP'
                logger.info(f"SHORT: SuperTrend flipped BULLISH → EXIT")
                return 'ST_FLIP'
        
        return None
    
    def can_reenter(self, df_1h, df_10m, current_idx):
        """
        Check if re-entry is possible after TP hit
        
        Re-entry Conditions (BUY):
        - Previous exit was TP_HIT
        - 1H bars still above EMA 200
        - 10M SuperTrend turns positive again
        
        Re-entry Conditions (SELL):
        - Previous exit was TP_HIT
        - 1H bars still below EMA 200
        - 10M SuperTrend turns negative again
        
        Returns:
            Boolean
        """
        if self.last_exit_reason != 'TP_HIT':
            return False
        
        if current_idx >= len(df_1h):
            return False
        
        current_time = df_1h.index[current_idx]
        current_1h = df_1h.iloc[current_idx]
        close_1h = current_1h['close']
        ema_1h = current_1h['ema']
        
        # Check 10M SuperTrend
        st_positive, _, _ = self.get_10m_supertrend_status(df_10m, current_time)
        
        # Check if conditions match for re-entry
        # For BUY: emaBull and stBull
        # For SELL: emaBear and stBear
        ema_bull = close_1h > ema_1h
        ema_bear = close_1h < ema_1h
        
        # Return True if either BUY or SELL conditions are met
        return (ema_bull and st_positive) or (ema_bear and not st_positive)
    
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
        
        # Store exit reason for potential re-entry logic
        self.last_exit_reason = reason
        
        # Note: Don't reset traded_in_bull_trend/traded_in_bear_trend here
        # They should only reset when ST flips or EMA crosses (handled in check_entry_signal)
        # This ensures same ST trend mein ek baar trade ke baad phir signal nahi aayega
        
        self.position = 0
        self.entry_price = 0
        self.tp_price = 0
        self.sl_price = 0
        
        return pnl
    
    def reset_trade_flags(self):
        """
        Reset trade flags - call this when parameters change or strategy needs reset
        This prevents double signals on same bar when parameters change
        """
        self.traded_in_bull_trend = False
        self.traded_in_bear_trend = False
        self.prev_st_bull = None
        self.prev_st_bear = None
        self.prev_1h_idx = None
        self.prev_ema_bull = None
        self.last_signal_bar_idx = None
        self.last_signal_direction = None
        logger.info("Trade flags reset (parameters changed or strategy reset)")
    
    def update_parameters(self, tp_percent=None, sl_percent=None, st_atr_period=None, st_multiplier=None):
        """
        Update strategy parameters
        Resets trade flags when parameters change to prevent double signals
        """
        params_changed = False
        
        if tp_percent is not None and tp_percent != self.tp_percent:
            self.tp_percent = tp_percent
            params_changed = True
        if sl_percent is not None and sl_percent != self.sl_percent:
            self.sl_percent = sl_percent
            params_changed = True
        if st_atr_period is not None and st_atr_period != self.st_atr_period:
            self.st_atr_period = st_atr_period
            params_changed = True
        if st_multiplier is not None and st_multiplier != self.st_multiplier:
            self.st_multiplier = st_multiplier
            params_changed = True
        
        # Reset trade flags when parameters change to prevent double signals
        if params_changed:
            self.reset_trade_flags()

