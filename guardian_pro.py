import time
import os
import threading
import winsound
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import psutil
import mss
import json
import pyautogui
import subprocess
import sys
import re
import shutil
import random

# Windows API for window focus & title reading
try:
    import win32gui
except ImportError:
    messagebox.showerror("Critical Error", "Missing Dependency: pywin32\nPlease run: pip install pywin32")
    sys.exit(1)

from pynput import keyboard, mouse
from pynput.keyboard import Controller, Key

# --- CONFIGURATION ---
CONFIG_FILE = "guardian_config.json"
MOD_FILENAME = "guardian-tracker-1.0.0.jar"
PROCESS_NAME = "javaw.exe"
ONE_HOUR_SECONDS = 3600
WARNING_DURATION = 10
MAX_RETRIES = 10
MIN_ROW_DISTANCE = 380 

# --- GLOBAL STATE ---
state = {
    "mode": "normal",       
    "engine": "ahk",        
    "status_text": "SYSTEM READY",
    "status_color": "#FFFF00", 
    "bg_color": "#1e1e1e",      
    "monitor": None,
    "kill_timer_start": None,
    "kill_warning_active": False,
    "running": False,       
    "active": False,        
    "handling_incident": False,
    "locraw_response": None,
    "final_log_path": None,
    "ahk_process": None,
    "selected_macro": "yazan.ahk",
    "current_pos": {"x": 0, "y": 0, "z": 0},
    "emergency_stop": False,
    "attacking": False,
    "skip_dist_check": True,
    "chat_open": False,
    "keys_held": False
}

state_lock = threading.Lock()
keyboard_ctl = Controller()

# --- HELPER FUNCTIONS ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def type_human(text):
    for char in text:
        # Abort instantly if focus is lost mid-typing
        if not is_minecraft_focused():
            print("[BOT] Focus lost! Aborting text entry.")
            return False 
            
        pyautogui.write(char)
        time.sleep(random.uniform(0.05, 0.15))
    return True

def is_minecraft_focused():
    """Returns True ONLY if the active window is Minecraft"""
    if state["mode"] == "test": return True
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        return "Minecraft" in title or "Badlion" in title or "Lunar" in title
    except:
        return False

def show_error(title, message):
    """Thread-safe error box"""
    threading.Thread(target=lambda: messagebox.showerror(title, message)).start()

# --- AUTO-INSTALLER (SMART) ---
def install_mod_logic(log_path):
    """
    Returns TRUE if a new install occurred (requires restart).
    Returns FALSE if mod was already there or failed.
    """
    try:
        # Calculate paths
        mc_root = os.path.dirname(os.path.dirname(log_path)) # logs -> .minecraft
        mods_folder = os.path.join(mc_root, "mods")
        dest_file = os.path.join(mods_folder, MOD_FILENAME)
        source_file = resource_path(MOD_FILENAME)
        
        if not os.path.exists(source_file):
            if not os.path.exists(dest_file):
                messagebox.showwarning("Mod Missing", 
                    f"Setup Error: Could not find '{MOD_FILENAME}'.\n"
                    "Place the JAR file in the same folder as this bot.")
            return False

        if not os.path.exists(mods_folder):
            os.makedirs(mods_folder)

        # CHECK: Does it exist?
        if not os.path.exists(dest_file):
            shutil.copy2(source_file, dest_file)
            return True # WE INSTALLED IT
            
    except Exception as e:
        messagebox.showerror("Install Error", f"Failed to access mods folder:\n{str(e)}")
        
    return False # No new install happened

# --- COORDINATE READER ---
def get_live_coords():
    result = {"pos": None}
    def callback(hwnd, extra):
        title = win32gui.GetWindowText(hwnd)
        if "Guardian:" in title:
            match = re.search(r"Guardian: (-?\d+) / (-?\d+) / (-?\d+)", title)
            if match:
                extra["pos"] = {
                    "x": int(match.group(1)), 
                    "y": int(match.group(2)), 
                    "z": int(match.group(3))
                }
    try:
        win32gui.EnumWindows(callback, result)
    except Exception:
        return None
    return result["pos"]

# --- ATTACK LOOP ---
def attack_loop():
    while state["running"]:
        attack_key = state.get("attack_key", "j")
        humanize = state.get("enable_humanization", True)
        
        should_attack = (state["active"] and 
                         not state["handling_incident"] and 
                         not state["kill_warning_active"] and
                         not state["emergency_stop"] and
                         not state["chat_open"] and
                         is_minecraft_focused())
        
        if should_attack:
            if not state["attacking"]:
                keyboard_ctl.press(attack_key)
                state["attacking"] = True
            
            # HUMANIZATION: 1% chance to release the key for a split second
            if humanize and random.random() < 0.01:
                keyboard_ctl.release(attack_key)
                time.sleep(random.uniform(0.1, 0.3))
                keyboard_ctl.press(attack_key)
        else:
            if state["attacking"]:
                keyboard_ctl.release(attack_key)
                state["attacking"] = False
        
        # Static sleep if robotic, randomized if humanized
        sleep_time = random.uniform(0.08, 0.12) if humanize else 0.1
        time.sleep(sleep_time)

