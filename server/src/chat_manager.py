# server/src/chat_manager.py
import threading
import json
import time

class ChatManager:
    def __init__(self, db):
        self.db = db
        self.rooms = {}  # {room_id: {'name': 'room_name', 'clients': {user_id: socket_object}, 'messages_count': 0}}
        self.room_locks = {} # {room_id: threading.Lock()}
        self.active_users = {} # {user_id: {'username': username, 'current_room_id': room_id}}
        self.load_rooms_from_db()

    def load_rooms_from_db(self):
        """Loads existing public rooms from the database on startup."""
        db_rooms = self.db.get_all_rooms()
        for room_data in db_rooms:
            room_id = room_data['id']
            room_name = room_data['name']
            if room_id not in self.rooms:
                self.rooms[room_id] = {
                    'name': room_name,
                    'clients': {},  # user_id: client_socket
                    'messages_count': self.db.get_room_stats(room_id).get('total_messages', 0),
                    'is_private': room_data['is_private']
                }
                self.room_locks[room_id] = threading.Lock()
                print(f"Loaded room: {room_name} (ID: {room_id}, Private: {room_data['is_private']})")

    def create_room(self, room_name, is_private, created_by_user_id):
        room_id = self.db.create_room(room_name, is_private, created_by_user_id)
        if room_id:
            self.rooms[room_id] = {
                'name': room_name,
                'clients': {},
                'messages_count': 0,
                'is_private': is_private
            }
            self.room_locks[room_id] = threading.Lock()
            print(f"Created new room: {room_name} (ID: {room_id}, Private: {is_private})")
            return room_id
        return None

    def join_room(self, user_id, username, client_socket, room_name):
        room_details = self.db.get_room_details(room_name)
        if not room_details:
            return {"status": "error", "message": f"Room '{room_name}' does not exist."}

        room_id = room_details['id']

        # Leave previous room if any
        if user_id in self.active_users and self.active_users[user_id].get('current_room_id'):
            self.leave_room(user_id, self.active_users[user_id]['current_room_id'])

        with self.room_locks.get(room_id, threading.Lock()): # Use existing lock or create a dummy one if somehow missing
            self.rooms[room_id]['clients'][user_id] = client_socket
            self.active_users[user_id] = {'username': username, 'current_room_id': room_id}
            self.db.update_user_active_time(user_id) # Mark user as active

        print(f"User {username} (ID: {user_id}) joined room: {room_name} (ID: {room_id})")
        
        # Notify others in the room
        join_message = f"{username} has joined the room."
        self.broadcast_message(room_id, "SERVER", join_message, exclude_user_id=user_id)

        # Get history
        history = self.db.get_message_history(room_id)
        room_stats = self.get_room_stats(room_id)
        active_users_in_room = [self.active_users[uid]['username'] for uid in self.rooms[room_id]['clients']]
        
        return {
            "status": "success",
            "message": f"Joined room '{room_name}'.",
            "room_id": room_id,
            "room_name": room_name,
            "history": history,
            "room_stats": room_stats,
            "active_users_in_room": active_users_in_room
        }

    def leave_room(self, user_id, room_id):
        if room_id in self.rooms and user_id in self.rooms[room_id]['clients']:
            with self.room_locks[room_id]:
                del self.rooms[room_id]['clients'][user_id]
                if user_id in self.active_users:
                    self.active_users[user_id]['current_room_id'] = None # Mark as no longer in a room

            username = self.db.get_username_by_id(user_id)
            room_name = self.db.get_room_name(room_id)
            print(f"User {username} (ID: {user_id}) left room: {room_name} (ID: {room_id})")
            
            # Notify others in the room
            leave_message = f"{username} has left the room."
            self.broadcast_message(room_id, "SERVER", leave_message)
            return True
        return False

    def disconnect_user(self, user_id):
        if user_id in self.active_users:
            room_id = self.active_users[user_id].get('current_room_id')
            if room_id:
                self.leave_room(user_id, room_id)
            del self.active_users[user_id]
            print(f"User ID {user_id} disconnected.")

    def send_message(self, user_id, room_id, message_content):
        if room_id not in self.rooms:
            return {"status": "error", "message": "Room does not exist."}
        if user_id not in self.rooms[room_id]['clients']:
            return {"status": "error", "message": "You are not in this room."}

        username = self.db.get_username_by_id(user_id)
        if not username:
            return {"status": "error", "message": "Invalid user."}

        # Save to database
        self.db.save_message(room_id, user_id, message_content)
        
        # Update in-memory message count for stats
        with self.room_locks[room_id]:
            self.rooms[room_id]['messages_count'] += 1

        # Broadcast to clients in the room
        self.broadcast_message(room_id, username, message_content)
        
        return {"status": "success", "message": "Message sent."}

    def broadcast_message(self, room_id, sender_username, message_content, exclude_user_id=None):
        if room_id not in self.rooms:
            return

        message_data = {
            "type": "chat_message",
            "sender": sender_username,
            "content": message_content,
            "timestamp": datetime.datetime.now().isoformat()
        }
        message_json = json.dumps(message_data) + '\n' # Add newline delimiter

        with self.room_locks[room_id]:
            clients_to_remove = []
            for client_user_id, client_socket in list(self.rooms[room_id]['clients'].items()):
                if client_user_id == exclude_user_id:
                    continue
                try:
                    client_socket.sendall(message_json.encode('utf-8'))
                except Exception as e:
                    print(f"Error sending message to {self.db.get_username_by_id(client_user_id)}: {e}")
                    clients_to_remove.append(client_user_id)
            
            for user_to_remove in clients_to_remove:
                self.leave_room(user_to_remove, room_id)

    def get_room_list(self, user_id):
        # For now, show all rooms. In a more complex system, private rooms would require invitations.
        rooms_list = self.db.get_all_rooms()
        return {"status": "success", "rooms": rooms_list}

    def get_room_stats(self, room_id):
        if room_id not in self.rooms:
            return {"total_users": 0, "total_messages": 0}

        db_stats = self.db.get_room_stats(room_id)
        current_active_users = len(self.rooms[room_id]['clients'])
        
        return {
            "total_users": current_active_users,
            "total_messages": db_stats.get('total_messages', 0)
        }

    def get_active_users_in_room(self, room_id):
        if room_id not in self.rooms:
            return []
        
        active_users = [self.db.get_username_by_id(uid) for uid in self.rooms[room_id]['clients']]
        return [u for u in active_users if u is not None]

    def get_leaderboard(self):
        return {"status": "success", "leaderboard": self.db.get_leaderboard()}
