# server/src/server.py
import socket
import threading
import json
import os 

from authentication import Authentication
from chat_manager import ChatManager
from database import Database


# Server Configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 12345      # Port for the server to listen on

# Database Configuration (These will be passed from environment variables in Docker Compose)
DB_NAME = os.getenv('POSTGRES_DB', 'chat_db')
DB_USER = os.getenv('POSTGRES_USER', 'chat_user')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'chat_password')
DB_HOST = os.getenv('DB_HOST', 'db') # 'db' is the service name in docker-compose

class ChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.db = Database(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST)
        self.auth = Authentication(self.db)
        self.chat_manager = ChatManager(self.db)

        self.clients = {}  # {client_socket: {'user_id': id, 'username': username, 'thread': thread}}
        self.client_id_counter = 0 # Simple counter for unique client IDs before login

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Server listening on {self.host}:{self.port}")
            while True:
                client_socket, client_address = self.server_socket.accept()
                self.client_id_counter += 1
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address, self.client_id_counter))
                client_thread.daemon = True # Allow main program to exit even if threads are running
                client_thread.start()
                self.clients[client_socket] = {'thread': client_thread, 'address': client_address, 'user_id': None, 'username': None}
                print(f"New connection from {client_address}. Assigned temporary ID: {self.client_id_counter}")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.shutdown()

    def handle_client(self, client_socket, client_address, temp_client_id):
        user_id = None
        username = None
        current_room_id = None
        
        # Initial authentication loop
        while user_id is None:
            try:
                self.send_response(client_socket, {"type": "prompt", "message": "Enter command (register/login): "})
                data = self.receive_data(client_socket)
                if not data:
                    break # Client disconnected
                
                try:
                    request = json.loads(data)
                    command = request.get('command')

                    if command == 'register':
                        response = self.auth.register_user(request.get('username'), request.get('password'))
                        self.send_response(client_socket, response)
                    elif command == 'login':
                        response = self.auth.login_user(request.get('username'), request.get('password'))
                        self.send_response(client_socket, response)
                        if response.get('status') == 'success':
                            user_id = response['user_id']
                            username = response['username']
                            self.clients[client_socket]['user_id'] = user_id
                            self.clients[client_socket]['username'] = username
                            self.chat_manager.active_users[user_id] = {'username': username, 'current_room_id': None}
                            print(f"User {username} (ID: {user_id}) authenticated from {client_address}")
                            break
                    else:
                        self.send_response(client_socket, {"status": "error", "message": "Invalid command. Use 'register' or 'login'."})

                except json.JSONDecodeError:
                    self.send_response(client_socket, {"status": "error", "message": "Invalid JSON format."})
                except Exception as e:
                    print(f"Error during authentication: {e}")
                    self.send_response(client_socket, {"status": "error", "message": f"Server error: {e}"})

            except ConnectionResetError:
                print(f"Client {client_address} disconnected abruptly during authentication.")
                break
            except Exception as e:
                print(f"Error during authentication for {client_address}: {e}")
                break

        if user_id is None: # If authentication failed or client disconnected
            self.cleanup_client(client_socket, user_id)
            return

        # Main chat loop after authentication
        while True:
            try:
                data = self.receive_data(client_socket)
                if not data:
                    print(f"Client {username} (ID: {user_id}) disconnected gracefully.")
                    break

                try:
                    request = json.loads(data)
                    command = request.get('command')
                    
                    if command == 'create_room':
                        room_name = request.get('room_name')
                        is_private = request.get('is_private', False)
                        response = self.chat_manager.create_room(room_name, is_private, user_id)
                        if response:
                            self.send_response(client_socket, {"status": "success", "message": f"Room '{room_name}' created (ID: {response})."})
                        else:
                            self.send_response(client_socket, {"status": "error", "message": f"Failed to create room '{room_name}'. It might already exist."})
                    
                    elif command == 'join_room':
                        room_name = request.get('room_name')
                        response = self.chat_manager.join_room(user_id, username, client_socket, room_name)
                        self.send_response(client_socket, response)
                        if response.get('status') == 'success':
                            current_room_id = response['room_id']
                        else:
                            current_room_id = None # Ensure client is marked as not in a room on server side
                    
                    elif command == 'leave_room':
                        if current_room_id:
                            if self.chat_manager.leave_room(user_id, current_room_id):
                                self.send_response(client_socket, {"status": "success", "message": f"Left room '{self.db.get_room_name(current_room_id)}'."})
                                current_room_id = None
                            else:
                                self.send_response(client_socket, {"status": "error", "message": "Failed to leave room."})
                        else:
                            self.send_response(client_socket, {"status": "error", "message": "You are not currently in a room."})

                    elif command == 'send_message':
                        if current_room_id:
                            message_content = request.get('message')
                            if message_content:
                                response = self.chat_manager.send_message(user_id, current_room_id, message_content)
                                # Only send success/error to the sender, broadcast handles others
                                if response.get('status') == 'error':
                                    self.send_response(client_socket, response)
                            else:
                                self.send_response(client_socket, {"status": "error", "message": "Message content cannot be empty."})
                        else:
                            self.send_response(client_socket, {"status": "error", "message": "You must join a room to send messages."})

                    elif command == 'list_rooms':
                        response = self.chat_manager.get_room_list(user_id)
                        self.send_response(client_socket, response)

                    elif command == 'room_stats':
                        if current_room_id:
                            stats = self.chat_manager.get_room_stats(current_room_id)
                            active_users = self.chat_manager.get_active_users_in_room(current_room_id)
                            self.send_response(client_socket, {
                                "status": "success",
                                "room_stats": stats,
                                "active_users": active_users
                            })
                        else:
                            self.send_response(client_socket, {"status": "error", "message": "You must be in a room to view stats."})

                    elif command == 'leaderboard':
                        response = self.chat_manager.get_leaderboard()
                        self.send_response(client_socket, response)

                    elif command == 'help':
                        help_message = """
Available commands:
  register <username> <password> - Create a new account
  login <username> <password> - Log in to your account
  create_room <room_name> [private] - Create a new chat room (add 'private' for private room)
  join_room <room_name> - Join an existing chat room
  leave_room - Leave the current chat room
  send <message> - Send a message to the current room
  list_rooms - List all available chat rooms
  room_stats - View statistics for the current room (active users, total messages)
  leaderboard - View the message leaderboard
  logout - Disconnect from the server
  help - Show this help message
"""
                        self.send_response(client_socket, {"type": "info", "message": help_message})

                    elif command == 'logout':
                        self.send_response(client_socket, {"status": "success", "message": "Logging out. Goodbye!"})
                        break # Exit the loop, leading to client cleanup

                    else:
                        self.send_response(client_socket, {"status": "error", "message": "Unknown command."})

                except json.JSONDecodeError:
                    self.send_response(client_socket, {"status": "error", "message": "Invalid JSON format."})
                except Exception as e:
                    print(f"Error handling client {username} (ID: {user_id}): {e}")
                    self.send_response(client_socket, {"status": "error", "message": f"Server internal error: {e}"})

            except ConnectionResetError:
                print(f"Client {username} (ID: {user_id}) disconnected abruptly.")
                break
            except Exception as e:
                print(f"Unexpected error with client {username} (ID: {user_id}): {e}")
                break
        
        self.cleanup_client(client_socket, user_id, current_room_id)

    def receive_data(self, client_socket):
        # Reads data until a newline character is found, to handle multiple commands in one send or partial sends
        buffer = b''
        while True:
            try:
                chunk = client_socket.recv(4096)
                if not chunk:
                    return None # Client disconnected
                buffer += chunk
                if b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    return line.decode('utf-8').strip()
            except socket.timeout:
                continue # No data yet, keep waiting
            except ConnectionResetError:
                return None # Client disconnected
            except Exception as e:
                print(f"Error receiving data: {e}")
                return None

    def send_response(self, client_socket, response_data):
        try:
            message = json.dumps(response_data) + '\n' # Add newline delimiter
            client_socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending response: {e}")

    def cleanup_client(self, client_socket, user_id, current_room_id=None):
        if user_id:
            if current_room_id:
                self.chat_manager.leave_room(user_id, current_room_id)
            self.chat_manager.disconnect_user(user_id) # Remove from active_users
        
        if client_socket in self.clients:
            del self.clients[client_socket]
        
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()
        except OSError as e:
            print(f"Error during socket shutdown/close: {e} (Client might already be closed)")
        except Exception as e:
            print(f"Unexpected error during client cleanup: {e}")
        
        print(f"Client socket closed.")


    def shutdown(self):
        print("Shutting down server...")
        for client_socket in list(self.clients.keys()):
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except OSError as e:
                print(f"Error closing client socket during shutdown: {e}")
        self.server_socket.close()
        self.db.close()
        print("Server shut down.")

if __name__ == "__main__":
    server = ChatServer(HOST, PORT)
    server.start()
