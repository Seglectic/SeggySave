import json, os, sys, zipfile, shutil, datetime
from pathlib import Path
from tkinter import Tk, filedialog, messagebox, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import ctypes


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)  # PyInstaller onefile temp dir
    return str(Path(base) / name)

## DPI Awareness stuff?
def set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # per-monitor v2 on Win 8.1+
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # Vista/7 fallback
        except Exception:
            pass


APP_NAME = "SeggySave - Abiotic Factor Edition"
CONF_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME
CONF_DIR.mkdir(parents=True, exist_ok=True)
CONF_FILE = CONF_DIR / "config.json"

def default_save_dir() -> Path:
    user = Path(os.environ.get("USERPROFILE", str(Path.home())))
    return user / "AppData" / "Local" / "AbioticFactor" / "Saved" / "SaveGames"

def load_dir() -> Path | None:
    if CONF_FILE.exists():
        try:
            d = Path(json.loads(CONF_FILE.read_text())["save_dir"])
            return d if d.exists() else None
        except Exception:
            return None
    return None

def save_dir(p: Path) -> None:
    CONF_FILE.write_text(json.dumps({"save_dir": str(p)}))

def ensure_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Couldn't create folder:\n{p}\n\n{e}")
        return False

def open_dir(p: Path) -> None:
    if not p.exists():
        if not ensure_dir(p): return
    os.startfile(p)  # Windows-only

def choose_dir(label) -> None:
    d = filedialog.askdirectory(title="Pick your save folder")
    if d:
        p = Path(d)
        if ensure_dir(p):
            save_dir(p)
            label.config(text=f"Save Dir: {p}")

def reset_to_default(label) -> None:
    p = default_save_dir()
    if ensure_dir(p):
        save_dir(p)
        label.config(text=f"Save Dir: {p}")

def backup_saves(p: Path) -> None:
    if not p.exists() or not any(p.iterdir()):
        messagebox.showinfo(APP_NAME, "Save folder is empty or missing.")
        return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = filedialog.asksaveasfilename(
        defaultextension=".zip",
        initialfile=f"AbioticFactor-Saves-{ts}.zip",
        filetypes=[("Zip files","*.zip")],
        title="Save backup as"
    )
    if not out: return
    try:
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(p):
                for f in files:
                    full = Path(root) / f
                    zf.write(full, full.relative_to(p))
        messagebox.showinfo(APP_NAME, f"Backup written:\n{out}")
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Backup failed:\n{e}")

