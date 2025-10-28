from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import random

app = Flask(__name__)

# Firebase init
cred = credentials.Certificate("firebase_key.json")  # path to your Firebase service account JSON
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register_account", methods=["POST"])
def register_account():
    data = request.json
    db.collection("accounts").add({
        "apiId": data.get("api_id"),
        "apiHash": data.get("api_hash"),
        "phone": data.get("phone"),
        "disabled": False
    })
    return jsonify({"status":"ok"})

@app.route("/get_accounts")
def get_accounts():
    docs = db.collection("accounts").stream()
    accounts = []
    for doc in docs:
        d = doc.to_dict()
        accounts.append({
            "id": doc.id,
            "apiId": d.get("apiId"),
            "apiHash": d.get("apiHash"),
            "phone": d.get("phone"),
            "disabled": d.get("disabled", False)
        })
    return jsonify(accounts)

@app.route("/toggle_account", methods=["POST"])
def toggle_account():
    data = request.json
    doc_id = data.get("id")
    disabled = data.get("disabled")
    db.collection("accounts").document(doc_id).update({"disabled": disabled})
    return jsonify({"status":"ok"})

@app.route("/add_members", methods=["POST"])
def add_members():
    data = request.json
    max_members = int(data.get("max_members", 0))
    accounts = db.collection("accounts").where("disabled","==",False).stream()
    acc_list = [a.to_dict() for a in accounts]
    members = [f"Member {i+1}" for i in range(max_members)]
    result = []
    added = failed = 0
    for acc in acc_list:
        for m in members:
            success = random.random() > 0.2
            status = "Added" if success else "Failed"
            if success: added += 1
            else: failed += 1
            result.append({"member": m, "status": status, "account": acc["phone"]})
    return jsonify({"total": max_members, "added": added, "failed": failed, "result": result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
