import os
import sys
import requests
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox

# --- CONFIGURATION ---

# 1. VERSION URL (The tiny text file)
# Go to your Code tab -> Click version.txt -> Click "Raw" -> Copy that URL
VERSION_URL = "https://raw.githubusercontent.com/tntcool48-dot/Guardian-Bot/refs/heads/main/version.txt"

# 2. EXE URL (The big file from Releases)
# Go to your Releases page -> Right-click the .exe asset -> Copy Link Address
EXE_URL = "https://github.com/tntcool48-dot/Guardian-Bot/releases/latest/download/GuardianBot.exe"

CURRENT_VERSION_FILE = "version.dat"
MAIN_EXE_NAME = "GuardianBot.exe"

class UpdaterApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Guardian Launcher")
        self.root.geometry("350x180")
        self.root.configure(bg="#2b2b2b")
        self.center_window()

        self.status_label = tk.Label(self.root, text="Checking for updates...", 
                                     fg="white", bg="#2b2b2b", font=("Segoe UI", 10))
        self.status_label.pack(pady=(30, 10))
        
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=280, mode="determinate")
        self.progress.pack(pady=10)
        
        # Start checking automatically
        self.root.after(1000, self.check_update)
        self.root.mainloop()

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def get_local_version(self):
        if os.path.exists(CURRENT_VERSION_FILE):
            try:
                with open(CURRENT_VERSION_FILE, "r") as f:
                    return float(f.read().strip())
            except: return 0.0
        return 0.0

    def check_update(self):
        try:
            print(f"Checking: {VERSION_URL}")
            response = requests.get(VERSION_URL, timeout=10)
            
            if response.status_code != 200:
                self.launch_game("Could not connect to update server.")
                return
            
            latest_version = float(response.text.strip())
            local_version = self.get_local_version()
            bot_exists = os.path.exists(MAIN_EXE_NAME)
            
            print(f"Local: {local_version} | Online: {latest_version} | Exists: {bot_exists}")

            # NEW LOGIC: Update if version is newer OR if the bot file is missing
            if latest_version > local_version or not bot_exists:
                reason = "New version found" if latest_version > local_version else "Bot file missing"
                self.status_label.config(text=f"{reason}. Downloading...")
                self.root.after(500, lambda: self.download_update(latest_version))
            else:
                self.status_label.config(text="Up to date! Launching...")
                self.root.after(1000, lambda: self.launch_game())
                
        except Exception as e:
            print(f"Update Check Failed: {e}")
            # Only try to launch if the file actually exists
            if os.path.exists(MAIN_EXE_NAME):
                self.launch_game("Skipping update check (Error).")
            else:
                self.status_label.config(text="Update failed & Bot missing!", fg="red")
                messagebox.showerror("Error", f"Could not download GuardianBot:\n{e}")

    def download_update(self, new_version):
        try:
            response = requests.get(EXE_URL, stream=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            temp_name = "new_update.tmp"
            block_size = 8192
            wrote = 0
            
            with open(temp_name, "wb") as f:
                for data in response.iter_content(block_size):
                    wrote += len(data)
                    f.write(data)
                    if total_size > 0:
                        percent = (wrote / total_size) * 100
                        self.progress['value'] = percent
                        self.root.update_idletasks()

            if os.path.exists(MAIN_EXE_NAME):
                try: os.remove(MAIN_EXE_NAME)
                except: pass # Try to overwrite anyway

            os.rename(temp_name, MAIN_EXE_NAME)
            
            with open(CURRENT_VERSION_FILE, "w") as f:
                f.write(str(new_version))
                
            self.status_label.config(text="Update Complete!")
            self.root.after(1000, lambda: self.launch_game())

        except Exception as e:
            messagebox.showerror("Update Failed", f"Failed to download:\n{e}")
            if os.path.exists(MAIN_EXE_NAME):
                self.launch_game()

    def launch_game(self, msg=None):
        if msg: print(msg)
        if os.path.exists(MAIN_EXE_NAME):
            subprocess.Popen([MAIN_EXE_NAME])
            self.root.destroy()
        else:
            self.status_label.config(text="Error: GuardianBot.exe missing!", fg="red")

if __name__ == "__main__":
    UpdaterApp()