def safe_extract(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        for m in zf.infolist():
            name = Path(m.filename)
            parts = [p for p in name.parts if p not in ("", ".", "..")]
            if not parts: continue
            out = dest.joinpath(*parts)
            if not str(out.resolve()).startswith(str(dest.resolve())):
                raise RuntimeError(f"Blocked unsafe path: {m.filename}")
        zf.extractall(dest)

def import_zip(p: Path) -> None:
    if not ensure_dir(p): return
    z = filedialog.askopenfilename(title="Choose save .zip", filetypes=[("Zip files","*.zip")])
    if not z: return
    try:
        if any(p.iterdir()):
            if not messagebox.askyesno(APP_NAME, f"Extract into:\n{p}\n\nExisting files may be overwritten. Continue?"):
                return
        safe_extract(Path(z), p)
        messagebox.showinfo(APP_NAME, f"Imported into:\n{p}")
    except zipfile.BadZipFile:
        messagebox.showerror(APP_NAME, "That file isn’t a valid .zip.")
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Import failed:\n{e}")

def current_dir() -> Path:
    p = load_dir()
    if p: return p
    d = default_save_dir()
    ensure_dir(d)
    save_dir(d)
    return d

# ---------- Worlds helpers ----------
def find_profiles(save_root: Path) -> list[Path]:
    """Return list of profile dirs (e.g., steamID) under SaveGames that contain a Worlds folder."""
    if not save_root.exists(): return []
    profiles = []
    for entry in save_root.iterdir():
        if entry.is_dir() and (entry / "Worlds").exists():
            profiles.append(entry)
    return profiles

def get_worlds_root(save_root: Path, profile_dir: Path | None = None) -> Path | None:
    """Return <profile>/Worlds, or None."""
    if profile_dir:
        wr = profile_dir / "Worlds"
        return wr if wr.exists() else None
    profiles = find_profiles(save_root)
    if len(profiles) == 1:
        return profiles[0] / "Worlds"
    elif len(profiles) > 1:
        # Caller will handle selection
        return None
    # No profiles; maybe game hasn’t created yet
    # Create a generic Worlds directly under SaveGames (fallback)
    wr = save_root / "Worlds"
    wr.mkdir(parents=True, exist_ok=True)
    return wr

def list_worlds(worlds_root: Path) -> list[str]:
    names = []
    if not worlds_root or not worlds_root.exists(): return names
    for entry in worlds_root.iterdir():
        if entry.is_dir():
            names.append(entry.name)
    return sorted(names)

def backup_world(worlds_root: Path, world_name: str) -> None:
    src = worlds_root / world_name
    if not src.exists():
        messagebox.showerror(APP_NAME, f"World not found:\n{src}")
        return
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = filedialog.asksaveasfilename(
        defaultextension=".zip",
        initialfile=f"AbioticFactor-World-{world_name}-{ts}.zip",
        filetypes=[("Zip files","*.zip")],
        title="Export world as"
    )
    if not out: return
    try:
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(src):
                for f in files:
                    full = Path(root) / f
                    zf.write(full, full.relative_to(src.parent))  # include folder name at top
        messagebox.showinfo(APP_NAME, f"World exported:\n{out}")
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Export failed:\n{e}")

def derive_single_top_folder(zip_path: Path) -> str | None:
    with zipfile.ZipFile(zip_path) as zf:
        top = set()
        for m in zf.infolist():
            parts = Path(m.filename).parts
            if parts:
                top.add(parts[0])
            if len(top) > 1:
                return None
        return next(iter(top)) if top else None

def import_world(worlds_root: Path, refresh_cb=None) -> None:
    if not ensure_dir(worlds_root): return
    z = filedialog.askopenfilename(title="Choose World .zip", filetypes=[("Zip files","*.zip")])
    if not z: return
    zip_path = Path(z)
    # Try to guess world folder name
    guess = None
    try:
        guess = derive_single_top_folder(zip_path)
        if guess and guess.lower().endswith(".txt"):  # edge case
            guess = None
    except Exception:
        pass
    world_name = simpledialog.askstring(APP_NAME, "World folder name:", initialvalue=(guess or "NewWorld"))
    if not world_name: return
    dest = worlds_root / world_name
    if dest.exists():
        if not messagebox.askyesno(APP_NAME, f"'{world_name}' exists. Overwrite?\n(This will delete the existing folder)"):
            return
        try:
            shutil.rmtree(dest)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Failed to remove existing folder:\n{e}")
            return
    try:
        dest.mkdir(parents=True, exist_ok=True)
        safe_extract(zip_path, dest.parent) if guess else safe_extract(zip_path, dest)
        # If guess was used and zip already contained the world folder, we extracted to parent
        # Ensure final folder is at 'dest'
        if guess and (dest.parent / guess) != dest:
            try:
                (dest.parent / guess).rename(dest)
            except Exception:
                pass
        messagebox.showinfo(APP_NAME, f"World imported:\n{dest}")
        if refresh_cb: refresh_cb()
    except zipfile.BadZipFile:
        messagebox.showerror(APP_NAME, "That file isn’t a valid .zip.")
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Import failed:\n{e}")

# ---------- UI ----------
def main():
    root = tb.Window(themename="darkly")
    root.title(APP_NAME)
    root.resizable(False, False)
    # root.iconbitmap("spagnet.ico")
    try:
     root.iconbitmap(resource_path("spagnet.ico"))
    except Exception:
     pass

    curr = current_dir()
    hdr = tb.Label(root, text=f"Save Dir: {curr}", anchor="w", justify="left", padding=(12, 8))
    hdr.pack(fill="x")

    # Profile selector (steamID) if multiple
    profiles = find_profiles(curr)
    sel_profile = {"path": profiles[0] if profiles else None}

    # --- Top actions ---
    topbar = tb.Frame(root)
    topbar.pack(fill="x", padx=12, pady=(0,4))

    tb.Button(topbar, text="Open Save Folder",
              bootstyle="primary", padding=(10, 8),
              command=lambda: open_dir(current_dir())
    ).pack(side="left", expand=True, fill="x", padx=(0,6))

    tb.Button(topbar, text="Restore Entire Save Directory (.zip)",
              bootstyle="success", padding=(10, 8),
              command=lambda: import_zip(current_dir())
    ).pack(side="left", expand=True, fill="x")

    # --- Backup button on its own line ---
    tb.Button(root, text="Backup Entire Save Directory (.zip)",
              bootstyle="info", padding=(10, 8),
              command=lambda: backup_saves(current_dir())
    ).pack(fill="x", padx=12, pady=(0,8))

    # --- Row: folder pick/reset ---
    row = tb.Frame(root); row.pack(fill="x", padx=12, pady=8)
    tb.Button(row, text="Change Folder…",
              bootstyle="secondary", padding=(8, 6),
              command=lambda: (choose_dir(hdr), refresh_all())
    ).pack(side="left", expand=True, fill="x", padx=(0,6))
    tb.Button(row, text="Reset to Abiotic Factor Default",
              bootstyle="secondary", padding=(8, 6),
              command=lambda: (reset_to_default(hdr), refresh_all())
    ).pack(side="left", expand=True, fill="x")

    # Profile selector UI (if multiple)
    prof_frame = tb.Frame(root); prof_frame.pack(fill="x", padx=12, pady=(0,8))
    prof_combo = None
    prof_label = tb.Label(prof_frame, text="Profile:", padding=(0, 6))
    prof_label.pack(side="left")
    import ttkbootstrap as _tb  # for Combobox
    prof_combo = _tb.Combobox(prof_frame, state="readonly", width=24)
    prof_combo.pack(side="left", padx=(6,0))
    def load_profiles_into_combo():
        nonlocal profiles, sel_profile
        profiles = find_profiles(current_dir())
        if not profiles:
            sel_profile["path"] = None
            prof_combo["values"] = []
            prof_combo.set("")
            prof_label.configure(text="Profile: (none)")
        elif len(profiles) == 1:
            sel_profile["path"] = profiles[0]
            prof_combo["values"] = [profiles[0].name]
            prof_combo.current(0)
            prof_label.configure(text="Profile:")
        else:
            vals = [p.name for p in profiles]
            prof_combo["values"] = vals
            if sel_profile["path"] in profiles:
                prof_combo.set(sel_profile["path"].name)
            else:
                prof_combo.current(0)
                sel_profile["path"] = profiles[0]
            prof_label.configure(text="Profile:")
    def on_profile_change(event=None):
        sel = prof_combo.get()
        for p in profiles:
            if p.name == sel:
                sel_profile["path"] = p
                break
        refresh_world_list()

    prof_combo.bind("<<ComboboxSelected>>", on_profile_change)

    # Worlds section
    worlds_box = tb.Labelframe(root, text="Worlds", padding=8)
    worlds_box.pack(fill="x", padx=12, pady=(0,12))
    worlds_frame = tb.Frame(worlds_box)
    worlds_frame.pack(fill="x")

    # Import World button (full width under worlds list)
    tb.Button(
        worlds_box,
        text="Import World (.zip)",
        bootstyle="warning-outline",
        padding=(10, 8),
        command=lambda: import_world(get_worlds_root(current_dir(), sel_profile["path"]), refresh_world_list)
    ).pack(fill="x", padx=4, pady=(8,0))

    def refresh_world_list():
        for child in worlds_frame.winfo_children():
            child.destroy()
        save_root = current_dir()
        wr = get_worlds_root(save_root, sel_profile["path"])
        if not wr or not wr.exists():
            tb.Label(worlds_frame, text="No Worlds folder found yet.", padding=(4,4)).pack(anchor="w")
            return
        worlds = list_worlds(wr)
        if not worlds:
            tb.Label(worlds_frame, text="No worlds detected.", padding=(4,4)).pack(anchor="w")
            return
        for name in worlds:
            row = tb.Frame(worlds_frame)
            row.pack(fill="x", pady=3)
            tb.Label(
                row,
                text=name,
                anchor="w",
                font=("TkDefaultFont", 11, "bold")
            ).pack(side="left", expand=True, fill="x")
            tb.Button(row, text="Export as .zip",
                      bootstyle="primary", padding=(8,6),
                      command=lambda n=name: backup_world(wr, n)
            ).pack(side="right")

    def refresh_all():
        hdr.config(text=f"Save Dir: {current_dir()}")
        load_profiles_into_combo()
        
        # --- Auto-refresh worlds on folder changes (polling) ---
    last_sig = {"val": None}

    def worlds_signature():
        save_root = current_dir()
        wr = get_worlds_root(save_root, sel_profile["path"])
        if not wr or not wr.exists():
            return ("none", ())
        names_mtime = []
        try:
            with os.scandir(wr) as it:
                for e in it:
                    if e.is_dir():
                        # include folder name + mtime (rounded) so create/rename/modify triggers
                        mtime = int(e.stat().st_mtime)
                        names_mtime.append((e.name, mtime))
        except FileNotFoundError:
            return ("none", ())
        names_mtime.sort()
        return (str(wr), tuple(names_mtime))

    def watch_worlds():
        sig = worlds_signature()
        if sig != last_sig["val"]:
            last_sig["val"] = sig
            refresh_world_list()
        root.after(1500, watch_worlds)  # ~1.5s poll

    # ensure manual folder/profile changes force a refresh on next tick
    def refresh_all_and_invalidate():
        last_sig["val"] = None
        refresh_all()

    # wire the invalidate helper where you change folders/profiles:
    # Change Folder…
    for child in row.winfo_children():
        pass  # existing buttons already created above
    # Replace the two existing commands with these:
    # Change Folder…
    row_slaves = row.pack_slaves()  # [ResetBtn, ChangeBtn] or vice-versa depending on creation order
    # safer: rebuild them quickly


    load_profiles_into_combo()
    refresh_world_list()

    # Center on primary display
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    watch_worlds()
    root.mainloop()

if __name__ == "__main__":
    set_dpi_awareness()
    main()