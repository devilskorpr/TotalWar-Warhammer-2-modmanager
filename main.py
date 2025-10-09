import os
import json
import subprocess
import flet as ft
import tkinter as tk
from tkinter import filedialog
import zipfile
import shutil
import tempfile

CONFIG_FILE = "config.json"
STANDARD_PACKS_FILE = "assets/standard_packs.txt"


# ------------- helpers / file paths ---------------

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

def get_user_script_path():
    return os.path.expandvars(r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\user.script.txt")

def get_active_mods_path():
    return os.path.expandvars(r"%APPDATA%\The Creative Assembly\Warhammer2\scripts\active_mods.script")

def safe_write_lines(path, lines):
    """Atomic write (temp -> replace)."""
    dirn = os.path.dirname(path)
    os.makedirs(dirn, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dirn, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise

def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f.readlines()]

# ------------- standard packs and scanning ---------------

def load_standard_packs(file_path=STANDARD_PACKS_FILE):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

def scan_mods(game_path):
    """Return list of tuples: (pack_filename, png_path_or_None). Ignores STANDARD_PACKS_FILE entries."""
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
    mods.sort(key=lambda x: x[0].lower())
    return mods

# ------------- active_mods.script handling ---------------

def read_active_mods_file():
    path = get_active_mods_path()
    if os.path.exists(path):
        lines = read_lines(path)
        return [ln for ln in lines if ln]
    # bootstrap from user.script: take non-standard mod lines
    user_lines = read_user_script_lines()
    standard = set(load_standard_packs())
    mods = []
    for ln in user_lines:
        s = ln.strip()
        if s.startswith('mod "') and s.endswith('";'):
            try:
                name = s.split('"')[1]
                if name not in standard:
                    mods.append(name)
            except Exception:
                continue
    safe_write_lines(path, mods)
    return mods

def write_active_mods_file(mod_list):
    path = get_active_mods_path()
    safe_write_lines(path, list(mod_list))

# ------------- user.script helpers ---------------

def read_user_script_lines():
    return read_lines(get_user_script_path())

def write_user_script_lines(lines):
    safe_write_lines(get_user_script_path(), list(lines))

def remove_mod_from_user_script(mod_name):
    """Remove any lines for this mod from user.script (if present)."""
    lines = read_user_script_lines()
    out = []
    changed = False
    for ln in lines:
        s = ln.strip()
        if s.startswith('mod "') and s.endswith('";'):
            try:
                name = s.split('"')[1]
            except Exception:
                name = None
            if name == mod_name:
                changed = True
                continue
        out.append(ln)
    if changed:
        write_user_script_lines(out)
    return changed

def sync_active_into_user_script(active_order):
    """
    Основная функция для кнопки 'Сохранить':
    - Удаляет из user.script все НЕ-стандартные (нашe) записи mod "...";
    - Затем в конец файла добавляет active_order в указанном порядке.
    - Стандартные (системные) моды остаются на своих местах.
    """
    existing = read_user_script_lines()
    standard = set(load_standard_packs())

    # Собираем все существующие строки, пропуская наши (не-стандартные) мод-строки
    out = []
    for ln in existing:
        s = ln.strip()
        if s.startswith('mod "') and s.endswith('";'):
            try:
                name = s.split('"')[1]
            except Exception:
                out.append(ln)
                continue
            if name in standard:
                # сохраняем системную строку на месте
                out.append(ln)
            else:
                # это наша предыдущая запись — пропускаем (удалим старую)
                continue
        else:
            out.append(ln)

    # Добавляем активные моды в нужном порядке в конец (только тех, которые есть в active_order)
    for m in active_order:
        line = f'mod "{m}";'
        # двойной контроль: не добавляем если такая точная строка уже где-то есть
        if line not in out:
            out.append(line)

    write_user_script_lines(out)
    return True

# ------------- pack/zip add/delete ---------------

def add_pack_file(pack_path, game_path):
    data_path = os.path.join(game_path, "data")
    os.makedirs(data_path, exist_ok=True)
    dest = os.path.join(data_path, os.path.basename(pack_path))
    if not os.path.exists(dest):
        shutil.copy(pack_path, dest)
    png_candidate = os.path.splitext(pack_path)[0] + ".png"
    if os.path.exists(png_candidate):
        dest_png = os.path.join(data_path, os.path.basename(png_candidate))
        if not os.path.exists(dest_png):
            shutil.copy(png_candidate, dest_png)

def add_zip_archive(zip_path, game_path):
    data_path = os.path.join(game_path, "data")
    os.makedirs(data_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            filename = os.path.basename(member)
            if not filename:
                continue
            if filename.lower().endswith(".pack") or filename.lower().endswith(".png"):
                target_path = os.path.join(data_path, filename)
                with zip_ref.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

def delete_mod_files(mod_name, game_path):
    data_path = os.path.join(game_path, "data")
    mod_path = os.path.join(data_path, mod_name)
    png_path = os.path.join(data_path, os.path.splitext(mod_name)[0] + ".png")
    if os.path.exists(mod_path):
        os.remove(mod_path)
    if os.path.exists(png_path):
        os.remove(png_path)


# ---------------- UI / main ----------------

def main(page: ft.Page):
    page.title = "Total War: Warhammer II — Mod Manager"
    page.window.width = 900
    page.window_height = 600
    page.window.resizable = False
    page.padding = 20

    # --- Переводы ---
    translations = {
        "ru": {
            "title": "Total War: Warhammer II — Mod Manager",
            "game_folder_ok": "Папка с игрой ✅: {}",
            "game_folder_not_set": "Папка с игрой не указана ❌",
            "choose_folder": "Выбрать папку с игрой",
            "add_mod": "➕ Добавить мод",
            "save": "💾 Сохранить",
            "refresh": "🔄 Обновить",
            "launch": "▶️ Запустить игру",
            "mod_list": "Список модов:",
            "mods_added": "Моды добавлены ✅",
            "saved": "Сохранено ✅",
            "refreshed": "Список модов обновлён 🔄",
            "game_launched": "Игра запущена 🎮",
            "game_not_found": "Файл не найден: {}",
            "game_folder_not_set_short": "Папка с игрой не указана!",
            "choose_mods": "Выберите моды (.pack или .zip)",
            "delete_mod": "Удалить мод",
            "move_up": "Поднять",
            "move_down": "Опустить",
            "backup_error": "Ошибка при создании резервной копии: {}",
        },
        "en": {
            "title": "Total War: Warhammer II — Mod Manager",
            "game_folder_ok": "Game folder ✅: {}",
            "game_folder_not_set": "Game folder not set ❌",
            "choose_folder": "Choose game folder",
            "add_mod": "➕ Add mod",
            "save": "💾 Save",
            "refresh": "🔄 Refresh",
            "launch": "▶️ Launch game",
            "mod_list": "Mod list:",
            "mods_added": "Mods added ✅",
            "saved": "Saved ✅",
            "refreshed": "Mod list refreshed 🔄",
            "game_launched": "Game launched 🎮",
            "game_not_found": "File not found: {}",
            "game_folder_not_set_short": "Game folder not set!",
            "choose_mods": "Choose mods (.pack or .zip)",
            "delete_mod": "Delete mod",
            "move_up": "Move up",
            "move_down": "Move down",
            "backup_error": "Error creating backup: {}",
        }
    }

    lang = "ru"  # текущий язык

    def tr(key):
        return translations[lang][key]

    # --- UI элементы ---
    game_path = load_config()
    path_valid = bool(game_path and os.path.exists(game_path))

    status = ft.Text(
        tr("game_folder_ok").format(game_path) if path_valid else tr("game_folder_not_set"),
        size=14
    )

    mods_column = ft.Column(scroll="auto", expand=True, spacing=6)

    image_container = ft.Container(
        content=ft.Image(src="assets/main.png", fit=ft.ImageFit.CONTAIN, width=300, height=300),
        width=300,
        height=300,
        bgcolor="black",
        alignment=ft.alignment.center,
        border=ft.border.all(1, "gray")
    )

    # --- Функция смены языка ---
    def set_language(new_lang):
        nonlocal lang
        lang = new_lang
        page.title = tr("title")
        status.value = tr("game_folder_ok").format(game_path) if path_valid else tr("game_folder_not_set")
        btn_add_mod.text = tr("add_mod")
        btn_save.text = tr("save")
        btn_refresh.text = tr("refresh")
        btn_launch.text = tr("launch")
        left_panel.controls[0].value = tr("mod_list")
        btn_choose_folder.text = tr("choose_folder")
        load_mod_list()
        page.update()

    # --- Остальные функции (load_mod_list, choose_folder, add_mod_file и т.д.) ---
    # Везде замените строки на tr("ключ") вместо текста!

    def load_mod_list(e=None):
        mods_column.controls.clear()

        if not (game_path and os.path.exists(game_path)):
            page.update()
            return

        all_mods = scan_mods(game_path)
        mods_dict = {fname: png for fname, png in all_mods}
        active_order = read_active_mods_file()

        changed = False
        cleaned_active = []
        for m in active_order:
            if m in mods_dict:
                cleaned_active.append(m)
            else:
                changed = True
        if changed:
            write_active_mods_file(cleaned_active)
            active_order = cleaned_active

        active_set = set(active_order)

        # Активные моды
        for mod_name in active_order:
            png = mods_dict.get(mod_name)

            def make_on_change(m, png_p):
                def on_change(e):
                    if not e.control.value:
                        mods = read_active_mods_file()
                        if m in mods:
                            mods.remove(m)
                            write_active_mods_file(mods)
                        remove_mod_from_user_script(m)
                        image_container.content = None
                        load_mod_list()
                return on_change

            def make_move_up(m):
                def f(e):
                    mods = read_active_mods_file()
                    if m in mods:
                        i = mods.index(m)
                        if i > 0:
                            mods[i], mods[i-1] = mods[i-1], mods[i]
                            write_active_mods_file(mods)
                            load_mod_list()
                return f

            def make_move_down(m):
                def f(e):
                    mods = read_active_mods_file()
                    if m in mods:
                        i = mods.index(m)
                        if i < len(mods)-1:
                            mods[i], mods[i+1] = mods[i+1], mods[i]
                            write_active_mods_file(mods)
                            load_mod_list()
                return f

            def make_delete(m):
                def f(e):
                    delete_mod_files(m, game_path)
                    mods = read_active_mods_file()
                    if m in mods:
                        mods.remove(m)
                        write_active_mods_file(mods)
                    remove_mod_from_user_script(m)
                    image_container.content = None
                    load_mod_list()
                return f

            cb = ft.Checkbox(label=mod_name, value=True, on_change=make_on_change(mod_name, png))
            up_btn = ft.IconButton(icon=ft.Icons.ARROW_UPWARD, on_click=make_move_up(mod_name), tooltip=tr("move_up"))
            down_btn = ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, on_click=make_move_down(mod_name), tooltip=tr("move_down"))
            del_btn = ft.IconButton(icon=ft.Icons.DELETE, on_click=make_delete(mod_name), tooltip=tr("delete_mod"))
            actions_row = ft.Row(controls=[up_btn, down_btn, del_btn], spacing=2)
            mods_column.controls.append(
                ft.Row(
                    controls=[cb, actions_row],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )

        # Неактивные моды
        inactive = [name for name in mods_dict.keys() if name not in active_set]
        inactive.sort(key=lambda x: x.lower())
        for mod_name in inactive:
            png = mods_dict.get(mod_name)

            def make_on_change_inactive(m, png_p):
                def on_change(e):
                    if e.control.value:
                        mods = read_active_mods_file()
                        if m not in mods:
                            mods.append(m)
                            write_active_mods_file(mods)
                        if png_p and os.path.exists(png_p):
                            image_container.content = ft.Image(src=png_p, fit=ft.ImageFit.CONTAIN, width=300, height=300)
                        else:
                            image_container.content = None
                        load_mod_list()
                return on_change

            def make_delete_inactive(m):
                def f(e):
                    delete_mod_files(m, game_path)
                    load_mod_list()
                return f

            cb = ft.Checkbox(label=mod_name, value=False, on_change=make_on_change_inactive(mod_name, png))
            del_btn = ft.IconButton(icon=ft.Icons.DELETE, on_click=make_delete_inactive(mod_name), tooltip=tr("delete_mod"))
            mods_column.controls.append(ft.Row(controls=[cb, del_btn],
                                               alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        page.update()

    def choose_folder(e):
        nonlocal game_path, path_valid
        new_path = select_game_folder()
        if not new_path:
            return
        game_path = new_path
        save_config(game_path)
        path_valid = bool(game_path and os.path.exists(game_path))
        status.value = tr("game_folder_ok").format(game_path) if path_valid else tr("game_folder_not_set")

        user_script_path = get_user_script_path()
        backup_path = os.path.join(os.path.dirname(user_script_path), "user_backup.script")
        if os.path.exists(user_script_path):
            try:
                shutil.copy(user_script_path, backup_path)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(tr("backup_error").format(ex)))
                page.snack_bar.open = True
                page.update()

        load_mod_list()

    def add_mod_file(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text(tr("game_folder_not_set_short")))
            page.snack_bar.open = True
            page.update()
            return
        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes("-topmost", True)
        file_paths = filedialog.askopenfilenames(
            title=tr("choose_mods"),
            filetypes=[("Pack files", "*.pack"), ("Zip archives", "*.zip")]
        )
        if not file_paths:
            return
        for file_path in file_paths:
            if file_path.lower().endswith(".pack"):
                add_pack_file(file_path, game_path)
            elif file_path.lower().endswith(".zip"):
                add_zip_archive(file_path, game_path)
        load_mod_list()
        page.snack_bar = ft.SnackBar(ft.Text(tr("mods_added")))
        page.snack_bar.open = True
        page.update()

    def save_button_action(e):
        active = read_active_mods_file()
        sync_active_into_user_script(active)
        page.snack_bar = ft.SnackBar(ft.Text(tr("saved")))
        page.snack_bar.open = True
        page.update()
        load_mod_list()

    def refresh_button_action(e):
        load_mod_list()
        page.snack_bar = ft.SnackBar(ft.Text(tr("refreshed")))
        page.snack_bar.open = True
        page.update()

    def launch_game(e):
        if not (game_path and os.path.exists(game_path)):
            page.snack_bar = ft.SnackBar(ft.Text(tr("game_folder_not_set_short")))
            page.snack_bar.open = True
            page.update()
            return
        exe_path = os.path.join(game_path, "Warhammer2.exe")
        if not os.path.exists(exe_path):
            page.snack_bar = ft.SnackBar(ft.Text(tr("game_not_found").format(exe_path)))
            page.snack_bar.open = True
            page.update()
            return
        try:
            subprocess.Popen(f'start "" "{exe_path}"', shell=True, cwd=game_path)
            page.snack_bar = ft.SnackBar(ft.Text(tr("game_launched")))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Ошибка при запуске: {ex}"))
            page.snack_bar.open = True
            page.update()

    # --- Кнопки и layout ---
    btn_add_mod = ft.ElevatedButton(tr("add_mod"), on_click=add_mod_file, width=520, height=48)
    btn_save = ft.ElevatedButton(tr("save"), on_click=save_button_action, width=300, height=48)
    btn_refresh = ft.ElevatedButton(tr("refresh"), on_click=refresh_button_action, width=300, height=48)
    btn_launch = ft.ElevatedButton(tr("launch"), on_click=launch_game, width=300, height=48)
    btn_choose_folder = ft.ElevatedButton(tr("choose_folder"), on_click=choose_folder)

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
        width=600,
        height=page.window_height - 70
    )

    left_panel = ft.Column(
        controls=[ft.Text(tr("mod_list"), size=16, weight="bold"), mods_container],
        expand=True
    )

    # --- Переключатель языка ---
    lang_row = ft.Row(
        controls=[
            ft.GestureDetector(
                content=ft.Image(src="ru_flag.jpg", width=32, height=24),
                on_tap=lambda e: set_language("ru")
            ),
            ft.GestureDetector(
                content=ft.Image(src="assets/eng_flag.png", width=32, height=24),
                on_tap=lambda e: set_language("en")
            ),
        ],
        spacing=10
    )

    bottom_row = ft.Row(
        controls=[status, lang_row, btn_choose_folder],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

    main_row = ft.Row(controls=[left_panel, right_panel], expand=True, spacing=20)
    layout = ft.Column(controls=[main_row, ft.Divider(), bottom_row], expand=True)
    page.add(layout)

    if path_valid:
        _ = read_active_mods_file()
        load_mod_list()

ft.app(target=main)
