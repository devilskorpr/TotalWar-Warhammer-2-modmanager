import os
import json
import subprocess
import flet as ft
import tkinter as tk
from tkinter import filedialog

CONFIG_FILE = "config.json"


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


def scan_mods(game_path):
    data_path = os.path.join(game_path, "data")
    if not os.path.exists(data_path):
        return []
    mods = []
    for fname in os.listdir(data_path):
        if fname.lower().endswith(".pack"):
            name_no_ext = os.path.splitext(fname)[0]
            png_path = os.path.join(data_path, name_no_ext + ".png")
            if os.path.exists(png_path):
                mods.append((fname, png_path))
    return mods


def get_active_mods_set():
    user_script = os.path.expandvars(r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt")
    active = []
    if os.path.exists(user_script):
        with open(user_script, "r", encoding="utf-8") as f:
            for line in f:
                ln = line.strip()
                if ln.startswith('mod "') and ln.endswith('";'):
                    try:
                        name = ln.split('"')[1]
                        active.append(name)
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

    active_mods_ordered = get_active_mods_set() if path_valid else []
    active_mods_set = set(active_mods_ordered)

    def load_mod_list(e=None):
        nonlocal active_mods_ordered, active_mods_set
        mods_column.controls.clear()
        if not (game_path and os.path.exists(game_path)):
            page.update()
            return

        active_mods_ordered = get_active_mods_set()
        active_mods_set = set(active_mods_ordered)

        mods = scan_mods(game_path)
        for mod_fname, png_path in mods:
            checked = (mod_fname in active_mods_set)

            def on_change(e, mod_name=mod_fname, png=png_path):
                if e.control.value:
                    active_mods_set.add(mod_name)
                else:
                    active_mods_set.discard(mod_name)
                image_container.content = ft.Image(src=png, fit=ft.ImageFit.CONTAIN, width=300, height=300)
                page.update()

            cb = ft.Checkbox(label=mod_fname, value=checked, on_change=on_change)
            mods_column.controls.append(cb)
        page.update()

    if path_valid:
        load_mod_list()

    def choose_folder(e):
        nonlocal game_path, path_valid, active_mods_ordered, active_mods_set
        new_path = select_game_folder()
        if not new_path:
            return
        game_path = new_path
        save_config(game_path)
        path_valid = bool(game_path and os.path.exists(game_path))
        status.value = f"Папка с игрой ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌"
        active_mods_ordered = get_active_mods_set() if path_valid else []
        active_mods_set = set(active_mods_ordered)
        load_mod_list()

    def save_changes(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text("Папка с игрой не указана или не существует!"))
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

    # === ЗАПУСК ИГРЫ через CMD ===
    def launch_game(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text("Папка с игрой не указана или не существует!"))
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
            # Переходим в директорию игры и запускаем через start "" "<путь>"
            subprocess.Popen(
                f'start "" "{exe_path}"',
                shell=True,
                cwd=game_path
            )
            page.snack_bar = ft.SnackBar(ft.Text("Игра запущена 🎮"))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Ошибка при запуске: {ex}"))
            page.snack_bar.open = True
            page.update()


    # --- кнопки ---
    btn_save = ft.ElevatedButton("💾 Сохранить", on_click=save_changes, width=300, height=48)
    btn_refresh = ft.ElevatedButton("🔄 Обновить", on_click=refresh_action, width=300, height=48)
    btn_launch = ft.ElevatedButton("▶️ Запустить игру", on_click=launch_game, width=300, height=48)

    buttons_column = ft.Column(
        controls=[btn_save, btn_refresh, btn_launch],
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
