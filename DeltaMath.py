import pyautogui
import pyperclip
import requests
import base64
import io
import time
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image


try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False


# ── Config ───────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = ""
MODEL = "google/gemini-2.5-flash"


# ── State ────────────────────────────────────────────────────────────────────
region = None
running = False


import math as _math

# ── AI ───────────────────────────────────────────────────────────────────────
def ask_ai(image, model):
    if not OPENROUTER_API_KEY:
        raise Exception("API Key is missing! Add it via the Settings tab.")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": model,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a math solver for DeltaMath. Your job is to set up the formula, not compute it.\n"
                        "Respond in exactly this format:\n"
                        "WORK: <2-3 lines: list every known side+angle, explicitly state which side is opposite which angle, then state the formula>\n"
                        "FORMULA: <a single valid Python math expression using math.sin, math.cos, math.tan, math.radians, math.sqrt, math.pi>\n"
                        "PRECISION: <integer: 0 for nearest integer, 1 for nearest 10th, 2 for nearest 100th. Use -1 if answer must stay in radical/symbolic form>\n\n"
                        "IMPORTANT — RADICAL/SYMBOLIC FORM:\n"
                        "- If the problem says 'simplest radical form', 'exact form', or 'leave in terms of pi', set PRECISION: -1\n"
                        "- When PRECISION is -1, FORMULA must be a Python string expression that returns the symbolic answer directly\n"
                        "- Example: polar (3sqrt(3), 0) to rectangular → x = 3sqrt(3), y = 0 → FORMULA: '3sqrt(3), 0'\n"
                        "- Example: answer is 2pi/3 → FORMULA: '2pi/3'\n"
                        "- Example: answer is sqrt(2)/2 → FORMULA: 'sqrt(2)/2'\n"
                        "- For radical form, think symbolically — do NOT compute decimals\n\n"
                        "LAW OF SINES — CRITICAL RULES:\n"
                        "- Side a is opposite angle A, side b opposite angle B, side c opposite angle C\n"
                        "- Formula: unknown = known_side * sin(angle_opposite_unknown) / sin(angle_opposite_known)\n"
                        "- Example: find t, given s=85, S=28°, T=87° → t = 85 * sin(87°) / sin(28°)\n"
                        "- The denominator is ALWAYS the angle opposite the KNOWN side, never the computed third angle\n\n"
                        "Other rules:\n"
                        "- FORMULA is a single Python eval()-able expression, no equals sign\n"
                        "- Always wrap degrees in math.radians() before trig functions\n"
                        "- PRECISION must be the very last line\n"
                        "- No LaTeX, no markdown"
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Set up the formula for the math problem in this image."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]
                }
            ]
        }
    )

    result = response.json()
    if 'choices' not in result:
        raise Exception(f"API error: {result.get('error', {}).get('message', str(result))}")

    raw = result['choices'][0]['message']['content'].strip()

    formula = None
    precision = 0
    for line in raw.splitlines():
        if line.startswith("FORMULA:"):
            formula = line.split("FORMULA:", 1)[1].strip()
        elif line.startswith("PRECISION:"):
            try:
                precision = int(line.split("PRECISION:", 1)[1].strip())
            except ValueError:
                precision = 0

    if not formula:
        raise Exception(f"Could not parse FORMULA from AI response:\n{raw}")

    try:
        if precision == -1:
            answer = eval(formula, {"math": _math, "__builtins__": {}}) if not formula.startswith("'") else formula.strip("'")
        else:
            value = eval(formula, {"math": _math, "__builtins__": {}})
            answer = f"{value:.{precision}f}"
    except Exception as e:
        raise Exception(f"Failed to eval formula '{formula}': {e}")

    return answer, raw


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


def click_textBox(image, confidence_level=0.8):
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


