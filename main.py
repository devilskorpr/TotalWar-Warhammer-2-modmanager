import os
import json
import flet as ft
import tkinter as tk
from tkinter import filedialog
import subprocess

CONFIG_FILE = "config.json"

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
    """Возвращает список модов с соответствующими PNG-картинками"""
    data_path = os.path.join(game_path, "data")
    if not os.path.exists(data_path):
        return []

    mods_with_images = []
    for f_name in os.listdir(data_path):
        if f_name.endswith(".pack"):
            name_without_ext = os.path.splitext(f_name)[0]
            png_path = os.path.join(data_path, name_without_ext + ".png")
            if os.path.exists(png_path):
                mods_with_images.append((f_name, png_path))
    return mods_with_images

def get_active_mods():
    """Возвращает множество имён активных модов .pack"""
    user_script_path = os.path.expandvars(
        r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt"
    )
    active_mods = set()
    if os.path.exists(user_script_path):
        with open(user_script_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith('mod "') and line.endswith('";'):
                    mod_name = line[5:-2]  # берем только имя модификации
                    active_mods.add(mod_name)
    return active_mods

def main(page: ft.Page):
    page.title = "Total War: Warhammer II Mod Manager"
    page.window_width = 900
    page.window_height = 600
    page.padding = 20

    game_path = load_config()
    path_valid = False
    if game_path and os.path.exists(game_path):
        path_valid = True
    else:
        game_path = None

    status = ft.Text(
        f"Папка с игрой указана ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌",
        size=14
    )

    mods_column = ft.Column(scroll="auto", expand=True, spacing=5)

    image_container = ft.Container(
        width=250,
        height=250,
        bgcolor="black",
        alignment=ft.alignment.center,
        border=ft.border.all(1, "gray")
    )

    def update_mods_list(e=None):
        mods_column.controls.clear()
        if game_path:
            active_mods = get_active_mods()
            for mod_name, png_path in scan_mods(game_path):
                is_active = mod_name in active_mods
                cb = ft.Checkbox(label=mod_name, value=is_active)

                def on_select(e, img_path=png_path):
                    image_container.content = ft.Image(
                        src=img_path,
                        fit=ft.ImageFit.CONTAIN,
                        width=250,
                        height=250
                    )
                    page.update()

                cb.on_change = on_select
                mods_column.controls.append(cb)
        page.update()

    if path_valid:
        update_mods_list()

    def choose_folder(e):
        nonlocal game_path, path_valid
        new_path = select_game_folder()
        if new_path:
            game_path = new_path
            save_config(game_path)
            path_valid = os.path.exists(game_path)
            status.value = f"Папка с игрой указана ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌"
            update_mods_list()

    choose_button = ft.ElevatedButton("Выбрать папку с игрой", on_click=choose_folder)

    def save_selected_mods(e):
        if not game_path:
            return

        user_script_path = os.path.expandvars(
            r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt"
        )

        existing_lines = []
        if os.path.exists(user_script_path):
            with open(user_script_path, "r", encoding="utf-8") as f:
                existing_lines = [line.rstrip("\n") for line in f.readlines()]

        # Текущее состояние модов
        existing_mods = {line[5:-2]: line for line in existing_lines if line.startswith('mod "') and line.endswith('";')}

        # Обновляем строки по чекбоксам
        for cb in mods_column.controls:
            if isinstance(cb, ft.Checkbox):
                mod_line = f'mod "{cb.label}";'
                if cb.value:
                    if cb.label not in existing_mods:
                        existing_lines.append(mod_line)
                        existing_mods[cb.label] = mod_line
                else:
                    if cb.label in existing_mods:
                        existing_lines.remove(existing_mods[cb.label])
                        del existing_mods[cb.label]

        # Записываем обратно
        with open(user_script_path, "w", encoding="utf-8") as f:
            for line in existing_lines:
                f.write(line + "\n")

        page.snack_bar = ft.SnackBar(ft.Text("Моды успешно сохранены!"))
        page.snack_bar.open = True
        page.update()

        update_mods_list()

    def launch_game(e):
        if not game_path or not os.path.exists(game_path):
            page.snack_bar = ft.SnackBar(ft.Text("Папка с игрой не указана или не существует!"))
            page.snack_bar.open = True
            page.update()
            return

        exe_path = os.path.join(game_path, "Warhammer2.exe")
        if not os.path.exists(exe_path):
            page.snack_bar = ft.SnackBar(ft.Text("Файл Warhammer2.exe не найден в папке игры!"))
            page.snack_bar.open = True
            page.update()
            return

        try:
            # На Windows лучше использовать shell=True и полный путь
            subprocess.Popen(f'"{exe_path}"', shell=True)
            page.snack_bar = ft.SnackBar(ft.Text("Игра запущена!"))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Ошибка при запуске игры: {ex}"))
            page.snack_bar.open = True
            page.update()


    refresh_button = ft.ElevatedButton("🔄 Обновить", width=250, height=50, on_click=update_mods_list)
    save_button = ft.ElevatedButton("💾 Сохранить", width=250, height=50, on_click=save_selected_mods)
    launch_button = ft.ElevatedButton("▶️ Запустить игру", width=250, height=50, on_click=launch_game)

    buttons_column = ft.Column(
        controls=[refresh_button, save_button, launch_button],
        spacing=10,
        alignment=ft.MainAxisAlignment.CENTER
    )

    right_column = ft.Column(
        controls=[image_container, buttons_column],
        width=page.window_width * 0.35,
        spacing=20
    )

    mods_container = ft.Container(
        content=mods_column,
        border=ft.border.all(1, "black"),
        padding=10,
        width=page.window_width * 0.63,
        height=page.window_height - 120,
    )

    bottom_row = ft.Row(
        controls=[status, choose_button],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.END
    )

    main_row = ft.Row(
        controls=[mods_container, right_column],
        spacing=20,
        expand=True
    )

    layout = ft.Column(
        controls=[
            ft.Text("Список Модов:", size=16, weight="bold"),
            main_row,
            bottom_row
        ],
        expand=True
    )

    page.add(layout)

ft.app(target=main)
