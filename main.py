import os
import json
import subprocess
import flet as ft
import tkinter as tk
from tkinter import filedialog
import zipfile
import shutil

CONFIG_FILE = "config.json"
STANDARD_PACKS_FILE = "standard_packs.txt"

# ---------------- helpers ----------------

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("game_path")
    return None

def save_config(path):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"game_path": path}, f, indent=4)

def select_game_folder():
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory(title="Выберите папку с игрой Total War: Warhammer II")
    return path if path else None

def load_standard_packs(file_path=STANDARD_PACKS_FILE):
    """Список файлов, которые не считаются модами"""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

def scan_mods(game_path):
    """Возвращает список модов (.pack), игнорируя стандартные файлы"""
    data_path = os.path.join(game_path, "data")
    if not os.path.exists(data_path):
        return []

    standard_files = set(load_standard_packs())
    mods = []
    for fname in os.listdir(data_path):
        if not fname.lower().endswith(".pack"):
            continue
        if fname in standard_files:
            continue
        name_no_ext = os.path.splitext(fname)[0]
        png_path = os.path.join(data_path, name_no_ext + ".png")
        mods.append((fname, png_path if os.path.exists(png_path) else None))
    return mods

def get_active_mods_set():
    user_script = os.path.expandvars(r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt")
    active = set()
    if os.path.exists(user_script):
        with open(user_script, "r", encoding="utf-8") as f:
            for line in f:
                ln = line.strip()
                if ln.startswith('mod "') and ln.endswith('";'):
                    try:
                        name = ln.split('"')[1]
                        active.add(name)
                    except Exception:
                        continue
    return active

def write_user_script_preserve(existing_lines, active_mods_set):
    existing_mod_lines = []
    other_lines = []
    for ln in existing_lines:
        if ln.strip().startswith('mod "') and ln.strip().endswith('";'):
            existing_mod_lines.append(ln)
        else:
            other_lines.append(ln)

    existing_mod_names = []
    existing_map = {}
    for ln in existing_mod_lines:
        try:
            name = ln.split('"')[1]
            existing_mod_names.append(name)
            existing_map[name] = ln
        except Exception:
            continue

    final_lines = []
    final_lines.extend(other_lines)

    for name in existing_mod_names:
        if name in active_mods_set:
            final_lines.append(existing_map[name])

    for name in sorted(active_mods_set):
        if name not in existing_map:
            final_lines.append(f'mod "{name}";')

    return final_lines

def add_pack_file(pack_path, game_path):
    data_path = os.path.join(game_path, "data")
    os.makedirs(data_path, exist_ok=True)
    shutil.copy(pack_path, data_path)
    # проверяем наличие PNG с таким же именем, если есть рядом с pack - копируем
    png_candidate = os.path.splitext(pack_path)[0] + ".png"
    if os.path.exists(png_candidate):
        shutil.copy(png_candidate, data_path)

def add_zip_archive(zip_path, game_path):
    data_path = os.path.join(game_path, "data")
    os.makedirs(data_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            filename = os.path.basename(member)
            if filename.lower().endswith(".pack") or filename.lower().endswith(".png"):
                target_path = os.path.join(data_path, filename)
                with open(target_path, "wb") as f_out:
                    f_out.write(zip_ref.read(member))

def delete_mod(mod_name, game_path):
    data_path = os.path.join(game_path, "data")
    mod_path = os.path.join(data_path, mod_name)
    png_path = os.path.join(data_path, os.path.splitext(mod_name)[0] + ".png")
    if os.path.exists(mod_path):
        os.remove(mod_path)
    if os.path.exists(png_path):
        os.remove(png_path)

# ---------------- UI ----------------

def main(page: ft.Page):
    page.title = "Total War: Warhammer II — Mod Manager"
    page.window_width = 900
    page.window_height = 600
    page.padding = 20

    game_path = load_config()
    path_valid = bool(game_path and os.path.exists(game_path))

    status = ft.Text(
        f"Папка с игрой ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌",
        size=14
    )

    mods_column = ft.Column(scroll="auto", expand=True, spacing=6)

    image_container = ft.Container(
        content=None,
        width=300,
        height=300,
        bgcolor="black",
        alignment=ft.alignment.center,
        border=ft.border.all(1, "gray")
    )

    active_mods_set = get_active_mods_set() if path_valid else set()

    def load_mod_list(e=None):
        mods_column.controls.clear()
        if not (game_path and os.path.exists(game_path)):
            page.update()
            return

        nonlocal active_mods_set
        active_mods_set = get_active_mods_set()

        mods = scan_mods(game_path)
        for mod_fname, png_path in mods:
            checked = (mod_fname in active_mods_set)

            def on_change(e, mod_name=mod_fname, png=png_path):
                if e.control.value:
                    active_mods_set.add(mod_name)
                else:
                    active_mods_set.discard(mod_name)
                if png and os.path.exists(png):
                    image_container.content = ft.Image(src=png, fit=ft.ImageFit.CONTAIN, width=300, height=300)
                else:
                    image_container.content = None
                page.update()

            def on_delete(e, mod_name=mod_fname):
                delete_mod(mod_name, game_path)
                active_mods_set.discard(mod_name)
                load_mod_list()

            cb = ft.Checkbox(label=mod_fname, value=checked, on_change=on_change)
            del_btn = ft.IconButton(icon="delete", on_click=on_delete, tooltip="Удалить мод")
            mods_column.controls.append(ft.Row(controls=[cb, del_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        page.update()

    if path_valid:
        load_mod_list()

    def choose_folder(e):
        nonlocal game_path, path_valid
        new_path = select_game_folder()
        if not new_path:
            return
        game_path = new_path
        save_config(game_path)
        path_valid = bool(game_path and os.path.exists(game_path))
        status.value = f"Папка с игрой ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌"
        load_mod_list()

    def save_changes(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text("Папка с игрой не указана!"))
            page.snack_bar.open = True
            page.update()
            return

        user_script = os.path.expandvars(r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt")
        os.makedirs(os.path.dirname(user_script), exist_ok=True)

        existing_lines = []
        if os.path.exists(user_script):
            with open(user_script, "r", encoding="utf-8") as f:
                existing_lines = [ln.rstrip("\n") for ln in f.readlines()]

        final_lines = write_user_script_preserve(existing_lines, active_mods_set)

        with open(user_script, "w", encoding="utf-8") as f:
            for ln in final_lines:
                f.write(ln + "\n")

        page.snack_bar = ft.SnackBar(ft.Text("Изменения сохранены ✅"))
        page.snack_bar.open = True
        page.update()
        load_mod_list()

    def refresh_action(e):
        load_mod_list()
        page.snack_bar = ft.SnackBar(ft.Text("Список модов обновлён 🔄"))
        page.snack_bar.open = True
        page.update()

    def launch_game(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text("Папка с игрой не указана!"))
            page.snack_bar.open = True
            page.update()
            return

        exe_path = os.path.join(game_path, "Warhammer2.exe")
        if not os.path.exists(exe_path):
            page.snack_bar = ft.SnackBar(ft.Text(f"Файл не найден: {exe_path}"))
            page.snack_bar.open = True
            page.update()
            return

        try:
            subprocess.Popen(f'start "" "{exe_path}"', shell=True, cwd=game_path)
            page.snack_bar = ft.SnackBar(ft.Text("Игра запущена 🎮"))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Ошибка при запуске: {ex}"))
            page.snack_bar.open = True
            page.update()

    def add_mod_file(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text("Укажите папку с игрой!"))
            page.snack_bar.open = True
            page.update()
            return

        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="Выберите мод (.pack или .zip)",
            filetypes=[("Pack файлы", "*.pack"), ("Zip архивы", "*.zip")]
        )
        if not file_path:
            return

        if file_path.lower().endswith(".pack"):
            add_pack_file(file_path, game_path)
        elif file_path.lower().endswith(".zip"):
            add_zip_archive(file_path, game_path)
        load_mod_list()

    # --- кнопки ---
    btn_save = ft.ElevatedButton("💾 Сохранить", on_click=save_changes, width=300, height=48)
    btn_refresh = ft.ElevatedButton("🔄 Обновить", on_click=refresh_action, width=300, height=48)
    btn_launch = ft.ElevatedButton("▶️ Запустить игру", on_click=launch_game, width=300, height=48)
    btn_add_mod = ft.ElevatedButton("➕ Добавить мод", on_click=add_mod_file, width=520, height=48)

    buttons_column = ft.Column(
        controls=[btn_add_mod, btn_save, btn_refresh, btn_launch],
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )

    right_panel = ft.Column(
        controls=[image_container, ft.Divider(height=18), buttons_column],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        width=320
    )

    mods_container = ft.Container(
        content=mods_column,
        border=ft.border.all(1, "white"),
        padding=10,
        width=520,
        height=page.window_height - 160
    )

    left_panel = ft.Column(
        controls=[ft.Text("Список модов:", size=16, weight="bold"), mods_container],
        expand=True
    )

    bottom_row = ft.Row(
        controls=[status, ft.ElevatedButton("Выбрать папку с игрой", on_click=choose_folder)],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

    main_row = ft.Row(controls=[left_panel, right_panel], expand=True, spacing=20)
    layout = ft.Column(controls=[main_row, ft.Divider(), bottom_row], expand=True)
    page.add(layout)

    if path_valid:
        load_mod_list()

ft.app(target=main)
