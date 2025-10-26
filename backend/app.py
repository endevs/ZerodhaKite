from flask import Flask, request, redirect, session
from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a-strong-secret-key')

kite = None

@app.route("/api/set-credentials", methods=["POST"])
def set_credentials():
    global kite
    data = request.get_json()
    api_key = data.get("api_key")
    api_secret = data.get("api_secret")
    session["api_key"] = api_key
    session["api_secret"] = api_secret
    kite = KiteConnect(api_key=api_key)
    return jsonify({"status": "success"})

@app.route("/login")
def login():
    if not kite:
        return "API key not set", 400
    return redirect(kite.login_url())

@app.route("/api/zerodha/callback")
def callback():
    request_token = request.args.get("request_token")
    if not request_token:
        return "Error: request_token not found", 400
    try:
        data = kite.generate_session(request_token, api_secret=os.environ.get("KITE_API_SECRET"))
        session["access_token"] = data["access_token"]
        return redirect("/dashboard")
    except Exception as e:
        return f"Error: {e}", 400

@app.route("/api/profile")
def profile():
    if "access_token" not in session:
        return "Unauthorized", 401
    try:
        kite.set_access_token(session["access_token"])
        profile = kite.profile()
        return profile
    except Exception as e:
        return f"Error: {e}", 400

from scheduler import start_scheduler

if __name__ == "__main__":
    start_scheduler()
    app.run(port=8000, debug=True)
