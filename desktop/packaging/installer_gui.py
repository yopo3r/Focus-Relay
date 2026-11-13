"""Instalador gráfico de Focus Relay para Windows (y también Linux/macOS con Python + tkinter).

Es el que abre `install_windows.bat`: un asistente con idioma, opciones, barra de progreso y botón de abrir al terminar.
Crea un entorno propio (`.venv`), instala las dependencias, deja accesos directos y, si se pide, el inicio con el sistema.
No usa nada fuera de la biblioteca estándar. La lógica (órdenes a ejecutar, textos) está separada de la ventana para probarla.
"""
import os
import subprocess
import sys
import threading

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_WIN = os.name == "nt"

LANGS = [("es", "Español"), ("en", "English"), ("fr", "Français"), ("pt", "Português"), ("de", "Deutsch"),
         ("it", "Italiano"), ("nl", "Nederlands"), ("ru", "Русский"), ("ja", "日本語"), ("ko", "한국어"), ("zh", "中文")]

# clave: (es, en, fr, pt, de, it, nl, ru, ja, ko, zh)
_ORDER = [c for c, _n in LANGS]
_T = {
    "title": ("Instalador de Focus Relay", "Focus Relay Setup", "Installation de Focus Relay", "Instalador do Focus Relay",
              "Focus Relay Setup", "Installazione di Focus Relay", "Focus Relay installeren", "Установка Focus Relay",
              "Focus Relay セットアップ", "Focus Relay 설치", "Focus Relay 安装程序"),
    "welcome": ("Te damos la bienvenida", "Welcome", "Bienvenue", "Boas-vindas", "Willkommen", "Benvenuto", "Welkom",
                "Добро пожаловать", "ようこそ", "환영합니다", "欢迎使用"),
    "intro": ("Este asistente instala Focus Relay en tu equipo: crea su propio entorno, instala lo necesario y deja accesos directos.",
              "This wizard installs Focus Relay on your computer: it creates its own environment, installs what it needs and adds shortcuts.",
              "Cet assistant installe Focus Relay sur votre ordinateur : il crée son propre environnement, installe le nécessaire et ajoute des raccourcis.",
              "Este assistente instala o Focus Relay no seu computador: cria um ambiente próprio, instala o necessário e adiciona atalhos.",
              "Dieser Assistent installiert Focus Relay auf deinem Computer: Er legt eine eigene Umgebung an, installiert alles Nötige und erstellt Verknüpfungen.",
              "Questa procedura installa Focus Relay sul computer: crea un ambiente dedicato, installa il necessario e aggiunge i collegamenti.",
              "Deze wizard installeert Focus Relay op je computer: hij maakt een eigen omgeving, installeert wat nodig is en voegt snelkoppelingen toe.",
              "Этот мастер установит Focus Relay на компьютер: создаст отдельное окружение, поставит всё нужное и добавит ярлыки.",
              "このウィザードは Focus Relay をインストールします。専用の環境を作成し、必要なものを導入して、ショートカットを追加します。",
              "이 마법사는 Focus Relay를 설치합니다. 전용 환경을 만들고 필요한 항목을 설치한 뒤 바로 가기를 추가합니다.",
              "本向导将在您的电脑上安装 Focus Relay：创建独立环境、安装所需组件并添加快捷方式。"),
    "language": ("Idioma", "Language", "Langue", "Idioma", "Sprache", "Lingua", "Taal", "Язык", "言語", "언어", "语言"),
    "opt_desktop": ("Crear un acceso directo en el escritorio", "Create a desktop shortcut", "Créer un raccourci sur le bureau",
                    "Criar um atalho na área de trabalho", "Verknüpfung auf dem Desktop erstellen",
                    "Crea un collegamento sul desktop", "Snelkoppeling op het bureaublad maken",
                    "Создать ярлык на рабочем столе", "デスクトップにショートカットを作成", "바탕 화면에 바로 가기 만들기", "创建桌面快捷方式"),
    "opt_startup": ("Iniciar Focus Relay con el sistema", "Start Focus Relay with the system", "Lancer Focus Relay au démarrage du système",
                    "Iniciar o Focus Relay com o sistema", "Focus Relay mit dem System starten", "Avvia Focus Relay con il sistema",
                    "Focus Relay met het systeem starten", "Запускать Focus Relay вместе с системой",
                    "システム起動時に Focus Relay を開始", "시스템 시작 시 Focus Relay 실행", "随系统启动 Focus Relay"),
    "opt_tasks": ("Al iniciar, abrir las Tareas para planificar el día", "On startup, open Tasks to plan the day",
                  "Au démarrage, ouvrir les Tâches pour planifier la journée", "Ao iniciar, abrir as Tarefas para planejar o dia",
                  "Beim Start die Aufgaben öffnen, um den Tag zu planen", "All'avvio, apri le Attività per pianificare la giornata",
                  "Bij het opstarten Taken openen om de dag te plannen", "При запуске открывать «Задачи» для планирования дня",
                  "起動時にタスクを開いて一日を計画", "시작할 때 할 일을 열어 하루 계획하기", "启动时打开任务页以规划当天"),
    "opt_launch": ("Abrir Focus Relay al terminar", "Open Focus Relay when finished", "Ouvrir Focus Relay à la fin",
                   "Abrir o Focus Relay ao terminar", "Focus Relay nach der Installation öffnen", "Apri Focus Relay al termine",
                   "Focus Relay openen na afloop", "Открыть Focus Relay после установки", "完了後に Focus Relay を開く",
                   "완료 후 Focus Relay 열기", "完成后打开 Focus Relay"),
    "install": ("Instalar", "Install", "Installer", "Instalar", "Installieren", "Installa", "Installeren", "Установить",
                "インストール", "설치", "安装"),
    "cancel": ("Cancelar", "Cancel", "Annuler", "Cancelar", "Abbrechen", "Annulla", "Annuleren", "Отмена", "キャンセル", "취소", "取消"),
    "finish": ("Terminar", "Finish", "Terminer", "Concluir", "Fertig", "Fine", "Voltooien", "Готово", "完了", "마침", "完成"),
    "retry": ("Reintentar", "Retry", "Réessayer", "Tentar de novo", "Erneut versuchen", "Riprova", "Opnieuw proberen", "Повторить",
              "再試行", "다시 시도", "重试"),
    "step_env": ("Creando el entorno…", "Creating the environment…", "Création de l'environnement…", "Criando o ambiente…",
                 "Umgebung wird erstellt…", "Creazione dell'ambiente…", "Omgeving wordt gemaakt…", "Создание окружения…",
                 "環境を作成しています…", "환경을 만드는 중…", "正在创建环境…"),
    "step_deps": ("Instalando dependencias (puede tardar un par de minutos)…",
                  "Installing dependencies (this can take a couple of minutes)…",
                  "Installation des dépendances (cela peut prendre quelques minutes)…",
                  "Instalando dependências (pode levar alguns minutos)…",
                  "Abhängigkeiten werden installiert (das kann ein paar Minuten dauern)…",
                  "Installazione delle dipendenze (può richiedere qualche minuto)…",
                  "Afhankelijkheden worden geïnstalleerd (dit kan enkele minuten duren)…",
                  "Установка зависимостей (это может занять несколько минут)…",
                  "依存パッケージをインストールしています（数分かかります）…", "종속성을 설치하는 중(몇 분 걸릴 수 있음)…",
                  "正在安装依赖（可能需要几分钟）…"),
    "step_links": ("Creando accesos directos…", "Creating shortcuts…", "Création des raccourcis…", "Criando atalhos…",
                   "Verknüpfungen werden erstellt…", "Creazione dei collegamenti…", "Snelkoppelingen worden gemaakt…",
                   "Создание ярлыков…", "ショートカットを作成しています…", "바로 가기를 만드는 중…", "正在创建快捷方式…"),
    "step_startup": ("Configurando el inicio con el sistema…", "Setting up start with the system…",
                     "Configuration du démarrage automatique…", "Configurando o início com o sistema…",
                     "Autostart wird eingerichtet…", "Configurazione dell'avvio automatico…", "Automatisch starten instellen…",
                     "Настройка автозапуска…", "自動起動を設定しています…", "자동 시작을 설정하는 중…", "正在设置开机自启…"),
    "done": ("¡Focus Relay quedó instalado!", "Focus Relay is installed!", "Focus Relay est installé !", "O Focus Relay foi instalado!",
             "Focus Relay ist installiert!", "Focus Relay è stato installato!", "Focus Relay is geïnstalleerd!",
             "Focus Relay установлен!", "Focus Relay のインストールが完了しました！", "Focus Relay 설치가 완료되었습니다!",
             "Focus Relay 安装完成！"),
    "done_sub": ("Lo encuentras en el menú Inicio.", "You'll find it in the Start menu.", "Vous le trouverez dans le menu Démarrer.",
                 "Você o encontra no menu Iniciar.", "Du findest es im Startmenü.", "Lo trovi nel menu Start.",
                 "Je vindt het in het Startmenu.", "Его можно найти в меню «Пуск».", "スタートメニューにあります。",
                 "시작 메뉴에서 찾을 수 있습니다.", "可在“开始”菜单中找到。"),
    "error": ("Algo salió mal. Revisa los detalles de abajo.", "Something went wrong. Check the details below.",
              "Un problème est survenu. Consultez les détails ci-dessous.", "Algo deu errado. Veja os detalhes abaixo.",
              "Etwas ist schiefgelaufen. Details siehe unten.", "Qualcosa è andato storto. Controlla i dettagli qui sotto.",
              "Er ging iets mis. Bekijk de details hieronder.", "Что-то пошло не так. Подробности ниже.",
              "問題が発生しました。下の詳細を確認してください。", "문제가 발생했습니다. 아래 자세한 내용을 확인하세요.",
              "出错了，请查看下方详情。"),
    "no_python": ("No se encontró Python 3.9 o superior.", "Python 3.9 or newer was not found.",
                  "Python 3.9 ou supérieur est introuvable.", "Python 3.9 ou superior não foi encontrado.",
                  "Python 3.9 oder neuer wurde nicht gefunden.", "Python 3.9 o successivo non trovato.",
                  "Python 3.9 of nieuwer is niet gevonden.", "Python 3.9 или новее не найден.",
                  "Python 3.9 以上が見つかりません。", "Python 3.9 이상을 찾을 수 없습니다.", "未找到 Python 3.9 或更高版本。"),
}


