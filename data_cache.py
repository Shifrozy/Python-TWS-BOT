"""
Data Cache Module
Saves and loads historical data to/from CSV files for offline backtesting
"""
import os
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCache:
    """
    CSV-based data cache for historical OHLCV data
    Enables offline backtesting when IBKR is unavailable
    """
    
    def __init__(self, cache_dir="./data_cache"):
        """
        Initialize data cache
        
        Args:
            cache_dir: Directory to store CSV files
        """
        self.cache_dir = cache_dir
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"Created cache directory: {self.cache_dir}")
    
    def _get_filename(self, symbol, timeframe):
        """Generate filename for a symbol and timeframe"""
        return os.path.join(self.cache_dir, f"{symbol}_{timeframe}.csv")
    
    def save_data(self, symbol, timeframe, df):
        """
        Save DataFrame to CSV cache
        
        Args:
            symbol: Instrument symbol (e.g., 'MNQ', 'NQ')
            timeframe: Timeframe string (e.g., '1H', '10M')
            df: DataFrame with OHLCV data (index should be datetime)
        
        Returns:
            str: Path to saved file
        """
        if df is None or df.empty:
            logger.warning(f"Cannot save empty DataFrame for {symbol} {timeframe}")
            return None
        
        filename = self._get_filename(symbol, timeframe)
        
        try:
            # If file exists, merge with existing data
            if os.path.exists(filename):
                existing_df = pd.read_csv(filename, index_col=0, parse_dates=True)
                # Combine and remove duplicates
                combined_df = pd.concat([existing_df, df])
                combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                combined_df = combined_df.sort_index()
                combined_df.to_csv(filename)
                logger.info(f"✓ Updated cache: {filename} ({len(combined_df)} total bars)")
            else:
                df.to_csv(filename)
                logger.info(f"✓ Saved new cache: {filename} ({len(df)} bars)")
            
            return filename
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            return None
    
    def load_data(self, symbol, timeframe, start_date=None, end_date=None):
        """
        Load data from CSV cache
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe string
            start_date: Optional start date filter (datetime or string)
            end_date: Optional end date filter (datetime or string)
        
        Returns:
            DataFrame with OHLCV data, or empty DataFrame if not found
        """
        filename = self._get_filename(symbol, timeframe)
        
        if not os.path.exists(filename):
            logger.warning(f"Cache not found: {filename}")
            return pd.DataFrame()
        
        try:
            df = pd.read_csv(filename, index_col=0, parse_dates=True)
            
            # Filter by date range if provided
            if start_date is not None:
                if isinstance(start_date, str):
                    start_date = pd.to_datetime(start_date)
                df = df[df.index >= start_date]
            
            if end_date is not None:
                if isinstance(end_date, str):
                    end_date = pd.to_datetime(end_date)
                df = df[df.index <= end_date]
            
            logger.info(f"✓ Loaded from cache: {filename} ({len(df)} bars)")
            return df
            
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return pd.DataFrame()
    
    def has_data(self, symbol, timeframe, start_date=None, end_date=None):
        """
        Check if cache has data for the requested range
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe string
            start_date: Start of required range
            end_date: End of required range
        
        Returns:
            bool: True if cache has sufficient data
        """
        df = self.load_data(symbol, timeframe, start_date, end_date)
        return not df.empty and len(df) > 0
    
    def get_cache_info(self, symbol=None):
        """
        Get information about cached data
        
        Args:
            symbol: Optional symbol filter
        
        Returns:
            dict: Cache statistics
        """
        info = {}
        
        if not os.path.exists(self.cache_dir):
            return info
        
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.csv'):
                filepath = os.path.join(self.cache_dir, filename)
                parts = filename.replace('.csv', '').split('_')
                
                if len(parts) >= 2:
                    file_symbol = parts[0]
                    timeframe = parts[1]
                    
                    if symbol and file_symbol != symbol:
                        continue
                    
                    try:
                        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
                        info[filename] = {
                            'symbol': file_symbol,
                            'timeframe': timeframe,
                            'bars': len(df),
                            'start': df.index.min().strftime('%Y-%m-%d %H:%M') if len(df) > 0 else 'N/A',
                            'end': df.index.max().strftime('%Y-%m-%d %H:%M') if len(df) > 0 else 'N/A',
                            'file_size': os.path.getsize(filepath),
                        }
                    except:
                        pass
        
        return info
    
    def clear_cache(self, symbol=None, timeframe=None):
        """
        Clear cached data
        
        Args:
            symbol: Optional symbol filter
            timeframe: Optional timeframe filter
        """
        if not os.path.exists(self.cache_dir):
            return
        
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.csv'):
                parts = filename.replace('.csv', '').split('_')
                
                if len(parts) >= 2:
                    file_symbol = parts[0]
                    file_timeframe = parts[1]
                    
                    if symbol and file_symbol != symbol:
                        continue
                    if timeframe and file_timeframe != timeframe:
                        continue
                    
                    filepath = os.path.join(self.cache_dir, filename)
                    os.remove(filepath)
                    logger.info(f"Deleted cache: {filepath}")


# Quick test
if __name__ == "__main__":
    import numpy as np
    
    print("Testing DataCache...")
    cache = DataCache()
    
    # Create sample data
    dates = pd.date_range(start='2025-12-18', end='2025-12-20', freq='1h')
    sample_data = pd.DataFrame({
        'open': np.random.uniform(21000, 21500, len(dates)),
        'high': np.random.uniform(21500, 22000, len(dates)),
        'low': np.random.uniform(20500, 21000, len(dates)),
        'close': np.random.uniform(21000, 21500, len(dates)),
        'volume': np.random.randint(1000, 5000, len(dates)),
    }, index=dates)
    
    # Test save
    print("\n--- Testing Save ---")
    cache.save_data('MNQ', '1H', sample_data)
    
    # Test load
    print("\n--- Testing Load ---")
    loaded = cache.load_data('MNQ', '1H')
    print(f"Loaded {len(loaded)} bars")
    print(loaded.head())
    
    # Test info
    print("\n--- Cache Info ---")
    info = cache.get_cache_info()
    for filename, details in info.items():
        print(f"{filename}: {details['bars']} bars, {details['start']} to {details['end']}")
    
    print("\n✓ DataCache test completed!")
