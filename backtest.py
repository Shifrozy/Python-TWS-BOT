"""
Backtesting Module
"""
import pandas as pd
import numpy as np
from strategy import TradingStrategy
from indicators import calculate_ema, calculate_supertrend
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtesting engine for the trading strategy"""
    
    def __init__(self, strategy, initial_capital=100000):
        """
        Initialize backtest engine
        
        Args:
            strategy: TradingStrategy instance
            initial_capital: Starting capital
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades = []
        self.equity_curve = []
    
    def run_backtest(self, df_1h, df_10m, contract_size=20):
        """
        Run backtest on historical data
        
        Args:
            df_1h: 1H DataFrame
            df_10m: 10M DataFrame
            contract_size: Contract multiplier (default 20 for NQ)
        
        Returns:
            Dictionary with backtest results (always returns a dict, never None)
        """
        # Validate input data
        if df_1h is None or df_1h.empty:
            logger.error("Backtest failed: df_1h is None or empty")
            return self.calculate_statistics()  # Return empty results
        
        if df_10m is None or df_10m.empty:
            logger.error("Backtest failed: df_10m is None or empty")
            return self.calculate_statistics()  # Return empty results
        
        try:
            # Prepare data
            df_1h, df_10m = self.strategy.prepare_data(df_1h.copy(), df_10m.copy())
            
            # Validate prepared data
            if df_1h.empty or df_10m.empty:
                logger.error("Backtest failed: Prepared dataframes are empty")
                return self.calculate_statistics()
            
            # Reset state
            self.capital = self.initial_capital
            self.trades = []
            self.equity_curve = []
            self.strategy.position = 0
            entry_time = None  # Track entry time for trades
            
            total_bars = len(df_1h)
            logger.info(f"Starting backtest loop: {total_bars} bars to process")
            
            # Iterate through 1H bars
            for i in range(total_bars):
                # Log progress every 100 bars (reduced for speed)
                if i == 0 or i == total_bars - 1 or (i + 1) % 100 == 0:
                    logger.info(f"Processing bar {i+1}/{total_bars} ({((i+1)/total_bars*100):.1f}%)")
                try:
                    current_1h = df_1h.iloc[i]
                    current_time = df_1h.index[i]
                    current_price = current_1h['close']
                    
                    # Check exit first if in position
                    if self.strategy.position != 0:
                        try:
                            exit_signal = self.strategy.check_exit_signal(df_10m, df_1h, current_time, current_price, i)
                            if exit_signal:
                                pnl_pct = self.strategy.exit_position(current_price, exit_signal)
                                if pnl_pct is not None:
                                    # Calculate PnL in dollars
                                    position_value = self.capital * 0.1  # Assume 10% of capital per trade
                                    pnl_dollar = position_value * (pnl_pct / 100)
                                    self.capital += pnl_dollar
                                    
                                    self.trades.append({
                                        'entry_time': entry_time if entry_time else current_time,
                                        'exit_time': current_time,
                                        'entry_price': self.strategy.entry_price,
                                        'exit_price': current_price,
                                        'pnl_pct': pnl_pct,
                                        'pnl_dollar': pnl_dollar,
                                        'exit_reason': exit_signal
                                    })
                                    entry_time = None  # Reset entry time
                                    
                                    # CONTINUOUS TRADING: After TP hit, if conditions still met, re-enter
                                    # As per client: "agar TP hit hone k bad 10 mints ke chart main 
                                    # again positive trade arhai buy ki to again buy ki trade place ho"
                                    if exit_signal == 'TP_HIT':
                                        # Check if we can re-enter using the strategy's can_reenter method
                                        if self.strategy.can_reenter(df_1h, df_10m, i):
                                            signal, entry_price = self.strategy.check_entry_signal(df_1h, df_10m, i)
                                            if signal:
                                                self.strategy.enter_position(signal, entry_price)
                                                entry_time = current_time  # Track new entry time
                                                logger.info(f"CONTINUOUS TRADING: Re-entry at {entry_price:.2f}")
                        except Exception as e:
                            logger.warning(f"Error checking exit signal at index {i}: {e}")
                            # Continue with next bar
                            continue
                    
                    # Check entry signal
                    if self.strategy.position == 0:
                        try:
                            signal, entry_price = self.strategy.check_entry_signal(df_1h, df_10m, i)
                            if signal:
                                self.strategy.enter_position(signal, entry_price)
                                entry_time = current_time  # Track entry time
                        except Exception as e:
                            logger.warning(f"Error checking entry signal at index {i}: {e}")
                            # Continue with next bar
                            continue
                    
                    # Record equity
                    self.equity_curve.append({
                        'time': current_time,
                        'equity': self.capital,
                        'price': current_price
                    })
                except Exception as e:
                    logger.warning(f"Error processing bar at index {i}: {e}")
                    # Continue with next bar
                    continue
            
            # Close any open position at the end
            if self.strategy.position != 0:
                try:
                    final_price = df_1h.iloc[-1]['close']
                    final_time = df_1h.index[-1]
                    pnl_pct = self.strategy.exit_position(final_price, 'END_OF_DATA')
                    if pnl_pct is not None:
                        position_value = self.capital * 0.1
                        pnl_dollar = position_value * (pnl_pct / 100)
                        self.capital += pnl_dollar
                        self.trades.append({
                            'entry_time': entry_time if entry_time else final_time,
                            'exit_time': final_time,
                            'entry_price': self.strategy.entry_price,
                            'exit_price': final_price,
                            'pnl_pct': pnl_pct,
                            'pnl_dollar': pnl_dollar,
                            'exit_reason': 'END_OF_DATA'
                        })
                except Exception as e:
                    logger.warning(f"Error closing final position: {e}")
            
            # Calculate statistics
            logger.info(f"Backtest loop completed. Total trades: {len(self.trades)}")
            results = self.calculate_statistics()
            logger.info(f"Statistics calculated. Total trades in results: {results.get('total_trades', 0)}")
            return results
        except Exception as e:
            logger.error(f"Backtest execution error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # Return empty results instead of None
            return self.calculate_statistics()
    
    def calculate_statistics(self):
        """Calculate backtest statistics - always returns a dict with all required keys"""
        try:
            if not self.trades:
                # Return empty results with empty DataFrames
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'total_pnl_pct': 0,
                    'avg_win': 0,
                    'avg_loss': 0,
                    'profit_factor': 0,
                    'max_drawdown': 0,
                    'final_capital': self.capital if hasattr(self, 'capital') else self.initial_capital,
                    'roi': 0,
                    'trades': pd.DataFrame(),
                    'equity_curve': pd.DataFrame(self.equity_curve) if self.equity_curve else pd.DataFrame()
                }
            
            trades_df = pd.DataFrame(self.trades)
            
            winning_trades = trades_df[trades_df['pnl_pct'] > 0]
            losing_trades = trades_df[trades_df['pnl_pct'] <= 0]
            
            total_trades = len(trades_df)
            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            total_pnl = trades_df['pnl_dollar'].sum()
            total_pnl_pct = trades_df['pnl_pct'].sum()
            
            avg_win = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
            avg_loss = abs(losing_trades['pnl_pct'].mean()) if len(losing_trades) > 0 else 0
            
            total_wins = winning_trades['pnl_dollar'].sum() if len(winning_trades) > 0 else 0
            total_losses = abs(losing_trades['pnl_dollar'].sum()) if len(losing_trades) > 0 else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
            
            # Calculate max drawdown
            if self.equity_curve:
                equity_df = pd.DataFrame(self.equity_curve)
                equity_df['peak'] = equity_df['equity'].expanding().max()
                equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
                max_drawdown = equity_df['drawdown'].min()
            else:
                equity_df = pd.DataFrame()
                max_drawdown = 0
            
            roi = ((self.capital - self.initial_capital) / self.initial_capital) * 100
            
            return {
                'total_trades': total_trades,
                'winning_trades': win_count,
                'losing_trades': loss_count,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'final_capital': self.capital,
                'roi': roi,
                'trades': trades_df,
                'equity_curve': equity_df
            }
        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            # Return safe default results
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'final_capital': self.initial_capital,
                'roi': 0,
                'trades': pd.DataFrame(),
                'equity_curve': pd.DataFrame()
            }

