// Idioma y tema de la extensión. Idioma: «auto» (el del navegador) o uno de los 11 de la app. Tema: «auto» (sigue al navegador), claro u oscuro.
const LANGS = { es: 'Español', en: 'English', fr: 'Français', pt: 'Português', zh: '中文', de: 'Deutsch', it: 'Italiano', nl: 'Nederlands', ru: 'Русский', ja: '日本語', ko: '한국어' };
const KEYS = ['pConsultando', 'pAppCerrada', 'pAppCerradaDetalle', 'pEnfoque', 'pPausa', 'pPausaDetalle', 'pSinBloqueo', 'pEspera', 'pIniciaSesion',
  'pBloquear', 'pYaBloqueado', 'pListo', 'pYaEstaba', 'pFallo', 'pAjustes', 'mPomW', 'mPomD', 'mTemp', 'mCrono',
  'bTitulo', 'bDesc', 'bVolver', 'oTabAjustes', 'oTabComo', 'oTabAcerca', 'oIdioma', 'oAuto', 'oTema', 'oTemaAuto', 'oClaro', 'oOscuro',
  'oPuerto', 'oPuertoAyuda', 'oGuardar', 'oOk', 'oNo', 'cTitulo', 'cIntro', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6',
  'aTitulo', 'aVersion', 'aDesc', 'aPrivacidad', 'aPermisos'];
