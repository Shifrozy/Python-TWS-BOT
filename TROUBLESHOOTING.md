# Troubleshooting Guide

## Connection Issues

### Error: Connection Refused
**Problem**: Cannot connect to TWS

**Solutions**:
1. Make sure TWS (Trader Workstation) is running
2. Enable API in TWS:
   - Go to `Configure` → `API` → `Settings`
   - Check "Enable ActiveX and Socket Clients"
   - Set Socket port (default: 7497 for paper, 7496 for live)
   - Click "OK" and restart TWS
3. Check firewall settings - allow TWS through firewall
4. Verify port number matches in both TWS and the bot

### Error: Connection Timeout
**Problem**: Connection takes too long or times out

**Solutions**:
1. Check if TWS is responding (try restarting TWS)
2. Verify the port number is correct
3. Check if another application is using the same Client ID
4. Try a different Client ID (1, 2, 3, etc.)

### Error: Client ID Already in Use
**Problem**: Another application is using the same Client ID

**Solutions**:
1. Close other applications using the same Client ID
2. Use a different Client ID in the bot (change from 1 to 2, 3, etc.)

### Error: Could not qualify contract
**Problem**: Cannot find the NQ futures contract

**Solutions**:
1. Make sure you have market data subscription for futures
2. Check if market is open (futures trade 24/5)
3. Verify contract symbol is correct (NQ for Nasdaq)
4. Try restarting TWS

## Runtime Errors

### Error: Module not found
**Problem**: Missing Python packages

**Solution**:
```bash
pip install -r requirements.txt
```

### Error: TWS API errors
**Problem**: Various API-related errors

**Solutions**:
1. Make sure TWS version is compatible (latest stable version recommended)
2. Check TWS logs for detailed error messages
3. Restart TWS if errors persist
4. Verify account has necessary permissions

## Common Issues

### Bot not placing orders
**Check**:
1. Is live trading enabled? (not just connected)
2. Are strategy conditions being met?
3. Check status panel for error messages
4. Verify account has buying power

### Price not updating
**Check**:
1. Is market data subscription active?
2. Is the contract loaded correctly?
3. Check TWS for market data errors

### Position not syncing
**Check**:
1. Is the bot connected to TWS?
2. Check if position exists in TWS
3. Verify contract symbol matches (NQ)

## Getting Help

If you encounter errors:
1. Check the status panel in the GUI for error messages
2. Check terminal/console output for detailed errors
3. Check TWS logs (Help → Logs in TWS)
4. Make sure all requirements are installed correctly

