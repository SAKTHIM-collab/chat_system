# server/src/database.py
import psycopg2
import hashlib
import json
import datetime

class Database:
    def __init__(self, dbname, user, password, host):
        self.conn = None
        self.cursor = None
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self._connect()
        self._create_tables()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host
            )
            self.cursor = self.conn.cursor()
            print("Database connected successfully.")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            # In a real-world scenario, you might want to retry or exit
            exit(1)

    def _create_tables(self):
        try:
            # Users table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Rooms table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    is_private BOOLEAN DEFAULT FALSE,
                    created_by_user_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Messages table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    room_id INTEGER REFERENCES rooms(id),
                    user_id INTEGER REFERENCES users(id),
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Leaderboard table (for message counts and active time)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS leaderboard (
                    user_id INTEGER UNIQUE REFERENCES users(id),
                    message_count INTEGER DEFAULT 0,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id)
                );
            """)
            self.conn.commit()
            print("Tables created/verified successfully.")
        except Exception as e:
            print(f"Error creating tables: {e}")
            self.conn.rollback()

    def add_user(self, username, password):
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            self.cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id;",
                (username, password_hash)
            )
            user_id = self.cursor.fetchone()[0]
            self.cursor.execute(
                "INSERT INTO leaderboard (user_id) VALUES (%s);",
                (user_id,)
            )
            self.conn.commit()
            return True
        except psycopg2.IntegrityError:
            self.conn.rollback()
            return False # Username already exists
        except Exception as e:
            print(f"Error adding user: {e}")
            self.conn.rollback()
            return False

    def verify_user(self, username, password):
        try:
            self.cursor.execute(
                "SELECT id, password_hash FROM users WHERE username = %s;",
                (username,)
            )
            result = self.cursor.fetchone()
            if result:
                user_id, stored_password_hash = result
                input_password_hash = hashlib.sha256(password.encode()).hexdigest()
                if stored_password_hash == input_password_hash:
                    return user_id
            return None
        except Exception as e:
            print(f"Error verifying user: {e}")
            return None

    def create_room(self, room_name, is_private, created_by_user_id):
        try:
            self.cursor.execute(
                "INSERT INTO rooms (name, is_private, created_by_user_id) VALUES (%s, %s, %s) RETURNING id;",
                (room_name, is_private, created_by_user_id)
            )
            room_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return room_id
        except psycopg2.IntegrityError:
            self.conn.rollback()
            return None # Room name already exists
        except Exception as e:
            print(f"Error creating room: {e}")
            self.conn.rollback()
            return None

    def get_room_id(self, room_name):
        try:
            self.cursor.execute(
                "SELECT id FROM rooms WHERE name = %s;",
                (room_name,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error getting room ID: {e}")
            return None

    def get_room_name(self, room_id):
        try:
            self.cursor.execute(
                "SELECT name FROM rooms WHERE id = %s;",
                (room_id,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error getting room name: {e}")
            return None

    def get_room_details(self, room_name):
        try:
            self.cursor.execute(
                "SELECT id, name, is_private FROM rooms WHERE name = %s;",
                (room_name,)
            )
            result = self.cursor.fetchone()
            if result:
                return {"id": result[0], "name": result[1], "is_private": result[2]}
            return None
        except Exception as e:
            print(f"Error getting room details: {e}")
            return None

    def get_all_rooms(self):
        try:
            self.cursor.execute(
                "SELECT id, name, is_private FROM rooms;"
            )
            return [{"id": r[0], "name": r[1], "is_private": r[2]} for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting all rooms: {e}")
            return []

    def save_message(self, room_id, user_id, content):
        try:
            self.cursor.execute(
                "INSERT INTO messages (room_id, user_id, content) VALUES (%s, %s, %s);",
                (room_id, user_id, content)
            )
            self.cursor.execute(
                "UPDATE leaderboard SET message_count = message_count + 1, last_active = NOW() WHERE user_id = %s;",
                (user_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving message: {e}")
            self.conn.rollback()
            return False

    def get_message_history(self, room_id, limit=50):
        try:
            self.cursor.execute(
                """
                SELECT u.username, m.content, m.timestamp
                FROM messages m
                JOIN users u ON m.user_id = u.id
                WHERE m.room_id = %s
                ORDER BY m.timestamp DESC
                LIMIT %s;
                """,
                (room_id, limit)
            )
            return [{"username": r[0], "content": r[1], "timestamp": r[2].isoformat()} for r in reversed(self.cursor.fetchall())]
        except Exception as e:
            print(f"Error getting message history: {e}")
            return []

    def get_username_by_id(self, user_id):
        try:
            self.cursor.execute(
                "SELECT username FROM users WHERE id = %s;",
                (user_id,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error getting username by ID: {e}")
            return None

    def get_room_stats(self, room_id):
        try:
            self.cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE room_id = %s;",
                (room_id,)
            )
            total_messages = self.cursor.fetchone()[0]
            # Active users in room is handled by chat_manager in real-time, not purely from DB
            return {"total_messages": total_messages}
        except Exception as e:
            print(f"Error getting room stats: {e}")
            return {"total_messages": 0}

    def get_leaderboard(self, limit=10):
        try:
            self.cursor.execute(
                """
                SELECT u.username, l.message_count, l.last_active
                FROM leaderboard l
                JOIN users u ON l.user_id = u.id
                ORDER BY l.message_count DESC, l.last_active DESC
                LIMIT %s;
                """,
                (limit,)
            )
            return [{"username": r[0], "message_count": r[1], "last_active": r[2].isoformat()} for r in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []

    def update_user_active_time(self, user_id):
        try:
            self.cursor.execute(
                "UPDATE leaderboard SET last_active = NOW() WHERE user_id = %s;",
                (user_id,)
            )
            self.conn.commit()
        except Exception as e:
            print(f"Error updating user active time: {e}")
            self.conn.rollback()

    def close(self):
        if self.conn:
            self.cursor.close()
            self.conn.close()
            print("Database connection closed.")