// Cada idioma: una lista en el orden de KEYS.
const TXT = {
es: ['Consultando…', 'App cerrada', 'Abre Focus Relay en tu computador para activar el bloqueo.', 'Enfoque activo', 'Bloqueo en pausa', 'Se reanuda desde la app.', 'En sesión (sin bloqueo)', 'En espera', 'Inicia una sesión en la app.',
 'Bloquear {site}', '{site} ya está bloqueado', 'Listo: se bloqueará en tus próximas sesiones.', 'Ese sitio ya estaba en la lista.', 'No se pudo: abre la app y revisa el puerto.', 'Ajustes y ayuda', 'Pomodoro · trabajo', 'Pomodoro · descanso', 'Temporizador', 'Cronómetro',
 'Tu atención está protegida', 'Este sitio vuelve a estar disponible al terminar la sesión de trabajo.', 'Volver', 'Ajustes', 'Cómo funciona', 'Acerca de', 'Idioma', 'Automático (idioma del navegador)', 'Tema', 'Automático (sigue al navegador)', 'Claro', 'Oscuro',
 'Puerto de la app', 'Por defecto 8765. Debe coincidir con Ajustes › Avanzado en la app.', 'Guardar y probar', 'Conectado con la app.', 'No se pudo conectar. Abre la app y revisa el puerto.',
 'Cómo funciona', 'La app de escritorio es la central de control; la extensión solo aplica el bloqueo en el navegador.',
 '1. Abre la app Focus Relay y elige los sitios en Ajustes › Bloqueo › «Bloqueo de sitios web…».', '2. Inicia un Pomodoro o un Temporizador en la app.', '3. Mientras dure la sesión de trabajo, los sitios de la lista quedan bloqueados; al terminar o en el descanso vuelven a abrirse.', '4. Las pausas, el modo estricto, la música y los trofeos se manejan en la app. Con el modo estricto no se puede soltar el bloqueo durante la sesión.', '5. Si la app está cerrada, la extensión no bloquea nada. Desde el popup puedes bloquear con un clic el sitio que estás viendo (solo agrega a la lista).', 'Con el botón del popup puedes bloquear el sitio actual.',
 'Acerca de', 'Versión {v}', 'Extensión de Focus Relay: bloquea sitios distractores mientras la app de escritorio tiene una sesión de trabajo activa.', 'Privacidad: solo habla con la app en este equipo (127.0.0.1). No envía datos a internet ni guarda nada fuera de tu navegador.', 'Permisos: redirigir los sitios bloqueados, guardar tus ajustes, programar la consulta periódica y leer la dirección de la pestaña solo cuando abres el popup.'],
en: ['Checking…', 'App closed', 'Open Focus Relay on your computer to turn blocking on.', 'Focus active', 'Blocking paused', 'It resumes from the app.', 'In session (no blocking)', 'Idle', 'Start a session in the app.',
 'Block {site}', '{site} is already blocked', 'Done: it will be blocked in your next sessions.', 'That site was already on the list.', "Couldn't do it: open the app and check the port.", 'Settings & help', 'Pomodoro · work', 'Pomodoro · break', 'Timer', 'Stopwatch',
 'Your attention is protected', 'This site will be available again when the work session ends.', 'Go back', 'Settings', 'How it works', 'About', 'Language', 'Automatic (browser language)', 'Theme', 'Automatic (follows the browser)', 'Light', 'Dark',
 'App port', 'Default 8765. It must match Settings › Advanced in the app.', 'Save and test', 'Connected to the app.', "Couldn't connect. Open the app and check the port.",
 'How it works', 'The desktop app is the control center; the extension only applies the blocking in the browser.',
 '1. Open the Focus Relay app and choose your sites in Settings › Blocking › “Website blocking…”.', '2. Start a Pomodoro or a Timer in the app.', '3. During the work session the listed sites are blocked; when it ends or during breaks they open again.', '4. Pauses, strict mode, music and trophies are handled in the app. In strict mode blocking can’t be released during a session.', '5. If the app is closed the extension blocks nothing. From the popup you can block the site you are viewing with one click (it only adds to the list).', 'Use the popup button to block the current site.',
 'About', 'Version {v}', 'Focus Relay extension: blocks distracting sites while the desktop app has a work session running.', 'Privacy: it only talks to the app on this computer (127.0.0.1). It sends no data to the internet and stores nothing outside your browser.', 'Permissions: redirect blocked sites, save your settings, schedule the periodic check, and read the tab address only when you open the popup.'],
fr: ['Vérification…', 'App fermée', "Ouvre Focus Relay sur ton ordinateur pour activer le blocage.", 'Concentration active', 'Blocage en pause', "Il reprend depuis l'app.", 'En session (sans blocage)', 'En attente', "Lance une session dans l'app.",
 'Bloquer {site}', '{site} est déjà bloqué', 'Fait : il sera bloqué lors de tes prochaines sessions.', 'Ce site était déjà dans la liste.', "Impossible : ouvre l'app et vérifie le port.", 'Réglages et aide', 'Pomodoro · travail', 'Pomodoro · pause', 'Minuteur', 'Chronomètre',
 'Ton attention est protégée', 'Ce site sera de nouveau disponible à la fin de la session de travail.', 'Retour', 'Réglages', 'Comment ça marche', 'À propos', 'Langue', 'Automatique (langue du navigateur)', 'Thème', 'Automatique (suit le navigateur)', 'Clair', 'Sombre',
 "Port de l'app", "8765 par défaut. Doit correspondre à Réglages › Avancé dans l'app.", 'Enregistrer et tester', "Connecté à l'app.", "Connexion impossible. Ouvre l'app et vérifie le port.",
 'Comment ça marche', "L'app de bureau est le centre de contrôle ; l'extension applique seulement le blocage dans le navigateur.",
 "1. Ouvre l'app Focus Relay et choisis les sites dans Réglages › Blocage › « Blocage de sites web… ».", "2. Lance un Pomodoro ou un Minuteur dans l'app.", '3. Pendant la session de travail, les sites de la liste sont bloqués ; à la fin ou pendant les pauses, ils se rouvrent.', "4. Pauses, mode strict, musique et trophées se gèrent dans l'app. En mode strict, le blocage ne peut pas être levé pendant la session.", "5. Si l'app est fermée, l'extension ne bloque rien. Depuis le popup, tu peux bloquer en un clic le site affiché (il s'ajoute seulement à la liste).", 'Utilise le bouton du popup pour bloquer le site actuel.',
 'À propos', 'Version {v}', "Extension Focus Relay : bloque les sites distrayants pendant qu'une session de travail est active dans l'app de bureau.", "Confidentialité : elle ne parle qu'à l'app sur cet ordinateur (127.0.0.1). Aucune donnée n'est envoyée sur internet ni stockée hors de ton navigateur.", "Autorisations : rediriger les sites bloqués, enregistrer tes réglages, planifier la vérification périodique et lire l'adresse de l'onglet seulement à l'ouverture du popup."],
pt: ['Consultando…', 'App fechado', 'Abra o Focus Relay no seu computador para ativar o bloqueio.', 'Foco ativo', 'Bloqueio em pausa', 'Volta a funcionar pelo app.', 'Em sessão (sem bloqueio)', 'Em espera', 'Inicie uma sessão no app.',
 'Bloquear {site}', '{site} já está bloqueado', 'Pronto: será bloqueado nas próximas sessões.', 'Esse site já estava na lista.', 'Não foi possível: abra o app e confira a porta.', 'Ajustes e ajuda', 'Pomodoro · trabalho', 'Pomodoro · pausa', 'Temporizador', 'Cronômetro',
 'Sua atenção está protegida', 'Este site volta a ficar disponível ao fim da sessão de trabalho.', 'Voltar', 'Ajustes', 'Como funciona', 'Sobre', 'Idioma', 'Automático (idioma do navegador)', 'Tema', 'Automático (segue o navegador)', 'Claro', 'Escuro',
 'Porta do app', 'Padrão 8765. Deve coincidir com Ajustes › Avançado no app.', 'Salvar e testar', 'Conectado ao app.', 'Não foi possível conectar. Abra o app e confira a porta.',
 'Como funciona', 'O app de desktop é a central de controle; a extensão só aplica o bloqueio no navegador.',
 '1. Abra o app Focus Relay e escolha os sites em Ajustes › Bloqueio › «Bloqueio de sites…».', '2. Inicie um Pomodoro ou um Temporizador no app.', '3. Durante a sessão de trabalho, os sites da lista ficam bloqueados; ao terminar ou nas pausas, voltam a abrir.', '4. Pausas, modo estrito, música e troféus são geridos no app. No modo estrito o bloqueio não pode ser liberado durante a sessão.', '5. Se o app estiver fechado, a extensão não bloqueia nada. No popup você pode bloquear com um clique o site que está vendo (só adiciona à lista).', 'Use o botão do popup para bloquear o site atual.',
 'Sobre', 'Versão {v}', 'Extensão do Focus Relay: bloqueia sites que distraem enquanto o app de desktop tem uma sessão de trabalho ativa.', 'Privacidade: só fala com o app neste computador (127.0.0.1). Não envia dados à internet nem guarda nada fora do seu navegador.', 'Permissões: redirecionar os sites bloqueados, salvar seus ajustes, agendar a consulta periódica e ler o endereço da aba somente ao abrir o popup.'],
zh: ['查询中…', '应用未打开', '请在电脑上打开 Focus Relay 以启用屏蔽。', '专注中', '屏蔽已暂停', '将在应用中恢复。', '会话中(未屏蔽)', '待机', '请在应用中开始一次会话。',
 '屏蔽 {site}', '{site} 已被屏蔽', '完成:下次会话起将屏蔽该网站。', '该网站已在列表中。', '失败:请打开应用并检查端口。', '设置与帮助', '番茄钟 · 工作', '番茄钟 · 休息', '计时器', '秒表',
 '你的注意力受到保护', '工作会话结束后,此网站将恢复访问。', '返回', '设置', '工作原理', '关于', '语言', '自动(浏览器语言)', '主题', '自动(跟随浏览器)', '浅色', '深色',
 '应用端口', '默认 8765。须与应用中的 设置 › 高级 一致。', '保存并测试', '已连接到应用。', '无法连接。请打开应用并检查端口。',
 '工作原理', '桌面应用是控制中心;扩展只负责在浏览器中执行屏蔽。',
 '1. 打开 Focus Relay 应用,在 设置 › 屏蔽 ›「网站屏蔽…」中选择网站。', '2. 在应用中开始番茄钟或计时器。', '3. 工作会话期间,列表中的网站会被屏蔽;结束或休息时恢复访问。', '4. 暂停、严格模式、音乐和奖杯都在应用中管理。严格模式下,会话期间无法解除屏蔽。', '5. 应用关闭时,扩展不会屏蔽任何内容。可在弹窗中一键屏蔽当前网站(只会添加到列表)。', '使用弹窗按钮屏蔽当前网站。',
 '关于', '版本 {v}', 'Focus Relay 扩展:在桌面应用进行工作会话时屏蔽分散注意力的网站。', '隐私:仅与本机上的应用通信(127.0.0.1)。不会向互联网发送数据,也不在浏览器之外保存任何内容。', '权限:重定向被屏蔽的网站、保存设置、定时检查,以及仅在打开弹窗时读取标签页地址。'],
de: ['Wird abgefragt…', 'App geschlossen', 'Öffne Focus Relay auf deinem Computer, um die Sperre zu aktivieren.', 'Fokus aktiv', 'Sperre pausiert', 'Sie läuft über die App weiter.', 'In Sitzung (ohne Sperre)', 'Bereit', 'Starte eine Sitzung in der App.',
 '{site} sperren', '{site} ist bereits gesperrt', 'Fertig: wird in deinen nächsten Sitzungen gesperrt.', 'Diese Website stand schon auf der Liste.', 'Nicht möglich: Öffne die App und prüfe den Port.', 'Einstellungen & Hilfe', 'Pomodoro · Arbeit', 'Pomodoro · Pause', 'Timer', 'Stoppuhr',
 'Deine Aufmerksamkeit ist geschützt', 'Diese Website ist nach der Arbeitssitzung wieder verfügbar.', 'Zurück', 'Einstellungen', 'So funktioniert es', 'Über', 'Sprache', 'Automatisch (Browsersprache)', 'Design', 'Automatisch (folgt dem Browser)', 'Hell', 'Dunkel',
 'Port der App', 'Standard 8765. Muss mit Einstellungen › Erweitert in der App übereinstimmen.', 'Speichern und testen', 'Mit der App verbunden.', 'Verbindung nicht möglich. Öffne die App und prüfe den Port.',
 'So funktioniert es', 'Die Desktop-App ist die Steuerzentrale; die Erweiterung setzt die Sperre nur im Browser um.',
 '1. Öffne die Focus-Relay-App und wähle die Websites unter Einstellungen › Sperre › „Websites sperren…“.', '2. Starte in der App einen Pomodoro oder Timer.', '3. Während der Arbeitssitzung sind die Websites der Liste gesperrt; nach dem Ende oder in Pausen sind sie wieder offen.', '4. Pausen, strenger Modus, Musik und Trophäen werden in der App verwaltet. Im strengen Modus lässt sich die Sperre während der Sitzung nicht lösen.', '5. Ist die App geschlossen, sperrt die Erweiterung nichts. Im Popup kannst du die aktuelle Website mit einem Klick sperren (sie wird nur der Liste hinzugefügt).', 'Mit der Popup-Schaltfläche sperrst du die aktuelle Website.',
 'Über', 'Version {v}', 'Focus-Relay-Erweiterung: sperrt ablenkende Websites, solange die Desktop-App eine Arbeitssitzung hat.', 'Datenschutz: Sie spricht nur mit der App auf diesem Computer (127.0.0.1). Es werden keine Daten ins Internet gesendet oder außerhalb deines Browsers gespeichert.', 'Berechtigungen: gesperrte Websites umleiten, Einstellungen speichern, die regelmäßige Abfrage planen und die Tab-Adresse nur beim Öffnen des Popups lesen.'],
it: ['Controllo…', 'App chiusa', 'Apri Focus Relay sul computer per attivare il blocco.', 'Concentrazione attiva', 'Blocco in pausa', "Riprende dall'app.", 'In sessione (senza blocco)', 'In attesa', "Avvia una sessione nell'app.",
 'Blocca {site}', '{site} è già bloccato', 'Fatto: sarà bloccato nelle prossime sessioni.', 'Quel sito era già nell\'elenco.', "Impossibile: apri l'app e controlla la porta.", 'Impostazioni e aiuto', 'Pomodoro · lavoro', 'Pomodoro · pausa', 'Timer', 'Cronometro',
 'La tua attenzione è protetta', 'Questo sito tornerà disponibile al termine della sessione di lavoro.', 'Indietro', 'Impostazioni', 'Come funziona', 'Informazioni', 'Lingua', 'Automatico (lingua del browser)', 'Tema', 'Automatico (segue il browser)', 'Chiaro', 'Scuro',
 "Porta dell'app", "Predefinita 8765. Deve coincidere con Impostazioni › Avanzate nell'app.", 'Salva e prova', "Connesso all'app.", "Impossibile connettersi. Apri l'app e controlla la porta.",
 'Come funziona', "L'app desktop è il centro di controllo; l'estensione applica solo il blocco nel browser.",
 "1. Apri l'app Focus Relay e scegli i siti in Impostazioni › Blocco › «Blocco siti web…».", "2. Avvia un Pomodoro o un Timer nell'app.", '3. Durante la sessione di lavoro i siti dell\'elenco sono bloccati; alla fine o nelle pause tornano accessibili.', "4. Pause, modalità rigorosa, musica e trofei si gestiscono nell'app. In modalità rigorosa il blocco non si può togliere durante la sessione.", "5. Se l'app è chiusa, l'estensione non blocca nulla. Dal popup puoi bloccare con un clic il sito che stai guardando (viene solo aggiunto all'elenco).", 'Usa il pulsante del popup per bloccare il sito attuale.',
 'Informazioni', 'Versione {v}', "Estensione di Focus Relay: blocca i siti che distraggono mentre l'app desktop ha una sessione di lavoro attiva.", 'Privacy: parla solo con l\'app su questo computer (127.0.0.1). Non invia dati a internet né salva nulla fuori dal browser.', "Autorizzazioni: reindirizzare i siti bloccati, salvare le impostazioni, pianificare il controllo periodico e leggere l'indirizzo della scheda solo quando apri il popup."],
nl: ['Opvragen…', 'App gesloten', 'Open Focus Relay op je computer om de blokkade te activeren.', 'Focus actief', 'Blokkade gepauzeerd', 'Hervat vanuit de app.', 'In sessie (zonder blokkade)', 'Wachtend', 'Start een sessie in de app.',
 '{site} blokkeren', '{site} is al geblokkeerd', 'Klaar: wordt geblokkeerd in je volgende sessies.', 'Die site stond al op de lijst.', 'Mislukt: open de app en controleer de poort.', 'Instellingen en hulp', 'Pomodoro · werk', 'Pomodoro · pauze', 'Timer', 'Stopwatch',
 'Je aandacht is beschermd', 'Deze site is weer beschikbaar na de werksessie.', 'Terug', 'Instellingen', 'Hoe het werkt', 'Over', 'Taal', 'Automatisch (taal van de browser)', 'Thema', 'Automatisch (volgt de browser)', 'Licht', 'Donker',
 'Poort van de app', 'Standaard 8765. Moet overeenkomen met Instellingen › Geavanceerd in de app.', 'Opslaan en testen', 'Verbonden met de app.', 'Verbinden mislukt. Open de app en controleer de poort.',
 'Hoe het werkt', 'De desktop-app is het controlecentrum; de extensie past alleen de blokkade in de browser toe.',
 '1. Open de Focus Relay-app en kies je sites bij Instellingen › Blokkade › “Websites blokkeren…”.', '2. Start een Pomodoro of Timer in de app.', '3. Tijdens de werksessie zijn de sites op de lijst geblokkeerd; na afloop of in pauzes zijn ze weer open.', '4. Pauzes, strikte modus, muziek en trofeeën regel je in de app. In de strikte modus kan de blokkade tijdens de sessie niet worden losgelaten.', '5. Is de app gesloten, dan blokkeert de extensie niets. In de popup blokkeer je met één klik de site die je bekijkt (wordt alleen aan de lijst toegevoegd).', 'Gebruik de knop in de popup om de huidige site te blokkeren.',
 'Over', 'Versie {v}', 'Focus Relay-extensie: blokkeert afleidende sites zolang de desktop-app een werksessie heeft.', 'Privacy: praat alleen met de app op deze computer (127.0.0.1). Stuurt geen gegevens naar internet en bewaart niets buiten je browser.', 'Machtigingen: geblokkeerde sites omleiden, je instellingen opslaan, de periodieke controle plannen en het tabadres alleen lezen als je de popup opent.'],
ru: ['Проверка…', 'Приложение закрыто', 'Откройте Focus Relay на компьютере, чтобы включить блокировку.', 'Фокус включён', 'Блокировка приостановлена', 'Возобновится из приложения.', 'В сессии (без блокировки)', 'Ожидание', 'Запустите сессию в приложении.',
 'Заблокировать {site}', '{site} уже заблокирован', 'Готово: будет блокироваться в следующих сессиях.', 'Этот сайт уже в списке.', 'Не получилось: откройте приложение и проверьте порт.', 'Настройки и справка', 'Помодоро · работа', 'Помодоро · перерыв', 'Таймер', 'Секундомер',
 'Ваше внимание под защитой', 'Этот сайт снова станет доступен после рабочей сессии.', 'Назад', 'Настройки', 'Как это работает', 'О расширении', 'Язык', 'Авто (язык браузера)', 'Тема', 'Авто (как в браузере)', 'Светлая', 'Тёмная',
 'Порт приложения', 'По умолчанию 8765. Должен совпадать с Настройки › Дополнительно в приложении.', 'Сохранить и проверить', 'Подключено к приложению.', 'Не удалось подключиться. Откройте приложение и проверьте порт.',
 'Как это работает', 'Настольное приложение — центр управления; расширение только применяет блокировку в браузере.',
 '1. Откройте Focus Relay и выберите сайты в Настройки › Блокировка › «Блокировка сайтов…».', '2. Запустите Помодоро или Таймер в приложении.', '3. Во время рабочей сессии сайты из списка заблокированы; после неё или в перерыве они снова открываются.', '4. Паузы, строгий режим, музыка и награды настраиваются в приложении. В строгом режиме блокировку нельзя снять во время сессии.', '5. Если приложение закрыто, расширение ничего не блокирует. Во всплывающем окне можно одним щелчком заблокировать текущий сайт (он только добавляется в список).', 'Кнопка во всплывающем окне блокирует текущий сайт.',
 'О расширении', 'Версия {v}', 'Расширение Focus Relay: блокирует отвлекающие сайты, пока в настольном приложении идёт рабочая сессия.', 'Конфиденциальность: общается только с приложением на этом компьютере (127.0.0.1). Данные в интернет не отправляются и вне браузера не хранятся.', 'Разрешения: перенаправлять заблокированные сайты, сохранять настройки, планировать периодическую проверку и читать адрес вкладки только при открытии окна.'],
ja: ['確認中…', 'アプリが閉じています', 'ブロックを有効にするには、パソコンで Focus Relay を開いてください。', '集中中', 'ブロック一時停止中', 'アプリから再開されます。', 'セッション中(ブロックなし)', '待機中', 'アプリでセッションを開始してください。',
 '{site} をブロック', '{site} はすでにブロック済みです', '完了: 次回のセッションからブロックされます。', 'このサイトはすでにリストにあります。', '失敗: アプリを開いてポートを確認してください。', '設定とヘルプ', 'ポモドーロ · 作業', 'ポモドーロ · 休憩', 'タイマー', 'ストップウォッチ',
 'あなたの集中は守られています', 'このサイトは作業セッションの終了後に再び開けます。', '戻る', '設定', '仕組み', 'このアプリについて', '言語', '自動(ブラウザの言語)', 'テーマ', '自動(ブラウザに合わせる)', 'ライト', 'ダーク',
 'アプリのポート', '既定は 8765。アプリの 設定 › 詳細設定 と一致させてください。', '保存してテスト', 'アプリに接続しました。', '接続できません。アプリを開いてポートを確認してください。',
 '仕組み', 'デスクトップアプリが司令塔で、拡張機能はブラウザでブロックを実行するだけです。',
 '1. Focus Relay アプリを開き、設定 › ブロック ›「サイトのブロック…」でサイトを選びます。', '2. アプリでポモドーロまたはタイマーを開始します。', '3. 作業セッション中はリストのサイトがブロックされ、終了後や休憩中は再び開けます。', '4. 一時停止、厳格モード、音楽、トロフィーはアプリで管理します。厳格モードではセッション中にブロックを解除できません。', '5. アプリが閉じていると、拡張機能は何もブロックしません。ポップアップから表示中のサイトをワンクリックでブロックできます(リストへの追加のみ)。', 'ポップアップのボタンで現在のサイトをブロックできます。',
 'このアプリについて', 'バージョン {v}', 'Focus Relay の拡張機能: デスクトップアプリで作業セッション中、気が散るサイトをブロックします。', 'プライバシー: このパソコン上のアプリ(127.0.0.1)とのみ通信します。インターネットへ送信せず、ブラウザ外にも保存しません。', '権限: ブロック対象サイトのリダイレクト、設定の保存、定期確認のスケジュール、ポップアップを開いたときのみタブのアドレスの読み取り。'],
ko: ['확인 중…', '앱이 닫혀 있음', '차단을 켜려면 컴퓨터에서 Focus Relay를 여세요.', '집중 중', '차단 일시 중지', '앱에서 다시 시작됩니다.', '세션 중(차단 없음)', '대기 중', '앱에서 세션을 시작하세요.',
 '{site} 차단', '{site}은(는) 이미 차단됨', '완료: 다음 세션부터 차단됩니다.', '이 사이트는 이미 목록에 있습니다.', '실패: 앱을 열고 포트를 확인하세요.', '설정 및 도움말', '포모도로 · 작업', '포모도로 · 휴식', '타이머', '스톱워치',
 '당신의 집중이 보호되고 있습니다', '이 사이트는 작업 세션이 끝나면 다시 열립니다.', '돌아가기', '설정', '작동 방식', '정보', '언어', '자동(브라우저 언어)', '테마', '자동(브라우저를 따름)', '라이트', '다크',
 '앱 포트', '기본값 8765. 앱의 설정 › 고급 과 같아야 합니다.', '저장 및 테스트', '앱에 연결되었습니다.', '연결할 수 없습니다. 앱을 열고 포트를 확인하세요.',
 '작동 방식', '데스크톱 앱이 제어 센터이며, 확장 프로그램은 브라우저에서 차단만 적용합니다.',
 '1. Focus Relay 앱을 열고 설정 › 차단 ›「웹사이트 차단…」에서 사이트를 고르세요.', '2. 앱에서 포모도로나 타이머를 시작하세요.', '3. 작업 세션 동안 목록의 사이트가 차단되고, 끝나거나 휴식 중에는 다시 열립니다.', '4. 일시 중지, 엄격 모드, 음악, 트로피는 앱에서 관리합니다. 엄격 모드에서는 세션 중 차단을 풀 수 없습니다.', '5. 앱이 닫혀 있으면 확장 프로그램은 아무것도 차단하지 않습니다. 팝업에서 보고 있는 사이트를 한 번에 차단할 수 있습니다(목록에 추가만 됩니다).', '팝업 버튼으로 현재 사이트를 차단할 수 있습니다.',
 '정보', '버전 {v}', 'Focus Relay 확장 프로그램: 데스크톱 앱에서 작업 세션이 진행되는 동안 방해되는 사이트를 차단합니다.', '개인정보: 이 컴퓨터의 앱(127.0.0.1)과만 통신합니다. 인터넷으로 데이터를 보내거나 브라우저 밖에 저장하지 않습니다.', '권한: 차단된 사이트 리디렉션, 설정 저장, 주기적 확인 예약, 팝업을 열 때만 탭 주소 읽기.'],
};
// Textos añadidos después (por idioma, fuera de la lista posicional).
const EXTRA = {
  pPermiso: {
    es: 'Firefox necesita tu permiso para bloquear sitios web.',
    en: 'Firefox needs your permission to block websites.',
    fr: 'Firefox a besoin de ton autorisation pour bloquer des sites.',
    pt: 'O Firefox precisa da sua permissão para bloquear sites.',
    zh: 'Firefox 需要你的授权才能屏蔽网站。',
    de: 'Firefox braucht deine Erlaubnis, um Websites zu blockieren.',
    it: 'Firefox ha bisogno del tuo permesso per bloccare i siti.',
    nl: 'Firefox heeft je toestemming nodig om websites te blokkeren.',
    ru: 'Firefox нужно ваше разрешение для блокировки сайтов.',
    ja: 'Firefox でサイトをブロックするには許可が必要です。',
    ko: 'Firefox에서 웹사이트를 차단하려면 권한이 필요합니다.'
  },
  pPermisoBtn: {
    es: 'Dar permiso', en: 'Grant permission', fr: 'Autoriser', pt: 'Conceder permissão', zh: '授予权限',
    de: 'Erlauben', it: 'Concedi permesso', nl: 'Toestemming geven', ru: 'Разрешить', ja: '許可する', ko: '권한 허용'
  },
  oBloqueado: {
    es: 'Bloqueado mientras hay una sesión en marcha: cambiar el puerto desconectaría el bloqueo. Podrás editarlo al terminar.',
    en: 'Locked while a session is running: changing the port would disconnect the blocking. You can edit it when the session ends.',
    fr: 'Verrouillé pendant une session : changer le port couperait le blocage. Modifiable à la fin de la session.',
    pt: 'Bloqueado durante uma sessão: mudar a porta desconectaria o bloqueio. Você poderá editar ao terminar.',
    zh: '会话进行中已锁定：更改端口会断开屏蔽。会话结束后可修改。',
    de: 'Während einer Sitzung gesperrt: Ein Portwechsel würde die Sperre trennen. Nach der Sitzung änderbar.',
    it: 'Bloccato durante una sessione: cambiare la porta scollegherebbe il blocco. Modificabile al termine.',
    nl: 'Vergrendeld tijdens een sessie: een andere poort zou de blokkade verbreken. Aanpasbaar na afloop.',
    ru: 'Заблокировано во время сессии: смена порта отключит блокировку. Изменить можно после её окончания.',
    ja: 'セッション中はロックされています。ポートを変えるとブロックが切れます。終了後に変更できます。',
    ko: '세션 중에는 잠겨 있습니다. 포트를 바꾸면 차단이 끊깁니다. 세션이 끝나면 변경할 수 있습니다.'
  }
};
let _lang = 'es';
function pickLang(pref) {
  if (pref && pref !== 'auto' && TXT[pref]) return pref;
  const nav = (navigator.language || 'es').slice(0, 2).toLowerCase();
  return TXT[nav] ? nav : 'en';
}
function t(key, vars) {
  const i = KEYS.indexOf(key);
  const ex = EXTRA[key];
  let s = ex ? (ex[_lang] || ex.en) : ((TXT[_lang] && TXT[_lang][i]) || TXT.es[i] || key);
  for (const k in (vars || {})) s = s.replace('{' + k + '}', vars[k]);
  return s;
}
// Aplica idioma y tema guardados y traduce los elementos con data-i="clave" (o data-i-ph para placeholder).
async function applyPrefs() {
  const p = await chrome.storage.local.get({ lang: 'auto', theme: 'auto' });
  _lang = pickLang(p.lang);
  const root = document.documentElement;
  root.lang = _lang;
  if (p.theme === 'light' || p.theme === 'dark') root.dataset.theme = p.theme; else delete root.dataset.theme;  // auto: sigue al navegador (prefers-color-scheme)
  document.querySelectorAll('[data-i]').forEach(e => { e.textContent = t(e.dataset.i, e.dataset.v ? JSON.parse(e.dataset.v) : null); });
  return p;
}
