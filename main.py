"""
Main Entry Point for Trading Bot
"""
import customtkinter as ctk
from gui import TradingBotGUI

if __name__ == "__main__":
    root = ctk.CTk()
    app = TradingBotGUI(root)
    root.mainloop()

