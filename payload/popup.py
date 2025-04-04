import sys
import tkinter as tk
from random import randint
from PIL import Image, ImageTk
from time import sleep
from threading import Thread
import os

class JumpingWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Catch Me If You Can!")
        self.root.geometry("200x200")
        self.root.configure(bg="white")
        self.root.overrideredirect(True)  # Remove window border
        self.root.attributes('-topmost', True)  # Keep window on top
        
        self.screen_width = root.winfo_screenwidth()
        self.screen_height = root.winfo_screenheight()
        
        self.window_width = 200
        self.window_height = 200
        
        self.set_random_position()
        self.add_background_image()
        
        # tracking the mouse so the user can't exit it
        self.running = True
        self.mouse_tracker_thread = Thread(target=self.track_mouse_position)
        self.mouse_tracker_thread.daemon = True
        self.mouse_tracker_thread.start()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def set_random_position(self):
        x = randint(0, self.screen_width - self.window_width)
        y = randint(0, self.screen_height - self.window_height)
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
    
    def track_mouse_position(self):
        try:
            while self.running:
                mouse_x = self.root.winfo_pointerx()
                mouse_y = self.root.winfo_pointery()
                
                window_x = self.root.winfo_x()
                window_y = self.root.winfo_y()
                
                distance_x = abs(mouse_x - (window_x + self.window_width/2))
                distance_y = abs(mouse_y - (window_y + self.window_height/2))
                
                # If mouse gets close to the window, move it
                # This creates a "bubble" around the window where it will flee
                if distance_x < 100 and distance_y < 100:
                    self.root.after(0, self.set_random_position)
                
                # Sleep to prevent high CPU usage
                sleep(0.05)
        except Exception as e:
            print(f"Error in mouse tracking: {e}")
            
    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)
    
    def add_background_image(self):
        try:
            image_path = self.resource_path("donkey.gif")
            
            if not os.path.exists(image_path):
                print(f"Image file not found: {image_path}")
                raise FileNotFoundError(f"Image file not found: {image_path}")
                
            image = Image.open(image_path)
            image = image.resize((self.window_width, self.window_height), Image.LANCZOS)
            
            photo = ImageTk.PhotoImage(image)
            
            label = tk.Label(self.root, image=photo, borderwidth=0)
            label.image = photo  # Keep a reference to avoid garbage collection
            label.pack(fill="both", expand=True)
            
            text_label = tk.Label(self.root, text="Can't catch me!", 
                                 font=("Arial", 10, "bold"),
                                 bg="white", fg="black")
            text_label.place(x=65, y=170)
            
        except Exception as e:
            print(f"Error loading image: {e}")
            self.root.configure(bg="lightblue")
            fallback_label = tk.Label(self.root, text="Can't catch me!", 
                                     font=("Arial", 12, "bold"),
                                     bg="lightblue")
            fallback_label.pack(expand=True)
    
    def on_close(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = JumpingWindow(root)
    root.mainloop()