def detect_lang(env=None):
    """Idioma del sistema (variables de entorno o configuración regional de Windows); `en` si no hay traducción."""
    env = os.environ if env is None else env
    for var in ("FR_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = (env.get(var) or "").strip()
        if v and v[:2].lower() in _ORDER:
            return v[:2].lower()
    try:
        import locale
        v = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "")[:2].lower()
        if v in _ORDER:
            return v
    except Exception:
        pass
    return "en"


def tr(key, lang):
    row = _T[key]
    return row[_ORDER.index(lang)] if lang in _ORDER else row[1]


def venv_python(app_dir=APP_DIR, windowed=False):
    sub = os.path.join(".venv", "Scripts", "pythonw.exe" if windowed else "python.exe") if IS_WIN \
        else os.path.join(".venv", "bin", "python")
    return os.path.join(app_dir, sub)


def plan(opts, app_dir=APP_DIR, base_python=None):
    """Lista de pasos [(clave_de_texto, [órdenes])] según las opciones elegidas. Cada orden es una lista de argumentos."""
    base_python = base_python or sys.executable
    py = venv_python(app_dir)
    steps = [("step_env", [[base_python, "-m", "venv", os.path.join(app_dir, ".venv")]]),
             ("step_deps", [[py, "-m", "pip", "install", "--upgrade", "pip", "-r", os.path.join(app_dir, "requirements.txt")]])]
    steps.append(("step_links", [["SHORTCUTS"]]))
    if opts.get("startup"):
        cmds = [[py, os.path.join(app_dir, "autostart", "install_autostart.py")]]
        if opts.get("tasks"):
            cmds.append([py, "-c", "import sys; sys.path.insert(0, sys.argv[1]); from config import update_config; "
                                   "update_config(startup_tasks=True)", app_dir])
        steps.append(("step_startup", cmds))
    return steps


