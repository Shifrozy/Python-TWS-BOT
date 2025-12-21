"""
Interactive Brokers TWS Connection Module
"""
from ib_insync import IB, Stock, Future, util
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
import asyncio

# CRITICAL: Enable nested event loops for GUI thread compatibility
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # Will work without it but may have issues in GUI context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IBKRConnection:
    """Manages connection to Interactive Brokers TWS"""
    
    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IBKR connection
        
        Args:
            host: TWS host (default 127.0.0.1)
            port: TWS port (7497 for paper trading, 7496 for live)
            client_id: Unique client ID
        """
        self.ib = None
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self._loop = None
    
    def connect(self):
        """Connect to TWS with proper event loop handling"""
        try:
            logger.info(f"Attempting to connect to {self.host}:{self.port} with Client ID {self.client_id}")
            
            # Create new event loop for this thread if needed
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            
            # Disconnect if already connected
            if self.ib is not None:
                try:
                    if self.ib.isConnected():
                        logger.info("Disconnecting existing connection...")
                        self.ib.disconnect()
                        time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Error disconnecting: {e}")
                self.connected = False
            
            # Create new IB instance
            self.ib = IB()
            
            logger.info("Creating new connection...")
            
            # Connect to TWS
            self.ib.connect(
                self.host, 
                self.port, 
                clientId=self.client_id
            )
            
            # Wait a bit to ensure connection is established
            time.sleep(1)
            
            # Verify connection
            if self.ib.isConnected():
                self.connected = True
                logger.info(f"✓ Successfully connected to TWS at {self.host}:{self.port} (Client ID: {self.client_id})")
                return True
            else:
                logger.error("✗ Connection established but isConnected() returned False")
                self.connected = False
                return False
                
        except ConnectionRefusedError as e:
            error_msg = f"✗ Connection refused to {self.host}:{self.port}"
            logger.error(error_msg)
            logger.error("Possible causes:")
            logger.error("  1. TWS is not running")
            logger.error("  2. API is not enabled in TWS (Configure -> API -> Settings)")
            logger.error(f"  3. Wrong port number (current: {self.port}, try 7497 for paper or 7496 for live)")
            logger.error(f"  4. Firewall blocking connection")
            self.connected = False
            return False
        except TimeoutError as e:
            error_msg = f"✗ Connection timeout to {self.host}:{self.port}"
            logger.error(error_msg)
            logger.error("Possible causes:")
            logger.error("  1. TWS is not responding")
            logger.error("  2. Network issues")
            logger.error(f"  3. Wrong port number (current: {self.port})")
            self.connected = False
            return False
        except OSError as e:
            error_msg = f"✗ Network error: {type(e).__name__}: {str(e)}"
            logger.error(error_msg)
            logger.error("Possible causes:")
            logger.error("  1. TWS is not running")
            logger.error(f"  2. Cannot reach {self.host}:{self.port}")
            logger.error("  3. Firewall blocking connection")
            self.connected = False
            return False
        except Exception as e:
            error_msg = f"✗ Connection failed: {type(e).__name__}: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Full error details: {repr(e)}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from TWS"""
        try:
            if self.ib is not None and self.connected:
                if self.ib.isConnected():
                    self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from TWS")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            self.connected = False
    
    def get_contract(self, symbol='NQ', exchange='CME', currency='USD', contract_month=None):
        """
        Get futures contract for Nasdaq (front month by default)
        
        Args:
            symbol: Contract symbol (default 'NQ' for Nasdaq)
            exchange: Exchange (default 'CME')
            currency: Currency (default 'USD')
            contract_month: Specific contract month (e.g., '202503' for March 2025)
        
        Returns:
            Contract object
        """
        if not self.connected or self.ib is None:
            raise ConnectionError("Not connected to TWS. Please connect first.")
        
        try:
            # If specific month provided, use it directly
            if contract_month:
                contract = Future(
                    symbol=symbol, 
                    exchange=exchange, 
                    currency=currency,
                    lastTradeDateOrContractMonth=contract_month
                )
                qualified = self.ib.qualifyContracts(contract)
                if qualified:
                    return qualified[0]
            
            # Get all available contracts using reqContractDetails
            base_contract = Future(symbol=symbol, exchange=exchange, currency=currency)
            logger.info(f"Requesting contract details for {symbol}...")
            details = self.ib.reqContractDetails(base_contract)
            
            if not details:
                # Try with GLOBEX exchange for NQ
                if symbol == 'NQ':
                    logger.info("Trying with GLOBEX exchange...")
                    base_contract = Future(symbol=symbol, exchange='GLOBEX', currency=currency)
                    details = self.ib.reqContractDetails(base_contract)
                
                if not details:
                    raise ValueError(f"No contracts found for {symbol}")
            
            logger.info(f"Found {len(details)} contracts")
            
            # Filter only quarterly contracts (March, June, Sept, Dec) and sort by expiry
            from datetime import datetime
            today = datetime.now().strftime('%Y%m%d')
            
            # Filter future contracts only (not expired)
            future_contracts = [d for d in details if d.contract.lastTradeDateOrContractMonth >= today]
            
            if not future_contracts:
                future_contracts = details  # Use all if none match
            
            # Sort by expiry date and get front month (nearest expiry)
            future_contracts.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
            
            # Get the front month contract
            front_month = future_contracts[0].contract
            logger.info(f"Selected front month: {front_month.localSymbol} ({front_month.lastTradeDateOrContractMonth})")
            
            # The contract from reqContractDetails should already be qualified
            return front_month
            
        except Exception as e:
            logger.error(f"Error getting contract: {type(e).__name__}: {str(e)}")
            raise
    
    def get_historical_data(self, contract, duration='1 M', bar_size='1 min', use_delayed=True, end_date=None):
        """
        Get historical data from IBKR (supports delayed data)
        
        Args:
            contract: Contract object
            duration: Duration string (e.g., '1 M', '1 D')
            bar_size: Bar size (e.g., '1 min', '10 mins', '1 hour')
            use_delayed: If True, use delayed data (no subscription required)
            end_date: End date string (YYYYMMDD HH:MM:SS) or None for current time
        
        Returns:
            DataFrame with OHLCV data
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # For delayed data, useRTH=False allows access to delayed data
                # Also, endDateTime='' means current time, but for delayed data we might want past date
                endDateTime = end_date if end_date else ''
                
                logger.info(f"Fetching {bar_size} data for {contract.symbol}, duration={duration} (attempt {attempt + 1}/{max_retries})")
                
                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=endDateTime,
                    durationStr=duration,
                    barSizeSetting=bar_size,
                    whatToShow='TRADES',
                    useRTH=False,  # False = include extended hours
                    formatDate=1,
                    keepUpToDate=False,  # Don't update in real-time for backtesting
                    timeout=60  # 60 second timeout to prevent indefinite hang
                )
                
                # Handle timeout or no data returned
                if bars is None or len(bars) == 0:
                    logger.warning(f"No data returned for {contract.symbol} ({duration}, {bar_size}) - attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        logger.info(f"Waiting 15 seconds before retry (IBKR pacing rule)...")
                        time.sleep(15)  # IBKR requires 15 sec between identical requests
                        continue
                    return pd.DataFrame()
                
                df = util.df(bars)
                if df is None or df.empty:
                    logger.warning(f"Empty DataFrame for {contract.symbol} ({duration}, {bar_size})")
                    return pd.DataFrame()
                
                df.set_index('date', inplace=True)
                df.columns = [col.lower() for col in df.columns]
                
                logger.info(f"✓ Fetched {len(df)} bars for {contract.symbol} ({bar_size})")
                return df[['open', 'high', 'low', 'close', 'volume']]
                
            except Exception as e:
                logger.error(f"Error fetching historical data (attempt {attempt + 1}): {type(e).__name__}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Waiting 15 seconds before retry...")
                    time.sleep(15)
                    continue
                return pd.DataFrame()
    
    def get_1h_data(self, contract, duration='30 D', use_delayed=True, end_date=None):
        """Get 1-hour timeframe data"""
        return self.get_historical_data(contract, duration=duration, bar_size='1 hour', use_delayed=use_delayed, end_date=end_date)
    
    def get_10m_data(self, contract, duration='5 D', use_delayed=True, end_date=None):
        """Get 10-minute timeframe data"""
        return self.get_historical_data(contract, duration=duration, bar_size='10 mins', use_delayed=use_delayed, end_date=end_date)
    
    def place_market_order(self, contract, action, quantity):
        """
        Place market order
        
        Args:
            contract: Contract object
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
        
        Returns:
            Trade object
        """
        from ib_insync import MarketOrder
        
        order = MarketOrder(action, quantity)
        trade = self.ib.placeOrder(contract, order)
        
        # Wait for order acknowledgment
        self.ib.sleep(0.5)
        
        logger.info(f"Placed {action} order for {quantity} contracts. Order ID: {trade.order.orderId}")
        return trade
    
    def place_bracket_order(self, contract, action, quantity, entry_price, 
                           take_profit_price, stop_loss_price):
        """
        Place bracket order (entry + TP + SL)
        
        Args:
            contract: Contract object
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            entry_price: Entry limit price
            take_profit_price: Take profit limit price
            stop_loss_price: Stop loss price
        
        Returns:
            List of Trade objects [parent, TP, SL]
        """
        from ib_insync import LimitOrder, StopOrder
        
        # Parent order (entry)
        parent_order = LimitOrder(action, quantity, entry_price)
        parent_trade = self.ib.placeOrder(contract, parent_order)
        
        # Take profit order
        tp_action = 'SELL' if action == 'BUY' else 'BUY'
        tp_order = LimitOrder(tp_action, quantity, take_profit_price)
        tp_order.parentId = parent_trade.order.orderId
        tp_trade = self.ib.placeOrder(contract, tp_order)
        
        # Stop loss order
        sl_order = StopOrder(tp_action, quantity, stop_loss_price)
        sl_order.parentId = parent_trade.order.orderId
        sl_trade = self.ib.placeOrder(contract, sl_order)
        
        self.ib.sleep(0.5)
        logger.info(f"Placed bracket order: Entry={entry_price}, TP={take_profit_price}, SL={stop_loss_price}")
        
        return [parent_trade, tp_trade, sl_trade]
    
    def place_stop_loss(self, contract, action, quantity, stop_price, parent_order_id=None):
        """
        Place stop loss order
        
        Args:
            contract: Contract object
            action: 'SELL' (for long) or 'BUY' (for short)
            quantity: Number of contracts
            stop_price: Stop loss price
            parent_order_id: Parent order ID for bracket
        
        Returns:
            Trade object
        """
        from ib_insync import StopOrder
        
        order = StopOrder(action, quantity, stop_price)
        if parent_order_id:
            order.parentId = parent_order_id
        
        trade = self.ib.placeOrder(contract, order)
        logger.info(f"Placed stop loss at {stop_price}")
        return trade
    
    def place_take_profit(self, contract, action, quantity, limit_price, parent_order_id=None):
        """
        Place take profit order
        
        Args:
            contract: Contract object
            action: 'SELL' (for long) or 'BUY' (for short)
            quantity: Number of contracts
            limit_price: Take profit price
            parent_order_id: Parent order ID for bracket
        
        Returns:
            Trade object
        """
        from ib_insync import LimitOrder
        
        order = LimitOrder(action, quantity, limit_price)
        if parent_order_id:
            order.parentId = parent_order_id
        
        trade = self.ib.placeOrder(contract, order)
        logger.info(f"Placed take profit at {limit_price}")
        return trade
    
    def cancel_order(self, trade):
        """Cancel an order"""
        try:
            self.ib.cancelOrder(trade.order)
            logger.info(f"Cancelled order {trade.order.orderId}")
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
    
    def get_open_orders(self):
        """Get all open orders"""
        return self.ib.openOrders()
    
    def place_limit_order(self, contract, action, quantity, limit_price):
        """
        Place limit order
        
        Args:
            contract: Contract object
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            limit_price: Limit price
        
        Returns:
            Order object
        """
        from ib_insync import LimitOrder
        
        order = LimitOrder(action, quantity, limit_price)
        trade = self.ib.placeOrder(contract, order)
        logger.info(f"Placed {action} limit order for {quantity} contracts at {limit_price}")
        return trade
    
    def get_positions(self):
        """Get current positions"""
        return self.ib.positions()
    
    def get_account_summary(self):
        """Get account summary"""
        account_values = self.ib.accountValues()
        return {av.tag: av.value for av in account_values}
    
    def detect_available_contract(self):
        """
        Auto-detect which contract (NQ or MNQ) has market data subscription
        
        Returns:
            tuple: (symbol, contract_object) or (None, None) if none available
        """
        if not self.connected or self.ib is None:
            return None, None
        
        # Try MNQ first (default), then NQ
        for symbol in ['MNQ', 'NQ']:
            try:
                logger.info(f"Checking market data subscription for {symbol}...")
                # Quick contract qualification check
                contract = self.get_contract(symbol=symbol)
                
                # Quick test - try to fetch minimal data (1 day)
                logger.info(f"  Quick subscription test for {symbol}...")
                test_data = self.get_1h_data(contract, duration='1 D', use_delayed=True)
                
                if test_data is not None and not test_data.empty and len(test_data) > 0:
                    logger.info(f"✓ Market data subscription detected for {symbol} ({len(test_data)} bars available)")
                    return symbol, contract
                else:
                    logger.info(f"⚠ No data available for {symbol}, trying next...")
            except Exception as e:
                logger.debug(f"Error checking {symbol}: {e}")
                continue
        
        logger.warning("✗ No market data subscription detected for NQ or MNQ")
        return None, None