def run_smart_farm_logic():
    turn_key = 'w' if "yazan" in state.get("selected_macro", "yazan").lower() else 's'
    strafe_key = 'd'       
    mode = "strafing"      
    
    last_pos = None
    stuck_ticks = 0
    row_start_z = None
    
    print(f"[PYTHON] Engine Started. Turn Style: {turn_key.upper()}")

    while state["running"]:
        if state["emergency_stop"]:
            time.sleep(1)
            continue

        # Load dynamic settings from GUI
        stuck_limit = state.get("stuck_threshold", 3)
        min_dist = state.get("min_row_distance", 380)
        macrocheck_enabled = state.get("enable_distance_check", True)
        humanize = state.get("enable_humanization", True)

        is_paused = (not state["active"] or 
                     state["handling_incident"] or 
                     state["kill_warning_active"] or 
                     state["chat_open"] or 
                     not is_minecraft_focused())

        if is_paused:
            if state["keys_held"]:
                for k in ['w', 'a', 's', 'd']: keyboard_ctl.release(k)
                state["keys_held"] = False
            
            time.sleep(0.2)
            last_pos = None 
            row_start_z = None 
            stuck_ticks = 0
            continue
            
        pos = get_live_coords()
        if state["mode"] == "test" and not pos: pos = state["current_pos"] 
        
        if not pos:
            time.sleep(1)
            continue
            
        state["current_pos"] = pos 
        if row_start_z is None: row_start_z = pos['z']

        state["keys_held"] = True 

        # --- MODE-AWARE STUCK ACCUMULATOR ---
        if last_pos:
            if mode == "strafing":
                # During the long row, ONLY monitor Z and Y (Ignores X sliding)
                if pos['z'] == last_pos['z'] and pos['y'] == last_pos['y']:
                    stuck_ticks += 1
                else:
                    stuck_ticks = 0
            elif mode == "turning":
                # During the turn gap, ONLY monitor X and Y (Because Z shouldn't move anyway)
                if pos['x'] == last_pos['x'] and pos['y'] == last_pos['y']:
                    stuck_ticks += 1
                else:
                    stuck_ticks = 0
        last_pos = pos
        
        if state["mode"] == "test" and state.get("force_stuck", False):
            stuck_ticks = stuck_limit + 1
            state["force_stuck"] = False 

        # --- TRIGGER FLAGS ---
        is_stuck = (stuck_ticks >= stuck_limit)
        is_lagging_hard = (stuck_ticks >= 25) # ~5 seconds of complete freeze

        # --- LOGIC MACHINE ---
        if mode == "strafing":
            if is_stuck:
                dist_traveled = abs(pos['z'] - row_start_z)
                
                if dist_traveled >= min_dist or state["skip_dist_check"] or not macrocheck_enabled:
                    # NORMAL TURN: We hit the wall at the end of the row
                    keyboard_ctl.release(strafe_key) 
                    time.sleep(random.uniform(0.05, 0.15) if humanize else 0.1)
                    mode = "turning"
                    stuck_ticks = 0 
                else:
                    # EARLY STUCK (Lag Failsafe): Don't panic, keep holding the key
                    keyboard_ctl.press(strafe_key)
                    
                    if is_lagging_hard:
                        trigger_emergency_stop()
                        stuck_ticks = 0 
            else:
                keyboard_ctl.press(strafe_key)

        elif mode == "turning":
            if is_stuck:
                # TURN COMPLETE: We hit the wall inside the turn gap
                keyboard_ctl.release(turn_key)
                strafe_key = 'a' if strafe_key == 'd' else 'd'
                mode = "strafing"
                
                row_start_z = pos['z'] 
                state["skip_dist_check"] = False 
                stuck_ticks = 0 
                time.sleep(random.uniform(0.05, 0.15) if humanize else 0.1)
            else:
                keyboard_ctl.press(turn_key)

        time.sleep(random.uniform(0.18, 0.25) if humanize else 0.2)

