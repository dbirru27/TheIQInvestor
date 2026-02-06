#!/usr/bin/env python3
"""
Email sender for InvestIQ reports
Uses Gmail SMTP with app password
"""
import smtplib
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

def load_config():
    config = configparser.ConfigParser()
    config.read('/Users/dansmacmini/.openclaw/workspace/.email_config.ini')
    return config['smtp']

def send_email(to_email, subject, body, attachment_path=None):
    """Send email with optional attachment"""
    cfg = load_config()
    
    msg = MIMEMultipart()
    msg['From'] = cfg['from']
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'html'))
    
    # Attach file if provided
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header(
            'Content-Disposition',
            f'attachment; filename={os.path.basename(attachment_path)}'
        )
        msg.attach(attachment)
    
    # Send
    with smtplib.SMTP(cfg['host'], int(cfg['port'])) as server:
        server.starttls()
        server.login(cfg['username'], cfg['password'])
        server.send_message(msg)
    
    print(f"✅ Email sent to {to_email}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python3 email_sender.py <to> <subject> <body_or_file> [attachment]")
        sys.exit(1)
    
    to = sys.argv[1]
    subject = sys.argv[2]
    body_file = sys.argv[3]
    attachment = sys.argv[4] if len(sys.argv) > 4 else None
    
    # Read body from file or use as-is
    if os.path.exists(body_file):
        with open(body_file, 'r') as f:
            body = f.read()
    else:
        body = body_file
    
    send_email(to, subject, body, attachment)
