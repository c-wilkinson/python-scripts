"""Syncs photos from a local folder to a Pix-Star digital photo frame via email.
Keeps track of sent photos using a local SQLite database to avoid duplicates.
"""

import os
import json
import smtplib
import sqlite3
from pathlib import Path
from email.message import EmailMessage
from mimetypes import guess_type

# Location of secrets/config file (SMTP credentials, Pix-Star email)
# i.e.
# {
#  "SMTP_SERVER": "*****",
#  "SMTP_PORT": **,
#  "SMTP_USERNAME": "****",
#  If using gmail, this should be an app password
#  "SMTP_PASSWORD": "****",
#  "PIXSTAR_EMAIL": "****"
# }
CONFIG_PATH = Path("photo_frame_sync_config/secrets.json")
# Folder containing the photos to be synced to the photo frame
PHOTO_DIR = Path(r"E:/Photos/Digital Photo Frame")
# SQLite database to track which photos have already been sent
DB_PATH = Path("photo_frame_sync_data/sent_photos.db")

# Load email credentials and target address from the secrets file
with open(CONFIG_PATH, encoding="utf-8") as f:
    config = json.load(f)

SMTP_SERVER = config["SMTP_SERVER"]
SMTP_PORT = config.get("SMTP_PORT", 465)
SMTP_USERNAME = config["SMTP_USERNAME"]
SMTP_PASSWORD = config["SMTP_PASSWORD"]
PIXSTAR_EMAIL = config["PIXSTAR_EMAIL"]

def init_db():
    """
    Initializes the SQLite database and ensures the sent_photos table exists.

    Returns:
        sqlite3.Connection: A connection object to the SQLite database.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_photos (
                filename TEXT PRIMARY KEY
            )
        """)
    return conn

def has_been_sent(conn, filename):
    """
    Checks if a given filename has already been recorded as sent.

    Args:
        conn (sqlite3.Connection): SQLite database connection.
        filename (str): The filename to check.

    Returns:
        bool: True if the filename is already recorded as sent, False otherwise.
    """
    cur = conn.execute("SELECT 1 FROM sent_photos WHERE filename = ?", (filename,))
    return cur.fetchone() is not None

def mark_as_sent(conn, filename):
    """
    Records a filename as sent to the database.

    Args:
        conn (sqlite3.Connection): SQLite database connection.
        filename (str): The filename to record.
    """
    with conn:
        conn.execute("INSERT OR IGNORE INTO sent_photos (filename) VALUES (?)", (filename,))

# --- Email Sender ---
def send_photo_via_email(file_path: Path):
    """
    Sends a single photo as an email attachment to the Pix-Star digital photo frame.

    Args:
        file_path (Path): Path to the image file to be sent.

    Raises:
        smtplib.SMTPException: If email sending fails.
        OSError: If reading the file fails.
    """
    msg = EmailMessage()
    msg['Subject'] = 'New Photo'
    msg['From'] = SMTP_USERNAME
    msg['To'] = PIXSTAR_EMAIL
    msg.set_content("See attached photo.")

    # Guess MIME type for proper email attachment formatting
    mime_type, _ = guess_type(file_path.name)
    maintype, subtype = mime_type.split("/") if mime_type else ("application", "octet-stream")

    # Attach the photo
    with open(file_path, 'rb') as f:
        msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=file_path.name)

    # Send the email using SSL
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        print(f"Sent: {file_path.name}")

# --- Main Orchestration ---
def sync_photos():
    """
    Scans the photo directory for new images and sends them via email if they haven't been sent yet.
    Records each successfully sent image in the local SQLite database.
    """
    conn = init_db()

    # Get list of supported image file types
    photos = sorted(PHOTO_DIR.glob("*.jpg")) + \
             sorted(PHOTO_DIR.glob("*.jpeg")) + \
             sorted(PHOTO_DIR.glob("*.png")) + \
             sorted(PHOTO_DIR.glob("*.gif")) + \
             sorted(PHOTO_DIR.glob("*.heic"))

    # Loop through photos and send those not yet emailed
    for photo in photos:
        if not has_been_sent(conn, photo.name):
            try:
                send_photo_via_email(photo)
                mark_as_sent(conn, photo.name)
            except Exception as e:
                print(f"Failed to send {photo.name}: {e}")

    conn.close()

if __name__ == "__main__":
    sync_photos()
