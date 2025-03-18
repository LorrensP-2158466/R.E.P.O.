import asyncio
import nio
import os
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

MATRIX_HOMESERVER = "https://matrix.org"
USERNAME = "@ivan_lorrens_repo_bot:matrix.org"  
PASSWORD = os.getenv('PASSWORD')
ROOM_ID = os.getenv('ROOM_ID')

class MatrixBot:
    def __init__(self, bot_id):
        self.device_id = f"BOT{bot_id}"
        self.username = USERNAME.replace("{number}", str(bot_id))
        self.store_path = f"{STORE_PATH}_{bot_id}"
        
        self.client = nio.AsyncClient(
            homeserver=MATRIX_HOMESERVER,
            user=self.username,
            device_id=self.device_id,
        )
        
        self.client.add_event_callback(self.message_callback, nio.RoomMessageText)
        
        self.client.add_to_device_callback(self.handle_to_device_callbacks)
        self.client.add_event_callback(self.handle_room_encryption, nio.RoomEncryptionEvent)
        
        print(f"[+] Bot {bot_id} initialized")

    async def handle_room_encryption(self, room, event):
        print(f"[*] Room {room.room_id} encryption event: {event}")

    async def login(self):
        # Login and sync to get current room states
        response = await self.client.login(PASSWORD)
        if isinstance(response, nio.LoginResponse):
            print(f"[+] Logged in as {self.username}")
            # Initial sync to receive encryption keys and room state
            sync_response = await self.client.sync(timeout=30000)
            if isinstance(sync_response, nio.SyncResponse):
                print("[+] Initial sync completed.")
                return True
            else:
                print(f"[!] Sync failed: {sync_response}")
                return False
        else:
            print(f"[!] Login failed: {response}")
            return False

    async def join_room(self):
        # Check if bot is already in the room
        if ROOM_ID in self.client.rooms:
            print(f"[+] Already in room {ROOM_ID}")
            return True
        
        # Join the room
        response = await self.client.join(ROOM_ID)
        if isinstance(response, nio.JoinResponse):
            print(f"[+] Joined room {ROOM_ID}")
            return True
        else:
            print(f"[!] Failed to join room: {response}")
            return False

    async def message_callback(self, room, event):
        if room.room_id != ROOM_ID:
            return
        
        if event.sender == self.username:
            return
        
        print(f"[>] Command received from {event.sender}: {event.body}")
        
        await self.execute_command(event.body)

    async def execute_command(self, command):
        print("[+] Executing")
                
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            print(f"[!] {error_msg}")
            await self.send_response(error_msg)

    async def send_response(self, message):
        try:
            await self.client.room_send(
                room_id=ROOM_ID,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": message
                }
            )
            print(f"[+] Response sent: {message[:50]}...")
        except Exception as e:
            print(f"[!] Failed to send response: {e}")

    async def run(self):
        # Login and join room
        if not await self.login():
            return
        
        if not await self.join_room():
            return
        
        print(f"[+] Bot {self.device_id} is ready and listening for commands")
        
        # Send ready message
        await self.send_response(f"Bot {self.device_id} is online and ready to receive commands")
        
        # Keep syncing to receive new messages
        while True:
            try:
                sync_response = await self.client.sync(timeout=30000)
                if not isinstance(sync_response, nio.SyncResponse):
                    print(f"[!] Sync error: {sync_response}")
            except Exception as e:
                print(f"[!] Error during sync: {e}")
                # Small delay before retrying
                await asyncio.sleep(5)

async def main():
    bot_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    
    bot = MatrixBot(bot_id)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())