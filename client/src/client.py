# client/src/client.py
import socket
import threading
import json
# Remove these three lines:
import sys
# import os
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import time
import datetime # Make sure this is present for timestamp formatting
import os

# Server Configuration (Use 'localhost' for local testing, 'server' for Docker Compose)
# If running client outside Docker and server in Docker, use 'localhost' if port mapping 
# is to localhost, or the Docker host IP. If client is also in Docker, use 'server'.
SERVER_HOST = os.getenv('SERVER_HOST', 'localhost') 
SERVER_PORT = int(os.getenv('SERVER_PORT', 12345))

class ChatClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.authenticated = False
        self.username = None
        self.current_room = None
        self.receive_thread = None

    def connect(self):
        try:
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"Connected to server at {self.host}:{self.port}")
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
        except Exception as e:
            print(f"Error connecting to server: {e}")
            self.connected = False

    def receive_messages(self):
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    print("Server disconnected.")
                    self.disconnect()
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    self.process_server_response(line.strip())
            except ConnectionResetError:
                print("Server closed the connection unexpectedly.")
                self.disconnect()
                break
            except OSError as e:
                if self.connected: # Only print if not intentionally disconnected
                    print(f"Socket error: {e}")
                break
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    def send_command(self, command_type, **kwargs):
        message = {"command": command_type}
        message.update(kwargs)
        try:
            self.socket.sendall((json.dumps(message) + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Error sending command: {e}")
            self.disconnect()

    def process_server_response(self, response_json):
        try:
            response = json.loads(response_json)
            response_type = response.get('type')
            status = response.get('status')
            message = response.get('message')

            if response_type == 'prompt':
                print(f"\nSERVER: {message}", end="") # Prompt, wait for user input
            elif response_type == 'chat_message':
                sender = response.get('sender')
                content = response.get('content')
                timestamp = response.get('timestamp')
                print(f"\n[{timestamp.split('T')[1].split('.')[0]}] <{sender}>: {content}")
                sys.stdout.write(f"\n{self.username}@chat_system > ") # Reprompt user
                sys.stdout.flush()
            elif status == 'success':
                print(f"\nSERVER: {message}")
                if 'user_id' in response: # Successful login
                    self.authenticated = True
                    self.username = response['username']
                    print("You are now logged in. Type 'help' for commands.")
                if 'room_name' in response: # Successful room join
                    self.current_room = response['room_name']
                    print(f"Currently in room: {self.current_room}")
                    history = response.get('history', [])
                    if history:
                        print("\n--- Chat History ---")
                        for msg in history:
                            print(f"[{msg['timestamp'].split('T')[1].split('.')[0]}] <{msg['username']}>: {msg['content']}")
                        print("--------------------\n")
                    room_stats = response.get('room_stats', {})
                    active_users = response.get('active_users_in_room', [])
                    print(f"Room Stats: Users in room: {room_stats.get('total_users', 0)}, Total messages: {room_stats.get('total_messages', 0)}")
                    print(f"Active Users in room: {', '.join(active_users)}")
                if 'rooms' in response:
                    print("\n--- Available Rooms ---")
                    for room in response['rooms']:
                        privacy_status = "(Private)" if room['is_private'] else "(Public)"
                        print(f"  - {room['name']} {privacy_status}")
                    print("-----------------------\n")
                if 'room_stats' in response and 'active_users' in response:
                    print(f"\n--- Room Statistics for {self.current_room} ---")
                    print(f"  Total Users (Currently Active): {response['room_stats'].get('total_users', 0)}")
                    print(f"  Total Messages (History): {response['room_stats'].get('total_messages', 0)}")
                    print(f"  Active Users: {', '.join(response['active_users'])}")
                    print("----------------------------------\n")
                if 'leaderboard' in response:
                    print("\n--- Leaderboard (Top Chatters) ---")
                    print(f"{'Username':<15} {'Messages':<10} {'Last Active (IST)':<25}")
                    print("-" * 50)
                    for entry in response['leaderboard']:
                        # Convert UTC to IST (UTC+5:30)
                        utc_dt = datetime.datetime.fromisoformat(entry['last_active'])
                        ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
                        ist_dt = utc_dt.astimezone(ist_tz)
                        print(f"{entry['username']:<15} {entry['message_count']:<10} {ist_dt.strftime('%Y-%m-%d %H:%M:%S'):<25}")
                    print("----------------------------------\n")
                
                # If command was 'leave_room' or 'logout'
                if message == "Left room" or message.startswith("Logging out"):
                    self.current_room = None
                    if message.startswith("Logging out"):
                        self.authenticated = False
                        self.username = None
                        self.disconnect() # Disconnect on logout
            elif status == 'error':
                print(f"\nERROR: {message}")
            else:
                print(f"\nSERVER RESPONSE: {response_json}")

            sys.stdout.write(f"\n{self.username if self.authenticated else 'guest'}@chat_system > ")
            sys.stdout.flush()

        except json.JSONDecodeError:
            print(f"Received malformed JSON: {response_json}")
        except Exception as e:
            print(f"Error processing server response: {e}, Response: {response_json}")
            
    def run(self):
        self.connect()
        if not self.connected:
            return

        while self.connected:
            try:
                sys.stdout.write(f"\n{self.username if self.authenticated else 'guest'}@chat_system > ")
                sys.stdout.flush()
                user_input = sys.stdin.readline().strip()

                if not user_input:
                    continue

                parts = user_input.split(' ', 1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if command == 'register':
                    if len(args.split()) == 2:
                        username, password = args.split()
                        self.send_command('register', username=username, password=password)
                    else:
                        print("Usage: register <username> <password>")
                elif command == 'login':
                    if len(args.split()) == 2:
                        username, password = args.split()
                        self.send_command('login', username=username, password=password)
                    else:
                        print("Usage: login <username> <password>")
                elif not self.authenticated:
                    print("You must be logged in to use this command. Use 'login <username> <password>' or 'register <username> <password>'.")
                elif command == 'create_room':
                    room_parts = args.split()
                    if len(room_parts) >= 1:
                        room_name = room_parts[0]
                        is_private = 'private' in [p.lower() for p in room_parts[1:]]
                        self.send_command('create_room', room_name=room_name, is_private=is_private)
                    else:
                        print("Usage: create_room <room_name> [private]")
                elif command == 'join_room':
                    if args:
                        self.send_command('join_room', room_name=args)
                    else:
                        print("Usage: join_room <room_name>")
                elif command == 'leave_room':
                    if self.current_room:
                        self.send_command('leave_room')
                    else:
                        print("You are not in any room to leave.")
                elif command == 'send':
                    if self.current_room:
                        if args:
                            self.send_command('send_message', message=args)
                        else:
                            print("Usage: send <your message>")
                    else:
                        print("You must join a room to send messages.")
                elif command == 'list_rooms':
                    self.send_command('list_rooms')
                elif command == 'room_stats':
                    self.send_command('room_stats')
                elif command == 'leaderboard':
                    self.send_command('leaderboard')
                elif command == 'logout':
                    self.send_command('logout')
                elif command == 'help':
                    self.send_command('help')
                elif command == 'exit':
                    print("Exiting chat client.")
                    self.disconnect()
                    break
                else:
                    print("Unknown command. Type 'help' for available commands.")
            except Exception as e:
                print(f"An error occurred during command input: {e}")
                self.disconnect()
                break

    def disconnect(self):
        if self.connected:
            try:
                self.connected = False
                self.socket.shutdown(socket.SHUT_RDWR) # Attempt to gracefully close
                self.socket.close()
                print("Disconnected from server.")
            except OSError as e:
                print(f"Error during socket shutdown/close: {e} (Socket might already be closed)")
            except Exception as e:
                print(f"Error during disconnect: {e}")

if __name__ == "__main__":
    # If you're running the client directly without Docker, you might need to adjust SERVER_HOST
    # For Docker Compose, 'server' is the correct hostname.
    # If running client locally and server in Docker, use 'localhost' if port 12345 is mapped.
    # A simple way to handle this is to check an environment variable or command-line arg.
    # For simplicity, we use os.getenv, expecting it to be set by Docker Compose or default to localhost.
    
    # Give the server a moment to start if this client is started immediately after docker-compose up
    # print("Waiting for server to be ready...")
    # time.sleep(3) 
    
    client = ChatClient(SERVER_HOST, SERVER_PORT)
    client.run()
