# server/src/authentication.py
import hashlib
import json

class Authentication:
    def __init__(self, db):
        self.db = db

    def register_user(self, username, password):
        if not username or not password:
            return {"status": "error", "message": "Username and password cannot be empty."}
        if self.db.add_user(username, password):
            return {"status": "success", "message": "Registration successful."}
        else:
            return {"status": "error", "message": "Username already exists."}

    def login_user(self, username, password):
        if not username or not password:
            return {"status": "error", "message": "Username and password cannot be empty."}
        user_id = self.db.verify_user(username, password)
        if user_id:
            return {"status": "success", "message": "Login successful.", "user_id": user_id, "username": username}
        else:
            return {"status": "error", "message": "Invalid username or password."}
