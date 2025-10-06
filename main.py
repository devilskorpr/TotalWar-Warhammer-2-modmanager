import os
import json
import flet as ft
import tkinter as tk
from tkinter import filedialog

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

def load_standard_packs(file_path="standard_packs.txt"):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]
    

def get_active_mods():
    user_script = os.path.expandvars(r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt")
    active_mods = set()
    if os.path.exists(user_script):
        with open(user_script, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and line.endswith(".pack"):
                    # оставляем только имя файла, без пути
                    active_mods.add(os.path.basename(line))
    return active_mods


def scan_mods(game_path):
    """
    Возвращает список модов (.pack), для которых есть соответствующая .png картинка
    в той же папке data/mods_images (или в той же папке, если картинки рядом с .pack)
    """
    data_path = os.path.join(game_path, "data")
    if not os.path.exists(data_path):
        return []

    all_packs = [f for f in os.listdir(data_path) if f.endswith(".pack")]

    # Проверяем наличие картинки для каждого мода
    mods_with_image = []
    for pack in all_packs:
        name_without_ext = os.path.splitext(pack)[0]
        png_path = os.path.join(data_path, name_without_ext + ".png")
        if os.path.exists(png_path):
            mods_with_image.append(pack)

    return mods_with_image

def main(page: ft.Page):
    page.title = "Total War: Warhammer II Mod Manager"
    page.window_width = 600
    page.window_height = 600
    page.padding = 20

    # Папка с игрой
    game_path = load_config()
    path_valid = False
    if game_path and os.path.exists(game_path):
        path_valid = True
    else:
        game_path = None

    # Статус папки
    status = ft.Text(
        f"Папка с игрой указана ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌",
        size=14
    )

    # Список модов (Column с прокруткой)
    mods_column = ft.Column(scroll="auto", expand=True, spacing=5)

    # Если путь уже указан, сразу подгружаем моды
    if path_valid:
        for mod in scan_mods(game_path):
            mods_column.controls.append(ft.Checkbox(label=mod))
    
    # Кнопка выбора папки
    def choose_folder(e):
        nonlocal game_path, path_valid
        new_path = select_game_folder()
        if new_path:
            game_path = new_path
            save_config(game_path)
            path_valid = os.path.exists(game_path)
            status.value = f"Папка с игрой указана ✅: {game_path}" if path_valid else "Папка с игрой не указана ❌"
            mods_column.controls.clear()
            for mod in scan_mods(game_path):
                mods_column.controls.append(ft.Checkbox(label=mod))
            page.update()

    choose_button = ft.ElevatedButton("Выбрать папку с игрой", on_click=choose_folder)

    # Нижний Row
    bottom_row = ft.Row(
        controls=[status, choose_button],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.END
    )

    # Рамка с модами, ограничена по ширине 1/3 окна
    mods_container = ft.Container(
        content=mods_column,
        border=ft.border.all(1, "black"),
        padding=10,
        width=600,
        height=page.height-100,   # можно подстроить под окно
    )

    # Основной layout
    layout = ft.Column(
        controls=[
            ft.Text("Список Модов:", size=16, weight="bold"),  # надпись за пределами рамки
            mods_container,
            bottom_row
        ],
        expand=True
    )

    page.add(layout)

ft.app(target=main)