def trigger_emergency_stop():
    state["emergency_stop"] = True
    state["active"] = False 
    state["status_text"] = "DISTANCE FAILURE"
    state["bg_color"] = "#FF0000"
    
    # Release Keys
    attack_k = state.get("attack_key", "j")
    for k in ['w', 'a', 's', 'd', attack_k]: keyboard_ctl.release(k)
    state["attacking"] = False
    
    # Start Alarm Sound Thread
    def alarm():
        while state["emergency_stop"]:
            winsound.Beep(2000, 500)
            time.sleep(0.5)
    threading.Thread(target=alarm, daemon=True).start()
    
    # Show Blocking Message Box in a Thread (so we can wait for close)
    def wait_for_user():
        messagebox.showerror("Safety Stop", "Row distance check failed.\nBot stopped for safety.\n\nClick OK to RESUME from current position.")
        # User Clicked OK - Resume Everything
        state["emergency_stop"] = False
        state["skip_dist_check"] = True 
        state["active"] = True
        winsound.Beep(1000, 200) # Confirmation Beep
        
    threading.Thread(target=wait_for_user).start()

# --- AHK LAUNCHER ---
def launch_ahk():
    script_name = state["selected_macro"]
    ahk_path = resource_path(script_name)
    ahk_exe = resource_path("AutoHotkey.exe") 
    if os.path.exists(ahk_path):
        try:
            if os.path.exists(ahk_exe):
                state["ahk_process"] = subprocess.Popen([ahk_exe, ahk_path])
            else:
                os.startfile(ahk_path)
        except Exception as e:
            show_error("AHK Error", str(e))

# --- PROTECTION LOGIC ---
def is_minecraft_running():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == PROCESS_NAME: return True
        except: pass
    return False

def check_location():
    state["locraw_response"] = None
    if state["mode"] == "test": return '{"server":"test","gametype":"SKYBLOCK","mode":"garden"}'

    # Cooldown check: prevent spamming /locraw too fast
    if time.time() - state.get("last_locraw_time", 0) < 10:
        print("[BOT] Locraw on cooldown. Waiting...")
        time.sleep(2)
        return "unknown"

    if not is_minecraft_focused():
        return "unknown"

    state["last_locraw_time"] = time.time()
    
    pyautogui.press('t')
    time.sleep(random.uniform(0.1, 0.3))
    
    # Only press enter if the typing finished successfully without losing focus
    typing_success = type_human('/locraw')
    time.sleep(random.uniform(0.1, 0.3))
    
    if typing_success and is_minecraft_focused():
        pyautogui.press('enter')
    
    start = time.time()
    while time.time() - start < 5:
        if state["locraw_response"]: return state["locraw_response"]
        time.sleep(0.2)
    return "unknown"

def handle_incident():
    with state_lock:
        if state["handling_incident"]: return
        state["handling_incident"] = True
    
    try:
        if state["engine"] == "ahk": pyautogui.press('f3')
        state["status_text"] = "INCIDENT DETECTED"
        state["bg_color"] = "#FF4500"
        time.sleep(4)
        
        loc = check_location()
        if '"mode":"garden"' in loc or '"map":"The Garden"' in loc:
            state["status_text"] = "FALSE ALARM"
            state["bg_color"] = "#008000"
            time.sleep(1)
            if state["engine"] == "ahk": pyautogui.press('f3')
            state["bg_color"] = "#1e1e1e"
            return
        
        for i in range(1, MAX_RETRIES+1):
            state["status_text"] = f"RECOVERY ATTEMPT {i}"
            state["bg_color"] = "#00FFFF"
            
            if state["mode"] != "test":
                # Wait for user to focus Minecraft before doing anything
                while not is_minecraft_focused():
                    state["status_text"] = "AWAITING FOCUS"
                    time.sleep(1)
                
                state["status_text"] = f"RECOVERY ATTEMPT {i}"
                pyautogui.click()
                time.sleep(random.uniform(0.1, 0.3))
                
                if is_minecraft_focused(): pyautogui.press('t')
                time.sleep(random.uniform(0.1, 0.3))
                
                # Only hit enter if it successfully typed the whole command
                if type_human('/warp garden'):
                    time.sleep(random.uniform(0.1, 0.3))
                    if is_minecraft_focused(): pyautogui.press('enter')
                
                time.sleep(8)
            else: time.sleep(2)
            
            if '"mode":"garden"' in check_location():
                state["status_text"] = "STABILIZING..."
                state["bg_color"] = "#0000AA"
                time.sleep(2.0)

                if state["mode"] != "test" and is_minecraft_focused():
                    pyautogui.keyDown('space'); pyautogui.keyUp('space')
                    time.sleep(0.05) 
                    pyautogui.keyDown('space'); pyautogui.keyUp('space')

                state["status_text"] = "RESUMING OPERATIONS"
                state["bg_color"] = "#008000"
                state["skip_dist_check"] = True 
                time.sleep(1)
                if state["engine"] == "ahk": pyautogui.press('f3')
                time.sleep(2)
                state["bg_color"] = "#1e1e1e"
                break
            time.sleep(2)
    except Exception as e:
        show_error("Recovery Error", str(e))
    finally: 
        with state_lock:
            state["handling_incident"] = False

