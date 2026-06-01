import pyautogui
import pyperclip
import requests
import base64
import io
import time
import threading
import hashlib
import json
import os
import tkinter as tk
from tkinter import ttk
from PIL import Image

HISTORY_FILE = "history.json"


# ── History helpers ───────────────────────────────────────────────────────────
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_history_entry(entry):
    history = load_history()
    history.insert(0, entry)          
    history = history[:200]           
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def img_to_b64(image):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


# ── Config ───────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = ""
MODEL = ""

# ── Supabase Auth Config ──────────────────────────────────────────────────────
SUPABASE_URL = ""   
SUPABASE_KEY = ""                    


def check_credentials(username, password):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/users",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            },
            params={
                "username": f"eq.{username}",
                "password_hash": f"eq.{pw_hash}"
            },
            timeout=5
        )
        return r.status_code == 200 and len(r.json()) > 0
    except Exception as e:
        return False


# ── State ────────────────────────────────────────────────────────────────────
region = None
running = False


import math as _math

# ── AI ───────────────────────────────────────────────────────────────────────
def ask_ai(image, model, max_tokens=500):
    if not OPENROUTER_API_KEY:
        raise Exception("API Key is missing! Add it via the Settings tab.")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    # ── Call 1: Solve the problem, show full reasoning ────────────────────────
    r1 = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert math solver. Solve the problem in the image step by step.\n"
                        "Show all your work clearly. Label every variable. Do not skip steps.\n"
                        "IMPORTANT: Always write your final answer on its own line at the end, clearly labeled 'Final answer: <value>'. Do this even if your reasoning is incomplete or cut short — the final answer line is the highest priority.\n"
                        "Use full precision in all intermediate calculations — never round until the final step.\n\n"
                        "SELF-CHECK — before writing your final answer:\n"
                        "- Recompute the answer a second time from scratch using a different approach or order\n"
                        "- If both computations agree, output that value\n"
                        "- If they disagree, find the error and correct it\n\n"
                        "SEQUENCES — critical rules:\n"
                        "- nth term of geometric sequence: a_n = a_1 * r^(n-1). For the 7th term, exponent is 6, NOT 7\n"
                        "- Verify r by checking a_2/a_1 AND a_3/a_2 — if they differ it is arithmetic, not geometric\n"
                        "- nth term of arithmetic sequence: a_n = a_1 + (n-1)*d\n\n"
                        "LAW OF SINES — always use: unknown = known_side * sin(opposite_angle_of_unknown) / sin(opposite_angle_of_known)\n"
                        "The denominator is ALWAYS the angle directly opposite the known side.\n\n"
                        "Read the problem carefully for precision instructions:\n"
                        "- 'nearest inch/cm/integer' → round to whole number\n"
                        "- 'nearest 10th' → 1 decimal place\n"
                        "- 'nearest 100th' / 'nearest thousandth' → 3 decimal places\n"
                        "- 'in terms of pi' → express symbolically with pi (e.g. pi/6)\n"
                        "- 'simplest radical form' / 'exact form' → leave as symbolic expression (e.g. 3sqrt(3))\n"
                        "- 'rectangular form' with two components → give both x and y values"
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        {"type": "text", "text": "Solve this problem step by step."}
                    ]
                }
            ]
        }
    )

    if 'choices' not in r1.json():
        raise Exception(f"API error (call 1): {r1.json().get('error', {}).get('message', str(r1.json()))}")

    reasoning = r1.json()['choices'][0]['message']['content'].strip()

    
    import re as _re
    precision_str = ""
    rl = reasoning.lower()
    if "nearest thousandth" in rl:
        precision_str = "Round to exactly 3 decimal places."
    elif "nearest hundredth" in rl or "nearest 100th" in rl:
        precision_str = "Round to exactly 2 decimal places."
    elif "nearest tenth" in rl or "nearest 10th" in rl:
        precision_str = "Round to exactly 1 decimal place."
    elif any(w in rl for w in ["nearest inch", "nearest cm", "nearest integer", "nearest whole", "nearest foot"]):
        precision_str = "Round to a whole number, no decimal point."

    # ── Call 2: Extract just the final answer in DeltaMath format ─────────────
    r2 = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json={
            "model": model,
            "max_tokens": 50,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract the final answer from a math solution and format it for DeltaMath input.\n"
                        "Output ONLY the raw answer string — nothing else. No explanation, no punctuation, no units.\n\n"
                        "FORMAT RULES:\n"
                        "- Fractions: use /  →  3/4\n"
                        "- Exponents: use ^  →  x^2\n"
                        "- Pi: write pi  →  pi/6  or  2pi\n"
                        "- Square roots: write sqrt(...)  →  sqrt(2)/2  or  3sqrt(3)\n"
                        "- Two-component answers (rectangular form): separate with comma  →  3sqrt(3), 0\n"
                        "- Multiple solutions: separate with comma  →  3,-3\n"
                        "- Decimal answers: use EXACTLY the number of decimal places specified below\n"
                        f"- {precision_str if precision_str else 'Use however many decimal places the problem requires.'}\n"
                        "- No LaTeX, no markdown, no words, no units"
                    )
                },
                {
                    "role": "user",
                    "content": f"Extract and format the final answer from this solution. Look for a line starting with 'Final answer:' first, otherwise use the last computed value:\n\n{reasoning}"
                }
            ]
        }
    )

    if 'choices' not in r2.json():
        raise Exception(f"API error (call 2): {r2.json().get('error', {}).get('message', str(r2.json()))}")

    answer = r2.json()['choices'][0]['message']['content'].strip()

    
    answer = answer.strip('$`"\' ')

   
    if any(c in answer for c in ['*', '^', '(']) and not any(w in answer for w in ['pi', 'sqrt', ',']):
        try:
            # Convert ^ to ** for Python, then eval safely
            expr = answer.replace('^', '**')
            value = eval(expr, {"__builtins__": {}, "_math": _math})
            # Apply detected precision
            if precision_str.startswith("Round to exactly 3"):
                answer = f"{value:.3f}"
            elif precision_str.startswith("Round to exactly 2"):
                answer = f"{value:.2f}"
            elif precision_str.startswith("Round to exactly 1"):
                answer = f"{value:.1f}"
            elif precision_str.startswith("Round to a whole"):
                answer = str(round(value))
            else:
               
                answer = f"{value:.10f}".rstrip('0').rstrip('.')
        except Exception:
            pass  

    return answer, reasoning


