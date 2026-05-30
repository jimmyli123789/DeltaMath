import pyautogui
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




# ── Config ──────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = ""
MODEL = "google/gemini-2.5-flash"




# ── State ────────────────────────────────────────────────────────────────────
region = None
input_pos = None
running = False
region_coords = {}




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
            "max_tokens" : 100,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a math solver. Think through problems carefully, but only ever respond with the final answer and nothing else."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": """
                            You are a deterministic math solver backend for a DeltaMath automation script.
                            Your sole task is to look at the image, solve the math problem, and output the exact keystrokes required to type the correct answer into the DeltaMath input box.


                            CRITICAL FORMATTING RULES FOR DELTAMATH SYNTAX:
                            1. NO EXPLANATIONS: Output ONLY the final raw answer string. Do not include text like "The answer is" or any conversational filler.
                            2. NO LATEX: Never use LaTeX symbols like '\\frac', '\\cdot', '\\sqrt', or '$'.
                            3. FRACTIONS: Use the forward slash '/'. (e.g., For a fraction like 3 over 4, output exactly '3/4').
                            4. EXPONENTS / POWERS: Use the caret '^'. (e.g., For x squared, output exactly 'x^2').
                            5. PI (π): Output the literal letters 'pi'. DeltaMath automatically converts the text 'pi' into the symbol π. (e.g., For 2π, output '2pi').
                            6. SQUARE ROOTS (√): Use the letters 'sqrt' followed by the number or use a fractional exponent if applicable, but standard DeltaMath accepts 'sqrt' for basic roots.
                            7. MULTIPLE ANSWERS / plus-minus (±): If a quadratic equation has two answers (e.g., x = 3 and x = -3), separate them with a comma ','. DeltaMath automatically creates a second input box when a comma is typed. (e.g., '3,-3').
                            8. MULTIPLE CHOICE: If the question is multiple choice, output the literal text string of the correct option exactly as it appears, without any keyboard syntax modifications.
                            9. FRACTIONS WITH SQUARE ROOTS IN THE NUMERATOR:
                            If an answer features a square root only in the numerator (like √2 over 2), you must use parenthesis or explicit navigation cues so the macro doesn't trap the whole fraction inside the root.
                            - To output √2 all over 2, output exactly: sqrt(2)/2
                            - Alternatively, you can output explicit navigation keystrokes by using [right] to exit a block. For example: sqrt(2)[right]/2
                            EXAMPLES OF CONVERSION:
                            - If the answer is 4π/3 -> Output: 4pi/3
                            - If the answer is x = -b ± √d -> Output the specific numerical values separated by a comma.
                            - If the answer is 5x³ -> Output: 5x^3


                            Double-check your math before outputting. If you fail to follow these formatting rules, the macro will type invalid characters and fail the assignment.
                            """},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]
                }
            ]
        }
    )
    result = response.json()
    if 'choices' not in result:
        raise Exception(f"API error: {result.get('error', {}).get('message', str(result))}")
    return result['choices'][0]['message']['content'].strip()




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
            target_x = x - 300  # Clicks 300 pixels to the left of the asset
            pyautogui.click(target_x, y)
            return True
    except Exception:
        pass
    return False




def screenshot_question():
    if region is None:
        raise Exception("Region coordinates are empty.")
    return pyautogui.screenshot(region=region)




def submit_answer(answer, text_box_image='SubmitAnswer.png'):
    if click_textBox(text_box_image):
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.typewrite(answer, interval=0.05)
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


        self._section_label(p, "API KEY")
        krow = tk.Frame(p, bg=BG3, bd=0, highlightthickness=1, highlightbackground=BORDER)
        krow.pack(fill="x", padx=14, pady=(0, 12))
        self.key_entry = tk.Entry(krow, bg=BG3, fg=TEXT, font=FONT, bd=0,
                                  insertbackground=TEXT, show="•")
        self.key_entry.insert(0, OPENROUTER_API_KEY)
        self.key_entry.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        tk.Button(krow, text="Save", bg=BG3, fg=GOLD, font=FONT_SM, bd=0,
                  relief="flat", cursor="hand2", command=self.save_key).pack(side="right", padx=8)


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
        self.safe_log("Ready — waiting to start...", "gold")


    def safe_log(self, msg, color=""):
        # Safely schedules text logging into the core UI main loop
        self.after(0, lambda: self._internal_log(msg, color))


    def _internal_log(self, msg, color=""):
        t = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        tag = color if color in ("gold", "green", "red") else ""
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
        overlay.attributes('-alpha', 0.3)
        overlay.configure(bg='blue')
        overlay.lift()
        overlay.focus_force()


        coords = {}


        def on_press(e):
            coords['x1'] = e.x_root
            coords['y1'] = e.y_root


        def on_release(e):
            coords['x2'] = e.x_root
            coords['y2'] = e.y_root
            overlay.destroy()


        overlay.bind('<ButtonPress-1>', on_press)
        overlay.bind('<ButtonRelease-1>', on_release)
        overlay.wait_window()


        self.deiconify()


        if 'x2' in coords:
            global region
            # Fix coordinates so calculation works even if drawn right-to-left
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


    def _run_loop(self):
        awaiting_next_button = False
       
        while running:
            try:
                if not awaiting_next_button:
                    image = screenshot_question()
                    answer = ask_ai(image, self.model_var.get())
                    self.safe_log(f"AI Solution: {answer}", "gold")
                   
                    # STEP 2: Attempt to type and submit
                    if submit_answer(answer, 'SubmitAnswer.png'):
                        self.safe_log("Answer entered. Waiting for 'Next Problem' button...", "green")
                        awaiting_next_button = True
                        time.sleep(1.5)  
                    else:
                        self.safe_log("Couldn't find text input box. Retrying scan...", "red")
                        time.sleep(1.0)
                       
                else:
                    x = 0
                    while x < 4:
                        pyautogui.click(1770,202)
                        time.sleep(0.5)
                        x = x + 1 
                   
            except Exception as e:
                self.safe_log(f"Error encountered: {e}", "red")
                time.sleep(1.0)
               
            # Master loop delay check
            delay = self.delay_var.get()
            for _ in range(max(1, delay * 10)):
                if not running:
                    break
                time.sleep(0.1)




if __name__ == "__main__":
    app = App()
    app.mainloop()



