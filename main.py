import os
import sys
import threading
import asyncio
import webbrowser
import concurrent.futures
import fitz
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
import ctypes  
from pdf_engine import PDFEngine

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pdfreaper.v1.0")
except:
    pass

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TkinterDnD_CTk(ctk.CTk, TkinterDnD.DnDWrapper if HAS_DND else object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if HAS_DND:
            self.TkdndVersion = TkinterDnD._require(self)

class PDFReaperApp(TkinterDnD_CTk):
    def __init__(self):
        super().__init__()
        self.title("PDF REAPER v1.0")
        self.geometry("1050x850")
        
        self.base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        
        try:
            icon_path = os.path.join(self.base_path, "reap.ico")
            self.iconbitmap(icon_path)
        except:
            pass

        self.app_state = {'is_running': False, 'is_paused': False, 'is_cancelled': False}
        self.source_list = []
        self.comp_map = {0: 0, 1: 25, 2: 50, 3: 75, 4: 100}
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.setup_sidebar()
        self.setup_main_area()
        self.update_button_states()

        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.handle_drop)

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#2b2b2b")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="PDF REAPER", font=("Arial", 22, "bold"), text_color="white").pack(pady=(30, 0))
        ctk.CTkLabel(self.sidebar, text="Version 1.0", font=("Arial", 12, "italic"), text_color="#aaaaaa").pack(pady=(0, 10))
        
        btn_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_container.pack(expand=True, fill="both", pady=20)
        
        inner_btns = ctk.CTkFrame(btn_container, fg_color="transparent")
        inner_btns.place(relx=0.5, rely=0.5, anchor="center")

        self.btn_convert = ctk.CTkButton(inner_btns, text="Convert", font=("Arial", 18, "bold"), 
                                         fg_color="#f28c28", hover_color="#d67b22", height=45, command=self.action_convert)
        self.btn_convert.pack(pady=(10, 50), fill="x")

        self.btn_cancel = ctk.CTkButton(inner_btns, text="Cancel", font=("Arial", 16, "bold"), 
                                        fg_color="#c0392b", hover_color="#922b21", height=40, command=self.action_cancel)
        self.btn_cancel.pack(pady=10, fill="x")

        self.btn_refresh = ctk.CTkButton(inner_btns, text="Refresh", font=("Arial", 16, "bold"), 
                                         fg_color="#27ae60", hover_color="#1e8449", height=40, command=self.action_refresh)
        self.btn_refresh.pack(pady=10, fill="x")

        icon_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        icon_frame.pack(side="bottom", pady=30)
        
        try:
            github_path = os.path.join(self.base_path, "github.png")
            github_image = ctk.CTkImage(Image.open(github_path), size=(30, 30))

            lbl_github = ctk.CTkLabel(icon_frame, text="", image=github_image, cursor="hand2")
            lbl_github.pack(side="left", padx=15)
            lbl_github.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/moonlightspeed/PDF-Reaper/"))
        except:
            pass

    def setup_main_area(self):
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="#333333", corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=30, pady=20)

        ctk.CTkLabel(self.content_frame, text="1. INPUT SOURCE", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 5))
        input_btns = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        input_btns.pack(fill="x", pady=5)
        
        ctk.CTkButton(input_btns, text="Import websites list (.txt)", width=160, command=self.load_txt).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(input_btns, text="or").pack(side="left", padx=5)
        self.btn_select_files = ctk.CTkButton(input_btns, text="Select files or folders", width=140, command=self.show_select_menu)
        self.btn_select_files.pack(side="left", padx=10)
        ctk.CTkLabel(input_btns, text="or").pack(side="left", padx=5)
        ctk.CTkButton(input_btns, text="Quick paste links", width=140, fg_color="#8e44ad", hover_color="#732d91", command=self.open_quick_paste).pack(side="left", padx=10)

        if HAS_DND:
            ctk.CTkLabel(self.content_frame, text="(Tip: You can drag and drop HTML files directly into this window)", text_color="gray", font=("Arial", 12, "italic")).pack(anchor="w")

        ctk.CTkLabel(self.content_frame, text="2. PROCESSING OPTIONS", font=("Arial", 16, "bold")).pack(anchor="w", pady=(25, 5))
        
        self.var_merge = ctk.BooleanVar(value=False)
        self.cb_merge = ctk.CTkCheckBox(self.content_frame, text="Merge all files into one PDF", variable=self.var_merge, command=self.toggle_split_options)
        self.cb_merge.pack(anchor="w", pady=5)

        self.split_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.var_split = ctk.BooleanVar(value=False)
        self.cb_split = ctk.CTkCheckBox(self.split_frame, text="Split PDF after finish merging", variable=self.var_split)
        self.cb_split.pack(anchor="w", pady=(5,0))
        split_input_frame = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        split_input_frame.pack(anchor="w", padx=25, pady=5)
        self.entry_split = ctk.CTkEntry(split_input_frame, width=80, placeholder_text="e.g. 50")
        self.entry_split.pack(side="left")
        ctk.CTkLabel(split_input_frame, text="pages / 1 pdf").pack(side="left", padx=10)

        comp_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        comp_frame.pack(fill="x", pady=15)
        ctk.CTkLabel(comp_frame, text="Compression Level:").pack(side="left", padx=(0, 15))
        
        self.slider_comp = ctk.CTkSlider(comp_frame, from_=0, to=4, number_of_steps=4, width=180, command=self.update_comp_lbl)
        self.slider_comp.set(2)
        self.slider_comp.pack(side="left")
        
        self.lbl_comp_val = ctk.CTkLabel(comp_frame, text="50%", text_color="#1a918b", font=("Arial", 16, "bold"))
        self.lbl_comp_val.pack(side="left", padx=15)
        ctk.CTkButton(comp_frame, text="Quick compress PDFs", fg_color="#16a085", hover_color="#0e6655", command=self.quick_compress_pdfs).pack(side="left", padx=20)

        sys_cb_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        sys_cb_frame.pack(fill="x", pady=10)
        
        self.var_max_cpu = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sys_cb_frame, text="Maximize CPU usage", variable=self.var_max_cpu).pack(side="left", padx=(0, 20))

        self.var_open = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sys_cb_frame, text="Auto-open folder when finished", variable=self.var_open).pack(side="left", padx=(0, 20))
        
        self.var_shutdown = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sys_cb_frame, text="Shutdown computer when finished", variable=self.var_shutdown).pack(side="left")

        ctk.CTkLabel(self.content_frame, text="3. OUTPUT DESTINATION", font=("Arial", 16, "bold")).pack(anchor="w", pady=(20, 5))
        out_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        out_frame.pack(fill="x", pady=5)
        
        self.entry_out = ctk.CTkEntry(out_frame, placeholder_text="Output folder...", width=400, state="disabled")
        self.entry_out.pack(side="left", padx=(0, 10))
        ctk.CTkButton(out_frame, text="Select Output Folder", width=80, fg_color="transparent", border_width=1, command=self.select_out_dir).pack(side="left")

        self.prog_lbl = ctk.CTkLabel(self.content_frame, text="Progress: 0%", font=("Arial", 14, "bold"))
        self.prog_lbl.pack(anchor="w", pady=(20, 0))
        
        self.progress_bar = ctk.CTkProgressBar(self.content_frame, width=400)
        self.progress_bar.set(0)
        self.progress_bar.pack(anchor="w", pady=5)

        self.log_box = ctk.CTkTextbox(self.content_frame, height=250, fg_color="#1e1e1e", font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.log_box.configure(state="disabled")

    def safe_update_ui(self, func, *args, **kwargs):
        self.after(0, lambda: func(*args, **kwargs))

    def update_button_states(self):
        if self.app_state['is_running']:
            self.btn_cancel.configure(state="normal")
            self.btn_refresh.configure(state="disabled")
            self.btn_select_files.configure(state="disabled")
        else:
            self.btn_cancel.configure(state="disabled")
            self.btn_select_files.configure(state="normal")
            if len(self.source_list) > 0:
                self.btn_refresh.configure(state="normal")
            else:
                self.btn_refresh.configure(state="disabled")

    def _log_internal(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def log(self, text):
        self.safe_update_ui(self._log_internal, text)

    def _update_progress_internal(self, val):
        self.progress_bar.set(val)
        self.prog_lbl.configure(text=f"Progress: {int(val*100)}%")

    def update_progress(self, val):
        self.safe_update_ui(self._update_progress_internal, val)

    def handle_drop(self, event):
        files = self.split_dnd_files(event.data)
        added = 0
        for f in files:
            if f.endswith((".html", ".htm")):
                self.source_list.append(f"file://{f}")
                self.log(f"[INPUT] Loaded HTML: {os.path.basename(f)}")
                added += 1
        self.log(f"[INFO] {added} file(s) imported via Drag & Drop.")
        self.update_button_states()

    def split_dnd_files(self, data):
        if data.startswith('{'): return [f.strip('{}') for f in data.split('} {')]
        return data.split()

    def open_quick_paste(self):
        top = ctk.CTkToplevel(self)
        top.title("Paste Links")
        top.geometry("500x300")
        top.attributes('-topmost', True)
        
        ctk.CTkLabel(top, text="Paste URLs here (one per line):").pack(pady=10)
        txt = ctk.CTkTextbox(top, width=450, height=180)
        txt.pack()
        
        def save_links():
            links = [l.strip() for l in txt.get("1.0", "end").split("\n") if l.strip()]
            for l in links:
                self.source_list.append(l)
                self.log(f"[INPUT] Loaded URL: {l}")
            self.log(f"[INFO] {len(links)} link(s) added.")
            self.update_button_states()
            top.destroy()
            
        ctk.CTkButton(top, text="Import Links", command=save_links).pack(pady=10)

    def show_select_menu(self):
        menu = Menu(self, tearoff=0, font=("Segoe UI", 12))
        menu.add_command(label="Import Folder", command=self.load_folder)
        menu.add_separator()
        menu.add_command(label="Import Files", command=self.load_html_files)
        x = self.btn_select_files.winfo_rootx()
        y = self.btn_select_files.winfo_rooty() + self.btn_select_files.winfo_height() + 5
        menu.tk_popup(x, y)

    def toggle_split_options(self):
        if self.var_merge.get():
            self.split_frame.pack(anchor="w", pady=5, after=self.cb_merge)
        else:
            self.split_frame.pack_forget()

    def update_comp_lbl(self, val):
        percent = self.comp_map[int(val)]
        self.lbl_comp_val.configure(text=f"{percent}%")

    def load_txt(self):
        path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]
            for u in urls:
                self.source_list.append(u)
                self.log(f"[INPUT] Loaded URL from TXT: {u}")
            self.log(f"[INFO] {len(urls)} link(s) imported from TXT.")
            self.update_button_states()

    def load_html_files(self):
        files = filedialog.askopenfilenames(filetypes=[("HTML", "*.html *.htm")])
        if files:
            for f in files:
                paths = f"file://{os.path.abspath(f)}"
                self.source_list.append(paths)
                self.log(f"[INPUT] Loaded HTML: {os.path.basename(f)}")
            self.log(f"[INFO] {len(files)} local HTML file(s) imported.")
            self.update_button_states()

    def load_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            count = 0
            for root, dirs, files in os.walk(folder):
                dirs.sort(); files.sort()
                for file in files:
                    if file.endswith((".html", ".htm")):
                        self.source_list.append(f"file://{os.path.join(root, file)}")
                        self.log(f"[INPUT] Scanned: {file}")
                        count += 1
            self.log(f"[INFO] Directory scanned. {count} HTML file(s) found.")
            self.update_button_states()

    def select_out_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_out.configure(state="normal")
            self.entry_out.delete(0, "end")
            self.entry_out.insert(0, folder)
            self.entry_out.configure(state="disabled")

    def quick_compress_pdfs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")], title="Select PDFs to Compress")
        if not files: return
        level = self.comp_map[int(self.slider_comp.get())]
        use_max_cpu = self.var_max_cpu.get()
        
        self.log(f"\n[SYSTEM] Executing Quick Compress on {len(files)} file(s).")
        self.log(f"[INFO] Target compression level: {level}%")
        self.update_progress(0)
        
        threading.Thread(target=self._run_quick_compress, args=(files, level, use_max_cpu), daemon=True).start()

    def _compress_task(self, f, garbage_val, do_deflate):
        if self.app_state['is_cancelled']: return None
        try:
            out_name = f.replace(".pdf", "_compressed.pdf")
            doc = fitz.open(f)
            doc.save(out_name, garbage=garbage_val, deflate=do_deflate)
            doc.close()
            return f"[SUCCESS] Output generated: {os.path.basename(out_name)}"
        except Exception as e:
            return f"[ERROR] Failed: {str(e)}"

    def _run_quick_compress(self, files, comp_level, use_max_cpu):
        self.app_state['is_running'] = True
        self.safe_update_ui(self.update_button_states)
        
        garbage_val = 0; do_deflate = False
        if comp_level == 25: garbage_val, do_deflate = 1, True
        elif comp_level == 50: garbage_val, do_deflate = 2, True
        elif comp_level == 75: garbage_val, do_deflate = 3, True
        elif comp_level == 100: garbage_val, do_deflate = 4, True
        
        cpu_cores = os.cpu_count() or 4
        max_workers = cpu_cores if use_max_cpu else max(1, cpu_cores // 2)
        self.log(f"[INFO] Allocated CPU Threads: {max_workers}")
        
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._compress_task, f, garbage_val, do_deflate) for f in files]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result: self.log(f"  └── {result}")
                completed += 1
                self.update_progress(completed / len(files))
                
        self.log("\n[SUCCESS] Quick Compression sequence complete.")
        self.safe_update_ui(self.reset_ui)

    def action_convert(self):
        if not self.app_state['is_running']:
            if not self.source_list:
                messagebox.showerror("Error", "No input source selected!")
                return
            if not self.entry_out.get():
                messagebox.showerror("Error", "Output destination not set!")
                return

            if self.app_state.get('browser_ready', False):
                self.start_conversion_logic()
            else:
                self.app_state['is_running'] = True
                self.update_button_states()
                threading.Thread(target=self.check_and_install_browsers, daemon=True).start()
        else:
            self.app_state['is_paused'] = not self.app_state['is_paused']
            if self.app_state['is_paused']:
                self.log("\n[SYSTEM] Execution paused.")
                self.btn_convert.configure(text="Resume", fg_color="#f28c28")
            else:
                self.log("\n[SYSTEM] Execution resumed.")
                self.btn_convert.configure(text="Pause", fg_color="#1f538d")

    def check_and_install_browsers(self):
        try:
            self.log("[SYSTEM] Verifying browser engine...")
            
            from playwright.sync_api import sync_playwright
            missing = False
            try:
                with sync_playwright() as p:
                    browser_path = p.chromium.executable_path
                    if not os.path.exists(browser_path):
                        missing = True
            except Exception:
                missing = True

            if missing:
                self.safe_update_ui(self._prompt_for_download)
            else:
                self.app_state['browser_ready'] = True
                self.safe_update_ui(self.start_conversion_logic)
                
        except Exception as e:
            self.log(f"[FATAL] Browser verification failed: {e}")
            self.safe_update_ui(self.reset_ui)

    def _prompt_for_download(self):
        if messagebox.askyesno("Browser Missing", "Chromium engine is required but not found. Download it now? (Approx. 100-150MB)"):
            self.log("[SYSTEM] Downloading Chromium... Please wait.")
            threading.Thread(target=self._download_browser_thread, daemon=True).start()
        else:
            self.log("[ERROR] Execution aborted: Browser engine missing.")
            self.reset_ui()

    def _download_browser_thread(self):
        import subprocess
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            self.log("[SYSTEM] Chromium installed successfully.")
            self.app_state['browser_ready'] = True
            self.safe_update_ui(self.start_conversion_logic)
        except Exception as e:
            self.log(f"[ERROR] Failed to download Chromium: {e}")
            self.safe_update_ui(self.reset_ui)

    def start_conversion_logic(self):
        self.app_state['is_running'] = True
        self.app_state['is_paused'] = False
        self.app_state['is_cancelled'] = False
        self.btn_convert.configure(text="Pause", fg_color="#1f538d", hover_color="#14375e") 
        self.update_button_states()
        self.update_progress(0)
        self.log("\n=== EXECUTION STARTED ===")
        
        options = {
            'merge': self.var_merge.get(),
            'split': self.var_split.get(),
            'split_pages': int(self.entry_split.get() or 0) if self.var_split.get() else 0,
            'compression': self.comp_map[int(self.slider_comp.get())],
            'max_cpu': self.var_max_cpu.get()
        }
        out_dir = self.entry_out.get()
        
        threading.Thread(target=self.run_engine_thread, args=(self.source_list.copy(), out_dir, options), daemon=True).start()

    def run_engine_thread(self, sources, out_dir, options):
        engine = PDFEngine(self.app_state, self.log, self.update_progress)
        asyncio.run(engine.process_all(sources, out_dir, options))
        
        self.safe_update_ui(self.reset_ui)
        if not self.app_state['is_cancelled']:
            if self.var_open.get():
                os.startfile(out_dir) if sys.platform == "win32" else None
            
            if self.var_shutdown.get():
                self.log("[SYSTEM] Shutting down computer in 10 seconds...")
                if sys.platform == "win32": os.system("shutdown /s /t 10")

    def action_cancel(self):
        if messagebox.askyesno("Cancel", "Are you sure you want to abort the current process?"):
            self.app_state['is_cancelled'] = True
            self.log("\n[SYSTEM] Cancelling... Closing resources.")
            self.reset_ui()

    def action_refresh(self):
        if messagebox.askyesno("Refresh", "Clear all loaded files and logs?"):
            self.source_list.clear()
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")
            self.update_progress(0)
            self.log("[SYSTEM] Data reset. Ready for a new batch!")
            self.update_button_states()

    def reset_ui(self):
        self.app_state['is_running'] = False
        self.app_state['is_paused'] = False
        self.btn_convert.configure(text="Convert", fg_color="#f28c28", hover_color="#d67b22")
        self.update_button_states()

if __name__ == "__main__":
    app = PDFReaperApp()
    app.mainloop()