def click_nextButton(image, confidence_level=0.5):
    print("Scanning screen for Next button...")
    try:
        button_loc = pyautogui.locateCenterOnScreen(image, confidence=confidence_level)
        if button_loc is not None:
            pyautogui.click(button_loc)
            return True
    except Exception:
        pass
    return False


def click_textBox(image, confidence_level=0.5):
    print("Scanning screen for Submit button offset...")
    try:
        button_loc = pyautogui.locateCenterOnScreen(image, confidence=confidence_level)
        if button_loc is not None:
            x, y = button_loc
            target_x = x - 300
            print(f"[DEBUG] Found submit ref at ({x}, {y}), clicking ({target_x}, {y})")
            pyautogui.click(target_x, y)
            return True
        else:
            print("[DEBUG] locateCenterOnScreen returned None — image not found")
            return False
    except pyautogui.ImageNotFoundException:
        print("[DEBUG] ImageNotFoundException — image not found on screen.")
        return False
    except Exception as e:
        print(f"[DEBUG] click_textBox unexpected error: {e}")
        return False


def screenshot_question():
    if region is None:
        raise Exception("Region coordinates are empty.")
    return pyautogui.screenshot(region=region)


def submit_answer(answer, text_box_images=('SubmitAnswer.png', 'SubmitAnswer2.png')):

    if isinstance(text_box_images, str):
        text_box_images = (text_box_images,)
    for img in text_box_images:
        if click_textBox(img):
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            pyperclip.copy(answer)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
            pyautogui.press('enter')
            time.sleep(0.4)
            pyautogui.press('enter')
            return True
    return False


# ── GUI ───────────────────────────────────────────────────────────────────────
BG       = "#111111"
BG2      = "#1a1a1a"
BG3      = "#222222"
BORDER   = "#2a2a2a"
GOLD     = "#e8b84b"
GREEN    = "#4caf82"
RED      = "#c0392b"
TEXT     = "#e0e0e0"
MUTED    = "#666666"
FONT     = ("Consolas", 10)
FONT_SM  = ("Consolas", 9)
FONT_LG  = ("Consolas", 12, "bold")

