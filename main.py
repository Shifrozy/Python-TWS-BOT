"""
Main Entry Point for Trading Bot
"""
import asyncio

# CRITICAL: Ensure an asyncio event loop is set on the current thread for Python 3.10+ / 3.12+ / 3.14+
try:
    asyncio.get_event_loop()
except RuntimeError:
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

import customtkinter as ctk
from gui import TradingBotGUI

if __name__ == "__main__":
    root = ctk.CTk()
    app = TradingBotGUI(root)
    root.mainloop()

