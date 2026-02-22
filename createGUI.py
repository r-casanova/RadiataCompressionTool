### this GUI is ai generated


import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from pathlib import Path

from RadiataCompressionTool import (
    MODE_DISPLAY, COMPRESSION_MODES,
    start_compression, start_decompression
)

def launch_gui():
    root = tk.Tk()
    root.title("RADIATA STORIES - SLZ/SLE Compression Tool")
    root.geometry("980x740")
    root.configure(bg="#C0C0C0")
    root.resizable(True, True)

    # Classic Windows 98/2000 look
    style = ttk.Style(root)
    try:
        style.theme_use('classic')
    except:
        style.theme_use('default')

    style.configure(".", background="#C0C0C0", foreground="#000000", font=("Courier New", 10))
    style.configure("TNotebook", background="#C0C0C0")
    style.configure("TNotebook.Tab", padding=[12, 5], font=("Courier New", 10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", "#A0A0A0")])

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    # Retro header function
    def create_retro_header(parent, text):
        header = tk.Label(parent, text=text, font=("Courier New", 14, "bold"),
                          bg="#000080", fg="#FFFFFF", relief="raised", bd=3, pady=8)
        header.pack(fill="x", pady=(0, 10))

    # ====================== COMPRESS TAB ======================
    compress_tab = ttk.Frame(notebook)
    notebook.add(compress_tab, text=" COMPRESS ")

    create_retro_header(compress_tab, "   RADIATA COMPRESSION TOOL v1.0   ")

    ttk.Label(compress_tab, text="Input Raw Files:", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(5, 2))

    files_frame = ttk.Frame(compress_tab)
    files_frame.pack(fill="both", expand=True, padx=12, pady=2)

    input_listbox = tk.Listbox(files_frame, selectmode="extended", height=9,
                               bg="#FFFFFF", fg="#000000", font=("Courier New", 10), relief="sunken", bd=3)
    input_listbox.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=input_listbox.yview)
    scrollbar.pack(side="right", fill="y")
    input_listbox.config(yscrollcommand=scrollbar.set)

    btn_frame = tk.Frame(compress_tab, bg="#C0C0C0")
    btn_frame.pack(fill="x", padx=12, pady=6)

    def add_input_files():
        files = filedialog.askopenfilenames(title="Select Raw Files to Compress")
        for f in files:
            if f not in input_listbox.get(0, "end"):
                input_listbox.insert("end", f)

    def remove_input_files():
        for i in reversed(input_listbox.curselection()):
            input_listbox.delete(i)

    tk.Button(btn_frame, text="➕ Add Files", command=add_input_files, relief="raised", bd=3,
              bg="#C0C0C0", activebackground="#A0A0A0", font=("Courier New", 10)).pack(side="left", padx=4)
    tk.Button(btn_frame, text="🗑 Remove Selected", command=remove_input_files, relief="raised", bd=3,
              bg="#C0C0C0", activebackground="#A0A0A0", font=("Courier New", 10)).pack(side="left", padx=4)
    tk.Button(btn_frame, text="Clear All", command=lambda: input_listbox.delete(0, "end"), relief="raised", bd=3,
              bg="#C0C0C0", activebackground="#A0A0A0", font=("Courier New", 10)).pack(side="left", padx=4)

    ttk.Label(compress_tab, text="Compression Mode (for all files):", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(12, 2))
    mode_var = tk.StringVar(value=MODE_DISPLAY[3])
    mode_combo = ttk.Combobox(compress_tab, textvariable=mode_var, values=list(MODE_DISPLAY.values()),
                              state="readonly", font=("Courier New", 10), width=50)
    mode_combo.pack(fill="x", padx=12)

    # ──────── SINGLE CHAIN TOGGLE (default = individual files) ────────
    ttk.Label(compress_tab, text="Output Options:", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(15, 5))

    chain_var = tk.BooleanVar(value=False)   # False = individual (default)

    tk.Checkbutton(compress_tab, text="Chained archive",
                   variable=chain_var, bg="#C0C0C0", font=("Courier New", 10), anchor="w").pack(anchor="w", padx=20, pady=4)

    sle_var = tk.BooleanVar(value=False)
    tk.Checkbutton(compress_tab, text="Encrypt as .SLE",
                   variable=sle_var, bg="#C0C0C0", font=("Courier New", 10), anchor="w").pack(anchor="w", padx=20, pady=2)

    output_frame = tk.Frame(compress_tab, bg="#C0C0C0")
    output_frame.pack(fill="x", padx=12, pady=8)

    output_path_var = tk.StringVar()
    tk.Label(output_frame, text="Output Path:", bg="#C0C0C0", font=("Courier New", 10)).pack(side="left")
    tk.Entry(output_frame, textvariable=output_path_var, font=("Courier New", 10), width=65, relief="sunken", bd=3).pack(side="left", padx=8, fill="x", expand=True)

    def browse_output():
        if chain_var.get():   # chained
            ext = ".sle" if sle_var.get() else ".slz"
            f = filedialog.asksaveasfilename(
                title="Save Chained Archive",
                defaultextension=ext,
                filetypes=[("SLZ/SLE Archive", "*.slz *.sle"), ("All Files", "*.*")]
            )
            if f: output_path_var.set(f)
        else:                 # individual → folder
            d = filedialog.askdirectory(title="Select Output Folder")
            if d: output_path_var.set(d)

    tk.Button(output_frame, text="Browse...", command=browse_output, relief="raised", bd=3,
              bg="#C0C0C0", activebackground="#A0A0A0", font=("Courier New", 10)).pack(side="left", padx=5)

    # ──────── LIVE PROGRESS + CONSOLE ────────
    ttk.Label(compress_tab, text="Live Progress:", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(10,2))
    
    current_status = tk.StringVar(value="Idle - Ready to compress")
    tk.Label(compress_tab, textvariable=current_status, font=("Courier New", 10), bg="#C0C0C0", fg="#006400", relief="sunken", bd=2, anchor="w", padx=8).pack(fill="x", padx=12, pady=2)
    
    progress_bar = ttk.Progressbar(compress_tab, length=720, mode='determinate')
    progress_bar.pack(fill="x", padx=12, pady=4)

    ttk.Label(compress_tab, text="Console Output / Stats:", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(8,2))
    
    console_frame = ttk.Frame(compress_tab)
    console_frame.pack(fill="both", expand=True, padx=12, pady=2)
    
    console = tk.Text(console_frame, height=14, bg="#001100", fg="#00FF80", font=("Courier New", 9), relief="sunken", bd=3)
    console.pack(side="left", fill="both", expand=True)
    console_scroll = ttk.Scrollbar(console_frame, orient="vertical", command=console.yview)
    console_scroll.pack(side="right", fill="y")
    console.config(yscrollcommand=console_scroll.set)

    # ──────── RUN COMPRESSION (uses chain_var only) ────────
    def run_compression():
        files = list(input_listbox.get(0, "end"))
        if not files:
            messagebox.showerror("Error", "Add at least one input file")
            return
        out_path = output_path_var.get().strip()
        if not out_path:
            messagebox.showerror("Error", "Choose an output path")
            return

        try:
            mode_name = mode_var.get()
            mode = next(k for k, v in MODE_DISPLAY.items() if v == mode_name)
        except StopIteration:
            messagebox.showerror("Error", "Invalid mode")
            return

        modes = [mode] * len(files)
        chain = chain_var.get()          # ←←← ONLY this line now

        if chain:
            output_paths = [out_path]
        else:
            ext = ".sle" if sle_var.get() else ".slz"
            output_paths = [os.path.join(out_path, Path(f).stem + ext) for f in files]

        # Reset UI
        console.delete("1.0", "end")
        progress_bar.configure(value=0)
        current_status.set("Starting compression...")

        def gui_log(text):
            root.after(0, lambda t=text: [console.insert("end", t + "\n"), console.see("end")])

        def gui_progress(percent, msg):
            root.after(0, lambda: progress_bar.configure(value=percent))
            root.after(0, lambda m=msg: current_status.set(m[:90]))

        def thread_target():
            try:
                start_compression(files, modes, output_paths, chain, log_func=gui_log, progress_callback=gui_progress)
                root.after(0, lambda: messagebox.showinfo("Success", "Compression complete!\nCheck the console below for full stats."))
                root.after(0, lambda: current_status.set("✓ All done!"))
            except Exception as e:
                root.after(0, lambda err=str(e): [messagebox.showerror("Error", err), current_status.set("ERROR: " + err[:60])])

        threading.Thread(target=thread_target, daemon=True).start()
        messagebox.showinfo("Running", "Compression started!\nWatch the progress bar and console.")

    # tk.Button(compress_tab, text="START COMPRESSION", command=run_compression, relief="raised", bd=5,
    #           bg="#C0C0C0", activebackground="#00FF00", font=("Courier New", 12, "bold"), height=2).pack(pady=12)
    tk.Button(compress_tab, text="START COMPRESSION", command=run_compression, relief="raised", bd=5,
            bg="#C0C0C0", activebackground="#00FF00", font=("Courier New", 12, "bold"), height=2).pack(pady=18)

    # ====================== DECOMPRESS TAB ======================
    decompress_tab = ttk.Frame(notebook)
    notebook.add(decompress_tab, text=" DECOMPRESS ")

    create_retro_header(decompress_tab, "   RADIATA DECOMPRESSION TOOL v1.0   ")

    ttk.Label(decompress_tab, text="Input SLZ / SLE Files:", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(5, 2))

    decomp_listbox = tk.Listbox(decompress_tab, selectmode="extended", height=10,
                                bg="#FFFFFF", fg="#000000", font=("Courier New", 10), relief="sunken", bd=3)
    decomp_listbox.pack(fill="both", expand=True, padx=12, pady=5)

    d_btn_frame = tk.Frame(decompress_tab, bg="#C0C0C0")
    d_btn_frame.pack(fill="x", padx=12, pady=6)

    def add_decomp_files():
        files = filedialog.askopenfilenames(title="Select SLZ/SLE Files", filetypes=[("SLZ/SLE", "*.slz *.sle"), ("All", "*.*")])
        for f in files:
            if f not in decomp_listbox.get(0, "end"):
                decomp_listbox.insert("end", f)

    tk.Button(d_btn_frame, text="➕ Add Files", command=add_decomp_files, relief="raised", bd=3,
              bg="#C0C0C0", font=("Courier New", 10)).pack(side="left", padx=4)
    tk.Button(d_btn_frame, text="🗑 Remove Selected", command=lambda: [decomp_listbox.delete(i) for i in reversed(decomp_listbox.curselection())],
              relief="raised", bd=3, bg="#C0C0C0", font=("Courier New", 10)).pack(side="left", padx=4)
    tk.Button(d_btn_frame, text="Clear All", command=lambda: decomp_listbox.delete(0, "end"), relief="raised", bd=3,
              bg="#C0C0C0", font=("Courier New", 10)).pack(side="left", padx=4)

    ttk.Label(decompress_tab, text="Output Directory:", font=("Courier New", 10, "bold"), background="#C0C0C0").pack(anchor="w", padx=12, pady=(12, 2))

    decomp_out_var = tk.StringVar()
    decomp_out_frame = tk.Frame(decompress_tab, bg="#C0C0C0")
    decomp_out_frame.pack(fill="x", padx=12)

    tk.Entry(decomp_out_frame, textvariable=decomp_out_var, font=("Courier New", 10), relief="sunken", bd=3).pack(side="left", fill="x", expand=True, padx=(0, 8))
    tk.Button(decomp_out_frame, text="Browse Folder", command=lambda: decomp_out_var.set(filedialog.askdirectory() or decomp_out_var.get()),
              relief="raised", bd=3, bg="#C0C0C0", font=("Courier New", 10)).pack(side="left")

    # ──────── DECOMPRESSION RUN FUNCTION ────────
    def run_decompression():
        files = list(decomp_listbox.get(0, "end"))
        if not files:
            messagebox.showerror("Error", "Add at least one SLZ/SLE file")
            return
        out_dir = decomp_out_var.get().strip()
        if not out_dir:
            messagebox.showerror("Error", "Select an output directory")
            return

        def thread_target():
            try:
                start_decompression(files, out_dir)
                root.after(0, lambda: messagebox.showinfo("Success",
                    f"Decompression finished!\n\nFiles saved to:\n{out_dir}"))
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=thread_target, daemon=True).start()
        messagebox.showinfo("Running", "Decompression started in background.\nWatch the terminal for details.")

    tk.Button(decompress_tab, text="START DECOMPRESSION", command=run_decompression, relief="raised", bd=5,
              bg="#C0C0C0", activebackground="#00FF00", font=("Courier New", 12, "bold"), height=2).pack(pady=25)

    root.mainloop()

if __name__ == "__main__":
    launch_gui()