import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()
def sendCriticalErrorMail(subject, message, recipientMail='errors@techniki.tech'):
    # Email content
    senderMail = os.getenv('SENDER_MAIL')  # Your Google Workspace email
    msg = MIMEMultipart()
    msg['To'] = recipientMail
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    sendPass = os.getenv('SENDER_PASS')
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(senderMail, sendPass)
        server.sendmail(senderMail, recipientMail, msg.as_string())
        print("Email sent successfully via SMTP relay.")
        server.quit()
    except Exception as e:
        print(f"Failed to send email via SMTP relay: {e}")


sendCriticalErrorMail(
    subject="Test Email via SMTP Relay",
    message="This is a test email sent using Google's SMTP relay service.",)