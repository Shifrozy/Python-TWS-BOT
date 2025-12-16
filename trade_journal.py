"""
Trade Journal Module
Logs all trades, performance metrics, and generates reports
"""
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradeJournal:
    """Maintains trade journal and generates reports"""
    
    def __init__(self, journal_file: str = "trade_journal.json"):
        """
        Initialize trade journal
        
        Args:
            journal_file: Path to journal file
        """
        self.journal_file = Path(journal_file)
        self.trades = []
        self.load_journal()
    
    def load_journal(self):
        """Load existing journal from file"""
        if self.journal_file.exists():
            try:
                with open(self.journal_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', [])
                logger.info(f"Loaded {len(self.trades)} trades from journal")
            except Exception as e:
                logger.error(f"Error loading journal: {e}")
                self.trades = []
        else:
            self.trades = []
    
    def save_journal(self):
        """Save journal to file"""
        try:
            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.journal_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Journal saved with {len(self.trades)} trades")
        except Exception as e:
            logger.error(f"Error saving journal: {e}")
    
    def add_trade(self, trade_data: dict):
        """
        Add a trade to journal
        
        Args:
            trade_data: Dictionary with trade information
        """
        trade_data['entry_time'] = datetime.now().isoformat()
        trade_data['trade_id'] = len(self.trades) + 1
        self.trades.append(trade_data)
        self.save_journal()
        logger.info(f"Trade #{trade_data['trade_id']} added to journal")
    
    def update_trade(self, trade_id: int, exit_data: dict):
        """
        Update trade with exit information
        
        Args:
            trade_id: Trade ID to update
            exit_data: Dictionary with exit information
        """
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                trade.update(exit_data)
                trade['exit_time'] = datetime.now().isoformat()
                self.save_journal()
                logger.info(f"Trade #{trade_id} updated")
                return
        logger.warning(f"Trade #{trade_id} not found")
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get all trades as DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)
    
    def get_performance_summary(self) -> dict:
        """Get performance summary"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0
            }
        
        df = self.get_trades_df()
        
        # Filter completed trades
        completed = df[df['exit_time'].notna()].copy()
        if completed.empty:
            return {'total_trades': len(df), 'open_trades': len(df[df['exit_time'].isna()])}
        
        completed['pnl'] = pd.to_numeric(completed.get('pnl', 0), errors='coerce')
        
        winning = completed[completed['pnl'] > 0]
        losing = completed[completed['pnl'] <= 0]
        
        return {
            'total_trades': len(completed),
            'open_trades': len(df[df['exit_time'].isna()]),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': (len(winning) / len(completed) * 100) if len(completed) > 0 else 0,
            'total_pnl': completed['pnl'].sum(),
            'avg_win': winning['pnl'].mean() if len(winning) > 0 else 0,
            'avg_loss': losing['pnl'].mean() if len(losing) > 0 else 0,
            'profit_factor': (winning['pnl'].sum() / abs(losing['pnl'].sum())) if len(losing) > 0 and losing['pnl'].sum() != 0 else 0,
            'largest_win': completed['pnl'].max(),
            'largest_loss': completed['pnl'].min()
        }
    
    def export_to_csv(self, filename: str = "trades_export.csv"):
        """Export trades to CSV"""
        df = self.get_trades_df()
        if not df.empty:
            df.to_csv(filename, index=False)
            logger.info(f"Trades exported to {filename}")
        else:
            logger.warning("No trades to export")
    
    def get_recent_trades(self, n: int = 10) -> pd.DataFrame:
        """Get recent N trades"""
        df = self.get_trades_df()
        if df.empty:
            return df
        return df.tail(n)