def monitor_logs():
    if not state.get("final_log_path") or not os.path.exists(state["final_log_path"]): return
    try:
        with open(state["final_log_path"], "r", encoding="utf-8", errors='ignore') as f:
            f.seek(0, 2)
            while state["running"]:
                if state["active"] or state["mode"] == "test":
                    line = f.readline()
                    if not line:
                        time.sleep(0.1); continue
                    if '{"server":' in line: state["locraw_response"] = line
                    
                    incident_triggers = ["Sending to server", "Evacuating to Hub", "A disconnect occurred"]
                    death_triggers = ["fell into the void", "slain by", "burned to death", "You died!"]

                    with state_lock:
                        is_handling = state["handling_incident"]

                    if not is_handling:
                        # Only handle Hub kicks if enabled
                        if state.get("handle_hub", True) and any(t in line for t in incident_triggers):
                            if state["mode"] == "normal":
                                threading.Thread(target=handle_incident, daemon=True).start()
                        
                        # Only handle Deaths if enabled
                        elif state.get("handle_deaths", True) and any(t in line for t in death_triggers):
                             threading.Thread(target=handle_death, daemon=True).start()
                else: 
                    time.sleep(0.5)
    except Exception as e: 
        print(f"Log Monitor Error: {e}")

def handle_death():
    with state_lock:
        if state["handling_incident"]: return
        state["handling_incident"] = True
    
    try:
        print("[BOT] Death detected. Waiting for Garden Hub respawn...")
        state["status_text"] = "DEATH DETECTED - RESPAWNING"
        state["bg_color"] = "#FFA500" 
        
        # Wait for standard Skyblock respawn time
        time.sleep(4.0)
        
        # Only press Z if Minecraft is actually the active window
        if is_minecraft_focused() or state["mode"] == "test":
            state["status_text"] = "TELEPORTING TO START..."
            print("[BOT] Pressing 'Z' to teleport.")
            pyautogui.press('z')
            time.sleep(2.0) # Wait for teleport to finish loading
        else:
            print("[BOT] WARNING: Minecraft lost focus. Could not press 'Z'.")
            
        # INSTANT IMMUNITY: The next wall hit will NOT trigger an alarm
        state["skip_dist_check"] = True
        
        state["status_text"] = "RESUMING..."
        state["bg_color"] = "#008000"
        time.sleep(1)
        state["bg_color"] = "#1e1e1e"
        
    except Exception as e:
        print(f"Death Handle Error: {e}")
    finally:
        with state_lock:
            state["handling_incident"] = False

def timer_loop():
    while state["running"]:
        if state["active"] and not state["emergency_stop"]:
            if state["kill_timer_start"] is None: state["kill_timer_start"] = time.time()
            elapsed = time.time() - state["kill_timer_start"]
            kill_limit = state.get("kill_timer_seconds", 3600)
            if elapsed > kill_limit: 
                trigger_kill_switch()
            
            left = int((ONE_HOUR_SECONDS - elapsed) / 60)
            if not state["kill_warning_active"] and not state["handling_incident"]:
                if state["chat_open"]: 
                    txt = "USER CHATTING"
                    col = "orange"
                elif not is_minecraft_focused():
                    txt = "AWAITING FOCUS"
                    col = "orange"
                else:
                    txt = f"ACTIVE | {left}m REMAINING"
                    col = "#00FF00"
                
                state["status_text"] = txt
                state["status_color"] = col
                state["bg_color"] = "#1e1e1e"
        else:
            if state["emergency_stop"]:
                state["status_text"] = "SAFETY STOP"
            else:
                state["status_text"] = "STANDBY (F7)"
                state["status_color"] = "#FFFF00"
                state["bg_color"] = "#1e1e1e"
                state["kill_timer_start"] = None
        time.sleep(0.5)

def trigger_kill_switch():
    state["kill_warning_active"] = True
    state["status_text"] = "HOURLY CHECK - VERIFY"
    state["bg_color"] = "#FF0000"
    def alarm():
        for _ in range(WARNING_DURATION * 2):
            if not state["kill_warning_active"]: break
            winsound.Beep(1000, 200); time.sleep(0.3)
    threading.Thread(target=alarm, daemon=True).start()
    
    confirmed = False
    def on_click(x, y, button, pressed):
        nonlocal confirmed
        if pressed and button == mouse.Button.left:
            confirmed = True; return False 
    with mouse.Listener(on_click=on_click) as listener:
        start = time.time()
        while time.time() - start < WARNING_DURATION:
            if confirmed: break
            time.sleep(0.1)
    state["kill_warning_active"] = False
    if confirmed:
        winsound.Beep(1500, 300)
        state["kill_timer_start"] = time.time()
    else: full_shutdown()

