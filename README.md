# Nasdaq Futures Trading Bot - EMA 200 + SuperTrend Strategy

A Python-based trading bot for Interactive Brokers TWS that implements an EMA 200 (1H) + SuperTrend (10M) trading strategy for Nasdaq futures.

## Strategy Overview

### Entry Conditions:
1. **1H Timeframe**: Bar must close above EMA 200 (confirmed)
2. **10M Timeframe**: SuperTrend must be positive (bullish)
3. Both conditions must be met simultaneously

### Exit Conditions:
1. Take Profit (TP) or Stop Loss (SL) hit
2. 10M SuperTrend turns negative (for long positions)
3. After TP hit, if 10M shows downtrend, exit. If it becomes positive again, enter another buy trade
4. Continuously trade as long as bars are above EMA 200 on 1H

### Strategy Rules:
- Don't trade if 10M SuperTrend is positive but 1H EMA is negative
- Don't trade if 10M is positive but 1H bar is still between EMA (not confirmed)
- Only trade when 1H bar closes above EMA 200 (confirmed)

## Features

- ✅ Interactive Brokers TWS Integration
- ✅ Real-time Trading
- ✅ Backtesting Engine
- ✅ CustomTkinter GUI
- ✅ Configurable Parameters (TP, SL, SuperTrend settings)
- ✅ Live Position Tracking
- ✅ Performance Statistics

## Installation

1. Install Python 3.8 or higher

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Make sure Interactive Brokers TWS is installed and running:
   - For paper trading: Port 7497
   - For live trading: Port 7496

## Usage

1. Start TWS (Trader Workstation) and enable API connections:
   - Go to Configure → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Set Socket port (default 7497 for paper, 7496 for live)

2. Test your TWS connection (recommended first step):
```bash
python test_connection.py
```
This will help diagnose any connection issues before running the main bot.

3. Run the application:
```bash
python main.py
```

3. In the GUI:
   - Enter TWS connection details:
     - Host: 127.0.0.1
     - Port: 7497 (paper trading) or 7496 (live trading)
     - Client ID: 1 (must be unique, use different ID if running multiple instances)
   - Click "Connect to TWS"
   - Adjust strategy parameters if needed (TP, SL, SuperTrend settings, Contract Quantity)
   - Click "Update Parameters" to save changes
   - Click "Run Backtest" to test the strategy
   - Click "Start Live Trading" to begin automated trading
   - Monitor real-time price, position, and account information

## Strategy Parameters

### Default Values (Client Verbal Specification)
| Parameter | Value |
|-----------|-------|
| EMA Period | 200 |
| SuperTrend ATR | **10** |
| SuperTrend Multiplier | **3.0** |
| Take Profit | **1.2%** |
| Stop Loss | **0.4%** |

### PineScript Values (Alternative)
| Parameter | Value |
|-----------|-------|
| EMA Period | 200 |
| SuperTrend ATR | **55** |
| SuperTrend Multiplier | **3.8** |
| Take Profit | **3.0%** |
| Stop Loss | **0.55%** |

You can change these in the GUI or update defaults in `strategy.py`

- **Contract Quantity**: Default 1 (number of contracts per trade)

## Strategy Logic (LONG ONLY - No Shorts)

### BUY Entry Condition
```
buyCond = position == 0 AND emaBull AND stBull
```
- `emaBull`: 1H close > EMA 200
- `stBull`: 10M close > SuperTrend
- Both conditions must be TRUE

### Exit Conditions
```
- TP: price >= entry * (1 + tpPct/100)
- SL: price <= entry * (1 - slPct/100)  
- ST Flip: stBear (10M close < supertrend) → EXIT
```

### Continuous Trading Logic
- After TP hit: If 10M becomes positive again → re-enter BUY
- Continue trading as long as 1H bars stay above EMA 200
- Exit when SuperTrend flips bearish

## Advanced Features

### Live Trading
- ✅ Real-time market data streaming
- ✅ Position synchronization with IBKR
- ✅ Account information display (Net Liquidation, Buying Power)
- ✅ Real-time price updates
- ✅ Order management and tracking
- ✅ Automatic position syncing
- ✅ Client ID configuration for multiple instances

### Risk Management
- ✅ **Automatic Position Sizing**: Calculates position size based on risk per trade
- ✅ **Risk Limits**: Max daily loss, max drawdown protection
- ✅ **Real-time Risk Monitoring**: Live risk metrics display
- ✅ **Account Protection**: Automatic trading halt when limits reached

### Advanced Order Types
- ✅ **Market Orders**: Standard market execution
- ✅ **Bracket Orders**: Entry + TP + SL in one order
- ✅ **Stop Loss Orders**: Automatic stop loss placement
- ✅ **Take Profit Orders**: Automatic profit taking

### Performance Analytics
- ✅ **Sharpe Ratio**: Risk-adjusted return metric
- ✅ **Sortino Ratio**: Downside risk-adjusted return
- ✅ **Calmar Ratio**: Return vs max drawdown
- ✅ **Trade Statistics**: Win rate, profit factor, expectancy
- ✅ **Drawdown Analysis**: Maximum drawdown tracking
- ✅ **Performance Dashboard**: Comprehensive metrics display

### Trade Journal
- ✅ **Automatic Trade Logging**: All trades recorded automatically
- ✅ **Trade History**: Complete trade database
- ✅ **Performance Summary**: Real-time statistics
- ✅ **CSV Export**: Export trades for external analysis
- ✅ **Trade Details**: Entry/exit prices, PnL, reasons

### Notifications
- ✅ **Email Alerts**: Trade entry/exit notifications
- ✅ **Risk Alerts**: Notifications when risk limits reached
- ✅ **Error Notifications**: Alerts for system errors
- ✅ **Configurable**: Enable/disable notifications

### Advanced Charting
- ✅ **Multi-timeframe Display**: 1H and 10M indicators
- ✅ **EMA 200 Overlay**: 1H timeframe indicator
- ✅ **SuperTrend Display**: 10M timeframe indicator
- ✅ **Real-time Updates**: Live chart updates during trading

## Project Structure

```
.
├── main.py              # Main entry point
├── gui.py               # CustomTkinter GUI
├── strategy.py          # Trading strategy logic
├── indicators.py        # Technical indicators (EMA, SuperTrend)
├── ibkr_connection.py   # IBKR TWS connection module
├── backtest.py              # Backtesting engine
├── risk_management.py       # Risk management module
├── trade_journal.py         # Trade journal and logging
├── performance_analytics.py # Performance analytics
├── notifications.py         # Email/notification system
├── test_connection.py       # Connection test script
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── TROUBLESHOOTING.md       # Troubleshooting guide
```

## Important Notes

⚠️ **Risk Warning**: This bot is for educational purposes. Always test thoroughly in paper trading mode before using real money. Trading involves substantial risk of loss.

⚠️ **TWS Configuration**: Make sure TWS API is properly configured and the bot has necessary permissions.

## License

This project is provided as-is for educational purposes.