THEMES = {
    "dark": {
        "BG": "#111111", "BG2": "#1a1a1a", "BG3": "#222222",
        "BORDER": "#2a2a2a", "TEXT": "#e0e0e0", "MUTED": "#666666",
        "TITLEBAR": "#0d0d0d", "icon": "☀"
    },
    "light": {
        "BG": "#f0f0f0", "BG2": "#ffffff", "BG3": "#e4e4e4",
        "BORDER": "#cccccc", "TEXT": "#111111", "MUTED": "#888888",
        "TITLEBAR": "#dcdcdc", "icon": "🌙"
    }
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DeltaMath Macro")
        self.geometry("520x800")
        self.resizable(True, True)
        self.configure(bg=BG)

        self._build_titlebar()
        self._build_tabs()
        self._build_run_panel()
        self._build_settings_panel()
        self._build_hotkeys_panel()
        self._build_log_panel()
        self._build_history_panel()

        self.show_tab("run")

        if KEYBOARD_AVAILABLE:
            keyboard.add_hotkey('q', self.stop_macro)
            keyboard.add_hotkey('s', self.start_macro)

    def _build_titlebar(self):
        bar = tk.Frame(self, bg="#0d0d0d", height=48)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg="#0d0d0d")
        left.pack(side="left", padx=12, pady=8)

        logo = tk.Label(left, text="D", bg=GOLD, fg="#111", font=("Consolas", 11, "bold"), width=2)
        logo.pack(side="left")

        info = tk.Frame(left, bg="#0d0d0d")
        info.pack(side="left", padx=8)
        tk.Label(info, text="Deltamath Automation", bg="#0d0d0d", fg=TEXT, font=("Lucida Console", 10, "bold")).pack(anchor="w")
        tk.Label(info, text="Jimmy Li & Big chud liam", bg="#0d0d0d", fg=MUTED, font=FONT_SM).pack(anchor="w")

        self.ontop_var = tk.BooleanVar(value=True)
        ontop_btn = tk.Button(bar, text="⊞ On Top: ON", bg="#0d0d0d", fg=GOLD,
                              font=FONT_SM, bd=0, relief="flat", cursor="hand2",
                              command=self.toggle_ontop)
        ontop_btn.pack(side="right", padx=12)
        self.ontop_btn = ontop_btn

        self.theme_name = "dark"
        self.theme_btn = tk.Button(bar, text="☀", bg="#0d0d0d", fg=MUTED,
                                   font=("Consolas", 12), bd=0, relief="flat",
                                   cursor="hand2", command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=4)

        self.wm_attributes("-topmost", True)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

    def toggle_ontop(self):
        val = not self.ontop_var.get()
        self.ontop_var.set(val)
        self.wm_attributes("-topmost", val)
        self.ontop_btn.config(text=f"⊞ On Top: {'ON' if val else 'OFF'}",
                              fg=GOLD if val else MUTED)

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.apply_theme()

    def apply_theme(self):
        global BG, BG2, BG3, BORDER, TEXT, MUTED
        t = THEMES[self.theme_name]
        BG, BG2, BG3 = t["BG"], t["BG2"], t["BG3"]
        BORDER, TEXT, MUTED = t["BORDER"], t["TEXT"], t["MUTED"]
        tb = t["TITLEBAR"]

        self.theme_btn.config(text=t["icon"])
        self.configure(bg=BG)

        def recolor(widget):
            cls = widget.winfo_class()
            try:
                if cls in ("Frame",):
                    bg = widget.cget("bg")
                    if bg in ("#111111", "#1a1a1a", "#222222", "#f0f0f0", "#ffffff", "#e4e4e4"):
                        if bg in ("#111111", "#f0f0f0"):
                            widget.config(bg=BG)
                        elif bg in ("#1a1a1a", "#ffffff"):
                            widget.config(bg=BG2)
                        elif bg in ("#222222", "#e4e4e4"):
                            widget.config(bg=BG3)
                    elif bg in ("#0d0d0d", "#dcdcdc"):
                        widget.config(bg=tb)
                elif cls in ("Label",):
                    bg = widget.cget("bg")
                    fg = widget.cget("fg")
                    new_bg = BG
                    if bg in ("#1a1a1a", "#ffffff"): new_bg = BG2
                    elif bg in ("#222222", "#e4e4e4"): new_bg = BG3
                    elif bg in ("#0d0d0d", "#dcdcdc"): new_bg = tb
                    elif bg in ("#111111", "#f0f0f0"): new_bg = BG
                    new_fg = fg
                    if fg in ("#e0e0e0", "#111111"): new_fg = TEXT
                    elif fg in ("#666666", "#888888"): new_fg = MUTED
                    widget.config(bg=new_bg, fg=new_fg)
                elif cls in ("Button",):
                    bg = widget.cget("bg")
                    new_bg = bg
                    if bg in ("#1a1a1a", "#ffffff"): new_bg = BG2
                    elif bg in ("#222222", "#e4e4e4"): new_bg = BG3
                    elif bg in ("#0d0d0d", "#dcdcdc"): new_bg = tb
                    elif bg in ("#111111", "#f0f0f0"): new_bg = BG
                    widget.config(bg=new_bg)
                elif cls in ("Entry", "Text"):
                    widget.config(bg=BG3, fg=TEXT, insertbackground=TEXT)
                elif cls == "Scale":
                    widget.config(bg=BG2, fg=TEXT, troughcolor=BG3)
            except Exception:
                pass
            for child in widget.winfo_children():
                recolor(child)

        recolor(self)

        
        self.log_text.tag_config("gold", foreground=GOLD)
        self.log_text.tag_config("green", foreground=GREEN)
        self.log_text.tag_config("red", foreground=RED)
        self.log_text.tag_config("muted", foreground=MUTED)
        self.log_text.config(bg=BG3, fg=MUTED)

        # Restyle combobox
        style = ttk.Style()
        style.configure("TCombobox", fieldbackground=BG3, background=BG3,
                        foreground=TEXT, bordercolor=BORDER, arrowcolor=GOLD)

    def _build_tabs(self):
        self.tab_frame = tk.Frame(self, bg="#0d0d0d")
        self.tab_frame.pack(fill="x")

        self.tab_btns = {}
        tabs = [("▶  Run", "run"), ("⚙  Settings", "settings"),
                ("⌨  Hotkeys", "hotkeys"), ("≡  Log", "log"), ("📋  History", "history")]
        for label, name in tabs:
            btn = tk.Button(self.tab_frame, text=label, bg="#0d0d0d", fg=MUTED,
                            font=FONT_SM, bd=0, relief="flat", padx=8, pady=8,
                            cursor="hand2", command=lambda n=name: self.show_tab(n))
            btn.pack(side="left", expand=True, fill="x")
            self.tab_btns[name] = btn

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")
        self.panels = {}

    def show_tab(self, name):
        for n, btn in self.tab_btns.items():
            btn.config(fg=GOLD if n == name else MUTED, bg=BG2 if n == name else "#0d0d0d")
        for n, panel in self.panels.items():
            panel.pack_forget()
        if name in self.panels:
            self.panels[name].pack(fill="both", expand=True)

    def _build_run_panel(self):
        p = tk.Frame(self, bg=BG2)
        self.panels["run"] = p

        self._section_label(p, "QUESTION REGION")
        rrow = tk.Frame(p, bg=BG3, bd=0, highlightthickness=1, highlightbackground=BORDER)
        rrow.pack(fill="x", padx=14, pady=(0, 12))
        self.region_label = tk.Label(rrow, text="Not set", bg=BG3, fg=MUTED, font=FONT, anchor="w")
        self.region_label.pack(side="left", padx=10, pady=8)
        tk.Button(rrow, text="Select", bg=BG3, fg=GOLD, font=FONT_SM, bd=0,
                  relief="flat", cursor="hand2", command=self.select_region).pack(side="right", padx=8)

        srow = tk.Frame(p, bg=BG2)
        srow.pack(fill="x", padx=14, pady=(4, 10))
        self.status_dot = tk.Label(srow, text="●", bg=BG2, fg=MUTED, font=("Consolas", 10))
        self.status_dot.pack(side="left")
        self.status_label = tk.Label(srow, text="Not started", bg=BG2, fg=MUTED, font=FONT_SM)
        self.status_label.pack(side="left", padx=6)

        self.start_btn = tk.Button(p, text="▶  Start", bg=GREEN, fg="white",
                                   font=("Consolas", 11, "bold"), bd=0, relief="flat",
                                   cursor="hand2", pady=10, command=self.toggle_run)
        self.start_btn.pack(fill="x", padx=14, pady=(0, 14))

    def _build_settings_panel(self):
        p = tk.Frame(self, bg=BG2)
        self.panels["settings"] = p

        self._section_label(p, "MODEL")
        self.model_var = tk.StringVar(value=MODEL)
        models = [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-flash-lite",
            "google/gemini-2.0-flash-001",
            "google/gemini-2.0-flash-lite-001",
            "meta-llama/llama-3.2-11b-vision-instruct",
        ]
        model_menu = ttk.Combobox(p, textvariable=self.model_var, values=models,
                                  font=FONT, state="readonly")
        model_menu.pack(fill="x", padx=14, pady=(0, 14))
        self._style_combobox()

        self._section_label(p, "DELAY BETWEEN QUESTIONS (SECONDS)")
        delay_row = tk.Frame(p, bg=BG2)
        delay_row.pack(fill="x", padx=14, pady=(0, 14))
        self.delay_var = tk.IntVar(value=2)
        self.delay_label = tk.Label(delay_row, text="2s", bg=BG2, fg=GOLD, font=FONT, width=4)
        self.delay_label.pack(side="right")
        slider = tk.Scale(delay_row, from_=1, to=10, orient="horizontal",
                          variable=self.delay_var, bg=BG2, fg=TEXT, troughcolor=BG3,
                          highlightthickness=0, bd=0, showvalue=False,
                          command=lambda v: self.delay_label.config(text=f"{int(float(v))}s"))
        slider.pack(side="left", fill="x", expand=True)

        self._section_label(p, "MAX TOKENS (REASONING DEPTH)")
        tok_row = tk.Frame(p, bg=BG2)
        tok_row.pack(fill="x", padx=14, pady=(0, 14))
        self.max_tokens_var = tk.IntVar(value=500)
        self.max_tokens_label = tk.Label(tok_row, text="500", bg=BG2, fg=GOLD, font=FONT, width=5)
        self.max_tokens_label.pack(side="right")
        tok_slider = tk.Scale(tok_row, from_=200, to=2000, resolution=100, orient="horizontal",
                              variable=self.max_tokens_var, bg=BG2, fg=TEXT, troughcolor=BG3,
                              highlightthickness=0, bd=0, showvalue=False,
                              command=lambda v: self.max_tokens_label.config(text=str(int(float(v)))))
        tok_slider.pack(side="left", fill="x", expand=True)

        # ── Next button click coords ─────────────────────────────────────────
        self._section_label(p, "NEXT BUTTON COORDS (X, Y)")
        coords_row = tk.Frame(p, bg=BG2)
        coords_row.pack(fill="x", padx=14, pady=(0, 14))

        tk.Label(coords_row, text="X:", bg=BG2, fg=TEXT, font=FONT).pack(side="left")
        self.next_x_var = tk.StringVar(value="1770")
        tk.Entry(coords_row, textvariable=self.next_x_var, bg=BG3, fg=TEXT, font=FONT,
                 bd=0, insertbackground=TEXT, width=6).pack(side="left", padx=(2, 10))

        tk.Label(coords_row, text="Y:", bg=BG2, fg=TEXT, font=FONT).pack(side="left")
        self.next_y_var = tk.StringVar(value="202")
        tk.Entry(coords_row, textvariable=self.next_y_var, bg=BG3, fg=TEXT, font=FONT,
                 bd=0, insertbackground=TEXT, width=6).pack(side="left", padx=(2, 10))

        tk.Button(coords_row, text="Crosshair", bg=BG3, fg=GOLD, font=FONT_SM, bd=0,
                  relief="flat", cursor="hand2", command=self.pick_next_coords).pack(side="left", padx=4)

        self._section_label(p, "API KEY")
        krow = tk.Frame(p, bg=BG3, bd=0, highlightthickness=1, highlightbackground=BORDER)
        krow.pack(fill="x", padx=14, pady=(0, 12))
        self.key_entry = tk.Entry(krow, bg=BG3, fg=TEXT, font=FONT, bd=0,
                                  insertbackground=TEXT, show="•")
        self.key_entry.insert(0, OPENROUTER_API_KEY)
        self.key_entry.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        tk.Button(krow, text="Save", bg=BG3, fg=GOLD, font=FONT_SM, bd=0,
                  relief="flat", cursor="hand2", command=self.save_key).pack(side="right", padx=8)

    def pick_next_coords(self):
        """Let user hover over Next button and press Enter to capture coords."""
        self.safe_log("Hover over the Next button, then press Enter...", "gold")
        self.withdraw()
        time.sleep(0.3)

        def capture():
            if KEYBOARD_AVAILABLE:
                keyboard.wait('enter')
            else:
                time.sleep(3)
            x, y = pyautogui.position()
            self.next_x_var.set(str(x))
            self.next_y_var.set(str(y))
            self.safe_log(f"Next button coords set: ({x}, {y})", "green")
            self.deiconify()

        threading.Thread(target=capture, daemon=True).start()

    def _style_combobox(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG3, background=BG3,
                        foreground=TEXT, bordercolor=BORDER, arrowcolor=GOLD)

    def save_key(self):
        global OPENROUTER_API_KEY
        OPENROUTER_API_KEY = self.key_entry.get()
        self.safe_log("API key updated", "gold")

    def _build_hotkeys_panel(self):
        p = tk.Frame(self, bg=BG2)
        self.panels["hotkeys"] = p

        hotkeys = [
            ("Stop macro", "Q"),
            ("Start macro", "S"),
            ("Re-select region", "F2"),
        ]
        for label, key in hotkeys:
            row = tk.Frame(p, bg=BG2)
            row.pack(fill="x", padx=14, pady=5)
            tk.Label(row, text=label, bg=BG2, fg=TEXT, font=FONT).pack(side="left")
            tk.Label(row, text=key, bg=BG3, fg=GOLD, font=FONT,
                     padx=10, pady=2).pack(side="right")

        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=14, pady=12)

    def _build_log_panel(self):
        p = tk.Frame(self, bg=BG2)
        self.panels["log"] = p

        self.log_text = tk.Text(p, bg=BG3, fg=MUTED, font=FONT_SM, bd=0,
                                relief="flat", state="disabled", wrap="word",
                                padx=10, pady=8)
        self.log_text.pack(fill="both", expand=True, padx=14, pady=14)
        self.log_text.tag_config("gold", foreground=GOLD)
        self.log_text.tag_config("green", foreground=GREEN)
        self.log_text.tag_config("red", foreground=RED)
        self.log_text.tag_config("muted", foreground=MUTED)
        self.safe_log("Ready — waiting to start...", "gold")

    def safe_log(self, msg, color=""):
        self.after(0, lambda: self._internal_log(msg, color))

    def _internal_log(self, msg, color=""):
        t = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        tag = color if color in ("gold", "green", "red", "muted") else ""
        self.log_text.insert("end", f"[{t}] {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG2, fg=MUTED, font=FONT_SM).pack(
            anchor="w", padx=14, pady=(12, 4))

    def set_status(self, text, color=MUTED):
        self.after(0, lambda: self._internal_set_status(text, color))

    def _internal_set_status(self, text, color):
        self.status_label.config(text=text, fg=color)
        self.status_dot.config(fg=color)

    def select_region(self):
        self.withdraw()
        time.sleep(0.3)
        self.safe_log("Draw a box around the question area...", "gold")

        import PIL.ImageTk as ImageTk

        overlay = tk.Toplevel()
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-alpha', 1.0)
        overlay.configure(bg='black')
        overlay.lift()
        overlay.focus_force()

        sw = overlay.winfo_screenwidth()
        sh = overlay.winfo_screenheight()

        canvas = tk.Canvas(overlay, cursor="cross", bg='black', highlightthickness=0)
        canvas.pack(fill='both', expand=True)

        bg_shot = pyautogui.screenshot()
        bg_photo = ImageTk.PhotoImage(bg_shot)
        canvas.create_image(0, 0, anchor='nw', image=bg_photo)
        canvas._bg_photo = bg_photo  

        # Single dim overlay covering whole screen
        dim = canvas.create_rectangle(0, 0, sw, sh, fill='black', stipple='gray50', outline='')

        # Pre-create the 4 dim cutout rects and dashed border — just move them on drag
        top_dim    = canvas.create_rectangle(0, 0, 0, 0, fill='black', stipple='gray50', outline='')
        bot_dim    = canvas.create_rectangle(0, 0, 0, 0, fill='black', stipple='gray50', outline='')
        left_dim   = canvas.create_rectangle(0, 0, 0, 0, fill='black', stipple='gray50', outline='')
        right_dim  = canvas.create_rectangle(0, 0, 0, 0, fill='black', stipple='gray50', outline='')
        sel_border = canvas.create_rectangle(0, 0, 0, 0, outline='white', width=2, dash=(6, 3))


        canvas.tag_raise(sel_border)

        coords = {}

        def on_press(e):
            coords['x1'] = e.x
            coords['y1'] = e.y
            canvas.itemconfig(dim, state='hidden')

        def on_drag(e):
            if 'x1' not in coords:
                return
            x1, y1 = coords['x1'], coords['y1']
            x2, y2 = e.x, e.y
            lx, rx = min(x1, x2), max(x1, x2)
            ty, by = min(y1, y2), max(y1, y2)

            canvas.coords(top_dim,   0,  0,  sw, ty)
            canvas.coords(bot_dim,   0,  by, sw, sh)
            canvas.coords(left_dim,  0,  ty, lx, by)
            canvas.coords(right_dim, rx, ty, sw, by)
            canvas.coords(sel_border, lx, ty, rx, by)

        def on_release(e):
            coords['x2'] = e.x
            coords['y2'] = e.y
            overlay.destroy()

        canvas.bind('<ButtonPress-1>', on_press)
        canvas.bind('<B1-Motion>', on_drag)
        canvas.bind('<ButtonRelease-1>', on_release)
        canvas.bind('<Escape>', lambda e: overlay.destroy())

        overlay.wait_window()
        self.deiconify()

        if 'x2' in coords:
            global region
            x = min(coords['x1'], coords['x2'])
            y = min(coords['y1'], coords['y2'])
            w = abs(coords['x2'] - coords['x1'])
            h = abs(coords['y2'] - coords['y1'])

            if w > 5 and h > 5:
                region = (x, y, w, h)
                self.region_label.config(text=f"({x}, {y}, {w}, {h})", fg=GREEN)
                self.safe_log(f"Region saved: {region}", "green")
            else:
                self.safe_log("Selection box too small. Try again.", "red")

    def toggle_run(self):
        if not running:
            self.start_macro()
        else:
            self.stop_macro()

    def start_macro(self):
        global running
        if running: return
        if region is None:
            self.safe_log("Set the question region first!", "red")
            return
        running = True
        self.start_btn.config(text="■  Stop", bg=RED)
        self.set_status("Running...", GREEN)
        self.safe_log("Macro started", "green")
        threading.Thread(target=self._run_loop, daemon=True).start()

    def stop_macro(self):
        global running
        if not running: return
        running = False
        self.start_btn.config(text="▶  Start", bg=GREEN)
        self.set_status("Stopped", MUTED)
        self.safe_log("Macro stopped", "red")

    def _get_next_coords(self):
        try:
            x = int(self.next_x_var.get())
            y = int(self.next_y_var.get())
            return x, y
        except ValueError:
            return 1770, 202  

    def _build_history_panel(self):
        import PIL.ImageTk as ImageTk
        p = tk.Frame(self, bg=BG2)
        self.panels["history"] = p

        # Top bar
        top = tk.Frame(p, bg=BG2)
        top.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(top, text="ANSWER HISTORY", bg=BG2, fg=MUTED, font=FONT_SM).pack(side="left")
        tk.Button(top, text="Clear All", bg=BG3, fg=RED, font=FONT_SM, bd=0,
                  relief="flat", cursor="hand2", command=self._clear_history).pack(side="right")

        # Scrollable list on left, detail on right
        pane = tk.Frame(p, bg=BG2)
        pane.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Left: entry list
        list_frame = tk.Frame(pane, bg=BG3, width=140)
        list_frame.pack(side="left", fill="y")
        list_frame.pack_propagate(False)

        self.hist_listbox = tk.Listbox(list_frame, bg=BG3, fg=TEXT, font=FONT_SM,
                                       bd=0, relief="flat", selectbackground=GOLD,
                                       selectforeground="#111", activestyle="none",
                                       highlightthickness=0)
        self.hist_listbox.pack(fill="both", expand=True)
        self.hist_listbox.bind("<<ListboxSelect>>", self._on_history_select)

        # Right: detail view
        detail = tk.Frame(pane, bg=BG2)
        detail.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.hist_img_label = tk.Label(detail, bg=BG2, anchor="nw")
        self.hist_img_label.pack(fill="x")

        self.hist_answer_label = tk.Label(detail, text="", bg=BG2, fg=GOLD,
                                          font=("Consolas", 11, "bold"), anchor="w")
        self.hist_answer_label.pack(fill="x", pady=(6, 2))

        self.hist_reasoning = tk.Text(detail, bg=BG3, fg=MUTED, font=FONT_SM,
                                      bd=0, relief="flat", wrap="word",
                                      state="disabled", height=10)
        self.hist_reasoning.pack(fill="both", expand=True)

        self._history_images = []  
        self._refresh_history()

    def _refresh_history(self):
        self.hist_listbox.delete(0, "end")
        self._hist_data = load_history()
        for e in self._hist_data:
            self.hist_listbox.insert("end", f"  {e['time'][11:16]}  →  {e['answer'][:12]}")
        if self._hist_data:
            self.hist_listbox.selection_set(0)
            self._on_history_select(None)

    def _on_history_select(self, event):
        import PIL.ImageTk as ImageTk
        sel = self.hist_listbox.curselection()
        if not sel:
            return
        e = self._hist_data[sel[0]]

  
        try:
            img_data = base64.b64decode(e["image_b64"])
            img = Image.open(io.BytesIO(img_data))
            img.thumbnail((260, 120))
            photo = ImageTk.PhotoImage(img)
            self.hist_img_label.config(image=photo)
            self._history_images = [photo]
        except Exception:
            self.hist_img_label.config(image="", text="[No image]")

        # Show answer
        self.hist_answer_label.config(text=f"Answer: {e['answer']}")

        # Show reasoning
        self.hist_reasoning.config(state="normal")
        self.hist_reasoning.delete("1.0", "end")
        self.hist_reasoning.insert("end", e.get("reasoning", ""))
        self.hist_reasoning.config(state="disabled")

    def _clear_history(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump([], f)
            self._refresh_history()
            self.hist_img_label.config(image="", text="")
            self.hist_answer_label.config(text="")
            self.hist_reasoning.config(state="normal")
            self.hist_reasoning.delete("1.0", "end")
            self.hist_reasoning.config(state="disabled")
        except Exception:
            pass

    def _run_loop(self):
        awaiting_next_button = False
        self.safe_log("Starting in 3 seconds — switch to your browser now...", "gold")
        time.sleep(3)

        while running:
            try:
                if not awaiting_next_button:
                    self.safe_log("Taking screenshot...", "muted")
                    image = screenshot_question()
                    self.safe_log("Calling AI...", "muted")
                    answer, reasoning = ask_ai(image, self.model_var.get(), self.max_tokens_var.get())

                    # Log the model's reasoning so you can audit it
                    for line in reasoning.strip().splitlines():
                        self.safe_log(f"  {line}", "muted")
                    self.safe_log(f"→ Answer: {answer}", "gold")

                    self.safe_log("Attempting to find text box and submit...", "muted")
                    if submit_answer(answer, 'SubmitAnswer.png'):
                        self.safe_log("Answer submitted. Clicking Next...", "green")
                        # Save to history
                        entry = {
                            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "answer": answer,
                            "reasoning": reasoning,
                            "image_b64": img_to_b64(image)
                        }
                        threading.Thread(target=save_history_entry, args=(entry,), daemon=True).start()
                        self.after(0, self._refresh_history)
                        awaiting_next_button = True
                        time.sleep(1.5)
                    else:
                        self.safe_log("Couldn't find text input box. Retrying...", "red")
                        time.sleep(1.0)

                else:
                    nx, ny = self._get_next_coords()
                    for _ in range(4):
                        pyautogui.click(nx, ny)
                        time.sleep(0.5)
                    awaiting_next_button = False  # ← fixed: reset so next question gets solved

            except Exception as e:
                self.safe_log(f"Error: {e}", "red")
                time.sleep(1.0)

            delay = self.delay_var.get()
            for _ in range(max(1, delay * 10)):
                if not running:
                    break
                time.sleep(0.1)


# ── Auth helpers ─────────────────────────────────────────────────────────────
def register_user(username, password):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/users",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={"username": f"eq.{username}"},
            timeout=5
        )
        if r.status_code == 200 and len(r.json()) > 0:
            return False, "Username already taken."
        r2 = requests.post(
            f"{SUPABASE_URL}/rest/v1/users",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json={"username": username, "password_hash": pw_hash},
            timeout=5
        )
        if r2.status_code in (200, 201):
            return True, ""
        return False, f"Server error: {r2.status_code}"
    except Exception as e:
        return False, f"Connection error: {e}"