def full_shutdown():
    state["running"] = False
    if state["ahk_process"]:
        try: state["ahk_process"].terminate()
        except: pass
    if state["engine"] == "python":
        try:
            attack_k = state.get("attack_key", "j")
            for k in ['w', 'a', 's', 'd', attack_k]: keyboard_ctl.release(k)
        except: pass
    os._exit(0)

# --- INPUT LISTENER ---
def on_press(key):
    if key == Key.f4: full_shutdown()
    if key == Key.f7: 
        if state["emergency_stop"]:
            # If user presses F7 during emergency, it also clears it
            state["emergency_stop"] = False
            state["skip_dist_check"] = True 
            state["active"] = False
            winsound.Beep(1000, 100)
        else:
            state["active"] = not state["active"]
            winsound.Beep(800 if state["active"] else 400, 100)
            if state["active"]: state["skip_dist_check"] = True
        
        if not state["active"] and state["engine"] == "python":
            attack_k = state.get("attack_key", "j")
            for k in ['w', 'a', 's', 'd', attack_k]: keyboard_ctl.release(k)
            state["attacking"] = False
        if state["engine"] == "ahk": pyautogui.press('f3')
    
    try:
        if hasattr(key, 'char') and key.char == '/':
            state["chat_open"] = True
        elif key == Key.enter or key == Key.esc:
            if state["chat_open"]:
                state["chat_open"] = False
                time.sleep(0.2)
    except AttributeError:
        pass

