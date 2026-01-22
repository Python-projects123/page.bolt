import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

# ---- Optional: Local offline inference (GGUF) ----
# pip install llama-cpp-python
try:
    from llama_cpp import Llama
except Exception:
    Llama = None

# ---- Optional: API mode ----
# pip install openai
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class AIGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Chat (Offline GGUF + Optional API)")
        self.geometry("980x720")
        self.configure(bg="#0f1117")

        # ====== State ======
        self.history = []  # list of (role, content)
        self.llm = None
        self.model_path = tk.StringVar(value="")
        self.mode = tk.StringVar(value="local")  # "local" or "api"

        # API key variable (you asked for it)
        self.api_key = None
        self.client = None

        # Performance knobs
        self.max_turns_keep = 6
        self.max_tokens = tk.IntVar(value=220)
        self.temperature = tk.DoubleVar(value=0.7)

        # ====== UI ======
        self._build_ui()
        self._apply_dark_theme()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#151821", bd=0, highlightthickness=1, highlightbackground="#262a36")
        header.pack(fill="x", padx=14, pady=(14, 10))

        tk.Label(header, text="AI Chat", fg="#e7eaf0", bg="#151821",
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=12, pady=10)

        self.status = tk.Label(header, text="Status: idle", fg="#9aa1b2", bg="#151821",
                               font=("Segoe UI", 10))
        self.status.pack(side="right", padx=12)

        # Controls row
        controls = tk.Frame(self, bg="#0f1117")
        controls.pack(fill="x", padx=14)

        # Mode selector
        tk.Label(controls, text="Mode:", fg="#9aa1b2", bg="#0f1117").pack(side="left", padx=(0, 6))
        tk.Radiobutton(controls, text="Local (GGUF)", variable=self.mode, value="local",
                       fg="#e7eaf0", bg="#0f1117", selectcolor="#151821",
                       activebackground="#0f1117", activeforeground="#e7eaf0",
                       command=self._mode_changed).pack(side="left")
        tk.Radiobutton(controls, text="API", variable=self.mode, value="api",
                       fg="#e7eaf0", bg="#0f1117", selectcolor="#151821",
                       activebackground="#0f1117", activeforeground="#e7eaf0",
                       command=self._mode_changed).pack(side="left", padx=(10, 0))

        # Model path + load button
        tk.Label(controls, text="Model (.gguf):", fg="#9aa1b2", bg="#0f1117").pack(side="left", padx=(18, 6))
        self.model_entry = tk.Entry(controls, textvariable=self.model_path, width=44,
                                    bg="#151821", fg="#e7eaf0", insertbackground="#e7eaf0",
                                    relief="flat", highlightthickness=1, highlightbackground="#262a36")
        self.model_entry.pack(side="left", padx=(0, 8), ipady=6)

        tk.Button(controls, text="Browse", command=self._browse_model,
                  bg="#222736", fg="#e7eaf0", relief="flat").pack(side="left", padx=(0, 8))

        tk.Button(controls, text="Load", command=self._load_model_clicked,
                  bg="#2b6cff", fg="white", relief="flat").pack(side="left", padx=(0, 12))

        tk.Button(controls, text="Set API Key", command=self._set_api_key,
                  bg="#222736", fg="#e7eaf0", relief="flat").pack(side="left")

        # Knobs row
        knobs = tk.Frame(self, bg="#0f1117")
        knobs.pack(fill="x", padx=14, pady=(10, 0))

        tk.Label(knobs, text="Max tokens:", fg="#9aa1b2", bg="#0f1117").pack(side="left", padx=(0, 6))
        tk.Spinbox(knobs, from_=32, to=1024, textvariable=self.max_tokens, width=6,
                   bg="#151821", fg="#e7eaf0", insertbackground="#e7eaf0",
                   relief="flat", highlightthickness=1, highlightbackground="#262a36").pack(side="left")

        tk.Label(knobs, text="Temperature:", fg="#9aa1b2", bg="#0f1117").pack(side="left", padx=(18, 6))
        tk.Spinbox(knobs, from_=0.0, to=2.0, increment=0.1, textvariable=self.temperature, width=6,
                   bg="#151821", fg="#e7eaf0", insertbackground="#e7eaf0",
                   relief="flat", highlightthickness=1, highlightbackground="#262a36").pack(side="left")

        tk.Button(knobs, text="Clear Chat", command=self._clear_chat,
                  bg="#d24b4b", fg="white", relief="flat").pack(side="right")

        # Chat box
        chat_frame = tk.Frame(self, bg="#0f1117", bd=0)
        chat_frame.pack(fill="both", expand=True, padx=14, pady=12)

        self.chat = tk.Text(chat_frame, wrap="word", bg="#0f1117", fg="#e7eaf0",
                            insertbackground="#e7eaf0", relief="flat",
                            highlightthickness=1, highlightbackground="#262a36",
                            padx=12, pady=12)
        self.chat.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(chat_frame, command=self.chat.yview)
        scroll.pack(side="right", fill="y")
        self.chat.configure(yscrollcommand=scroll.set)

        self.chat.tag_configure("user", foreground="#b7d7ff")
        self.chat.tag_configure("ai", foreground="#d7f7c2")
        self.chat.tag_configure("meta", foreground="#9aa1b2")

        # Composer
        composer = tk.Frame(self, bg="#151821", highlightthickness=1, highlightbackground="#262a36")
        composer.pack(fill="x", padx=14, pady=(0, 14))

        self.input = tk.Text(composer, height=3, wrap="word",
                             bg="#0f1117", fg="#e7eaf0", insertbackground="#e7eaf0",
                             relief="flat", highlightthickness=1, highlightbackground="#262a36",
                             padx=12, pady=10)
        self.input.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.input.bind("<Return>", self._enter_to_send)

        self.send_btn = tk.Button(composer, text="Send", command=self._send_clicked,
                                  bg="#2b6cff", fg="white", relief="flat", width=10)
        self.send_btn.pack(side="right", padx=(0, 12), pady=10)

        self._write_ai("Tip: Local mode needs a .gguf model loaded. API mode needs a key.\n")

    def _apply_dark_theme(self):
        # Tk widgets already styled; keep minimal
        pass

    # ---------- UI actions ----------
    def _mode_changed(self):
        if self.mode.get() == "api":
            self._set_status("API mode selected (needs key).")
        else:
            self._set_status("Local mode selected (needs GGUF model).")

    def _browse_model(self):
        path = filedialog.askopenfilename(
            title="Select a GGUF model file",
            filetypes=[("GGUF model", "*.gguf"), ("All files", "*.*")]
        )
        if path:
            self.model_path.set(path)

    def _set_api_key(self):
        key = tk.simpledialog.askstring("API Key", "Enter your API key (stored in variable: api_key):", show="*")
        if key:
            self.api_key = key.strip()
            if OpenAI:
                self.client = OpenAI(api_key=self.api_key)
            self.mode.set("api")
            self._set_status("API key set. Using API mode.")
        else:
            self._set_status("API key not set.")

    def _load_model_clicked(self):
        if self.mode.get() != "local":
            self.mode.set("local")

        if Llama is None:
            messagebox.showerror(
                "Missing dependency",
                "llama-cpp-python is not installed.\n\nRun:\n  pip install llama-cpp-python"
            )
            return

        path = self.model_path.get().strip()
        if not path:
            messagebox.showwarning("Model missing", "Pick a .gguf file first.")
            return
        if not os.path.exists(path):
            messagebox.showerror("Not found", "That model file path does not exist.")
            return

        self._set_status("Loading model (this may take a bit)…")
        self.send_btn.configure(state="disabled")

        def worker():
            try:
                # You can tune n_ctx and n_threads as needed
                self.llm = Llama(
                    model_path=path,
                    n_ctx=2048,
                    n_threads=os.cpu_count() or 8,
                    # n_gpu_layers=0  # keep CPU for simplest setup
                )
                # Warm-up
                _ = self.llm("Hello", max_tokens=1)
                self._ui(lambda: self._set_status("Model loaded. Ready (Local)."))
                self._ui(lambda: self.send_btn.configure(state="normal"))
                self._ui(lambda: self._write_ai("Local model loaded. Ask me anything.\n"))
            except Exception as e:
                self._ui(lambda: self._set_status("Model load failed."))
                self._ui(lambda: self.send_btn.configure(state="normal"))
                self._ui(lambda: messagebox.showerror("Load failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _clear_chat(self):
        self.chat.delete("1.0", "end")
        self.history = []
        self._write_ai("Chat cleared.\n")

    def _enter_to_send(self, event):
        # Enter sends; Shift+Enter newline
        if event.state & 0x0001:  # shift
            return
        self._send_clicked()
        return "break"

    def _send_clicked(self):
        user_text = self.input.get("1.0", "end").strip()
        if not user_text:
            return
        self.input.delete("1.0", "end")

        self._write_user(user_text + "\n")
        self.send_btn.configure(state="disabled")
        self._set_status("Thinking…")

        def worker():
            try:
                if self.mode.get() == "local":
                    reply = self._infer_local(user_text)
                else:
                    reply = self._infer_api(user_text)

                self._ui(lambda: self._write_ai(reply + "\n"))
                self.history.append(("user", user_text))
                self.history.append(("assistant", reply))
                self._ui(lambda: self._set_status("Ready."))
            except Exception as e:
                self._ui(lambda: self._write_ai(f"⚠ Error: {e}\n"))
                self._ui(lambda: self._set_status("Error."))
            finally:
                self._ui(lambda: self.send_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- Inference ----------
    def _infer_local(self, user_text: str) -> str:
        if self.llm is None:
            raise RuntimeError("No local model loaded. Click Load after selecting a .gguf file.")

        prompt = self._build_prompt(user_text)
        out = self.llm(
            prompt,
            max_tokens=int(self.max_tokens.get()),
            temperature=float(self.temperature.get()),
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["\nUser:", "\nAssistant:"]
        )
        text = (out.get("choices", [{}])[0].get("text") or "").strip()
        return text or "(No output.)"

    def _infer_api(self, user_text: str) -> str:
        if not self.api_key:
            raise RuntimeError("No API key set. Click Set API Key.")
        if OpenAI is None or self.client is None:
            raise RuntimeError("openai library not installed. Run: pip install openai")

        messages = [{"role": "system", "content": "You are a helpful, concise assistant."}]
        # keep short context for speed
        compact = self._compact_history(max_turns=6)
        messages.extend(compact)
        messages.append({"role": "user", "content": user_text})

        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4,
            max_tokens=300
        )
        return (resp.choices[0].message.content or "").strip() or "(No output.)"

    def _compact_history(self, max_turns=6):
        # convert self.history -> messages, but cap it for speed
        msgs = []
        # self.history is [("user",..),("assistant",..),...]
        pairs = []
        i = 0
        while i + 1 < len(self.history):
            r1, c1 = self.history[i]
            r2, c2 = self.history[i+1]
            if r1 == "user" and r2 == "assistant":
                pairs.append((c1, c2))
            i += 2

        for u, a in pairs[-max_turns:]:
            msgs.append({"role": "user", "content": u})
            msgs.append({"role": "assistant", "content": a})
        return msgs

    def _build_prompt(self, user_text: str) -> str:
        # lag reducer: cap turns
        pairs = []
        i = 0
        while i + 1 < len(self.history):
            r1, c1 = self.history[i]
            r2, c2 = self.history[i+1]
            if r1 == "user" and r2 == "assistant":
                pairs.append((c1, c2))
            i += 2

        recent = pairs[-self.max_turns_keep:]

        p = "You are a helpful, concise assistant.\n"
        for u, a in recent:
            p += f"User: {u}\nAssistant: {a}\n"
        p += f"User: {user_text}\nAssistant:"
        return p

    # ---------- UI helpers ----------
    def _set_status(self, s: str):
        self.status.config(text=f"Status: {s}")

    def _write_user(self, text: str):
        self.chat.insert("end", "You\n", ("meta",))
        self.chat.insert("end", text, ("user",))
        self.chat.insert("end", "\n")
        self.chat.see("end")

    def _write_ai(self, text: str):
        self.chat.insert("end", "AI\n", ("meta",))
        self.chat.insert("end", text, ("ai",))
        self.chat.insert("end", "\n")
        self.chat.see("end")

    def _ui(self, fn):
        self.after(0, fn)


if __name__ == "__main__":
    app = AIGUI()
    app.mainloop()