# ── Login Window ──────────────────────────────────────────────────────────────
class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DeltaMath Macro — Login")
        self.geometry("600x600")
        self.resizable(True, True)
        self.configure(bg=BG)
        self.success = False
        self.wm_attributes("-topmost", True)
        self._build_header()
        self._show_login()

    def _build_header(self):
        bar = tk.Frame(self, bg="#0d0d0d", height=48)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        left = tk.Frame(bar, bg="#0d0d0d")
        left.pack(side="left", padx=12, pady=8)
        tk.Label(left, text="D", bg=GOLD, fg="#111", font=("Consolas", 11, "bold"), width=2).pack(side="left")
        info = tk.Frame(left, bg="#0d0d0d")
        info.pack(side="left", padx=8)
        tk.Label(info, text="Deltamath Automation", bg="#0d0d0d", fg=TEXT,
                 font=("Lucida Console", 10, "bold")).pack(anchor="w")
        self.subtitle = tk.Label(info, text="Sign in to continue", bg="#0d0d0d", fg=MUTED, font=FONT_SM)
        self.subtitle.pack(anchor="w")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        self.body_frame = None

    def _clear_body(self):
        if self.body_frame:
            self.body_frame.destroy()
        self.body_frame = tk.Frame(self, bg=BG2)
        self.body_frame.pack(fill="both", expand=True, padx=20, pady=16)

    def _field(self, parent, label, show=None):
        tk.Label(parent, text=label, bg=BG2, fg=MUTED, font=FONT_SM).pack(anchor="w")
        row = tk.Frame(parent, bg=BG3, highlightthickness=1, highlightbackground=BORDER)
        row.pack(fill="x", pady=(4, 12))
        entry = tk.Entry(row, bg=BG3, fg=TEXT, font=FONT, bd=0, insertbackground=TEXT,
                         show=show if show else "")
        entry.pack(fill="x", padx=10, pady=8)
        return entry

    def _error(self, parent):
        lbl = tk.Label(parent, text="", bg=BG2, fg=RED, font=FONT_SM)
        lbl.pack(anchor="w", pady=(0, 6))
        return lbl

    # ── Login form ────────────────────────────────────────────────────────────
    def _show_login(self):
        self.subtitle.config(text="Sign in to continue")
        self._clear_body()
        p = self.body_frame

        self.u = self._field(p, "USERNAME")
        self.u.focus()
        self.pw = self._field(p, "PASSWORD", show="•")
        self.pw.bind("<Return>", lambda e: self._do_login())
        self.err = self._error(p)

        tk.Button(p, text="Sign In", bg=GREEN, fg="white", font=("Consolas", 11, "bold"),
                  bd=0, relief="flat", cursor="hand2", pady=8,
                  command=self._do_login).pack(fill="x")

        tk.Button(p, text="Create an account", bg=BG2, fg=MUTED, font=FONT_SM,
                  bd=0, relief="flat", cursor="hand2", pady=6,
                  command=self._show_register).pack()

    def _do_login(self):
        u, pw = self.u.get().strip(), self.pw.get()
        if not u or not pw:
            self.err.config(text="Please fill in all fields.")
            return
        self.err.config(text="Signing in...")
        threading.Thread(target=self._auth_thread, args=(u, pw), daemon=True).start()

    def _auth_thread(self, u, pw):
        ok = check_credentials(u, pw)
        self.after(0, lambda: self._on_login(ok))

    def _on_login(self, ok):
        if ok:
            self.success = True
            self.destroy()
        else:
            self.err.config(text="Incorrect username or password.")
            self.pw.delete(0, "end")

    # ── Register form ─────────────────────────────────────────────────────────
    def _show_register(self):
        self.subtitle.config(text="Create an account")
        self._clear_body()
        self.geometry("360x340")
        p = self.body_frame

        self.ru = self._field(p, "USERNAME")
        self.ru.focus()
        self.rpw = self._field(p, "PASSWORD", show="•")
        self.rpw2 = self._field(p, "CONFIRM PASSWORD", show="•")
        self.rpw2.bind("<Return>", lambda e: self._do_register())
        self.rerr = self._error(p)

        tk.Button(p, text="Create Account", bg=GREEN, fg="white", font=("Consolas", 11, "bold"),
                  bd=0, relief="flat", cursor="hand2", pady=8,
                  command=self._do_register).pack(fill="x")

        tk.Button(p, text="← Back to sign in", bg=BG2, fg=MUTED, font=FONT_SM,
                  bd=0, relief="flat", cursor="hand2", pady=6,
                  command=lambda: [self.geometry("360x300"), self._show_login()]).pack()

    def _do_register(self):
        u = self.ru.get().strip()
        pw = self.rpw.get()
        pw2 = self.rpw2.get()
        if not u or not pw or not pw2:
            self.rerr.config(text="Please fill in all fields.")
            return
        if pw != pw2:
            self.rerr.config(text="Passwords do not match.")
            return
        if len(pw) < 6:
            self.rerr.config(text="Password must be at least 6 characters.")
            return
        self.rerr.config(text="Creating account...")
        threading.Thread(target=self._reg_thread, args=(u, pw), daemon=True).start()

    def _reg_thread(self, u, pw):
        ok, msg = register_user(u, pw)
        self.after(0, lambda: self._on_register(ok, msg))

    def _on_register(self, ok, msg):
        if ok:
            # Auto-login after successful registration
            self.success = True
            self.destroy()
        else:
            self.rerr.config(text=msg)


if __name__ == "__main__":
    login = LoginWindow()
    login.mainloop()
    if login.success:
        app = App()
        app.mainloop()