class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Guardian Pro")
        self.root.geometry("550x650") # Slightly taller to fit the new options
        self.root.configure(bg="#1e1e1e")
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure Notebook (Tabs) style for dark mode
        style.configure("TNotebook", background="#1e1e1e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#333", foreground="white", padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", "#006600")])
        style.configure("TFrame", background="#1e1e1e")

        tk.Label(self.root, text="GUARDIAN AUTOMATION", font=("Segoe UI", 16, "bold"), fg="#00ff00", bg="#1e1e1e").pack(pady=15)
        
        # --- NOTEBOOK SETUP ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=15, pady=(0, 15))

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_failsafes = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_main, text="Main Controls")
        self.notebook.add(self.tab_settings, text="Delays & Timers")
        self.notebook.add(self.tab_failsafes, text="Failsafes")

        # ==========================================
        # TAB 1: MAIN CONTROLS
        # ==========================================
        # Log Path
        tk.Label(self.tab_main, text="Minecraft Log Directory", fg="#cccccc", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(pady=(15,5))
        self.path_var = tk.StringVar()
        log_frame = tk.Frame(self.tab_main, bg="#1e1e1e")
        log_frame.pack(fill="x", padx=30)
        tk.Entry(log_frame, textvariable=self.path_var, width=50, bg="#333", fg="white", insertbackground="white").pack(side="left", padx=(50,10))
        tk.Button(log_frame, text="Browse", command=self.browse_file, bg="#444", fg="white", relief="flat").pack(side="left")
        
        # Monitor
        tk.Label(self.tab_main, text="Display Output", fg="#cccccc", bg="#1e1e1e", font=("Segoe UI", 10, "bold")).pack(pady=(20,5))
        self.monitor_combo = ttk.Combobox(self.tab_main, state="readonly", width=45)
        self.monitors = self.get_monitors()
        self.monitor_combo['values'] = [m['label'] for m in self.monitors]
        if self.monitors: 
            self.monitor_combo.current(0)
        self.monitor_combo.pack()

        # Settings Frame (Inside Main Tab)
        settings_frame = tk.Frame(self.tab_main, bg="#1e1e1e")
        settings_frame.pack(pady=20)

        tk.Label(settings_frame, text="Engine:", fg="#cccccc", bg="#1e1e1e").grid(row=0, column=0, padx=10, sticky="w")
        self.engine_var = tk.StringVar(value="python")
        tk.Radiobutton(settings_frame, text="AHK (Legacy)", variable=self.engine_var, value="ahk", bg="#1e1e1e", fg="#00ffff", selectcolor="#333").grid(row=0, column=1, sticky="w")
        tk.Radiobutton(settings_frame, text="Python (Smart)", variable=self.engine_var, value="python", bg="#1e1e1e", fg="#FFAA00", selectcolor="#333").grid(row=0, column=2, sticky="w")

        tk.Label(settings_frame, text="Turn Logic:", fg="#cccccc", bg="#1e1e1e").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.macro_var = tk.StringVar(value="yazan.ahk")
        tk.Radiobutton(settings_frame, text="Yazan Style (Forward / W)", variable=self.macro_var, value="yazan.ahk", bg="#1e1e1e", fg="white", selectcolor="#333").grid(row=1, column=1, columnspan=2, sticky="w")
        tk.Radiobutton(settings_frame, text="Cizare Style (Backward / S)", variable=self.macro_var, value="cizare.ahk", bg="#1e1e1e", fg="white", selectcolor="#333").grid(row=2, column=1, columnspan=2, sticky="w")

        tk.Label(settings_frame, text="Mode:", fg="#cccccc", bg="#1e1e1e").grid(row=3, column=0, padx=10, pady=(10,0), sticky="w")
        self.mode_var = tk.StringVar(value="normal")
        tk.Radiobutton(settings_frame, text="Standard Play", variable=self.mode_var, value="normal", bg="#1e1e1e", fg="#00ff00", selectcolor="#333").grid(row=3, column=1, pady=(10,0), sticky="w")
        tk.Radiobutton(settings_frame, text="Test Mode", variable=self.mode_var, value="test", bg="#1e1e1e", fg="yellow", selectcolor="#333").grid(row=3, column=2, pady=(10,0), sticky="w")

        # Attack Keybind
        tk.Label(settings_frame, text="Attack Bind:", fg="#cccccc", bg="#1e1e1e").grid(row=4, column=0, padx=10, pady=(15,0), sticky="w")
        self.attack_key_var = tk.StringVar(value="j")
        tk.Entry(settings_frame, textvariable=self.attack_key_var, width=5, bg="#333", fg="white", justify="center", insertbackground="white").grid(row=4, column=1, pady=(15,0), sticky="w")

        # ==========================================
        # TAB 2: DELAYS & TIMERS
        # ==========================================
        self.stuck_threshold_var = tk.IntVar(value=3)
        tk.Label(self.tab_settings, text="Stuck Tick Threshold (Ticks stuck before turning):", bg="#1e1e1e", fg="#cccccc").pack(anchor="w", padx=20, pady=(20, 5))
        tk.Scale(self.tab_settings, from_=1, to=10, orient="horizontal", variable=self.stuck_threshold_var, bg="#1e1e1e", fg="white", highlightthickness=0).pack(fill="x", padx=20)

        self.kill_timer_var = tk.IntVar(value=60)
        tk.Label(self.tab_settings, text="Kill-Switch Timer (Minutes before pause alarm):", bg="#1e1e1e", fg="#cccccc").pack(anchor="w", padx=20, pady=(15, 5))
        tk.Scale(self.tab_settings, from_=10, to=120, resolution=5, orient="horizontal", variable=self.kill_timer_var, bg="#1e1e1e", fg="white", highlightthickness=0).pack(fill="x", padx=20)

        self.min_dist_var = tk.IntVar(value=380)
        tk.Label(self.tab_settings, text="Minimum Row Distance (Blocks expected per row):", bg="#1e1e1e", fg="#cccccc").pack(anchor="w", padx=20, pady=(15, 5))
        tk.Scale(self.tab_settings, from_=50, to=500, resolution=10, orient="horizontal", variable=self.min_dist_var, bg="#1e1e1e", fg="white", highlightthickness=0).pack(fill="x", padx=20)

        # ==========================================
        # TAB 3: FAILSAFES
        # ==========================================
        tk.Label(self.tab_failsafes, text="Active Protections", font=("Segoe UI", 12, "bold"), bg="#1e1e1e", fg="white").pack(anchor="w", padx=20, pady=(20, 10))

        self.enable_hub_handling = tk.BooleanVar(value=True)
        tk.Checkbutton(self.tab_failsafes, text="Enable Hub Disconnect Recovery (/warp garden)", variable=self.enable_hub_handling, bg="#1e1e1e", fg="#00FFFF", selectcolor="#333", activebackground="#1e1e1e", activeforeground="white").pack(anchor="w", padx=20, pady=5)

        self.enable_death_handling = tk.BooleanVar(value=True)
        tk.Checkbutton(self.tab_failsafes, text="Enable Death Recovery (Teleport using 'Z' key)", variable=self.enable_death_handling, bg="#1e1e1e", fg="#FFA500", selectcolor="#333", activebackground="#1e1e1e", activeforeground="white").pack(anchor="w", padx=20, pady=5)

        self.enable_distance_check = tk.BooleanVar(value=True)
        tk.Checkbutton(self.tab_failsafes, text="Enable Macrocheck (Distance Stop Alarm)", variable=self.enable_distance_check, bg="#1e1e1e", fg="#FF0000", selectcolor="#333", activebackground="#1e1e1e", activeforeground="white").pack(anchor="w", padx=20, pady=5)

        self.enable_humanization = tk.BooleanVar(value=True)
        tk.Checkbutton(self.tab_failsafes, text="Enable Input Humanization (Randomized delays)", variable=self.enable_humanization, bg="#1e1e1e", fg="#00FF00", selectcolor="#333", activebackground="#1e1e1e", activeforeground="white").pack(anchor="w", padx=20, pady=5)

        # ==========================================
        # PERSISTENT BOTTOM BUTTON
        # ==========================================
        tk.Button(self.root, text="INITIALIZE SYSTEM", bg="#006600", fg="white", font=("Segoe UI", 12, "bold"), relief="flat", command=self.start_bot).pack(fill="x", padx=50, pady=(0, 20), ipady=5)

        self.load_config()
        self.root.mainloop()

    def get_monitors(self):
        try:
            with mss.mss() as sct:
                mons = []
                for i, m in enumerate(sct.monitors):
                    if i == 0: continue
                    m['label'] = f"Display {i}: {m['width']}x{m['height']}"
                    m['index'] = i
                    mons.append(m)
                return mons
        except Exception as e:
            messagebox.showerror("Error", f"Failed to detect monitors: {e}")
            return []

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("Log", "*.log")])
        if f: 
            self.path_var.set(f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.macro_var.set(data.get("selected_macro", "yazan.ahk"))
                    self.mode_var.set(data.get("mode", "normal"))
                    self.path_var.set(data.get("log_path", ""))
                    self.engine_var.set(data.get("engine", "python"))
                    self.attack_key_var.set(data.get("attack_key", "j"))
                    
                    self.stuck_threshold_var.set(data.get("stuck_threshold", 3))
                    self.kill_timer_var.set(data.get("kill_timer_mins", 60))
                    self.min_dist_var.set(data.get("min_row_distance", 380))
                    
                    self.enable_hub_handling.set(data.get("enable_hub_handling", True))
                    self.enable_death_handling.set(data.get("enable_death_handling", True))
                    self.enable_distance_check.set(data.get("enable_distance_check", True))
                    self.enable_humanization.set(data.get("enable_humanization", True))

                    saved_idx = data.get("monitor_index", 0)
                    if 0 <= saved_idx < len(self.monitors):
                        self.monitor_combo.current(saved_idx)
            except Exception as e: 
                print(f"Warning: Failed to load config cleanly: {e}")

    def start_bot(self):
        raw = self.path_var.get().strip().strip('"')
        if os.path.isdir(raw):
            c = os.path.join(raw, "logs", "latest.log")
            if os.path.exists(c): 
                raw = c
            else: 
                raw = os.path.join(raw, "latest.log")
        
        if not os.path.exists(raw): 
            messagebox.showerror("Configuration Error", "Invalid Log Path provided.")
            return
        
        # 1. SMART MOD INSTALL
        if self.engine_var.get() == "python":
            just_installed = install_mod_logic(raw)
            if just_installed:
                messagebox.showinfo("Setup Required", 
                                    "Guardian Mod installed successfully!\n\n"
                                    "Please RESTART Minecraft to load the mod,\n"
                                    "then click Initialize System again.")
                return 

        # 2. CHECK PROCESS
        if not is_minecraft_running() and self.mode_var.get() == "normal":
            messagebox.showerror("Process Error", "Minecraft (javaw.exe) is not running.\nPlease start the game.")
            return

        # Save Config
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "log_path": raw, 
                "engine": self.engine_var.get(), 
                "selected_macro": self.macro_var.get(),
                "mode": self.mode_var.get(),
                "attack_key": self.attack_key_var.get(),
                "monitor_index": self.monitor_combo.current(),
                "stuck_threshold": self.stuck_threshold_var.get(),
                "kill_timer_mins": self.kill_timer_var.get(),
                "min_row_distance": self.min_dist_var.get(),
                "enable_hub_handling": self.enable_hub_handling.get(),
                "enable_death_handling": self.enable_death_handling.get(),
                "enable_distance_check": self.enable_distance_check.get(),
                "enable_humanization": self.enable_humanization.get()
            }, f, indent=4)
            
        # Update Global State
        state.update({
            "final_log_path": raw, 
            "engine": self.engine_var.get(), 
            "selected_macro": self.macro_var.get(), 
            "mode": self.mode_var.get(), 
            "monitor": self.monitors[self.monitor_combo.current()],
            
            # --- NEW VARIABLES ---
            "attack_key": self.attack_key_var.get(),
            "stuck_threshold": self.stuck_threshold_var.get(),
            "kill_timer_seconds": self.kill_timer_var.get() * 60,
            "min_row_distance": self.min_dist_var.get(),
            "handle_hub": self.enable_hub_handling.get(),
            "handle_deaths": self.enable_death_handling.get(),
            "enable_distance_check": self.enable_distance_check.get(),
            "enable_humanization": self.enable_humanization.get()
        })
        
        self.root.destroy()
        start_main_bot()

