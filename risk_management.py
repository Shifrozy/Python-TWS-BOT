"""
Advanced Risk Management Module
Handles position sizing, risk calculation, and portfolio management
"""
import logging
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskManager:
    """Advanced risk management for trading"""
    
    def __init__(self, 
                 account_balance: float = 100000,
                 risk_per_trade: float = 1.0,  # 1% risk per trade
                 max_position_size: float = 10.0,  # 10% max position
                 max_daily_loss: float = 5.0,  # 5% max daily loss
                 max_drawdown: float = 20.0):  # 20% max drawdown
        """
        Initialize risk manager
        
        Args:
            account_balance: Starting account balance
            risk_per_trade: Risk percentage per trade (default 1%)
            max_position_size: Maximum position size as % of account (default 10%)
            max_daily_loss: Maximum daily loss percentage (default 5%)
            max_drawdown: Maximum drawdown percentage (default 20%)
        """
        self.account_balance = account_balance
        self.initial_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.peak_balance = account_balance
        self.current_drawdown = 0.0
    
    def calculate_position_size(self, entry_price: float, stop_loss_price: float, 
                               contract_multiplier: int = 20) -> int:
        """
        Calculate position size based on risk
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            contract_multiplier: Contract multiplier (20 for NQ)
        
        Returns:
            Number of contracts to trade
        """
        if stop_loss_price == entry_price:
            return 0
        
        # Calculate risk per contract
        price_risk = abs(entry_price - stop_loss_price)
        dollar_risk_per_contract = price_risk * contract_multiplier
        
        if dollar_risk_per_contract == 0:
            return 0
        
        # Calculate risk amount based on account balance
        risk_amount = self.account_balance * (self.risk_per_trade / 100)
        
        # Calculate number of contracts
        num_contracts = int(risk_amount / dollar_risk_per_contract)
        
        # Apply max position size limit
        max_contracts_by_size = int((self.account_balance * self.max_position_size / 100) / 
                                   (entry_price * contract_multiplier))
        num_contracts = min(num_contracts, max_contracts_by_size)
        
        # Ensure at least 1 contract if we have enough capital
        if num_contracts == 0 and risk_amount >= dollar_risk_per_contract:
            num_contracts = 1
        
        return max(0, num_contracts)
    
    def can_trade(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed based on risk limits
        
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        # Check daily loss limit
        daily_loss_pct = (self.daily_pnl / self.initial_balance) * 100
        if daily_loss_pct <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: {daily_loss_pct:.2f}%"
        
        # Check drawdown limit
        if self.account_balance < self.peak_balance:
            drawdown = ((self.peak_balance - self.account_balance) / self.peak_balance) * 100
            self.current_drawdown = drawdown
            if drawdown >= self.max_drawdown:
                return False, f"Max drawdown reached: {drawdown:.2f}%"
        
        return (True, "OK")
    
    def update_balance(self, pnl: float):
        """Update account balance after trade"""
        self.account_balance += pnl
        self.total_pnl += pnl
        self.daily_pnl += pnl
        
        # Update peak balance
        if self.account_balance > self.peak_balance:
            self.peak_balance = self.account_balance
            self.current_drawdown = 0.0
    
    def reset_daily_pnl(self):
        """Reset daily PnL (call at start of new trading day)"""
        self.daily_pnl = 0.0
    
    def get_risk_metrics(self) -> dict:
        """Get current risk metrics"""
        return {
            'account_balance': self.account_balance,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': (self.total_pnl / self.initial_balance) * 100,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': (self.daily_pnl / self.initial_balance) * 100,
            'current_drawdown': self.current_drawdown,
            'peak_balance': self.peak_balance,
            'can_trade': self.can_trade()[0]
        }
    
    def update_parameters(self, risk_per_trade: Optional[float] = None,
                        max_position_size: Optional[float] = None,
                        max_daily_loss: Optional[float] = None,
                        max_drawdown: Optional[float] = None):
        """Update risk parameters"""
        if risk_per_trade is not None:
            self.risk_per_trade = risk_per_trade
        if max_position_size is not None:
            self.max_position_size = max_position_size
        if max_daily_loss is not None:
            self.max_daily_loss = max_daily_loss
        if max_drawdown is not None:
            self.max_drawdown = max_drawdown

