"""
Performance Analytics Module
Advanced performance metrics and analysis
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """Advanced performance analytics"""
    
    def __init__(self):
        """Initialize analytics"""
        self.equity_curve = []
        self.trades = []
    
    def add_equity_point(self, timestamp: datetime, equity: float):
        """Add equity point to curve"""
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': equity
        })
    
    def add_trade(self, trade_data: Dict):
        """Add trade data"""
        self.trades.append(trade_data)
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sharpe ratio
        
        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
        
        Returns:
            Sharpe ratio
        """
        if len(self.equity_curve) < 2:
            return 0.0
        
        df = pd.DataFrame(self.equity_curve)
        df['returns'] = df['equity'].pct_change()
        returns = df['returns'].dropna()
        
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        # Annualized Sharpe ratio
        excess_returns = returns.mean() - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe = (excess_returns / returns.std()) * np.sqrt(252)
        
        return sharpe
    
    def calculate_sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        Calculate Sortino ratio (only penalizes downside volatility)
        
        Args:
            risk_free_rate: Annual risk-free rate
        
        Returns:
            Sortino ratio
        """
        if len(self.equity_curve) < 2:
            return 0.0
        
        df = pd.DataFrame(self.equity_curve)
        df['returns'] = df['equity'].pct_change()
        returns = df['returns'].dropna()
        
        if len(returns) == 0:
            return 0.0
        
        # Downside deviation (only negative returns)
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        excess_returns = returns.mean() - (risk_free_rate / 252)
        sortino = (excess_returns / downside_returns.std()) * np.sqrt(252)
        
        return sortino
    
    def calculate_max_drawdown(self) -> Dict:
        """
        Calculate maximum drawdown
        
        Returns:
            Dictionary with max_drawdown, max_drawdown_pct, and duration
        """
        if len(self.equity_curve) < 2:
            return {'max_drawdown': 0, 'max_drawdown_pct': 0, 'duration_days': 0}
        
        df = pd.DataFrame(self.equity_curve)
        df['peak'] = df['equity'].expanding().max()
        df['drawdown'] = df['equity'] - df['peak']
        df['drawdown_pct'] = (df['drawdown'] / df['peak']) * 100
        
        max_dd = df['drawdown'].min()
        max_dd_pct = df['drawdown_pct'].min()
        
        # Calculate drawdown duration
        in_drawdown = df['drawdown'] < 0
        if in_drawdown.any():
            drawdown_periods = []
            start = None
            for i, in_dd in enumerate(in_drawdown):
                if in_dd and start is None:
                    start = i
                elif not in_dd and start is not None:
                    drawdown_periods.append(i - start)
                    start = None
            if start is not None:
                drawdown_periods.append(len(df) - start)
            
            max_duration = max(drawdown_periods) if drawdown_periods else 0
        else:
            max_duration = 0
        
        return {
            'max_drawdown': abs(max_dd),
            'max_drawdown_pct': abs(max_dd_pct),
            'duration_days': max_duration
        }
    
    def calculate_calmar_ratio(self) -> float:
        """
        Calculate Calmar ratio (annual return / max drawdown)
        
        Returns:
            Calmar ratio
        """
        if len(self.equity_curve) < 2:
            return 0.0
        
        df = pd.DataFrame(self.equity_curve)
        total_return = (df['equity'].iloc[-1] / df['equity'].iloc[0] - 1) * 100
        
        # Annualize return (assuming daily data)
        days = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).days
        if days == 0:
            return 0.0
        annual_return = total_return * (365 / days)
        
        max_dd = self.calculate_max_drawdown()
        max_dd_pct = abs(max_dd['max_drawdown_pct'])
        
        if max_dd_pct == 0:
            return 0.0
        
        calmar = annual_return / max_dd_pct
        return calmar
    
    def calculate_trade_statistics(self) -> Dict:
        """Calculate detailed trade statistics"""
        if not self.trades:
            return {}
        
        df = pd.DataFrame(self.trades)
        
        # Filter completed trades
        completed = df[df.get('exit_time', pd.Series()).notna()].copy()
        if completed.empty:
            return {'total_trades': len(df), 'open_trades': len(df)}
        
        completed['pnl'] = pd.to_numeric(completed.get('pnl', 0), errors='coerce')
        completed['pnl_pct'] = pd.to_numeric(completed.get('pnl_pct', 0), errors='coerce')
        
        winning = completed[completed['pnl'] > 0]
        losing = completed[completed['pnl'] <= 0]
        
        # Calculate holding periods
        if 'entry_time' in completed.columns and 'exit_time' in completed.columns:
            completed['entry_time'] = pd.to_datetime(completed['entry_time'])
            completed['exit_time'] = pd.to_datetime(completed['exit_time'])
            completed['holding_period'] = (completed['exit_time'] - completed['entry_time']).dt.total_seconds() / 3600  # hours
        
        return {
            'total_trades': len(completed),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': (len(winning) / len(completed) * 100) if len(completed) > 0 else 0,
            'total_pnl': completed['pnl'].sum(),
            'avg_pnl': completed['pnl'].mean(),
            'avg_win': winning['pnl'].mean() if len(winning) > 0 else 0,
            'avg_loss': losing['pnl'].mean() if len(losing) > 0 else 0,
            'largest_win': completed['pnl'].max(),
            'largest_loss': completed['pnl'].min(),
            'profit_factor': (winning['pnl'].sum() / abs(losing['pnl'].sum())) if len(losing) > 0 and losing['pnl'].sum() != 0 else 0,
            'avg_holding_period_hours': completed['holding_period'].mean() if 'holding_period' in completed.columns else 0,
            'expectancy': (completed['pnl'].mean() * (len(winning) / len(completed))) if len(completed) > 0 else 0
        }
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        trade_stats = self.calculate_trade_statistics()
        drawdown_stats = self.calculate_max_drawdown()
        
        report = {
            'trade_statistics': trade_stats,
            'drawdown_analysis': drawdown_stats,
            'sharpe_ratio': self.calculate_sharpe_ratio(),
            'sortino_ratio': self.calculate_sortino_ratio(),
            'calmar_ratio': self.calculate_calmar_ratio(),
            'timestamp': datetime.now().isoformat()
        }
        
        return report