def shortcut_script(app_dir, desktop):
    """PowerShell que crea los accesos directos (menú Inicio y, si se pide, escritorio)."""
    pyw = venv_python(app_dir, windowed=True)
    main = os.path.join(app_dir, "main.py")
    ico = os.path.join(app_dir, "assets", "icon.ico")
    dirs = "[Environment]::GetFolderPath('Programs')" + (",[Environment]::GetFolderPath('Desktop')" if desktop else "")

    def q(s):
        return s.replace("'", "''")
    return ("$s=New-Object -ComObject WScript.Shell; foreach($d in @(%s)){ $l=$s.CreateShortcut((Join-Path $d 'Focus Relay.lnk')); "
            "$l.TargetPath='%s'; $l.Arguments='\"%s\"'; $l.WorkingDirectory='%s'; $l.IconLocation='%s'; $l.Save() }"
            % (dirs, q(pyw), q(main), q(app_dir), q(ico)))


def run_cmd(cmd, log, app_dir, opts):
    """Ejecuta una orden enviando su salida a `log`. Devuelve el código de salida."""
    if cmd == ["SHORTCUTS"]:
        if not IS_WIN:
            log("(shortcuts: use autostart/install_autostart.py --menu on Linux)\n")
            return subprocess.call([venv_python(app_dir), os.path.join(app_dir, "autostart", "install_autostart.py"), "--menu"])
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
               shortcut_script(app_dir, opts.get("desktop"))]
    flags = 0x08000000 if IS_WIN else 0                      # CREATE_NO_WINDOW: sin ventanas negras
    p = subprocess.Popen(cmd, cwd=app_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", creationflags=flags)
    for line in p.stdout:
        log(line)
    return p.wait()


def main():
    import tkinter as tk
    from tkinter import ttk

    lang = detect_lang()
    root = tk.Tk()
    root.geometry("560x470")
    root.minsize(520, 440)
    try:
        ico = os.path.join(APP_DIR, "assets", "icon.ico")
        if IS_WIN and os.path.exists(ico):
            root.iconbitmap(ico)
    except Exception:
        pass
    style = ttk.Style()
    for theme in ("vista", "clam"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break
    BG = "#f4f6fb"
    root.configure(bg=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG)
    style.configure("TCheckbutton", background=BG)
    style.configure("H.TLabel", font=("Segoe UI", 18, "bold"), background=BG)
    style.configure("S.TLabel", font=("Segoe UI", 10), foreground="#5b6577", background=BG)

    lang_var = tk.StringVar(value=dict(LANGS)[lang])
    opts = {k: tk.BooleanVar(value=v) for k, v in (("desktop", True), ("startup", False), ("tasks", False), ("launch", True))}
    state = {"running": False, "done": False}

    outer = ttk.Frame(root, padding=22)
    outer.pack(fill="both", expand=True)
    head = ttk.Label(outer, style="H.TLabel")
    head.pack(anchor="w")
    intro = ttk.Label(outer, style="S.TLabel", wraplength=500, justify="left")
    intro.pack(anchor="w", pady=(6, 14))
    langrow = ttk.Frame(outer)
    langrow.pack(fill="x", pady=(0, 10))
    lang_lbl = ttk.Label(langrow)
    lang_lbl.pack(side="left", padx=(0, 10))
    combo = ttk.Combobox(langrow, state="readonly", values=[n for _c, n in LANGS], textvariable=lang_var, width=18)
    combo.pack(side="left")
    optframe = ttk.Frame(outer)
    optframe.pack(fill="x")
    checks = {}
    for key in ("desktop", "startup", "tasks", "launch"):
        checks[key] = ttk.Checkbutton(optframe, variable=opts[key])
        checks[key].pack(anchor="w", pady=3, padx=(0 if key not in ("tasks",) else 22, 0))
    progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
    status = ttk.Label(outer, style="S.TLabel", wraplength=500)
    logbox = tk.Text(outer, height=8, bg="#10131c", fg="#cfd6e6", relief="flat", font=("Consolas", 9), wrap="word")
    logbox.configure(state="disabled")
    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(14, 0))
    primary = ttk.Button(buttons)
    primary.pack(side="right")
    cancel = ttk.Button(buttons)
    cancel.pack(side="right", padx=8)

    def L(key):
        return tr(key, current_lang())

    def current_lang():
        name = lang_var.get()
        return next((c for c, n in LANGS if n == name), "en")

    def refresh_texts(*_a):
        root.title(L("title"))
        head.configure(text=L("welcome"))
        intro.configure(text=L("intro"))
        lang_lbl.configure(text=L("language"))
        for key, w in checks.items():
            w.configure(text=L("opt_" + key))
        cancel.configure(text=L("cancel"))
        if state["done"]:
            primary.configure(text=L("finish"))
        elif not state["running"]:
            primary.configure(text=L("install"))

    def tasks_state(*_a):
        checks["tasks"].configure(state="normal" if opts["startup"].get() else "disabled")
        if not opts["startup"].get():
            opts["tasks"].set(False)

    def log(text):
        def add():
            logbox.configure(state="normal")
            logbox.insert("end", text)
            logbox.see("end")
            logbox.configure(state="disabled")
        root.after(0, add)

    def set_status(text, pct=None):
        def upd():
            status.configure(text=text)
            if pct is not None:
                progress.configure(value=pct)
        root.after(0, upd)

    def worker():
        o = {k: v.get() for k, v in opts.items()}
        steps = plan(o)
        total = len(steps)
        ok = True
        for i, (key, cmds) in enumerate(steps):
            set_status(L(key), 100 * i / total)
            for cmd in cmds:
                log("$ " + " ".join(str(c) for c in cmd[:6]) + "\n")
                try:
                    rc = run_cmd(cmd, log, APP_DIR, o)
                except Exception as exc:
                    log(f"{exc}\n")
                    rc = 1
                if rc != 0:
                    ok = False
                    break
            if not ok:
                break
        root.after(0, lambda: finished(ok))

    def finished(ok):
        state["running"] = False
        progress.stop()
        if ok:
            state["done"] = True
            progress.configure(value=100)
            status.configure(text=L("done") + "  " + L("done_sub"))
            cancel.pack_forget()
            primary.configure(text=L("finish"), state="normal")
        else:
            status.configure(text=L("error"), foreground="#c0392b")
            primary.configure(text=L("retry"), state="normal")
            cancel.configure(state="normal")

    def start():
        if state["running"]:
            return
        state["running"] = True
        primary.configure(state="disabled")
        cancel.configure(state="disabled")
        langrow.pack_forget()
        optframe.pack_forget()
        intro.pack_forget()
        head.configure(text=L("title"))
        progress.pack(fill="x", pady=(10, 6), before=buttons)
        status.configure(foreground="#5b6577")
        status.pack(fill="x", before=buttons)
        logbox.pack(fill="both", expand=True, pady=(10, 0), before=buttons)
        threading.Thread(target=worker, daemon=True).start()

    def on_primary():
        if state["done"]:
            if opts["launch"].get():
                try:
                    subprocess.Popen([venv_python(APP_DIR, windowed=True), os.path.join(APP_DIR, "main.py")], cwd=APP_DIR)
                except Exception:
                    pass
            root.destroy()
        else:
            start()

    primary.configure(command=on_primary)
    cancel.configure(command=root.destroy)
    combo.bind("<<ComboboxSelected>>", refresh_texts)
    opts["startup"].trace_add("write", tasks_state)
    refresh_texts()
    tasks_state()
    root.mainloop()


if __name__ == "__main__":
    main()
