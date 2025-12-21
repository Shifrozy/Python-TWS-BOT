"""
Alternative Data Source Module
Uses yfinance for free historical data when IBKR is not available
Supports NQ futures and other instruments
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if yfinance is available
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available. Install with: pip install yfinance")


class AlternativeDataSource:
    """
    Alternative data source using yfinance
    Provides free historical data for backtesting
    """
    
    # Symbol mapping for futures
    SYMBOL_MAP = {
        'MNQ': 'NQ=F',      # Micro Nasdaq E-mini
        'NQ': 'NQ=F',       # Nasdaq E-mini  
        'MES': 'ES=F',      # Micro S&P 500 E-mini
        'ES': 'ES=F',       # S&P 500 E-mini
        'GC': 'GC=F',       # Gold
        'CL': 'CL=F',       # Crude Oil
        'BTC': 'BTC-USD',   # Bitcoin
    }
    
    def __init__(self):
        """Initialize alternative data source"""
        self.available = YFINANCE_AVAILABLE
    
    def get_yf_symbol(self, ibkr_symbol):
        """Convert IBKR symbol to yfinance symbol"""
        return self.SYMBOL_MAP.get(ibkr_symbol, f"{ibkr_symbol}=F")
    
    def get_historical_data(self, symbol='MNQ', interval='1h', period='30d', 
                           start_date=None, end_date=None):
        """
        Get historical data from yfinance
        
        Args:
            symbol: IBKR-style symbol (MNQ, NQ, ES, etc.)
            interval: '1m', '5m', '15m', '30m', '1h', '1d', '1wk', '1mo'
            period: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'
            start_date: Start date (datetime or string 'YYYY-MM-DD')
            end_date: End date (datetime or string 'YYYY-MM-DD')
        
        Returns:
            DataFrame with OHLCV data
        """
        if not self.available:
            logger.error("yfinance not available")
            return pd.DataFrame()
        
        try:
            yf_symbol = self.get_yf_symbol(symbol)
            logger.info(f"Fetching data for {yf_symbol} (IBKR: {symbol})")
            
            ticker = yf.Ticker(yf_symbol)
            
            # Use date range if provided, otherwise use period
            if start_date and end_date:
                # Convert to string format if datetime
                if isinstance(start_date, datetime):
                    start_date = start_date.strftime('%Y-%m-%d')
                if isinstance(end_date, datetime):
                    end_date = end_date.strftime('%Y-%m-%d')
                
                df = ticker.history(start=start_date, end=end_date, interval=interval)
            else:
                df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No data returned for {yf_symbol}")
                return pd.DataFrame()
            
            # Standardize column names
            df.columns = [col.lower() for col in df.columns]
            
            # Keep only OHLCV columns
            columns_to_keep = ['open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in columns_to_keep if col in df.columns]]
            
            logger.info(f"✓ Fetched {len(df)} bars for {yf_symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return pd.DataFrame()
    
    def get_1h_data(self, symbol='MNQ', days=30, end_date=None):
        """
        Get 1-hour data (matches IBKR interface)
        
        Args:
            symbol: IBKR-style symbol
            days: Number of days of data
            end_date: End date
        
        Returns:
            DataFrame with 1H OHLCV data
        """
        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date.split()[0], '%Y%m%d')
            start_date = end_date - timedelta(days=days)
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        return self.get_historical_data(
            symbol=symbol,
            interval='1h',
            start_date=start_date,
            end_date=end_date
        )
    
    def get_10m_data(self, symbol='MNQ', days=7, end_date=None):
        """
        Get 10-minute data (approximated with 15m since yfinance doesn't support 10m)
        Note: yfinance intraday data is limited to last 60 days
        
        Args:
            symbol: IBKR-style symbol
            days: Number of days of data (max 60 for intraday)
            end_date: End date
        
        Returns:
            DataFrame with ~10M OHLCV data (actually 15min)
        """
        # yfinance limits intraday data
        days = min(days, 59)  # Max 59 days for intraday
        
        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date.split()[0], '%Y%m%d')
            start_date = end_date - timedelta(days=days)
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        # Use 15m since 10m is not available in yfinance
        # This is close enough for backtesting purposes
        df = self.get_historical_data(
            symbol=symbol,
            interval='15m',  # Closest to 10m available
            start_date=start_date,
            end_date=end_date
        )
        
        if not df.empty:
            logger.info(f"Note: Using 15-minute data (yfinance doesn't support 10m)")
        
        return df
    
    def test_connection(self):
        """Test if yfinance is working"""
        if not self.available:
            return False, "yfinance not installed"
        
        try:
            df = self.get_historical_data('NQ', interval='1d', period='5d')
            if not df.empty:
                return True, f"yfinance working - got {len(df)} bars"
            else:
                return False, "No data returned"
        except Exception as e:
            return False, f"Error: {e}"


# Quick test
if __name__ == "__main__":
    print("Testing Alternative Data Source...")
    source = AlternativeDataSource()
    
    success, msg = source.test_connection()
    print(f"Connection test: {msg}")
    
    if success:
        print("\n--- 1H Data (last 7 days) ---")
        df_1h = source.get_1h_data('MNQ', days=7)
        print(df_1h.head())
        print(f"Total bars: {len(df_1h)}")
        
        print("\n--- 15M Data (last 5 days) ---")
        df_10m = source.get_10m_data('MNQ', days=5)
        print(df_10m.head())
        print(f"Total bars: {len(df_10m)}")
