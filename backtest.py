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
            Dictionary with backtest results
        """
        # Prepare data
        df_1h, df_10m = self.strategy.prepare_data(df_1h.copy(), df_10m.copy())
        
        # Reset state
        self.capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        self.strategy.position = 0
        entry_time = None  # Track entry time for trades
        
        # Iterate through 1H bars
        for i in range(len(df_1h)):
            current_1h = df_1h.iloc[i]
            current_time = df_1h.index[i]
            current_price = current_1h['close']
            
            # Check exit first if in position
            if self.strategy.position != 0:
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
            
            # Check entry signal
            if self.strategy.position == 0:
                signal, entry_price = self.strategy.check_entry_signal(df_1h, df_10m, i)
                if signal:
                    self.strategy.enter_position(signal, entry_price)
                    entry_time = current_time  # Track entry time
            
            # Record equity
            self.equity_curve.append({
                'time': current_time,
                'equity': self.capital,
                'price': current_price
            })
        
        # Close any open position at the end
        if self.strategy.position != 0:
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
        
        # Calculate statistics
        results = self.calculate_statistics()
        return results
    
    def calculate_statistics(self):
        """Calculate backtest statistics"""
        if not self.trades:
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
                'final_capital': self.capital,
                'roi': 0
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
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['peak'] = equity_df['equity'].expanding().max()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
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

