"""
Notification System
Sends alerts via email, desktop notifications, etc.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications and alerts"""
    
    def __init__(self, 
                 email_enabled: bool = False,
                 smtp_server: str = "smtp.gmail.com",
                 smtp_port: int = 587,
                 email_from: str = "",
                 email_to: str = "",
                 email_password: str = ""):
        """
        Initialize notification manager
        
        Args:
            email_enabled: Enable email notifications
            smtp_server: SMTP server address
            smtp_port: SMTP port
            email_from: Sender email
            email_to: Recipient email
            email_password: Email password or app password
        """
        self.email_enabled = email_enabled
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email_from = email_from
        self.email_to = email_to
        self.email_password = email_password
        
        # Load from environment if available
        if not email_from and os.getenv('EMAIL_FROM'):
            self.email_from = os.getenv('EMAIL_FROM')
        if not email_to and os.getenv('EMAIL_TO'):
            self.email_to = os.getenv('EMAIL_TO')
        if not email_password and os.getenv('EMAIL_PASSWORD'):
            self.email_password = os.getenv('EMAIL_PASSWORD')
    
    def send_email(self, subject: str, body: str) -> bool:
        """
        Send email notification
        
        Args:
            subject: Email subject
            body: Email body
        
        Returns:
            True if sent successfully
        """
        if not self.email_enabled or not self.email_from or not self.email_to:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_from, self.email_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent: {subject}")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def notify_trade_entry(self, symbol: str, action: str, quantity: int, price: float):
        """Notify trade entry"""
        subject = f"Trade Entry: {action} {quantity} {symbol}"
        body = f"""
Trade Entry Alert

Symbol: {symbol}
Action: {action}
Quantity: {quantity}
Entry Price: ${price:.2f}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_email(subject, body)
        logger.info(f"Trade entry notification: {action} {quantity} {symbol} @ {price}")
    
    def notify_trade_exit(self, symbol: str, action: str, quantity: int, 
                         entry_price: float, exit_price: float, pnl: float, reason: str):
        """Notify trade exit"""
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if action == 'BUY' else ((entry_price - exit_price) / entry_price * 100)
        subject = f"Trade Exit: {symbol} | PnL: ${pnl:.2f} ({pnl_pct:.2f}%)"
        body = f"""
Trade Exit Alert

Symbol: {symbol}
Action: {action}
Quantity: {quantity}
Entry Price: ${entry_price:.2f}
Exit Price: ${exit_price:.2f}
PnL: ${pnl:.2f} ({pnl_pct:.2f}%)
Exit Reason: {reason}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_email(subject, body)
        logger.info(f"Trade exit notification: {symbol} | PnL: ${pnl:.2f}")
    
    def notify_risk_limit(self, message: str):
        """Notify risk limit reached"""
        subject = "Risk Limit Alert"
        body = f"""
Risk Limit Reached

{message}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Trading has been paused due to risk limits.
"""
        self.send_email(subject, body)
        logger.warning(f"Risk limit notification: {message}")
    
    def notify_error(self, error_message: str):
        """Notify error"""
        subject = "Trading Bot Error"
        body = f"""
Error Alert

{error_message}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_email(subject, body)
        logger.error(f"Error notification: {error_message}")

