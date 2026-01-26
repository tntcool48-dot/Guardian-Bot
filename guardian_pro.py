import time
import os
import threading
import winsound
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from pynput import keyboard, mouse
import psutil
import mss
import json
import pyautogui
import subprocess
import sys

# --- CONFIGURATION ---
CONFIG_FILE = "guardian_config.json"
PROCESS_NAME = "javaw.exe"
ONE_HOUR_SECONDS = 3600
WARNING_DURATION = 10
MAX_RETRIES = 10  

# --- GLOBAL STATE ---
state = {
    "mode": "normal",
    "status_text": "READY",
    "status_color": "#FFFF00", # Yellow
    "bg_color": "#202020",      # Dark Grey
    "monitor": None,
    "kill_timer_start": None,
    "kill_warning_active": False,
    "running": False,
    "active": False,
    "handling_incident": False,
    "locraw_response": None,
    "final_log_path": None,
    "ahk_process": None,
    "selected_macro": "yazan.ahk"
}

# --- RESOURCE HELPER ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Use the folder where THIS script is located
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- AHK LAUNCHER ---
def launch_ahk():
    """ Launches the selected AutoHotkey script """
    script_name = state["selected_macro"]
    ahk_path = resource_path(script_name)
    ahk_exe = resource_path("AutoHotkey.exe") 
    
    print(f"[AHK] Launching: {script_name}")
    
    if os.path.exists(ahk_path):
        try:
            if os.path.exists(ahk_exe):
                # Run using the bundled engine
                state["ahk_process"] = subprocess.Popen([ahk_exe, ahk_path])
            else:
                # Fallback to system AHK
                os.startfile(ahk_path)
            print("[AHK] Script started successfully.")
        except Exception as e:
            print(f"[AHK] Error starting script: {e}")
    else:
        # Fallback Logic
        print(f"[AHK] Warning: Could not find {script_name}")
        fallback = "cizare.ahk" if "yazan" in script_name else "yazan.ahk"
        
        if os.path.exists(resource_path(fallback)):
             print(f"[AHK] Found {fallback} instead. Launching that.")
             if os.path.exists(ahk_exe):
                state["ahk_process"] = subprocess.Popen([ahk_exe, resource_path(fallback)])
             else:
                os.startfile(resource_path(fallback))

# --- PROCESS CHECKER ---
def is_minecraft_running():
    """ Checks if javaw.exe is currently running """
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == PROCESS_NAME:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

