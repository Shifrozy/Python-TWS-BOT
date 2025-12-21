"""
Test script to diagnose TWS connection issues
Run this to test your TWS connection before using the main bot
"""
import sys
from ibkr_connection import IBKRConnection
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_connection():
    """Test TWS connection with detailed diagnostics"""
    print("=" * 60)
    print("TWS Connection Test")
    print("=" * 60)
    print()
    
    # Get connection details
    print("Enter TWS connection details:")
    host = input("Host (default: 127.0.0.1): ").strip() or "127.0.0.1"
    
    port_input = input("Port (default: 7497 for paper, 7496 for live): ").strip()
    port = int(port_input) if port_input else 7497
    
    client_id_input = input("Client ID (default: 1): ").strip()
    client_id = int(client_id_input) if client_id_input else 1
    
    print()
    print(f"Attempting to connect to {host}:{port} with Client ID {client_id}...")
    print()
    
    # Create connection
    ibkr = IBKRConnection(host=host, port=port, client_id=client_id)
    
    # Test connection
    print("Step 1: Testing connection...")
    if ibkr.connect():
        print("✓ Connection successful!")
        print()
        
        # Test contract (using continuous contract - auto rollover)
        print("Step 2: Testing contract qualification (Continuous Contract)...")
        try:
            contract = ibkr.get_contract(use_continuous=True)
            contract_month = getattr(contract, 'lastTradeDateOrContractMonth', 'Continuous')
            print(f"✓ Contract loaded: {contract.symbol} (Continuous Contract)")
            if contract_month != 'Continuous':
                print(f"   Current front month: {contract_month}")
            print("   IBKR will automatically handle contract rollover")
            print()
            
            # Test historical data
            print("Step 3: Testing historical data fetch...")
            df_1h = ibkr.get_1h_data(contract, duration='1 D')
            if not df_1h.empty:
                print(f"✓ 1H data fetched: {len(df_1h)} bars")
            else:
                print("⚠ 1H data is empty (might need market data subscription)")
            
            df_10m = ibkr.get_10m_data(contract, duration='1 D')
            if not df_10m.empty:
                print(f"✓ 10M data fetched: {len(df_10m)} bars")
            else:
                print("⚠ 10M data is empty (might need market data subscription)")
            print()
            
            print("=" * 60)
            print("All tests passed! Your connection is working.")
            print("You can now use the main bot.")
            print("=" * 60)
            
        except Exception as e:
            print(f"✗ Error testing contract/data: {e}")
            print("Connection works but contract/data access failed.")
            print("This might be due to:")
            print("  - Missing market data subscription")
            print("  - Market is closed")
            print("  - Contract symbol issue")
    else:
        print("✗ Connection failed!")
        print()
        print("Troubleshooting steps:")
        print("1. Make sure TWS is running")
        print("2. In TWS, go to: Configure → API → Settings")
        print("3. Enable 'Enable ActiveX and Socket Clients'")
        print(f"4. Set Socket port to: {port}")
        print("5. Click OK and restart TWS")
        print("6. Make sure no firewall is blocking the connection")
        print("7. Try a different Client ID if current one is in use")
        print()
        print("If problem persists, check TWS logs:")
        print("  Help → Logs in TWS")
    
    # Cleanup
    try:
        ibkr.disconnect()
    except:
        pass
    
    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        test_connection()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")