# --- TEST DASHBOARD ---
class TestDashboard:
    def __init__(self):
        self.root = tk.Tk(); self.root.title("SIMULATION CONTROL"); self.root.geometry("300x400"); self.root.attributes("-topmost", True)
        
        tk.Label(self.root, text="SYSTEM SIMULATION", font=("bold", 10)).pack(pady=10)
        
        tk.Button(self.root, text="Trigger Incident (Log Event)", bg="orange", 
                  command=lambda: threading.Thread(target=handle_incident, daemon=True).start()).pack(fill=tk.X, pady=2, padx=10)
        
        tk.Button(self.root, text="Trigger Hourly Verification", bg="red", fg="white", 
                  command=trigger_kill_switch).pack(fill=tk.X, pady=2, padx=10)
        
        tk.Label(self.root, text="Simulate Z-Axis:", pady=10).pack()
        self.z_scale = tk.Scale(self.root, from_=0, to=500, orient=tk.HORIZONTAL, command=self.update_z)
        self.z_scale.pack(fill=tk.X, padx=10)
        
        tk.Button(self.root, text="SIMULATE COLLISION (Stop)", bg="yellow", 
                  command=self.simulate_wall).pack(fill=tk.X, pady=5, padx=10)
                  
        tk.Label(self.root, text="State Flags:", pady=10).pack()
        self.chat_btn = tk.Button(self.root, text="Toggle Chat Open", command=self.toggle_chat)
        self.chat_btn.pack(fill=tk.X, padx=10)
        
        tk.Button(self.root, text="TERMINATE", bg="black", fg="white", 
                  command=full_shutdown).pack(fill=tk.X, pady=20, padx=10)

    def update_z(self, val): state["current_pos"]["z"] = int(val)
    def simulate_wall(self): state["force_stuck"] = True
    def toggle_chat(self): 
        state["chat_open"] = not state["chat_open"]
        self.chat_btn.config(bg="green" if state["chat_open"] else "SystemButtonFace")