# --- LAUNCHER GUI CLASS ---
class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Guardian Bot - v22")
        self.root.geometry("450x550")
        self.root.configure(bg="#2b2b2b")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Title
        tk.Label(self.root, text="Guardian Log Protection", font=("Segoe UI", 16, "bold"), 
                 fg="#00ff00", bg="#2b2b2b").pack(pady=15)
        
        # 1. LOG FILE SECTION
        tk.Label(self.root, text="Minecraft Log Path:", fg="white", bg="#2b2b2b", font=("Segoe UI", 10, "bold")).pack(pady=(10,0))
        lbl_info = tk.Label(self.root, text="Select 'latest.log' or paste your Profile folder.", 
                            fg="#aaaaaa", bg="#2b2b2b", font=("Segoe UI", 8))
        lbl_info.pack()

        self.path_var = tk.StringVar()
        self.entry = tk.Entry(self.root, textvariable=self.path_var, width=55, bg="#444", fg="white", borderwidth=0)
        self.entry.pack(pady=5, ipady=4)
        
        btn_frame = tk.Frame(self.root, bg="#2b2b2b")
        btn_frame.pack()
        tk.Button(btn_frame, text="Browse...", bg="#555", fg="white", command=self.browse_file).pack(side=tk.LEFT, padx=5)
        
        # 2. MONITOR SELECTION
        tk.Label(self.root, text="Overlay Monitor:", fg="white", bg="#2b2b2b", font=("Segoe UI", 10, "bold")).pack(pady=(20,0))
        self.monitor_combo = ttk.Combobox(self.root, state="readonly", width=40)
        self.monitors = self.get_monitors()
        self.monitor_combo['values'] = [m['label'] for m in self.monitors]
        if self.monitors: self.monitor_combo.current(0)
        self.monitor_combo.pack(pady=5)
        
        # 3. MACRO SELECTION
        tk.Label(self.root, text="Select Macro:", fg="white", bg="#2b2b2b", font=("Segoe UI", 10, "bold")).pack(pady=(20,0))
        self.macro_var = tk.StringVar(value="yazan.ahk")
        
        frame_macro = tk.Frame(self.root, bg="#2b2b2b")
        frame_macro.pack()
        
        tk.Radiobutton(frame_macro, text="Yazan", variable=self.macro_var, value="yazan.ahk", 
                       bg="#2b2b2b", fg="#00ffff", selectcolor="#444", activebackground="#2b2b2b").pack(side=tk.LEFT, padx=20)
        
        tk.Radiobutton(frame_macro, text="Cizare", variable=self.macro_var, value="cizare.ahk", 
                       bg="#2b2b2b", fg="#ff00ff", selectcolor="#444", activebackground="#2b2b2b").pack(side=tk.LEFT, padx=20)

        # 4. MODE SELECTION
        tk.Label(self.root, text="Operation Mode:", fg="white", bg="#2b2b2b", font=("Segoe UI", 10, "bold")).pack(pady=(20,0))
        self.mode_var = tk.StringVar(value="normal")
        frame_mode = tk.Frame(self.root, bg="#2b2b2b")
        frame_mode.pack()
        tk.Radiobutton(frame_mode, text="Normal (Safe)", variable=self.mode_var, value="normal", 
                       bg="#2b2b2b", fg="#00ff00", selectcolor="#444", activebackground="#2b2b2b").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_mode, text="Test Mode", variable=self.mode_var, value="test", 
                       bg="#2b2b2b", fg="yellow", selectcolor="#444", activebackground="#2b2b2b").pack(side=tk.LEFT, padx=10)

        # 5. START BUTTON
        tk.Button(self.root, text="LAUNCH GUARDIAN", bg="#008800", fg="white", font=("Segoe UI", 12, "bold"),
                  command=self.start_bot).pack(pady=30, fill=tk.X, padx=40)

        self.load_config()
        self.root.mainloop()

    def get_monitors(self):
        with mss.mss() as sct:
            mons = []
            for i, m in enumerate(sct.monitors):
                if i == 0: continue
                m['label'] = f"Monitor {i}: {m['width']}x{m['height']}"
                m['index'] = i
                mons.append(m)
            return mons

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Log Files", "*.log"), ("All Files", "*.*")])
        if f: self.path_var.set(f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.path_var.set(data.get("log_path", ""))
                    self.macro_var.set(data.get("selected_macro", "yazan.ahk"))
            except: pass

    def start_bot(self):
        # 1. CHECK MINECRAFT PROCESS
        if not is_minecraft_running():
            messagebox.showerror("Error", "Minecraft (javaw.exe) is NOT running!\nPlease start the game first.")
            return

        # 2. PATH VALIDATION
        raw = self.path_var.get().strip().strip('"')
        
        if os.path.isdir(raw):
            check = os.path.join(raw, "logs", "latest.log")
            if os.path.exists(check):
                raw = check
            else:
                check = os.path.join(raw, "latest.log")
                if os.path.exists(check):
                    raw = check
        
        if not raw.endswith("latest.log") and (raw.endswith("logs") or raw.endswith("logs\\")):
            raw = os.path.join(raw, "latest.log")

        if not os.path.exists(raw):
            messagebox.showerror("Error", "Invalid Log Path!")
            return

        # 3. SAVE & START
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "log_path": raw,
                "selected_macro": self.macro_var.get()
            }, f)
            
        state["final_log_path"] = raw
        state["mode"] = self.mode_var.get()
        state["selected_macro"] = self.macro_var.get()
        state["monitor"] = self.monitors[self.monitor_combo.current()]
        
        self.root.destroy()
        start_main_bot()

