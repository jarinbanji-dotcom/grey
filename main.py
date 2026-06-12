import firebase_admin
from firebase_admin import credentials, db
import requests
import time
import threading

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = '8414741935:AAHrQxNw9iFHZxf-5syA6uG2lFyJzKVHQ_A'
FIREBASE_DB_URL = 'https://forgrey-5cff2-default-rtdb.firebaseio.com/'
SERVICE_ACCOUNT_KEY_PATH = 'firebasekey.json'

is_initial_load = True


# ----------------------------------------------------
# 1. TELEGRAM FUNCTIONS
# ----------------------------------------------------

def send_telegram_message(chat_id, text):
    """Sends a DM to a specific Telegram user."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"[-] Failed to send message to {chat_id}: {e}")


def telegram_polling_worker():
    """Background thread that continuously checks Telegram for new subscribers."""
    print("[*] Telegram polling thread started. Listening for /start...")
    last_update_id = 0

    while True:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {"offset": last_update_id + 1, "timeout": 30}
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                updates = response.json().get("result", [])
                for update in updates:
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = message.get("chat", {}).get("id")
                    username = message.get("chat", {}).get("username", "Unknown")

                    # If a user types /start, register them in Firebase
                    if text.strip() == "/start" and chat_id:
                        print(f"[+] New subscriber registration request from @{username} ({chat_id})")

                        # Save to Firebase under /subscribers/chat_id
                        db.reference(f'subscribers/{chat_id}').set({
                            "username": username,
                            "subscribed_at": int(time.time())
                        })

                        # Welcome confirmation DM
                        send_telegram_message(chat_id, "✅ You have successfully subscribed to 'grey' message alerts!")
        except Exception as e:
            print(f"[-] Telegram polling error: {e}")
        time.sleep(1)


# ----------------------------------------------------
# 2. FIREBASE REALTIME DATABASE FUNCTIONS
# ----------------------------------------------------

def broadcast_alert_to_all():
    """Fetches all registered subscribers from Firebase and sends them an alert."""
    subscribers_ref = db.reference('subscribers').get()

    if not subscribers_ref:
        print("[!] Alert triggered, but there are zero registered subscribers.")
        return

    # extract the list of chat IDs
    chat_ids = subscribers_ref.keys()
    print(f"[*] Broadcasting alert to {len(chat_ids)} subscribers...")

    for chat_id in chat_ids:
        send_telegram_message(chat_id, "🚨 New message arrived ....")


def db_listener(event):
    print("event")
    print(event.event_type)
    """Callback triggered whenever data changes inside 'messages/nikky__testing1234'."""
    global is_initial_load

    if is_initial_load:
        is_initial_load = False
        print("[*] Initial synchronization complete. Listening for 'testing1234'...")
        return

    # Ensure it's a valid 'put' event with incoming data
    if event.event_type == 'put' and event.data:
        data = event.data
        print(data)
        inner_data = next(iter(data.values()))
        print(inner_data)

        if isinstance(inner_data, dict):

            # SCENARIO A: A single new message is pushed.
            # Firebase sends just the contents of the new '-O...' ID.
            # data looks exactly like: {"from": "testing1234", "ts": 1781002055215, "type": "image", ...}
            if inner_data.get('from') == 'grey':
                print(f"[+] Alert! New message from testing1234 detected at path: {event.path}")
                # Call your Telegram function here!
                broadcast_alert_to_all()


            # SCENARIO B: A bulk update happens.
            # Firebase sends multiple '-O...' IDs at once.
            else:
                for child_id, inner_data in data.items():
                    if isinstance(inner_data, dict) and inner_data.get('from') == 'testing1234':
                        print(f"[+] Alert! New message from testing1234 detected inside ID: {child_id}")
                        # Call your Telegram function here!
                        # broadcast_alert_to_all() or send_direct_test_alert(str(inner_data))
                        break  # Stop checking after we find a match to avoid spamming


# ----------------------------------------------------
# 3. MAIN COORDINTOR
# ----------------------------------------------------

def main():
    # Initialize Firebase
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})

    # Start the Telegram polling loop inside a background thread
    telegram_thread = threading.Thread(target=telegram_polling_worker, daemon=True)
    telegram_thread.start()

    # Main thread listens to Firebase Realtime Database
    print("[*] Establishing connection to Firebase Realtime Database...")
    messages_ref = db.reference('messages')
    messages_ref.listen(db_listener)

    # Keep the main process alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down application gracefully.")


if __name__ == "__main__":
    main()