# --- STATUS OVERLAY ---
class StatusOverlay:
    def __init__(self, monitor):
        self.root = tk.Tk(); self.root.overrideredirect(True); self.root.attributes("-topmost", True); self.root.attributes("-alpha", 0.9)
        self.root.configure(bg=state["bg_color"])
        x = monitor["left"] + monitor["width"] - 420; y = monitor["top"] + 50
        self.root.geometry(f"400x100+{x}+{y}")
        
        self.lbl_status = tk.Label(self.root, text="INIT", font=("Consolas", 14, "bold"), fg=state["status_color"], bg=state["bg_color"])
        self.lbl_status.pack(pady=5)
        
        self.lbl_info = tk.Label(self.root, text="...", font=("Consolas", 10), fg="white", bg=state["bg_color"])
        self.lbl_info.pack()
        
        self.update_gui()
        self.root.mainloop()

    def update_gui(self):
        if not state["running"]: self.root.destroy(); return
        
        self.lbl_status.config(text=state["status_text"], fg=state["status_color"], bg=state["bg_color"])
        self.root.configure(bg=state["bg_color"])
        
        p = state["current_pos"]
        if state["engine"] == "python": 
            self.lbl_info.config(text=f"POS: {p['x']}, {p['y']}, {p['z']}")
        else: 
            self.lbl_info.config(text=f"MACRO: {state['selected_macro']}")
            
        self.root.after(200, self.update_gui)

# --- ENTRY POINT ---
def start_main_bot():
    state["running"] = True
    
    if state["engine"] == "python":
        threading.Thread(target=run_smart_farm_logic, daemon=True).start()
        threading.Thread(target=attack_loop, daemon=True).start() 
    else: 
        launch_ahk()

    threading.Thread(target=timer_loop, daemon=True).start()
    threading.Thread(target=monitor_logs, daemon=True).start()
    
    keyboard.Listener(on_press=on_press).start()
    
    if state["mode"] == "test": 
        threading.Thread(target=lambda: TestDashboard().root.mainloop(), daemon=True).start()
    
    StatusOverlay(state["monitor"])

if __name__ == "__main__": 
    LauncherApp()