# --- OVERLAY GUI ---
class StatusOverlay:
    def __init__(self, monitor):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9) 
        self.root.configure(bg=state["bg_color"])
        
        x_pos = monitor["left"] + monitor["width"] - 420
        y_pos = monitor["top"] + 50
        self.root.geometry(f"400x80+{x_pos}+{y_pos}")
        
        self.label = tk.Label(self.root, text="Initializing...", 
                              font=("Consolas", 14, "bold"), fg=state["status_color"], bg=state["bg_color"])
        self.label.pack(expand=True, fill='both')
        self.update_gui()
        self.root.mainloop()

    def update_gui(self):
        if not state["running"]:
            self.root.destroy()
            return
        self.label.config(text=state["status_text"], fg=state["status_color"], bg=state["bg_color"])
        self.root.configure(bg=state["bg_color"])
        self.root.after(200, self.update_gui)

# --- BOT LOGIC ---
def type_human(text):
    pyautogui.write(text, interval=0.12)

def check_location():
    state["locraw_response"] = None
    
    # Send /locraw
    pyautogui.press('t')
    time.sleep(0.2)
    type_human('/locraw')
    time.sleep(0.2)
    pyautogui.press('enter')
    
    # Wait for response
    start = time.time()
    while time.time() - start < 5:
        if state["locraw_response"]: 
            return state["locraw_response"]
        time.sleep(0.2)
    return "unknown"

def handle_incident():
    if state["handling_incident"]: return
    state["handling_incident"] = True
    
    try:
        # 1. PAUSE MACRO IMMEDIATELY
        print("[BOT] World Switch Detected! Pausing Macro...")
        pyautogui.press('f3') 
        state["status_text"] = "CHECKING LOCATION..."
        state["status_color"] = "white"
        state["bg_color"] = "#FF4500" # Orange-Red
        time.sleep(4)
        
        # 2. CHECK LOCATION
        loc = check_location()
        if '"mode":"garden"' in loc or '"map":"The Garden"' in loc:
            state["status_text"] = "FALSE ALARM. RESUMING..."
            state["status_color"] = "white"
            state["bg_color"] = "#008000" # Green
            time.sleep(1)
            pyautogui.press('f3')
            time.sleep(2)
            state["bg_color"] = "black"
            return
        
        # 3. WARP LOOP
        print(f"[BOT] Unsafe Location: {loc}. Warping...")
        for i in range(1, MAX_RETRIES+1):
            state["status_text"] = f"WARPING ATTEMPT {i}..."
            state["status_color"] = "black"
            state["bg_color"] = "#00FFFF" # Cyan
            
            # Warp Command
            pyautogui.click()
            time.sleep(0.2)
            pyautogui.press('t')
            time.sleep(0.2)
            type_human('/warp garden')
            time.sleep(0.2)
            pyautogui.press('enter')
            
            # Wait for Warp (Loading Screen)
            time.sleep(8)
            
            # 4. VERIFY ARRIVAL (NEW LOGIC)
            if '"mode":"garden"' in check_location():
                # We are definitely in the garden now.
                state["status_text"] = "LANDED! STOPPING FLIGHT..."
                state["status_color"] = "white"
                state["bg_color"] = "#0000AA" # Deep Blue
                
                # Wait for world to settle (2s)
                print("[BOT] Confirmed Garden. Waiting 2s before double-space...")
                time.sleep(2.0)

             # --- FASTER ANTI-FLY (Double Jump) ---
                print("[BOT] Executing Fast Double-Jump...")
                
                # Jump 1 (Quick Tap)
                pyautogui.keyDown('space')
                pyautogui.keyUp('space')
                
                # Gap (Faster but not instant)
                time.sleep(0.05) 
                
                # Jump 2 (Quick Tap)
                pyautogui.keyDown('space') 
                pyautogui.keyUp('space')
                # -------------------------------------------------

                # Resume Macro
                state["status_text"] = "SUCCESS! RESUMING..."
                state["status_color"] = "white"
                state["bg_color"] = "#008000" # Green
                time.sleep(1)
                pyautogui.press('f3')
                time.sleep(2)
                state["bg_color"] = "black"
                break
            
            # If check failed, loop will retry warp
            time.sleep(2)
            
    except Exception as e:
        print(f"Error: {e}")
    finally: 
        state["handling_incident"] = False

