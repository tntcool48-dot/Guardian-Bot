import os
import sys
import requests
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox

# --- CONFIGURATION ---
# 1. VERSION URL (Raw text file)
VERSION_URL = "https://raw.githubusercontent.com/tntcool48-dot/Guardian-Bot/main/version.txt"

# 2. EXE URL (The Release file)
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

        self.status_label = tk.Label(self.root, text="Checking status...", 
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
        # PRIORITY CHECK: Is the bot even installed?
        if not os.path.exists(MAIN_EXE_NAME):
            self.status_label.config(text="Bot missing. Force installing...", fg="yellow")
            # Force download version 1.0 initially
            self.root.after(1000, lambda: self.download_update(1.0))
            return

        # If installed, check for updates normally
        try:
            print(f"Checking: {VERSION_URL}")
            response = requests.get(VERSION_URL, timeout=10)
            
            if response.status_code != 200:
                self.launch_game("Offline Mode (Cannot check updates)")
                return
            
            latest_version = float(response.text.strip())
            local_version = self.get_local_version()
            
            if latest_version > local_version:
                self.status_label.config(text=f"Update found (v{latest_version})...")
                self.root.after(500, lambda: self.download_update(latest_version))
            else:
                self.status_label.config(text="Up to date! Launching...")
                self.root.after(1000, lambda: self.launch_game())
                
        except Exception as e:
            print(f"Check Failed: {e}")
            self.launch_game("Skipping update check (Error).")

    def download_update(self, new_version):
        try:
            print(f"Downloading from: {EXE_URL}")
            response = requests.get(EXE_URL, stream=True, timeout=30)
            
            # CHECK IF LINK IS BROKEN
            if response.status_code == 404:
                messagebox.showerror("Download Error", "Error 404: The release file was not found on GitHub.\n\nDid you create the Release?")
                self.root.destroy()
                return
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            total_size = int(response.headers.get('content-length', 0))
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
                except: pass 

            os.rename(temp_name, MAIN_EXE_NAME)
            
            with open(CURRENT_VERSION_FILE, "w") as f:
                f.write(str(new_version))
                
            self.status_label.config(text="Install Complete!")
            self.root.after(1000, lambda: self.launch_game())

        except Exception as e:
            messagebox.showerror("Update Failed", f"Failed to download:\n{e}")
            # Do not try to launch if we failed to download the missing file
            if os.path.exists(MAIN_EXE_NAME):
                self.launch_game()
            else:
                self.root.destroy()

    def launch_game(self, msg=None):
        if msg: print(msg)
        if os.path.exists(MAIN_EXE_NAME):
            subprocess.Popen([MAIN_EXE_NAME])
            self.root.destroy()
        else:
            self.status_label.config(text="Error: GuardianBot.exe missing!", fg="red")
            messagebox.showerror("Error", "GuardianBot.exe is missing and could not be downloaded.")

if __name__ == "__main__":
    UpdaterApp()