def submit_answer(answer, text_box_image='SubmitAnswer.png'):
    if click_textBox(text_box_image):
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DeltaMath Macro")
        self.geometry("400x520")
        self.resizable(True, True)
        self.configure(bg=BG)

        self._build_titlebar()
        self._build_tabs()
        self._build_run_panel()
        self._build_settings_panel()
        self._build_hotkeys_panel()
        self._build_log_panel()

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
        self.wm_attributes("-topmost", True)

        sep = tk.Frame(self, bg=BORDER, height=1)
        sep.pack(fill="x")

    def toggle_ontop(self):
        val = not self.ontop_var.get()
        self.ontop_var.set(val)
        self.wm_attributes("-topmost", val)
        self.ontop_btn.config(text=f"⊞ On Top: {'ON' if val else 'OFF'}",
                              fg=GOLD if val else MUTED)

    def _build_tabs(self):
        self.tab_frame = tk.Frame(self, bg="#0d0d0d")
        self.tab_frame.pack(fill="x")

        self.tab_btns = {}
        tabs = [("▶  Run", "run"), ("⚙  Settings", "settings"),
                ("⌨  Hotkeys", "hotkeys"), ("≡  Log", "log")]
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

        overlay = tk.Toplevel()
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-alpha', 1.0)
        overlay.configure(bg='black')
        overlay.lift()
        overlay.focus_force()

        sw = overlay.winfo_screenwidth()
        sh = overlay.winfo_screenheight()

        canvas = tk.Canvas(overlay, cursor="cross", bg='black',
                           highlightthickness=0)
        canvas.pack(fill='both', expand=True)

        import PIL.ImageTk as ImageTk
        bg_shot = pyautogui.screenshot()
        bg_image = ImageTk.PhotoImage(bg_shot)

        canvas.create_image(0, 0, anchor='nw', image=bg_image)
        dim = canvas.create_rectangle(0, 0, sw, sh, fill='black', stipple='gray50', outline='')

        coords = {}
        rect_id = None
        bright_id = None
        dash_id = None

        def on_press(e):
            coords['x1'] = e.x
            coords['y1'] = e.y

        def on_drag(e):
            nonlocal rect_id, bright_id, dash_id
            if 'x1' not in coords:
                return
            x1, y1 = coords['x1'], coords['y1']
            x2, y2 = e.x, e.y


            if rect_id:
                canvas.delete(rect_id)
            if bright_id:
                canvas.delete(bright_id)
            if dash_id:
                canvas.delete(dash_id)


            bright_id = canvas.create_image(0, 0, anchor='nw', image=bg_image)

            canvas.delete(dim)
            canvas.create_rectangle(0, 0, sw, min(y1, y2),
                                    fill='black', stipple='gray50', outline='')
            canvas.create_rectangle(0, max(y1, y2), sw, sh,
                                    fill='black', stipple='gray50', outline='')
            canvas.create_rectangle(0, min(y1, y2), min(x1, x2), max(y1, y2),
                                    fill='black', stipple='gray50', outline='')
            canvas.create_rectangle(max(x1, x2), min(y1, y2), sw, max(y1, y2),
                                    fill='black', stipple='gray50', outline='')

            # Dashed border
            dash_id = canvas.create_rectangle(
                min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2),
                outline='white', width=2, dash=(6, 3)
            )

        def on_release(e):
            coords['x2'] = e.x
            coords['y2'] = e.y
            overlay.destroy()

        canvas.bind('<ButtonPress-1>', on_press)
        canvas.bind('<B1-Motion>', on_drag)
        canvas.bind('<ButtonRelease-1>', on_release)
        canvas.bind('<Escape>', lambda e: overlay.destroy())


        canvas._bg_image = bg_image

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
                    answer, reasoning = ask_ai(image, self.model_var.get())

                    for line in reasoning.strip().splitlines():
                        self.safe_log(f"  {line}", "muted")
                    self.safe_log(f"→ Answer: {answer}", "gold")

                    self.safe_log("Attempting to find text box and submit...", "muted")
                    if submit_answer(answer, 'SubmitAnswer.png'):
                        self.safe_log("Answer submitted. Clicking Next...", "green")
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
                    awaiting_next_button = False  

            except Exception as e:
                self.safe_log(f"Error: {e}", "red")
                time.sleep(1.0)

            delay = self.delay_var.get()
            for _ in range(max(1, delay * 10)):
                if not running:
                    break
                time.sleep(0.1)


if __name__ == "__main__":
    app = App()
    app.mainloop()