def monitor_logs():
    try:
        with open(state["final_log_path"], "r", encoding="utf-8", errors='ignore') as f:
            f.seek(0, 2)
            
            while state["running"]:
                if state["active"] or state["mode"] == "test":
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    
                    # Check for Locraw
                    if '{"server":' in line: 
                        state["locraw_response"] = line
                    
                    # Check for World Switch
                    triggers = ["Sending to server", "Evacuating to Hub", "A disconnect occurred"]
                    if not state["handling_incident"] and any(t in line for t in triggers):
                        if state["mode"] == "normal":
                            threading.Thread(target=handle_incident, daemon=True).start()
                else: 
                    time.sleep(0.5)
    except: 
        pass

def timer_loop():
    while state["running"]:
        if state["active"]:
            if state["kill_timer_start"] is None: 
                state["kill_timer_start"] = time.time()
            
            elapsed = time.time() - state["kill_timer_start"]
            if elapsed > ONE_HOUR_SECONDS: 
                trigger_kill_switch()
            
            left = int((ONE_HOUR_SECONDS - elapsed) / 60)
            if not state["kill_warning_active"] and not state["handling_incident"]:
                state["status_text"] = f"GUARD ON | {left}m LEFT"
                state["status_color"] = "#00FF00" # Neon Green
                state["bg_color"] = "black"
        else:
            state["status_text"] = "PAUSED (F7 to Start)"
            state["status_color"] = "#FFFF00" # Yellow
            state["bg_color"] = "#202020"     # Dark Grey
            state["kill_timer_start"] = None
        time.sleep(0.5)

def trigger_kill_switch():
    state["kill_warning_active"] = True
    state["status_text"] = "⚠️ 1 HOUR CHECK! CLICK SCREEN! ⚠️"
    state["status_color"] = "white"
    state["bg_color"] = "red"
    
    def alarm():
        for _ in range(WARNING_DURATION * 2):
            if not state["kill_warning_active"]: break
            winsound.Beep(1000, 200)
            time.sleep(0.3)
    threading.Thread(target=alarm, daemon=True).start()
    
    confirmed = False
    def on_click(x, y, button, pressed):
        nonlocal confirmed
        if pressed and button == mouse.Button.left:
            confirmed = True
            return False 
            
    with mouse.Listener(on_click=on_click) as listener:
        start = time.time()
        while time.time() - start < WARNING_DURATION:
            if confirmed: break
            time.sleep(0.1)
            
    state["kill_warning_active"] = False
    if confirmed:
        winsound.Beep(1500, 300)
        state["kill_timer_start"] = time.time()
    else:
        for proc in psutil.process_iter():
            if proc.name() == PROCESS_NAME: proc.kill()
        os._exit(0)

def on_press(key):
    # F4 = Emergency Quit + Kill AHK
    if key == keyboard.Key.f4: 
        state["running"] = False
        
        # Kill the AHK process if it exists
        if state["ahk_process"]:
            try:
                state["ahk_process"].terminate()
                print("[AHK] Process terminated via F4")
            except: pass
            
        os._exit(0)
    
    # F7 = Toggle Pause/Resume
    if key == keyboard.Key.f7: 
        state["active"] = not state["active"]
        winsound.Beep(800 if state["active"] else 400, 100)
        
        # KEY FEATURE: SYNC MACRO
        # If we just became active -> Press F3 to START macro
        # If we just paused -> Press F3 to STOP macro
        print(f"[SYNC] Toggling Macro via F3 (Active: {state['active']})")
        pyautogui.press('f3')

    # Test Mode Controls
    if state["mode"] == "test" and hasattr(key, 'char'):
        if key.char == 't': 
            threading.Thread(target=handle_incident, daemon=True).start()
        if key.char == 'l': 
            state["locraw_response"] = '{"server":"m","gametype":"SKYBLOCK","mode":"hub"}'

def start_main_bot():
    state["running"] = True
    launch_ahk()
    threading.Thread(target=monitor_logs, daemon=True).start()
    threading.Thread(target=timer_loop, daemon=True).start()
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    StatusOverlay(state["monitor"])

if __name__ == "__main__":
    LauncherApp()