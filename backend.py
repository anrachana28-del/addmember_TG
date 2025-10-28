import asyncio
import os
from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
import firebase_admin
from firebase_admin import credentials, firestore

# === Firebase setup ===
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-service-account.json")  # JSON download from Firebase
    firebase_admin.initialize_app(cred)
db = firestore.client()

# === Prepare session folder ===
if not os.path.exists("sessions"):
    os.mkdir("sessions")

clients = {}  # live Telegram clients {phone: TelegramClient}

# === Load accounts from Firebase ===
def get_enabled_accounts():
    docs = db.collection("accounts").where("disabled", "==", False).stream()
    accounts = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        accounts.append(data)
    return accounts

# === Initialize Telethon clients ===
async def init_clients():
    accounts = get_enabled_accounts()
    for acc in accounts:
        phone = acc['phone']
        if phone not in clients:
            client = TelegramClient(f"sessions/{phone}", acc['apiId'], acc['apiHash'])
            await client.start(phone)
            clients[phone] = client
            print(f"[+] Logged in {phone}")
        else:
            print(f"[i] Client already active {phone}")

# === Add members ===
async def add_members(source_link, target_link, max_members_per_account=50):
    await init_clients()
    results = []
    accounts = get_enabled_accounts()
    if not accounts:
        print("[!] No enabled accounts found")
        return results

    for acc in accounts:
        client = clients[acc['phone']]
        try:
            source_entity = await client.get_entity(source_link)
            target_entity = await client.get_entity(target_link)
            members = await client.get_participants(source_entity, limit=max_members_per_account)
            print(f"[i] {len(members)} members fetched from {source_link} using {acc['phone']}")

            for m in members:
                try:
                    await client(InviteToChannelRequest(channel=target_entity, users=[m]))
                    print(f"[+] Added {m.username or m.id} using {acc['phone']}")
                    results.append({"member": m.username or str(m.id), "status": "Added", "account": acc['phone']})
                except UserPrivacyRestrictedError:
                    print(f"[-] Privacy Error {m.username or m.id}")
                    results.append({"member": m.username or str(m.id), "status": "Failed: Privacy", "account": acc['phone']})
                except FloodWaitError as e:
                    print(f"[!] FloodWait {e.seconds}s, sleeping...")
                    await asyncio.sleep(e.seconds)
                    results.append({"member": m.username or str(m.id), "status": f"Failed: FloodWait {e.seconds}s", "account": acc['phone']})
                await asyncio.sleep(3)  # avoid flood wait
        except Exception as e:
            print(f"[!] Error with {acc['phone']}: {e}")
    return results

# === Live loop example ===
async def main_loop():
    while True:
        # Example: check Firestore for jobs to run
        jobs = db.collection("jobs").where("status", "==", "pending").stream()
        for job in jobs:
            j = job.to_dict()
            print(f"[i] Running job {job.id}")
            res = await add_members(j['source'], j['target'], j.get('max_members', 50))
            db.collection("jobs").document(job.id).update({"status": "done", "results": res})
            print(f"[i] Job {job.id} completed")
        await asyncio.sleep(30)  # check every 30s

# === Start live bot ===
if __name__ == "__main__":
    print("[*] Telegram live bot starting...")
    asyncio.run(main_loop())
