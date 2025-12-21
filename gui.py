"""
CustomTkinter GUI for Trading Bot
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os
import re
import threading
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import logging
try:
    from tkcalendar import DateEntry
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False
    import warnings
    warnings.warn("tkcalendar not available. Install with: pip install tkcalendar")

from ibkr_connection import IBKRConnection
from strategy import TradingStrategy
from backtest import BacktestEngine
from trade_journal import TradeJournal
from performance_analytics import PerformanceAnalytics
from notifications import NotificationManager
from data_cache import DataCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TradingBotGUI:
    """Main GUI Application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Nasdaq Futures Trading Bot - EMA 200 + SuperTrend")
        self.root.geometry("1400x900")
        
        # Initialize components
        self.ibkr = IBKRConnection()
        self.strategy = TradingStrategy()
        self.backtest_engine = None
        self.is_trading = False
        self.trading_thread = None
        self.backtest_running = False
        self.backtest_thread = None
        self.backtest_cancelled = False
        self.contract = None
        self.market_data_subscribed = False
        self.market_data_ticker = None
        
        # Advanced components
        self.trade_journal = TradeJournal()
        self.performance_analytics = PerformanceAnalytics()
        self.notifications = NotificationManager()
        self.data_cache = DataCache()  # CSV data caching for offline backtest
        
        # Data storage
        self.df_1h = None
        self.df_10m = None
        self.backtest_results = None
        self.current_price = 0.0
        self.contract_quantity = 1
        self.current_trade_id = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        # ===== TOP BAR: Connection + Controls =====
        top_bar = ctk.CTkFrame(self.root, height=160)
        top_bar.pack(fill="x", padx=10, pady=(10, 5))
        # top_bar.pack_propagate(False)  # Commented out to allow buttons to be visible
        
        self.setup_top_bar(top_bar)
        
        # ===== MAIN AREA =====
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Left Sidebar - Parameters (small, fixed width)
        left_sidebar = ctk.CTkFrame(main_frame, width=280)
        left_sidebar.pack(side="left", fill="y", padx=(0, 10))
        left_sidebar.pack_propagate(False)
        
        # Scrollable sidebar
        sidebar_scroll = ctk.CTkScrollableFrame(left_sidebar, width=260)
        sidebar_scroll.pack(fill="both", expand=True)
        
        # Parameters only in sidebar
        self.setup_strategy_panel(sidebar_scroll)
        # Risk Management panel removed - using simple contract quantity parameter
        
        # Right panel - Main content
        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True)
        
        # Right panel with tabs
        self.setup_tabs_panel(right_panel)
    
    def setup_top_bar(self, parent):
        """Setup top bar with connection and controls"""
        # Connection Section
        conn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        conn_frame.pack(side="left", fill="y", padx=10, pady=5)
        
        conn_label = ctk.CTkLabel(conn_frame, text="TWS Connection", font=("Arial", 12, "bold"))
        conn_label.pack(anchor="w")
        
        # Connection inputs row
        conn_inputs = ctk.CTkFrame(conn_frame, fg_color="transparent")
        conn_inputs.pack(fill="x", pady=2)
        
        ctk.CTkLabel(conn_inputs, text="Host:", width=40).pack(side="left")
        self.host_entry = ctk.CTkEntry(conn_inputs, width=100)
        self.host_entry.insert(0, "127.0.0.1")
        self.host_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(conn_inputs, text="Port:", width=35).pack(side="left")
        self.port_entry = ctk.CTkEntry(conn_inputs, width=60)
        self.port_entry.insert(0, "7497")
        self.port_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(conn_inputs, text="ID:", width=25).pack(side="left")
        self.client_id_entry = ctk.CTkEntry(conn_inputs, width=40)
        self.client_id_entry.insert(0, "1")
        self.client_id_entry.pack(side="left", padx=2)
        
        # Connection buttons row
        conn_btns = ctk.CTkFrame(conn_frame, fg_color="transparent")
        conn_btns.pack(fill="x", pady=2)
        
        self.connect_btn = ctk.CTkButton(conn_btns, text="🔌 Connect", command=self.connect_ibkr,
                                          fg_color="#28a745", hover_color="#218838", width=80, height=28)
        self.connect_btn.pack(side="left", padx=2)
        
        self.disconnect_btn = ctk.CTkButton(conn_btns, text="⏏ Disconnect", command=self.disconnect_ibkr,
                                             fg_color="#dc3545", hover_color="#c82333", width=90, height=28, state="disabled")
        self.disconnect_btn.pack(side="left", padx=2)
        
        self.conn_status = ctk.CTkLabel(conn_btns, text="● Disconnected", text_color="#dc3545", font=("Arial", 11, "bold"))
        self.conn_status.pack(side="left", padx=10)
        
        # Separator
        sep1 = ctk.CTkFrame(parent, width=2, fg_color="#555555")
        sep1.pack(side="left", fill="y", padx=10, pady=10)
        
        # Trading Controls Section
        ctrl_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl_frame.pack(side="left", fill="y", padx=10, pady=5)
        
        ctrl_label = ctk.CTkLabel(ctrl_frame, text="Trading Controls", font=("Arial", 12, "bold"))
        ctrl_label.pack(anchor="w")
        
        # Backtest row 1: Data source
        bt_row1 = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        bt_row1.pack(fill="x", pady=2)
        
        self.data_source_var = ctk.StringVar(value="csv")  # Default to CSV
        ctk.CTkRadioButton(bt_row1, text="CSV", variable=self.data_source_var, value="csv", width=50).pack(side="left")
        ctk.CTkRadioButton(bt_row1, text="Delayed", variable=self.data_source_var, value="delayed", width=65).pack(side="left")
        ctk.CTkRadioButton(bt_row1, text="Live", variable=self.data_source_var, value="realtime", width=50).pack(side="left")
        
        # Backtest row 2: Date range
        bt_row2 = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        bt_row2.pack(fill="x", pady=2)
        
        ctk.CTkLabel(bt_row2, text="From:", width=35).pack(side="left")
        
        # From date calendar
        from_date_frame = tk.Frame(bt_row2, bg="#212121")
        from_date_frame.pack(side="left", padx=2)
        if CALENDAR_AVAILABLE:
            # Default to start of current month
            default_from = datetime.now().replace(day=1)
            self.backtest_from_calendar = DateEntry(
                from_date_frame,
                width=12,
                background='#2b2b2b',
                foreground='white',
                selectbackground='#1f538d',
                selectforeground='white',
                normalbackground='#2b2b2b',
                normalforeground='white',
                borderwidth=1,
                date_pattern='yyyy-mm-dd',
                year=default_from.year,
                month=default_from.month,
                day=default_from.day,
                font=('Arial', 9)
            )
            self.backtest_from_calendar.pack()
        else:
            # Fallback to entry if calendar not available
            self.backtest_from_date = ctk.CTkEntry(bt_row2, width=80, placeholder_text="YYYYMMDD")
            self.backtest_from_date.pack(side="left", padx=2)
            default_from = datetime.now().replace(day=1)
            self.backtest_from_date.insert(0, default_from.strftime("%Y%m%d"))
        
        ctk.CTkLabel(bt_row2, text="To:", width=25).pack(side="left", padx=(5,0))
        
        # To date calendar
        to_date_frame = tk.Frame(bt_row2, bg="#212121")
        to_date_frame.pack(side="left", padx=2)
        if CALENDAR_AVAILABLE:
            # Default to today
            default_to = datetime.now()
            self.backtest_to_calendar = DateEntry(
                to_date_frame,
                width=12,
                background='#2b2b2b',
                foreground='white',
                selectbackground='#1f538d',
                selectforeground='white',
                normalbackground='#2b2b2b',
                normalforeground='white',
                borderwidth=1,
                date_pattern='yyyy-mm-dd',
                year=default_to.year,
                month=default_to.month,
                day=default_to.day,
                font=('Arial', 9)
            )
            self.backtest_to_calendar.pack()
        else:
            # Fallback to entry if calendar not available
            self.backtest_to_date = ctk.CTkEntry(bt_row2, width=80, placeholder_text="YYYYMMDD")
            self.backtest_to_date.pack(side="left", padx=2)
            default_to = datetime.now()
            self.backtest_to_date.insert(0, default_to.strftime("%Y%m%d"))
        
        # Backtest row 3: Download + Backtest buttons
        bt_row3 = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        bt_row3.pack(fill="x", pady=2)
        
        self.download_btn = ctk.CTkButton(bt_row3, text="⬇ Download", command=self.download_data,
                                           fg_color="#17a2b8", hover_color="#138496", width=85, height=28)
        self.download_btn.pack(side="left", padx=2)
        
        self.backtest_btn = ctk.CTkButton(bt_row3, text="▶ Backtest", command=self.run_backtest_from_cache,
                                           fg_color="#FF8C00", hover_color="#FF6600", width=80, height=28)
        self.backtest_btn.pack(side="left", padx=2)
        
        self.stop_backtest_btn = ctk.CTkButton(bt_row3, text="⏹", command=self.stop_backtest,
                                                fg_color="#6c757d", hover_color="#5a6268", width=30, height=28, state="disabled")
        self.stop_backtest_btn.pack(side="left", padx=2)
        
        # Download status
        self.download_status = ctk.CTkLabel(ctrl_frame, text="No data", text_color="#888888", font=("Arial", 9))
        self.download_status.pack(anchor="w")
        
        # Live trading row
        live_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        live_row.pack(fill="x", pady=2)
        
        self.start_trading_btn = ctk.CTkButton(live_row, text="▶ Live", command=self.start_trading,
                                                fg_color="#28a745", hover_color="#218838", width=65, height=28)
        self.start_trading_btn.pack(side="left", padx=2)
        
        self.stop_trading_btn = ctk.CTkButton(live_row, text="⏹ Stop", command=self.stop_trading,
                                               fg_color="#dc3545", hover_color="#c82333", width=65, height=28, state="disabled")
        self.stop_trading_btn.pack(side="left", padx=2)
        
        # Separator
        sep2 = ctk.CTkFrame(parent, width=2, fg_color="#555555")
        sep2.pack(side="left", fill="y", padx=10, pady=10)
        
        # Status Section
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        status_label = ctk.CTkLabel(status_frame, text="Status", font=("Arial", 12, "bold"))
        status_label.pack(anchor="w")
        
        # Progress indicator
        self.progress_label = ctk.CTkLabel(status_frame, text="Ready", text_color="#888888", font=("Arial", 10))
        self.progress_label.pack(anchor="w")
        
        # Quick status text
        self.quick_status = ctk.CTkLabel(status_frame, text="Connect to TWS to begin", 
                                          text_color="#aaaaaa", font=("Arial", 10), wraplength=250)
        self.quick_status.pack(anchor="w", pady=2)
    
    def setup_connection_panel(self, parent):
        """Setup IBKR connection panel"""
        conn_frame = ctk.CTkFrame(parent)
        conn_frame.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(conn_frame, text="IBKR Connection", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Host
        host_label = ctk.CTkLabel(conn_frame, text="Host:")
        host_label.pack(anchor="w", padx=10)
        self.host_entry = ctk.CTkEntry(conn_frame, width=200)
        self.host_entry.insert(0, "127.0.0.1")
        self.host_entry.pack(padx=10, pady=5)
        
        # Port
        port_label = ctk.CTkLabel(conn_frame, text="Port:")
        port_label.pack(anchor="w", padx=10)
        self.port_entry = ctk.CTkEntry(conn_frame, width=200)
        self.port_entry.insert(0, "7497")
        self.port_entry.pack(padx=10, pady=5)
        
        # Client ID
        client_id_label = ctk.CTkLabel(conn_frame, text="Client ID:")
        client_id_label.pack(anchor="w", padx=10)
        self.client_id_entry = ctk.CTkEntry(conn_frame, width=200)
        self.client_id_entry.insert(0, "1")
        self.client_id_entry.pack(padx=10, pady=5)
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        # Connect button
        self.connect_btn = ctk.CTkButton(
            btn_frame, 
            text="🔌 Connect", 
            command=self.connect_ibkr,
            fg_color="#28a745",
            hover_color="#218838",
            width=95
        )
        self.connect_btn.pack(side="left", padx=2)
        
        # Disconnect button
        self.disconnect_btn = ctk.CTkButton(
            btn_frame,
            text="⏏ Disconnect",
            command=self.disconnect_ibkr,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled",
            width=95
        )
        self.disconnect_btn.pack(side="left", padx=2)
        
        # Connection status frame
        status_frame = ctk.CTkFrame(conn_frame, fg_color="#2b2b2b", corner_radius=8)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        self.conn_status = ctk.CTkLabel(
            status_frame, 
            text="● Disconnected", 
            text_color="#dc3545",
            font=("Arial", 12, "bold")
        )
        self.conn_status.pack(pady=8)
    
    def setup_strategy_panel(self, parent):
        """Setup strategy parameters panel"""
        strat_frame = ctk.CTkFrame(parent)
        strat_frame.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(strat_frame, text="Strategy Parameters", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # SuperTrend ATR Period (script.pine default: 55)
        st_atr_label = ctk.CTkLabel(strat_frame, text="SuperTrend ATR Period:")
        st_atr_label.pack(anchor="w", padx=10)
        self.st_atr_entry = ctk.CTkEntry(strat_frame, width=200)
        self.st_atr_entry.insert(0, "55")
        self.st_atr_entry.pack(padx=10, pady=5)
        
        # SuperTrend Multiplier (script.pine default: 3.8)
        st_mult_label = ctk.CTkLabel(strat_frame, text="SuperTrend Multiplier:")
        st_mult_label.pack(anchor="w", padx=10)
        self.st_mult_entry = ctk.CTkEntry(strat_frame, width=200)
        self.st_mult_entry.insert(0, "3.8")
        self.st_mult_entry.pack(padx=10, pady=5)
        
        # Take Profit % (script.pine default: 3.0)
        tp_label = ctk.CTkLabel(strat_frame, text="Take Profit (%):")
        tp_label.pack(anchor="w", padx=10)
        self.tp_entry = ctk.CTkEntry(strat_frame, width=200)
        self.tp_entry.insert(0, "3.0")
        self.tp_entry.pack(padx=10, pady=5)
        
        # Stop Loss % (script.pine default: 0.55)
        sl_label = ctk.CTkLabel(strat_frame, text="Stop Loss (%):")
        sl_label.pack(anchor="w", padx=10)
        self.sl_entry = ctk.CTkEntry(strat_frame, width=200)
        self.sl_entry.insert(0, "0.55")
        self.sl_entry.pack(padx=10, pady=5)
        
        # Contract Quantity
        qty_label = ctk.CTkLabel(strat_frame, text="Contract Quantity:")
        qty_label.pack(anchor="w", padx=10)
        self.quantity_entry = ctk.CTkEntry(strat_frame, width=200)
        self.quantity_entry.insert(0, "1")
        self.quantity_entry.pack(padx=10, pady=5)
        
        # Initial Capital (for backtest only)
        capital_label = ctk.CTkLabel(strat_frame, text="Initial Capital ($) - Backtest:")
        capital_label.pack(anchor="w", padx=10)
        self.initial_capital_entry = ctk.CTkEntry(strat_frame, width=200)
        self.initial_capital_entry.insert(0, "100000")
        self.initial_capital_entry.pack(padx=10, pady=5)
        
        # Update button
        update_btn = ctk.CTkButton(
            strat_frame,
            text="Update Parameters",
            command=self.update_strategy_params
        )
        update_btn.pack(pady=10)
    
    # Risk Management panel removed - using simple contract quantity parameter instead
    # def setup_risk_panel(self, parent):
    #     """Setup risk management panel - REMOVED"""
    #     pass
    
    def setup_control_panel(self, parent):
        """Setup trading control panel with separate download and backtest buttons"""
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(control_frame, text="Trading Controls", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # ===== DATA DOWNLOAD SECTION =====
        download_label = ctk.CTkLabel(control_frame, text="📥 Data Download:", font=("Arial", 12, "bold"))
        download_label.pack(anchor="w", padx=10, pady=(5,0))
        
        # Date Range Frame
        date_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        date_frame.pack(fill="x", padx=10, pady=5)
        
        # From Date
        from_label = ctk.CTkLabel(date_frame, text="From:", width=40)
        from_label.pack(side="left", padx=2)
        
        if CALENDAR_AVAILABLE:
            self.download_from_date = DateEntry(
                date_frame, 
                width=10, 
                background='#1f538d',
                foreground='white',
                date_pattern='yyyy-mm-dd'
            )
            # Default: 7 days ago
            default_from = datetime.now() - timedelta(days=7)
            self.download_from_date.set_date(default_from.date())
        else:
            self.download_from_date = ctk.CTkEntry(date_frame, width=90, placeholder_text="YYYYMMDD")
            self.download_from_date.insert(0, (datetime.now() - timedelta(days=7)).strftime("%Y%m%d"))
        self.download_from_date.pack(side="left", padx=2)
        
        # To Date
        to_label = ctk.CTkLabel(date_frame, text="To:", width=25)
        to_label.pack(side="left", padx=2)
        
        if CALENDAR_AVAILABLE:
            self.download_to_date = DateEntry(
                date_frame, 
                width=10, 
                background='#1f538d',
                foreground='white',
                date_pattern='yyyy-mm-dd'
            )
            self.download_to_date.set_date(datetime.now().date())
        else:
            self.download_to_date = ctk.CTkEntry(date_frame, width=90, placeholder_text="YYYYMMDD")
            self.download_to_date.insert(0, datetime.now().strftime("%Y%m%d"))
        self.download_to_date.pack(side="left", padx=2)
        
        # Data Source Option
        data_source_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        data_source_frame.pack(fill="x", padx=10, pady=5)
        
        self.data_source_var = ctk.StringVar(value="delayed")
        
        delayed_radio = ctk.CTkRadioButton(
            data_source_frame, 
            text="Delayed (Free)", 
            variable=self.data_source_var, 
            value="delayed",
            font=("Arial", 11)
        )
        delayed_radio.pack(side="left", padx=5)
        
        realtime_radio = ctk.CTkRadioButton(
            data_source_frame, 
            text="Real-time", 
            variable=self.data_source_var, 
            value="realtime",
            font=("Arial", 11)
        )
        realtime_radio.pack(side="left", padx=5)
        
        # Download Button
        self.download_btn = ctk.CTkButton(
            control_frame,
            text="⬇️ Download Data",
            command=self.download_data,
            fg_color="#17a2b8",
            hover_color="#138496",
            height=35
        )
        self.download_btn.pack(pady=5, fill="x", padx=10)
        
        # Download Status
        self.download_status = ctk.CTkLabel(
            control_frame, 
            text="No data downloaded", 
            text_color="#888888",
            font=("Arial", 10)
        )
        self.download_status.pack(pady=2)
        
        # ===== BACKTEST SECTION =====
        backtest_label = ctk.CTkLabel(control_frame, text="📊 Backtest:", font=("Arial", 12, "bold"))
        backtest_label.pack(anchor="w", padx=10, pady=(10,0))
        
        # Backtest buttons frame
        backtest_btn_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        backtest_btn_frame.pack(fill="x", padx=10, pady=5)
        
        # Start Backtest button
        self.backtest_btn = ctk.CTkButton(
            backtest_btn_frame,
            text="▶ Start Backtest",
            command=self.run_backtest_from_cache,
            fg_color="#FF8C00",
            hover_color="#FF6600",
            height=35,
            width=100
        )
        self.backtest_btn.pack(side="left", padx=2, expand=True, fill="x")
        
        # Stop Backtest button
        self.stop_backtest_btn = ctk.CTkButton(
            backtest_btn_frame,
            text="⏹ Stop",
            command=self.stop_backtest,
            fg_color="#6c757d",
            hover_color="#5a6268",
            state="disabled",
            height=35,
            width=60
        )
        self.stop_backtest_btn.pack(side="left", padx=2)
        
        # ===== LIVE TRADING SECTION =====
        live_label = ctk.CTkLabel(control_frame, text="🔴 Live Trading:", font=("Arial", 12, "bold"))
        live_label.pack(anchor="w", padx=10, pady=(15,0))
        
        # Live trading buttons frame
        live_btn_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        live_btn_frame.pack(fill="x", padx=10, pady=5)
        
        # Start Trading button
        self.start_trading_btn = ctk.CTkButton(
            live_btn_frame,
            text="▶ Start Live",
            command=self.start_trading,
            fg_color="#28a745",
            hover_color="#218838",
            height=35,
            width=100
        )
        self.start_trading_btn.pack(side="left", padx=2, expand=True, fill="x")
        
        # Stop Trading button
        self.stop_trading_btn = ctk.CTkButton(
            live_btn_frame,
            text="⏹ Stop",
            command=self.stop_trading,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled",
            height=35,
            width=60
        )
        self.stop_trading_btn.pack(side="left", padx=2)
        
        # Legacy support - keep these for compatibility
        self.backtest_duration_entry = ctk.CTkEntry(control_frame)
        self.backtest_duration_entry.insert(0, "7")
        # Hide it but keep for compatibility
        # self.backtest_duration_entry.pack_forget()
    
    def setup_status_panel(self, parent):
        """Setup console-style status panel"""
        status_frame = ctk.CTkFrame(parent, fg_color="#1a1a1a")
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Console header
        header_frame = ctk.CTkFrame(status_frame, fg_color="#2d2d2d", height=30)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        title = ctk.CTkLabel(
            header_frame, 
            text="Console Output", 
            font=("Consolas", 12, "bold"),
            text_color="#00ff00"
        )
        title.pack(side="left", padx=10, pady=5)
        
        # Clear button
        clear_btn = ctk.CTkButton(
            header_frame,
            text="Clear",
            command=self.clear_console,
            fg_color="#444444",
            hover_color="#555555",
            width=60,
            height=25,
            font=("Arial", 10)
        )
        clear_btn.pack(side="right", padx=10, pady=2)
        
        # Console text area - terminal style
        self.status_text = ctk.CTkTextbox(
            status_frame, 
            height=250,
            fg_color="#0d0d0d",
            text_color="#00ff00",
            font=("Consolas", 11),
            corner_radius=0
        )
        self.status_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_status("=== Trading Bot Console ===")
        self.log_status("Application started. Connect to TWS to begin.")
        
        # Bottom status bar
        status_bar = ctk.CTkFrame(status_frame, fg_color="#2d2d2d", height=25)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)
        
        self.position_label = ctk.CTkLabel(
            status_bar, 
            text="Position: None", 
            font=("Consolas", 10),
            text_color="#888888"
        )
        self.position_label.pack(side="left", padx=10, pady=2)
        
        self.price_label = ctk.CTkLabel(
            status_bar,
            text="Price: --",
            font=("Consolas", 10),
            text_color="#888888"
        )
        self.price_label.pack(side="left", padx=10, pady=2)
        
        self.account_label = ctk.CTkLabel(
            status_bar,
            text="Account: --",
            font=("Consolas", 10),
            text_color="#888888"
        )
        self.account_label.pack(side="right", padx=10, pady=2)
    
    def setup_tabs_panel(self, parent):
        """Setup tabs for different views"""
        # Create tabview
        self.tabview = ctk.CTkTabview(parent)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Status/Log tab (first - important)
        status_tab = self.tabview.add("📋 Log")
        self.setup_status_panel(status_tab)
        
        # Charts tab
        charts_tab = self.tabview.add("📊 Charts")
        self.setup_chart_panel(charts_tab)
        
        # Backtest Results tab
        backtest_tab = self.tabview.add("📈 Backtest")
        self.setup_results_panel(backtest_tab)
        
        # Performance tab
        performance_tab = self.tabview.add("📉 Performance")
        self.setup_performance_panel(performance_tab)
        
        # Trade Journal tab
        journal_tab = self.tabview.add("📝 Journal")
        self.setup_journal_panel(journal_tab)
    
    def setup_chart_panel(self, parent):
        """Setup chart panel"""
        chart_frame = ctk.CTkFrame(parent)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        title = ctk.CTkLabel(chart_frame, text="Price Chart with Indicators", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Price Chart with Indicators")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price")
        
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def setup_performance_panel(self, parent):
        """Setup performance analytics panel"""
        perf_frame = ctk.CTkFrame(parent)
        perf_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        title = ctk.CTkLabel(perf_frame, text="Performance Analytics", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Performance metrics text
        self.performance_text = ctk.CTkTextbox(perf_frame, height=400)
        self.performance_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Update button
        update_perf_btn = ctk.CTkButton(
            perf_frame,
            text="Update Performance Metrics",
            command=self.update_performance_metrics
        )
        update_perf_btn.pack(pady=10)
    
    def setup_journal_panel(self, parent):
        """Setup trade journal panel"""
        journal_frame = ctk.CTkFrame(parent)
        journal_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        title = ctk.CTkLabel(journal_frame, text="Trade Journal", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Journal text
        self.journal_text = ctk.CTkTextbox(journal_frame, height=400)
        self.journal_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Buttons frame
        btn_frame = ctk.CTkFrame(journal_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="Refresh Journal",
            command=self.refresh_journal
        )
        refresh_btn.pack(side="left", padx=5)
        
        export_btn = ctk.CTkButton(
            btn_frame,
            text="Export to CSV",
            command=self.export_journal
        )
        export_btn.pack(side="left", padx=5)
    
    def setup_results_panel(self, parent):
        """Setup backtest results panel"""
        results_frame = ctk.CTkFrame(parent)
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        title = ctk.CTkLabel(results_frame, text="Backtest Results", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Results text
        self.results_text = ctk.CTkTextbox(results_frame, height=400)
        self.results_text.pack(fill="both", expand=True, padx=10, pady=10)
    
    def log_status(self, message):
        """Log message to status panel"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert("end", f"[{timestamp}] {message}\n")
        self.status_text.see("end")
    
    def check_tws_client_id(self):
        """
        Check TWS settings file for Master API Client ID
        Returns Client ID if found, None otherwise
        """
        try:
            # Common TWS settings file locations
            possible_paths = [
                os.path.join(os.environ.get('APPDATA', ''), 'IB', 'TWS', 'jts.ini'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'IB', 'TWS', 'jts.ini'),
                os.path.join('C:', 'Jts', 'jts.ini'),
                os.path.join(os.path.expanduser('~'), 'Jts', 'jts.ini'),
            ]
            
            # Also check for settings in registry or config files
            # TWS stores settings in jts.ini file
            for path in possible_paths:
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Look for Master API Client ID setting
                            # Common patterns: MasterAPIclientId=2 or masterApiClientId=2
                            patterns = [
                                r'MasterAPIclientId\s*=\s*(\d+)',
                                r'masterApiClientId\s*=\s*(\d+)',
                                r'MasterApiClientId\s*=\s*(\d+)',
                                r'masterAPIclientId\s*=\s*(\d+)',
                            ]
                            
                            for pattern in patterns:
                                match = re.search(pattern, content, re.IGNORECASE)
                                if match:
                                    client_id = int(match.group(1))
                                    logger.info(f"Found TWS Master API Client ID: {client_id} in {path}")
                                    return client_id
                    except Exception as e:
                        logger.debug(f"Error reading TWS settings file {path}: {e}")
                        continue
            
            # If not found in files, return None (no restriction)
            logger.debug("TWS Master API Client ID not found in settings files")
            return None
            
        except Exception as e:
            logger.debug(f"Error checking TWS Client ID: {e}")
            return None
    
    def connect_ibkr(self):
        """Connect to IBKR TWS"""
        host = self.host_entry.get()
        try:
            port = int(self.port_entry.get())
            client_id = int(self.client_id_entry.get())
        except ValueError:
            self.log_status("Error: Port and Client ID must be numbers")
            return
        
        self.ibkr.host = host
        self.ibkr.port = port
        self.ibkr.client_id = client_id
        
        def connect_thread():
            try:
                self.log_status(f"Connecting to TWS at {host}:{port} (Client ID: {client_id})...")
                self.log_status("")
                
                # Check TWS settings for Master API Client ID before connection
                tws_client_id = self.check_tws_client_id()
                if tws_client_id is not None and tws_client_id != client_id:
                    self.log_status(f"✗ Client ID mismatch detected!")
                    self.log_status(f"   - Your Client ID: {client_id}")
                    self.log_status(f"   - TWS Master API Client ID: {tws_client_id}")
                    self.log_status("")
                    self.log_status("Connection rejected. Please:")
                    self.log_status("1. Change your Client ID to match TWS settings, OR")
                    self.log_status("2. In TWS: Configure → API → Settings")
                    self.log_status("   Set 'Master API client ID' to match your Client ID")
                    self.log_status("")
                    self.root.after(0, lambda: self.conn_status.configure(text="● Client ID Mismatch", text_color="#dc3545"))
                    return
                
                self.log_status("IMPORTANT: Make sure TWS is running and API is enabled!")
                self.log_status("In TWS: Configure → API → Settings → Enable ActiveX and Socket Clients")
                self.log_status("")
                
                # Try connection
                connection_result = self.ibkr.connect()
                
                if connection_result:
                    self.root.after(0, lambda: self.conn_status.configure(text="● Connected", text_color="#28a745"))
                    self.log_status("✓ Successfully connected to TWS!")
                    self.root.after(0, lambda: self.connect_btn.configure(state="disabled"))
                    self.root.after(0, lambda: self.disconnect_btn.configure(state="normal"))
                    
                    # Auto-detect market data subscription and contract
                    self.log_status("")
                    self.log_status("="*50)
                    self.log_status("AUTO-DETECTING MARKET DATA SUBSCRIPTION...")
                    self.log_status("="*50)
                    
                    detected_symbol, detected_contract = self.ibkr.detect_available_contract()
                    
                    if detected_symbol and detected_contract:
                        self.contract = detected_contract
                        contract_month = getattr(self.contract, 'lastTradeDateOrContractMonth', 'Continuous')
                        contract_info = f"{self.contract.symbol} (Continuous Contract)"
                        if contract_month != 'Continuous':
                            contract_info += f" - Current: {contract_month}"
                        self.log_status(f"✓ Contract detected: {contract_info}")
                        self.log_status("   IBKR will automatically handle contract rollover")
                        self.log_status("")
                        self.log_status("✓ Market data subscription confirmed!")
                        self.log_status("")
                        self.log_status("="*50)
                        self.log_status("AUTO-STARTING BACKTEST...")
                        self.log_status("="*50)
                        self.log_status("")
                        
                        # Auto-start backtest with default date range (last 3 days - smaller for reliability)
                        from datetime import datetime, timedelta
                        default_to = datetime.now()
                        default_from = default_to - timedelta(days=3)  # Default 3 days
                        
                        # Update date fields if available
                        if CALENDAR_AVAILABLE and hasattr(self, 'backtest_from_calendar'):
                            self.backtest_from_calendar.set_date(default_from.date())
                            self.backtest_to_calendar.set_date(default_to.date())
                        elif hasattr(self, 'backtest_from_date'):
                            self.backtest_from_date.delete(0, "end")
                            self.backtest_from_date.insert(0, default_from.strftime("%Y%m%d"))
                            self.backtest_to_date.delete(0, "end")
                            self.backtest_to_date.insert(0, default_to.strftime("%Y%m%d"))
                        
                        # Set data source to CSV (default - no auto-download)
                        self.data_source_var.set("csv")
                        
                        # Ready message - no auto-start
                        self.log_status("")
                        self.log_status("Ready! Use the buttons above to:")
                        self.log_status("  - Click 'Download' to fetch new data from IBKR")
                        self.log_status("  - Click 'Backtest' to run backtest on cached CSV data")
                        self.log_status("")
                    else:
                        # Fallback to manual contract loading
                        try:
                            self.log_status("⚠ Auto-detection failed, trying manual contract load...")
                            self.contract = self.ibkr.get_contract(use_continuous=True)
                            contract_month = getattr(self.contract, 'lastTradeDateOrContractMonth', 'Continuous')
                            contract_info = f"{self.contract.symbol} (Continuous Contract)"
                            if contract_month != 'Continuous':
                                contract_info += f" - Current: {contract_month}"
                            self.log_status(f"✓ Contract loaded: {contract_info}")
                            self.log_status("   IBKR will automatically handle contract rollover")
                        except Exception as e:
                            error_msg = f"⚠ Warning: Could not load contract: {type(e).__name__}: {str(e)}"
                            self.log_status(error_msg)
                            self.log_status("You can still run backtests if you have historical data access.")
                            self.log_status("This might be due to:")
                            self.log_status("  - Market is closed")
                            self.log_status("  - Missing market data subscription")
                else:
                    self.root.after(0, lambda: self.conn_status.configure(text="● Connection Failed", text_color="#dc3545"))
                    self.log_status("✗ Failed to connect to TWS.")
                    self.log_status("")
                    self.log_status("Troubleshooting steps:")
                    self.log_status("1. ✓ Is TWS running? (Check Task Manager)")
                    self.log_status("2. ✓ In TWS: Configure → API → Settings")
                    self.log_status("3. ✓ Enable 'Enable ActiveX and Socket Clients'")
                    self.log_status(f"4. ✓ Set Socket port to: {port}")
                    self.log_status("5. ✓ Click OK and RESTART TWS")
                    self.log_status("6. ✓ Check firewall settings")
                    self.log_status(f"7. ✓ Try different Client ID (current: {client_id})")
                    self.log_status("")
                    self.log_status("For detailed testing, run: python test_connection.py")
            except Exception as e:
                error_msg = f"✗ Unexpected error: {type(e).__name__}: {str(e)}"
                self.log_status(error_msg)
                import traceback
                self.log_status(traceback.format_exc())
                self.root.after(0, lambda: self.conn_status.configure(text="● Error", text_color="#dc3545"))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def disconnect_ibkr(self):
        """Disconnect from IBKR TWS"""
        try:
            if self.is_trading:
                self.stop_trading()
            
            if self.market_data_subscribed:
                self.unsubscribe_market_data()
            
            self.ibkr.disconnect()
            self.conn_status.configure(text="● Disconnected", text_color="#dc3545")
            self.log_status("Disconnected from TWS")
            self.connect_btn.configure(state="normal")
            self.disconnect_btn.configure(state="disabled")
            self.contract = None
        except Exception as e:
            self.log_status(f"Error during disconnect: {e}")
            self.conn_status.configure(text="● Disconnected", text_color="#dc3545")
            self.connect_btn.configure(state="normal")
            self.disconnect_btn.configure(state="disabled")
    
    def update_strategy_params(self):
        """Update strategy parameters"""
        try:
            st_atr = int(self.st_atr_entry.get())
            st_mult = float(self.st_mult_entry.get())
            tp = float(self.tp_entry.get())
            sl = float(self.sl_entry.get())
            qty = int(self.quantity_entry.get())
            
            self.strategy.update_parameters(
                tp_percent=tp,
                sl_percent=sl,
                st_atr_period=st_atr,
                st_multiplier=st_mult
            )
            self.contract_quantity = qty
            
            self.log_status(f"Strategy parameters updated: TP={tp}%, SL={sl}%, ST ATR={st_atr}, ST Mult={st_mult}, Qty={qty}")
        except ValueError as e:
            self.log_status(f"Error updating parameters: {e}")
    
    def update_progress(self, text, color="#888888"):
        """Update progress indicator"""
        self.root.after(0, lambda: self.progress_label.configure(text=text, text_color=color))
        self.root.after(0, lambda: self.quick_status.configure(text=text))
    
    def clear_console(self):
        """Clear console output"""
        self.status_text.delete("1.0", "end")
        self.log_status("=== Console Cleared ===")
    
    def download_data(self):
        """Download data from IBKR and save to cache"""
        if not self.ibkr.connected:
            self.log_status("[ERROR] Please connect to TWS first!")
            self.update_progress("Not connected", "#dc3545")
            return
        
        def download_thread():
            try:
                import time
                
                self.log_status("")
                self.log_status("=" * 50)
                self.log_status("DOWNLOADING DATA FROM IBKR...")
                self.log_status("=" * 50)
                
                # Get date range from top bar fields
                if CALENDAR_AVAILABLE and hasattr(self, 'backtest_from_calendar'):
                    from_date = self.backtest_from_calendar.get_date()
                    to_date = self.backtest_to_calendar.get_date()
                    from_date_str = from_date.strftime("%Y%m%d")
                    to_date_str = to_date.strftime("%Y%m%d")
                elif hasattr(self, 'backtest_from_date'):
                    from_date_str = self.backtest_from_date.get()
                    to_date_str = self.backtest_to_date.get()
                else:
                    # Fallback to default 7 days
                    from datetime import datetime, timedelta
                    to_date_str = datetime.now().strftime("%Y%m%d")
                    from_date_str = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
                
                use_delayed = self.data_source_var.get() == "delayed"
                
                self.log_status(f"Date Range: {from_date_str} to {to_date_str}")
                self.log_status(f"Data Source: {'Delayed' if use_delayed else 'Real-time'}")
                
                # Calculate duration
                from datetime import datetime
                from_dt = datetime.strptime(from_date_str, "%Y%m%d")
                to_dt = datetime.strptime(to_date_str, "%Y%m%d")
                duration_days = (to_dt - from_dt).days + 1
                
                if duration_days <= 0:
                    self.log_status("[ERROR] Invalid date range")
                    return
                
                self.log_status(f"Duration: {duration_days} days")
                
                # Get contract
                if self.contract is None:
                    self.log_status("Loading contract...")
                    self.contract = self.ibkr.get_contract(symbol='MNQ')
                
                symbol = getattr(self.contract, 'symbol', 'MNQ')
                
                # Disable download button
                self.root.after(0, lambda: self.download_btn.configure(state="disabled", text="Downloading..."))
                
                # Download 1H data
                self.log_status("")
                self.log_status("[1/2] Downloading 1H data...")
                start_time = time.time()
                
                # Use current time as end date for best results
                df_1h = self.ibkr.get_1h_data(
                    self.contract,
                    duration=f"{duration_days} D",
                    use_delayed=use_delayed,
                    end_date=''
                )
                elapsed = time.time() - start_time
                
                if df_1h is not None and not df_1h.empty:
                    self.data_cache.save_data(symbol, '1H', df_1h)
                    self.log_status(f"[OK] 1H: {len(df_1h)} bars saved ({elapsed:.1f}s)")
                else:
                    self.log_status(f"[FAIL] 1H data download failed ({elapsed:.1f}s)")
                
                # Wait for pacing
                self.log_status("Waiting 5s (IBKR pacing)...")
                time.sleep(5)
                
                # Download 10M data
                self.log_status("[2/2] Downloading 10M data...")
                start_time = time.time()
                
                duration_10m = min(duration_days, 30)  # IBKR limit
                df_10m = self.ibkr.get_10m_data(
                    self.contract,
                    duration=f"{duration_10m} D",
                    use_delayed=use_delayed,
                    end_date=''
                )
                elapsed = time.time() - start_time
                
                if df_10m is not None and not df_10m.empty:
                    self.data_cache.save_data(symbol, '10M', df_10m)
                    self.log_status(f"[OK] 10M: {len(df_10m)} bars saved ({elapsed:.1f}s)")
                else:
                    self.log_status(f"[FAIL] 10M data download failed ({elapsed:.1f}s)")
                
                # Update status
                self.log_status("")
                self.log_status("=" * 50)
                
                # Get final cache info
                cache_info = self.data_cache.get_cache_info(symbol)
                if cache_info:
                    for fname, info in cache_info.items():
                        self.log_status(f"Cached: {fname} - {info['bars']} bars")
                
                self.log_status("DOWNLOAD COMPLETE")
                self.log_status("=" * 50)
                
                # Update download status label
                h1_bars = len(df_1h) if df_1h is not None and not df_1h.empty else 0
                m10_bars = len(df_10m) if df_10m is not None and not df_10m.empty else 0
                status_text = f"Data: {h1_bars} (1H) + {m10_bars} (10M) bars"
                self.root.after(0, lambda: self.download_status.configure(
                    text=status_text,
                    text_color="#28a745" if h1_bars > 0 else "#dc3545"
                ))
                
            except Exception as e:
                self.log_status(f"[ERROR] {type(e).__name__}: {str(e)}")
                logger.exception("Download error")
            finally:
                # Re-enable download button
                self.root.after(0, lambda: self.download_btn.configure(state="normal", text="Download Data"))
        
        # Run in thread
        threading.Thread(target=download_thread, daemon=True).start()
    
    def run_backtest_from_cache(self):
        """Run backtest using cached data or download first if needed"""
        data_source = self.data_source_var.get()
        
        self.log_status("")
        self.log_status("=" * 50)
        
        # If CSV selected, load directly from cache
        if data_source == "csv":
            self.log_status("RUNNING BACKTEST FROM CSV CACHE...")
            self.log_status("=" * 50)
            
            symbol = 'MNQ'
            if self.contract:
                symbol = getattr(self.contract, 'symbol', 'MNQ')
            
            self.log_status(f"Loading cached data for {symbol}...")
            
            self.df_1h = self.data_cache.load_data(symbol, '1H')
            self.df_10m = self.data_cache.load_data(symbol, '10M')
            
            if self.df_1h.empty or self.df_10m.empty:
                self.log_status("[ERROR] No cached data found!")
                self.log_status("Please download data first using the Download button.")
                self.log_status("Or select 'Delayed' or 'Live' data source.")
                self.update_progress("No cached data", "#dc3545")
                return
            
            self.log_status(f"[OK] 1H data: {len(self.df_1h)} bars")
            self.log_status(f"[OK] 10M data: {len(self.df_10m)} bars")
            
            # Run backtest
            self._run_backtest_logic()
        else:
            # For Delayed/Live, use old run_backtest method
            self.log_status("RUNNING BACKTEST (IBKR DATA)...")
            self.log_status("=" * 50)
            self.run_backtest()
    
    def _run_backtest_logic(self):
        """Internal method to run backtest on loaded data"""
        if self.df_1h is None or self.df_1h.empty:
            self.log_status("[ERROR] No 1H data available!")
            return
        
        if self.df_10m is None or self.df_10m.empty:
            self.log_status("[ERROR] No 10M data available!")
            return
        
        # Update strategy parameters
        self.update_strategy_params()
        
        self.log_status("")
        self.log_status("Running strategy analysis...")
        
        # Update UI state
        self.backtest_running = True
        self.backtest_cancelled = False
        self.backtest_btn.configure(state="disabled", text="Running...")
        self.stop_backtest_btn.configure(state="normal")
        
        def backtest_worker():
            try:
                # Prepare data with indicators using strategy.prepare_data
                self.log_status("Preparing data and calculating indicators...")
                df_1h_prepared, df_10m_prepared = self.strategy.prepare_data(
                    self.df_1h.copy(), 
                    self.df_10m.copy()
                )
                
                if df_1h_prepared.empty or df_10m_prepared.empty:
                    self.log_status("[ERROR] Data preparation failed!")
                    return
                
                self.log_status(f"[OK] 1H data prepared: {len(df_1h_prepared)} bars")
                self.log_status(f"[OK] 10M data prepared: {len(df_10m_prepared)} bars")
                
                # Run backtest
                self.log_status("Generating trade signals...")
                initial_capital = float(self.initial_capital_entry.get())
                
                self.backtest_engine = BacktestEngine(
                    strategy=self.strategy,
                    initial_capital=initial_capital
                )
                
                # Run backtest with prepared data (contract_size for MNQ = 2)
                contract_size = 2  # MNQ contract multiplier
                results = self.backtest_engine.run_backtest(df_1h_prepared, df_10m_prepared, contract_size=contract_size)
                
                if results:
                    self.backtest_results = results
                    self.log_status("")
                    self.log_status("=" * 50)
                    self.log_status("BACKTEST RESULTS")
                    self.log_status("=" * 50)
                    self.log_status(f"Total Trades: {results.get('total_trades', 0)}")
                    self.log_status(f"Win Rate: {results.get('win_rate', 0):.1f}%")
                    self.log_status(f"Total P&L: ${results.get('total_pnl', 0):,.2f}")
                    self.log_status(f"Max Drawdown: {results.get('max_drawdown', 0):.1f}%")
                    self.log_status("=" * 50)
                    
                    self.display_backtest_results()
                    self.update_progress("Backtest complete", "#28a745")
                else:
                    self.log_status("[WARN] No trades generated in backtest")
                    self.update_progress("No trades", "#ffc107")
                    
            except Exception as e:
                self.log_status(f"[ERROR] Backtest failed: {e}")
                logger.exception("Backtest error")
            finally:
                self.root.after(0, self._reset_backtest_ui)
        
        threading.Thread(target=backtest_worker, daemon=True).start()

    
    def run_backtest(self):
        """Run backtest on historical data with custom date range"""
        if not self.ibkr.connected:
            self.log_status("Please connect to TWS first!")
            self.update_progress("⚠ Not connected", "#dc3545")
            return
        
        if self.backtest_running:
            self.log_status("⚠ Backtest already running! Please wait for it to complete or stop it first.")
            return
        
        # Get date range from calendar or entry fields
        # Initialize variables to avoid scope issues
        from_date_str = None
        to_date_str = None
        from_date = None
        to_date = None
        duration_days = None
        
        try:
            if CALENDAR_AVAILABLE and hasattr(self, 'backtest_from_calendar'):
                # Get dates from calendar widgets (returns date object, convert to datetime)
                from_date_obj = self.backtest_from_calendar.get_date()
                to_date_obj = self.backtest_to_calendar.get_date()
                from_date = datetime.combine(from_date_obj, datetime.min.time())
                to_date = datetime.combine(to_date_obj, datetime.min.time())
                from_date_str = from_date.strftime("%Y%m%d")
                to_date_str = to_date.strftime("%Y%m%d")
            else:
                # Fallback to entry fields
                if hasattr(self, 'backtest_from_date'):
                    from_date_str = self.backtest_from_date.get().strip()
                else:
                    from_date_str = ""
                    
                if hasattr(self, 'backtest_to_date'):
                    to_date_str = self.backtest_to_date.get().strip()
                else:
                    to_date_str = ""
                
                if from_date_str:
                    from_date = datetime.strptime(from_date_str, "%Y%m%d")
                else:
                    # Default: start of current month
                    from_date = datetime.now().replace(day=1)
                    from_date_str = from_date.strftime("%Y%m%d")
                    if hasattr(self, 'backtest_from_date'):
                        self.backtest_from_date.delete(0, "end")
                        self.backtest_from_date.insert(0, from_date_str)
                
                if to_date_str:
                    to_date = datetime.strptime(to_date_str, "%Y%m%d")
                else:
                    # Default: today
                    to_date = datetime.now()
                    to_date_str = to_date.strftime("%Y%m%d")
                    if hasattr(self, 'backtest_to_date'):
                        self.backtest_to_date.delete(0, "end")
                        self.backtest_to_date.insert(0, to_date_str)
            
            # Ensure all variables are set
            if from_date_str is None or to_date_str is None or from_date is None or to_date is None:
                self.log_status("✗ Error: Failed to parse dates")
                return
            
            # Validate dates
            if to_date <= from_date:
                self.log_status("✗ Error: To date must be after From date")
                return
            
            # Calculate duration in days
            duration_days = (to_date - from_date).days
            if duration_days > 365:
                self.log_status("✗ Error: Date range cannot exceed 365 days")
                return
            
        except ValueError as e:
            self.log_status(f"✗ Error: Invalid date format. Use YYYYMMDD (e.g., 20240101)")
            return
        except Exception as e:
            self.log_status(f"✗ Error: Failed to get date range: {e}")
            logger.exception("Date parsing error")
            return
        
        data_source = self.data_source_var.get()
        use_delayed = (data_source == "delayed")
        
        # Verify all variables are set before starting thread
        if from_date_str is None or to_date_str is None or duration_days is None:
            self.log_status("✗ Error: Date variables not properly initialized")
            return
        
        # Set running state and update UI immediately
        self.backtest_running = True
        self.backtest_cancelled = False
        self.backtest_btn.configure(state="disabled", text="⏳ Running...")
        self.stop_backtest_btn.configure(state="normal")
        self.update_progress("⏳ Starting backtest...", "#FF8C00")
        
        # Start thread immediately (non-blocking)
        def backtest_thread():
            # Declare variables as nonlocal to access from outer scope
            nonlocal from_date_str, to_date_str, from_date, to_date, duration_days, use_delayed
            
            # Setup event loop for this thread
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            try:
                self.log_status("="*50)
                self.log_status("STARTING BACKTEST")
                self.log_status("="*50)
                self.log_status(f"Data Source: {'Delayed (Free)' if use_delayed else 'Real-time'}")
                self.log_status(f"Date Range: {from_date_str} to {to_date_str}")
                self.log_status(f"Duration: {duration_days} days")
                self.log_status("")
                
                # Check cancellation before contract fetch
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                # Get contract (using continuous contract - auto rollover)
                self.update_progress("📋 Loading contract...", "#888888")
                self.log_status("Step 1: Loading contract...")
                try:
                    # Use already loaded contract if available to avoid re-qualification
                    # But check if we need a different contract for the end_date
                    need_new_contract = False
                    if self.contract and hasattr(self.contract, 'symbol'):
                        # Check if existing contract is suitable for end_date
                        contract_expiry = getattr(self.contract, 'lastTradeDateOrContractMonth', '')
                        if contract_expiry and len(contract_expiry) >= 6:
                            try:
                                from datetime import datetime
                                end_date_obj = datetime.strptime(to_date_str, "%Y%m%d")
                                contract_expiry_obj = datetime.strptime(contract_expiry[:6] + "01", "%Y%m%d")
                                # If contract expires before end_date, need new contract
                                if contract_expiry_obj < end_date_obj:
                                    need_new_contract = True
                            except:
                                pass
                        
                        if not need_new_contract:
                            contract = self.contract
                            self.log_status(f"✓ Using existing contract: {contract.symbol}")
                        else:
                            self.log_status(f"⚠ Existing contract expires before end_date, loading new contract...")
                    else:
                        need_new_contract = True
                    
                    if need_new_contract:
                        self.log_status("Loading new contract for end_date (this may take a few seconds)...")
                        self.log_status(f"   Target end_date: {to_date_str}")
                        try:
                            contract = self.ibkr.get_contract(use_continuous=True, end_date=to_date_str)
                            self.contract = contract  # Store for future use
                            self.log_status(f"✓ Contract loaded: {contract.symbol}")
                        except Exception as e:
                            self.log_status(f"⚠ Error loading contract with end_date: {e}")
                            self.log_status("   Falling back to default contract...")
                            contract = self.ibkr.get_contract(use_continuous=True)
                            self.contract = contract
                    else:
                        contract = self.contract
                        self.log_status(f"✓ Using existing contract: {contract.symbol}")
                    
                    # Verify contract is loaded
                    if contract is None:
                        raise ValueError("Contract is None - cannot proceed")
                    
                    contract_month = getattr(contract, 'lastTradeDateOrContractMonth', 'Continuous')
                    self.log_status(f"✓ Contract: {contract.symbol} (Continuous Contract)")
                    if contract_month != 'Continuous':
                        self.log_status(f"   Current front month: {contract_month}")
                    self.log_status("   IBKR will automatically handle rollover for historical data")
                    self.log_status("")  # Blank line for clarity
                except Exception as e:
                    self.log_status(f"✗ Error loading contract: {e}")
                    logger.exception("Contract loading error")
                    self.update_progress("✗ Contract load failed", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                # For delayed data, end date cannot be in future
                # If delayed data and end date is future, use today's date
                self.log_status("")
                self.log_status("Step 2: Validating date range...")
                today = datetime.now().date()
                
                # Validate from_date is not in future
                if from_date.date() > today:
                    self.log_status(f"✗ Error: From date ({from_date_str}) is in future")
                    self.log_status("   Please select a past or current date")
                    self.update_progress("✗ Invalid date range", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                # Validate to_date is not before from_date
                if to_date.date() < from_date.date():
                    self.log_status(f"✗ Error: To date ({to_date_str}) is before from date ({from_date_str})")
                    self.log_status("   To date must be after or equal to from date")
                    self.update_progress("✗ Invalid date range", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                # For delayed data, end date cannot be in future
                if use_delayed and to_date.date() > today:
                    self.log_status(f"⚠ Warning: End date ({to_date_str}) is in future")
                    self.log_status(f"   For delayed data, using today's date: {today.strftime('%Y%m%d')}")
                    to_date = datetime.now()
                    to_date_str = today.strftime("%Y%m%d")
                    # Recalculate duration
                    duration_days = (to_date.date() - from_date.date()).days
                    if duration_days <= 0:
                        self.log_status("✗ Error: Date range invalid after adjustment")
                        self.update_progress("✗ Invalid date range", "#dc3545")
                        self.root.after(0, self._reset_backtest_ui)
                        return
                
                # Adjust for weekends - move end date to Friday if weekend
                weekday = to_date.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
                if weekday == 5:  # Saturday
                    to_date = to_date - timedelta(days=1)
                    to_date_str = to_date.strftime("%Y%m%d")
                    self.log_status(f"⚠ Saturday detected, adjusting end date to Friday: {to_date_str}")
                elif weekday == 6:  # Sunday
                    to_date = to_date - timedelta(days=2)
                    to_date_str = to_date.strftime("%Y%m%d")
                    self.log_status(f"⚠ Sunday detected, adjusting end date to Friday: {to_date_str}")
                
                # Recalculate duration after weekend adjustment
                duration_days = (to_date.date() - from_date.date()).days
                if duration_days <= 0:
                    self.log_status("✗ Error: Date range invalid after weekend adjustment")
                    self.update_progress("✗ Invalid date range", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                # Validate date range is not too large (sanity check)
                if duration_days > 365:
                    self.log_status(f"⚠ Warning: Date range is very large ({duration_days} days)")
                    self.log_status("   This may take a long time and use significant memory")
                    self.log_status("   Consider using a smaller range for faster results")
                
                # Validate minimum date range
                if duration_days < 1:
                    self.log_status("✗ Error: Date range must be at least 1 day")
                    self.update_progress("✗ Invalid date range", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                # Format dates for IBKR API
                # Use empty string for current time (recommended for recent data)
                # Otherwise use YYYYMMDD-HH:MM:SS format
                if to_date.date() >= datetime.now().date():
                    end_date_str = ''  # Empty = current time (best for recent data)
                    self.log_status("Using current time as end date (recommended)")
                else:
                    end_date_str = to_date.strftime("%Y%m%d-23:59:59")
                
                # Calculate duration strings
                duration_1h = f"{duration_days} D"
                # IBKR allows 10-min bars for up to 30 days
                duration_10m = f"{min(duration_days, 30)} D"
                
                self.log_status(f"✓ Date range validated: {from_date_str} to {to_date_str} ({duration_days} days)")
                
                # Fetch data with delayed flag
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                self.log_status("")
                self.log_status("Step 3: Fetching historical data...")
                self.update_progress("📊 Fetching 1H data...", "#888888")
                self.log_status(f"Fetching 1H data ({duration_1h})...")
                self.log_status(f"   Data Source: {'Delayed (Free)' if use_delayed else 'Real-time'}")
                self.log_status(f"   End Date: {end_date_str}")
                self.log_status(f"   ⏳ Fetching data (usually 5-15 seconds)...")
                
                import time
                start_time = time.time()
                try:
                    self.log_status(f"   Requesting 1H data: {duration_1h}...")
                    self.df_1h = self.ibkr.get_1h_data(
                        contract, 
                        duration=duration_1h, 
                        use_delayed=use_delayed,
                        end_date=end_date_str
                    )
                    elapsed_1h = time.time() - start_time
                except Exception as e:
                    elapsed_1h = time.time() - start_time
                    self.log_status(f"✗ Error fetching 1H data after {elapsed_1h:.1f} seconds: {e}")
                    logger.exception("1H data fetch error")
                    self.df_1h = pd.DataFrame()  # Set empty to trigger error handling below
                
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                if not self.df_1h.empty:
                    self.log_status(f"✓ 1H data fetched in {elapsed_1h:.1f} seconds ({len(self.df_1h)} bars)")
                else:
                    self.log_status(f"✗ 1H data fetch failed after {elapsed_1h:.1f} seconds")
                
                self.update_progress("📊 Fetching 10M data...", "#888888")
                self.log_status(f"   Requesting 10M data: {duration_10m}...")
                self.log_status(f"   Data Source: {'Delayed (Free)' if use_delayed else 'Real-time'}")
                self.log_status(f"   End Date: {end_date_str}")
                self.log_status(f"   ⏳ Fetching data (usually 5-15 seconds)...")
                
                start_time = time.time()
                try:
                    self.df_10m = self.ibkr.get_10m_data(
                        contract, 
                        duration=duration_10m, 
                        use_delayed=use_delayed,
                        end_date=end_date_str
                    )
                    elapsed_10m = time.time() - start_time
                except Exception as e:
                    elapsed_10m = time.time() - start_time
                    self.log_status(f"✗ Error fetching 10M data after {elapsed_10m:.1f} seconds: {e}")
                    logger.exception("10M data fetch error")
                    self.df_10m = pd.DataFrame()  # Set empty to trigger error handling below
                
                if not self.df_10m.empty:
                    self.log_status(f"✓ 10M data fetched in {elapsed_10m:.1f} seconds ({len(self.df_10m)} bars)")
                else:
                    self.log_status(f"✗ 10M data fetch failed after {elapsed_10m:.1f} seconds")
                
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                # Validate data before proceeding
                if self.df_1h is None or self.df_1h.empty:
                    # TRY LOADING FROM CACHE
                    self.log_status("")
                    self.log_status("⚠ IBKR data fetch failed, trying cache...")
                    try:
                        symbol = getattr(contract, 'symbol', 'MNQ')
                        cached_1h = self.data_cache.load_data(symbol, '1H')
                        if not cached_1h.empty:
                            self.df_1h = cached_1h
                            self.log_status(f"✓ Loaded 1H data from cache ({len(self.df_1h)} bars)")
                        else:
                            self.log_status("✗ No cached 1H data available")
                    except Exception as e:
                        self.log_status(f"✗ Cache load error: {e}")
                else:
                    # SAVE SUCCESSFUL FETCH TO CACHE
                    try:
                        symbol = getattr(contract, 'symbol', 'MNQ')
                        self.data_cache.save_data(symbol, '1H', self.df_1h)
                        self.log_status(f"💾 Saved 1H data to cache for offline use")
                    except Exception as e:
                        logger.debug(f"Cache save error: {e}")
                
                # Re-check after cache attempt
                if self.df_1h is None or self.df_1h.empty:
                    self.log_status("")
                    self.log_status("✗ ERROR: 1H data is empty or None")
                    self.log_status("")
                    self.log_status("Troubleshooting steps:")
                    self.log_status("1. ✓ Check TWS is connected and running")
                    self.log_status("2. ✓ Verify market data subscription in TWS")
                    self.log_status("3. ✓ Check date range is valid (not in future for delayed data)")
                    self.log_status("4. ✓ Try smaller date range (e.g., 3 days instead of 6)")
                    self.log_status("5. ✓ Check if market was open during this period")
                    if use_delayed:
                        self.log_status("6. ✓ For delayed data, end date must be today or earlier")
                    else:
                        self.log_status("6. ✓ For real-time data, ensure subscription is active")
                    self.log_status("")
                    self.update_progress("✗ 1H data fetch failed", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                if self.df_10m is None or self.df_10m.empty:
                    # TRY LOADING FROM CACHE
                    self.log_status("")
                    self.log_status("⚠ IBKR 10M data fetch failed, trying cache...")
                    try:
                        symbol = getattr(contract, 'symbol', 'MNQ')
                        cached_10m = self.data_cache.load_data(symbol, '10M')
                        if not cached_10m.empty:
                            self.df_10m = cached_10m
                            self.log_status(f"✓ Loaded 10M data from cache ({len(self.df_10m)} bars)")
                        else:
                            self.log_status("✗ No cached 10M data available")
                    except Exception as e:
                        self.log_status(f"✗ Cache load error: {e}")
                else:
                    # SAVE SUCCESSFUL FETCH TO CACHE
                    try:
                        symbol = getattr(contract, 'symbol', 'MNQ')
                        self.data_cache.save_data(symbol, '10M', self.df_10m)
                        self.log_status(f"💾 Saved 10M data to cache for offline use")
                    except Exception as e:
                        logger.debug(f"Cache save error: {e}")
                
                # Re-check after cache attempt
                if self.df_10m is None or self.df_10m.empty:
                    self.log_status("")
                    self.log_status("✗ ERROR: 10M data is empty or None")
                    self.log_status("")
                    self.log_status("Troubleshooting steps:")
                    self.log_status("1. ✓ Check TWS is connected and running")
                    self.log_status("2. ✓ Verify market data subscription in TWS")
                    self.log_status("3. ✓ Check date range is valid (10M data limited to 5 days)")
                    self.log_status("4. ✓ Try smaller date range (e.g., 3 days instead of 5)")
                    self.log_status("5. ✓ Check if market was open during this period")
                    if use_delayed:
                        self.log_status("6. ✓ For delayed data, end date must be today or earlier")
                    else:
                        self.log_status("6. ✓ For real-time data, ensure subscription is active")
                    self.log_status("")
                    self.update_progress("✗ 10M data fetch failed", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                # Additional validation: check minimum data points
                if len(self.df_1h) < 2:
                    self.log_status("")
                    self.log_status("✗ ERROR: Insufficient 1H data (need at least 2 bars)")
                    self.log_status(f"   Received: {len(self.df_1h)} bars")
                    self.log_status("   Try increasing the date range")
                    self.log_status("")
                    self.update_progress("✗ Insufficient data", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                if len(self.df_10m) < 2:
                    self.log_status("")
                    self.log_status("✗ ERROR: Insufficient 10M data (need at least 2 bars)")
                    self.log_status(f"   Received: {len(self.df_10m)} bars")
                    self.log_status("   Try increasing the date range")
                    self.log_status("")
                    self.update_progress("✗ Insufficient data", "#dc3545")
                    self.root.after(0, self._reset_backtest_ui)
                    return
                
                self.log_status(f"✓ 1H bars: {len(self.df_1h)}")
                self.log_status(f"✓ 10M bars: {len(self.df_10m)}")
                self.log_status("")
                
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                # Update strategy parameters from GUI
                self.update_strategy_params()
                
                # Get initial capital
                try:
                    initial_capital = float(self.initial_capital_entry.get())
                except:
                    initial_capital = 100000
                
                # Run backtest
                self.update_progress("🔄 Running simulation...", "#FF8C00")
                self.log_status(f"Running backtest simulation (Capital: ${initial_capital:,.0f})...")
                self.backtest_engine = BacktestEngine(self.strategy, initial_capital=initial_capital)
                
                # Check cancellation before running simulation
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                # Run backtest - ensure it always returns a result
                try:
                    self.log_status(f"Processing {len(self.df_1h)} bars...")
                    self.backtest_results = self.backtest_engine.run_backtest(self.df_1h, self.df_10m)
                    self.log_status(f"✓ Backtest simulation completed")
                    
                    # Validate results
                    if self.backtest_results is None:
                        self.log_status("⚠ Warning: Backtest returned None, using empty results")
                        self.backtest_results = {
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
                            'final_capital': initial_capital,
                            'roi': 0,
                            'trades': pd.DataFrame(),
                            'equity_curve': pd.DataFrame()
                        }
                    else:
                        self.log_status(f"✓ Backtest results received: {self.backtest_results.get('total_trades', 0)} trades")
                except Exception as e:
                    self.log_status(f"✗ Error during backtest execution: {e}")
                    logger.exception("Backtest execution error")
                    self.backtest_results = {
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
                        'final_capital': initial_capital,
                        'roi': 0,
                        'trades': pd.DataFrame(),
                        'equity_curve': pd.DataFrame()
                    }
                
                if self.backtest_cancelled:
                    self.log_status("Backtest cancelled by user")
                    return
                
                # Display results
                self.log_status("Preparing to display results...")
                if self.backtest_results and isinstance(self.backtest_results, dict):
                    self.log_status(f"Results ready: {self.backtest_results.get('total_trades', 0)} trades found")
                self.root.after(0, self.display_backtest_results)
                self.root.after(0, self.plot_charts)
                
                self.log_status("")
                self.log_status("="*50)
                self.log_status("✓ BACKTEST COMPLETED!")
                self.log_status("="*50)
                
                self.update_progress("✓ Backtest complete!", "#28a745")
                self.root.after(0, self._reset_backtest_ui)
                
            except Exception as e:
                self.log_status(f"✗ Backtest error: {e}")
                logger.exception("Backtest error")
                self.update_progress(f"✗ Error: {str(e)[:30]}", "#dc3545")
                self.root.after(0, self._reset_backtest_ui)
        
        # Store thread reference and start immediately
        self.backtest_thread = threading.Thread(target=backtest_thread, daemon=True)
        self.backtest_thread.start()
    
    def _reset_backtest_ui(self):
        """Reset backtest UI after completion or cancellation"""
        self.backtest_running = False
        self.backtest_btn.configure(state="normal", text="▶ Start Backtest")
        self.stop_backtest_btn.configure(state="disabled")
    
    def stop_backtest(self):
        """Stop running backtest"""
        if not self.backtest_running:
            return
        
        self.log_status("⏹ Stopping backtest...")
        self.backtest_cancelled = True
        self.update_progress("⏹ Cancelling...", "#dc3545")
        
        # Reset UI immediately
        self._reset_backtest_ui()
        self.log_status("Backtest stopped by user")
    
    def display_backtest_results(self):
        """Display backtest results"""
        if self.backtest_results is None:
            self.log_status("⚠ No backtest results to display (results is None)")
            return
        
        results = self.backtest_results
        
        # Ensure all required keys exist
        if not isinstance(results, dict):
            self.log_status(f"⚠ Invalid backtest results format: {type(results)}")
            return
        
        # Check if results dict is empty (shouldn't happen but check anyway)
        if not results:
            self.log_status("⚠ No backtest results to display (empty dict)")
            return
        
        try:
            self.results_text.delete("1.0", "end")
            
            result_str = f"""
Total Trades: {results['total_trades']}
Winning Trades: {results['winning_trades']}
Losing Trades: {results['losing_trades']}
Win Rate: {results['win_rate']:.2f}%
Total PnL: ${results['total_pnl']:.2f} ({results['total_pnl_pct']:.2f}%)
Average Win: {results['avg_win']:.2f}%
Average Loss: {results['avg_loss']:.2f}%
Profit Factor: {results['profit_factor']:.2f}
Max Drawdown: {results['max_drawdown']:.2f}%
Final Capital: ${results['final_capital']:.2f}
ROI: {results['roi']:.2f}%
"""
            self.results_text.insert("1.0", result_str)
            self.log_status(f"✓ Results displayed: {results['total_trades']} trades, PnL: ${results['total_pnl']:.2f}")
        except KeyError as e:
            self.log_status(f"⚠ Missing key in results: {e}")
            logger.exception("Error displaying results")
        except Exception as e:
            self.log_status(f"⚠ Error displaying results: {e}")
            logger.exception("Error displaying results")
    
    def plot_charts(self):
        """Plot price chart with indicators"""
        if self.df_1h is None or self.df_1h.empty:
            return
        
        self.ax.clear()
        
        # Plot price
        self.ax.plot(self.df_1h.index, self.df_1h['close'], label='Price', linewidth=1)
        
        # Plot EMA if available
        if 'ema' in self.df_1h.columns:
            self.ax.plot(self.df_1h.index, self.df_1h['ema'], label='EMA 200', color='yellow', linewidth=2)
        
        # Plot SuperTrend from 10M (resample to 1H for display)
        if self.df_10m is not None and 'supertrend' in self.df_10m.columns:
            st_1h = self.df_10m['supertrend'].resample('1H').last()
            st_1h = st_1h.reindex(self.df_1h.index, method='ffill')
            self.ax.plot(st_1h.index, st_1h.values, label='SuperTrend (10M)', color='green', linewidth=1.5, alpha=0.7)
        
        self.ax.set_title("Price Chart with Indicators")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price")
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        self.canvas.draw()
    
    def subscribe_market_data(self):
        """Subscribe to real-time market data
        
        Returns:
            bool: True if subscription successful, False otherwise
        """
        if not self.contract or not self.ibkr.connected:
            return False
        
        try:
            # Request market data and get ticker object
            ticker = self.ibkr.ib.reqMktData(self.contract, '', False, False)
            
            # Wait a bit to check if subscription is successful
            import time
            time.sleep(0.5)
            
            # Check if ticker has valid data
            if ticker is None:
                self.log_status("⚠ Market data subscription failed - No market data available")
                self.log_status("   Trading will continue using historical data")
                return False
            
            self.market_data_subscribed = True
            self.market_data_ticker = ticker
            
            # Set up market data callback using ticker's updateEvent
            def on_tickUpdate(ticker):
                try:
                    if ticker.last and ticker.last > 0:
                        self.current_price = ticker.last
                        self.root.after(0, lambda p=ticker.last: self.price_label.configure(text=f"Price: ${p:.2f}"))
                except Exception as e:
                    logger.debug(f"Error in ticker update: {e}")
            
            # Subscribe to ticker updates
            ticker.updateEvent += on_tickUpdate
            return True
        except Exception as e:
            self.log_status(f"⚠ Market data subscription failed: {str(e)}")
            self.log_status("   Trading will continue using historical data")
            logger.exception("Market data subscription error")
            return False
    
    def unsubscribe_market_data(self, silent=False):
        """Unsubscribe from market data
        
        Args:
            silent: If True, don't log unsubscribe message
        """
        if self.contract and self.market_data_subscribed:
            try:
                if self.market_data_ticker:
                    self.ibkr.ib.cancelMktData(self.contract)
                    self.market_data_ticker = None
                else:
                    self.ibkr.ib.cancelMktData(self.contract)
                self.market_data_subscribed = False
                if not silent:
                    self.log_status("Unsubscribed from market data")
            except Exception as e:
                if not silent:
                    self.log_status(f"Error unsubscribing: {e}")
                logger.exception("Market data unsubscribe error")
    
    def sync_positions(self):
        """Sync positions with IBKR"""
        try:
            positions = self.ibkr.get_positions()
            found_position = False
            
            if positions:
                # Get contract symbol from current contract or default to MNQ
                target_symbol = 'MNQ'
                if self.contract and hasattr(self.contract, 'symbol'):
                    target_symbol = self.contract.symbol
                
                for pos in positions:
                    # Check if this is our contract (MNQ/NQ futures)
                    if hasattr(pos.contract, 'symbol') and pos.contract.symbol == target_symbol:
                        found_position = True
                        if pos.position > 0:
                            self.strategy.position = 1
                            self.strategy.entry_price = pos.avgCost
                            # Calculate TP/SL based on current price
                            if self.current_price > 0:
                                self.strategy.tp_price = self.strategy.entry_price * (1 + self.strategy.tp_percent / 100)
                                self.strategy.sl_price = self.strategy.entry_price * (1 - self.strategy.sl_percent / 100)
                            self.log_status(f"Synced position: LONG {pos.position} @ {pos.avgCost:.2f}")
                        elif pos.position < 0:
                            self.strategy.position = -1
                            self.strategy.entry_price = pos.avgCost
                            # Calculate TP/SL based on current price
                            if self.current_price > 0:
                                self.strategy.tp_price = self.strategy.entry_price * (1 - self.strategy.tp_percent / 100)
                                self.strategy.sl_price = self.strategy.entry_price * (1 + self.strategy.sl_percent / 100)
                            self.log_status(f"Synced position: SHORT {abs(pos.position)} @ {pos.avgCost:.2f}")
                        self.update_position_display()
                        break
            
            if not found_position and self.strategy.position != 0:
                # Position closed externally
                self.log_status("No position found in IBKR, position may have been closed")
                # Don't reset automatically, let user know
                
        except Exception as e:
            self.log_status(f"Error syncing positions: {e}")
    
    def update_account_info(self):
        """Update account information"""
        try:
            account_summary = self.ibkr.get_account_summary()
            if account_summary:
                net_liquidation = account_summary.get('NetLiquidation', 'N/A')
                buying_power = account_summary.get('BuyingPower', 'N/A')
                self.root.after(0, lambda: self.account_label.configure(
                    text=f"Net Liq: ${net_liquidation} | Buying Power: ${buying_power}"
                ))
        except Exception as e:
            pass  # Silently fail for account info
    
    def start_trading(self):
        """Start live trading"""
        if not self.ibkr.connected:
            self.log_status("Please connect to TWS first!")
            return
        
        if self.is_trading:
            return
        
        if not self.contract:
            try:
                self.log_status("Loading contract (Continuous - auto rollover)...")
                self.contract = self.ibkr.get_contract(use_continuous=True)
                contract_month = getattr(self.contract, 'lastTradeDateOrContractMonth', 'Continuous')
                self.log_status(f"✓ Contract: {self.contract.symbol} (Continuous Contract)")
                if contract_month != 'Continuous':
                    self.log_status(f"   Current front month: {contract_month}")
            except Exception as e:
                self.log_status(f"Error getting contract: {e}")
                return
        
        self.is_trading = True
        self.start_trading_btn.configure(state="disabled")
        self.stop_trading_btn.configure(state="normal")
        
        # Subscribe to market data (optional - trading works without it)
        market_data_available = self.subscribe_market_data()
        
        if market_data_available:
            self.log_status("✓ Live trading started with real-time market data")
        else:
            self.log_status("✓ Live trading started (using historical data)")
        
        # Sync positions
        self.sync_positions()
        
        # Update account info
        self.update_account_info()
        
        def trading_loop():
            # Setup event loop for this thread
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            while self.is_trading:
                try:
                    # Sync positions periodically
                    if self.ibkr.connected:
                        self.sync_positions()
                        self.update_account_info()
                    
                    # Fetch latest data
                    df_1h = self.ibkr.get_1h_data(self.contract, duration='5 D')
                    df_10m = self.ibkr.get_10m_data(self.contract, duration='1 D')
                    
                    if df_1h.empty or df_10m.empty:
                        import time
                        time.sleep(60)
                        continue
                    
                    # Prepare data
                    df_1h, df_10m = self.strategy.prepare_data(df_1h, df_10m)
                    
                    # Check signals
                    current_idx = len(df_1h) - 1
                    signal, price = self.strategy.check_entry_signal(df_1h, df_10m, current_idx)
                    
                    if signal and self.strategy.position == 0:
                        # Use contract quantity parameter (simple risk management)
                        position_size = self.contract_quantity
                        
                        if position_size <= 0:
                            self.log_status("Contract quantity must be > 0, skipping trade")
                            import time
                            time.sleep(60)
                            continue
                        
                        # Place order
                        try:
                            trade = self.ibkr.place_market_order(self.contract, signal, position_size)
                            self.strategy.enter_position(signal, price)
                            
                            # Log to journal
                            self.current_trade_id = len(self.trade_journal.trades) + 1
                            # Calculate SL price for journal entry
                            sl_price = price * (1 - self.strategy.sl_percent / 100) if signal == 'BUY' else price * (1 + self.strategy.sl_percent / 100)
                            self.trade_journal.add_trade({
                                'action': signal,
                                'quantity': position_size,
                                'entry_price': price,
                                'stop_loss': sl_price,
                                'take_profit': self.strategy.tp_price
                            })
                            
                            # Notify
                            contract_symbol = self.contract.symbol if self.contract and hasattr(self.contract, 'symbol') else 'MNQ'
                            self.notifications.notify_trade_entry(contract_symbol, signal, position_size, price)
                            
                            self.log_status(f"Entry signal: {signal} {position_size} contracts at {price:.2f}")
                            self.update_position_display()
                            
                            # Wait for order fill
                            import time
                            time.sleep(2)
                            self.sync_positions()
                        except Exception as e:
                            self.log_status(f"Error placing order: {e}")
                            self.notifications.notify_error(f"Error placing order: {e}")
                    
                    # Check exit
                    if self.strategy.position != 0:
                        current_time = df_1h.index[-1]
                        # Use real-time price if available, otherwise use close
                        current_price = self.current_price if self.current_price > 0 else df_1h.iloc[-1]['close']
                        current_idx = len(df_1h) - 1
                        exit_signal = self.strategy.check_exit_signal(df_10m, df_1h, current_time, current_price, current_idx)
                        
                        if exit_signal:
                            # Close position
                            try:
                                close_action = 'SELL' if self.strategy.position == 1 else 'BUY'
                                # Get actual position size from IBKR
                                positions = self.ibkr.get_positions()
                                qty_to_close = self.contract_quantity
                                # Get contract symbol from current contract or default to MNQ
                                target_symbol = 'MNQ'
                                if self.contract and hasattr(self.contract, 'symbol'):
                                    target_symbol = self.contract.symbol
                                
                                for pos in positions:
                                    if hasattr(pos.contract, 'symbol') and pos.contract.symbol == target_symbol:
                                        qty_to_close = abs(pos.position)
                                        break
                                
                                trade = self.ibkr.place_market_order(self.contract, close_action, qty_to_close)
                                
                                # Calculate PnL
                                entry_price = self.strategy.entry_price
                                pnl = (current_price - entry_price) * qty_to_close * 20 if self.strategy.position == 1 else (entry_price - current_price) * qty_to_close * 20
                                
                                # Update journal
                                if self.current_trade_id:
                                    self.trade_journal.update_trade(self.current_trade_id, {
                                        'exit_price': current_price,
                                        'exit_reason': exit_signal,
                                        'pnl': pnl,
                                        'pnl_pct': ((current_price - entry_price) / entry_price * 100) if self.strategy.position == 1 else ((entry_price - current_price) / entry_price * 100)
                                    })
                                
                                # Update analytics
                                self.performance_analytics.add_trade({
                                    'entry_price': entry_price,
                                    'exit_price': current_price,
                                    'pnl': pnl,
                                    'exit_reason': exit_signal
                                })
                                
                                # Notify
                                contract_symbol = self.contract.symbol if self.contract and hasattr(self.contract, 'symbol') else 'MNQ'
                                self.notifications.notify_trade_exit(contract_symbol, 'BUY' if self.strategy.position == 1 else 'SELL', 
                                                                    qty_to_close, entry_price, current_price, pnl, exit_signal)
                                
                                self.strategy.exit_position(current_price, exit_signal)
                                self.log_status(f"Exit signal: {exit_signal} at {current_price:.2f} | PnL: ${pnl:.2f}")
                                self.update_position_display()
                                self.root.after(0, self.refresh_journal)
                                self.root.after(0, self.update_performance_metrics)
                                
                                # Wait for order fill
                                import time
                                time.sleep(2)
                                self.sync_positions()
                                
                                # After TP hit, if conditions still met, re-enter (continuous trading)
                                if exit_signal == 'TP_HIT':
                                    signal, entry_price = self.strategy.check_entry_signal(df_1h, df_10m, current_idx)
                                    if signal:
                                        try:
                                            # Use contract quantity parameter for re-entry
                                            position_size = self.contract_quantity
                                            if position_size > 0:
                                                trade = self.ibkr.place_market_order(self.contract, signal, position_size)
                                                self.strategy.enter_position(signal, entry_price)
                                                self.log_status(f"Re-entry after TP: {signal} at {entry_price:.2f}")
                                                self.update_position_display()
                                                time.sleep(2)
                                                self.sync_positions()
                                        except Exception as e:
                                            self.log_status(f"Error in re-entry: {e}")
                            except Exception as e:
                                self.log_status(f"Error closing position: {e}")
                                self.notifications.notify_error(f"Error closing position: {e}")
                    
                    # Update charts
                    self.df_1h = df_1h
                    self.df_10m = df_10m
                    self.root.after(0, self.plot_charts)
                    
                    # Wait before next iteration
                    import time
                    time.sleep(60)  # Check every minute
                    
                except Exception as e:
                    self.log_status(f"Trading error: {e}")
                    logger.exception("Trading error")
                    import time
                    time.sleep(60)
        
        self.trading_thread = threading.Thread(target=trading_loop, daemon=True)
        self.trading_thread.start()
    
    def stop_trading(self):
        """Stop live trading"""
        self.is_trading = False
        self.unsubscribe_market_data()
        self.start_trading_btn.configure(state="normal")
        self.stop_trading_btn.configure(state="disabled")
        self.log_status("Live trading stopped.")
    
    def update_position_display(self):
        """Update position display"""
        if self.strategy.position == 0:
            self.position_label.configure(text="Position: None")
        elif self.strategy.position == 1:
            self.position_label.configure(
                text=f"Position: LONG @ {self.strategy.entry_price:.2f} | TP: {self.strategy.tp_price:.2f} | SL: {self.strategy.sl_price:.2f}",
                text_color="green"
            )
        else:
            self.position_label.configure(
                text=f"Position: SHORT @ {self.strategy.entry_price:.2f} | TP: {self.strategy.tp_price:.2f} | SL: {self.strategy.sl_price:.2f}",
                text_color="red"
            )
    
    def update_performance_metrics(self):
        """Update performance analytics display"""
        try:
            report = self.performance_analytics.get_performance_report()
            trade_stats = report.get('trade_statistics', {})
            drawdown = report.get('drawdown_analysis', {})
            
            metrics_text = f"""
PERFORMANCE METRICS
{'='*50}

TRADE STATISTICS:
Total Trades: {trade_stats.get('total_trades', 0)}
Winning Trades: {trade_stats.get('winning_trades', 0)}
Losing Trades: {trade_stats.get('losing_trades', 0)}
Win Rate: {trade_stats.get('win_rate', 0):.2f}%
Total PnL: ${trade_stats.get('total_pnl', 0):.2f}
Average PnL: ${trade_stats.get('avg_pnl', 0):.2f}
Average Win: ${trade_stats.get('avg_win', 0):.2f}
Average Loss: ${trade_stats.get('avg_loss', 0):.2f}
Largest Win: ${trade_stats.get('largest_win', 0):.2f}
Largest Loss: ${trade_stats.get('largest_loss', 0):.2f}
Profit Factor: {trade_stats.get('profit_factor', 0):.2f}
Expectancy: ${trade_stats.get('expectancy', 0):.2f}

RISK METRICS:
Sharpe Ratio: {report.get('sharpe_ratio', 0):.2f}
Sortino Ratio: {report.get('sortino_ratio', 0):.2f}
Calmar Ratio: {report.get('calmar_ratio', 0):.2f}

DRAWDOWN ANALYSIS:
Max Drawdown: ${drawdown.get('max_drawdown', 0):.2f}
Max Drawdown %: {drawdown.get('max_drawdown_pct', 0):.2f}%
Duration: {drawdown.get('duration_days', 0)} days

Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.performance_text.delete("1.0", "end")
            self.performance_text.insert("1.0", metrics_text)
        except Exception as e:
            self.performance_text.delete("1.0", "end")
            self.performance_text.insert("1.0", f"Error updating metrics: {e}")
    
    def refresh_journal(self):
        """Refresh trade journal display"""
        try:
            summary = self.trade_journal.get_performance_summary()
            recent_trades = self.trade_journal.get_recent_trades(20)
            
            journal_text = f"""
TRADE JOURNAL SUMMARY
{'='*50}

Total Trades: {summary.get('total_trades', 0)}
Open Trades: {summary.get('open_trades', 0)}
Winning Trades: {summary.get('winning_trades', 0)}
Losing Trades: {summary.get('losing_trades', 0)}
Win Rate: {summary.get('win_rate', 0):.2f}%
Total PnL: ${summary.get('total_pnl', 0):.2f}
Average Win: ${summary.get('avg_win', 0):.2f}
Average Loss: ${summary.get('avg_loss', 0):.2f}
Profit Factor: {summary.get('profit_factor', 0):.2f}

{'='*50}
RECENT TRADES (Last 20)
{'='*50}
"""
            if not recent_trades.empty:
                journal_text += recent_trades.to_string(index=False)
            else:
                journal_text += "\nNo trades recorded yet."
            
            self.journal_text.delete("1.0", "end")
            self.journal_text.insert("1.0", journal_text)
        except Exception as e:
            self.journal_text.delete("1.0", "end")
            self.journal_text.insert("1.0", f"Error refreshing journal: {e}")
    
    def export_journal(self):
        """Export trade journal to CSV"""
        try:
            filename = f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            self.trade_journal.export_to_csv(filename)
            self.log_status(f"Trade journal exported to {filename}")
        except Exception as e:
            self.log_status(f"Error exporting journal: {e}")
    
    def update_risk_metrics_display(self):
        """Update risk metrics display - removed (using simple contract quantity parameter)"""
        pass

