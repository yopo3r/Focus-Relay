# Contributing

```bash
cd desktop
python -m venv --system-site-packages .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt ruff
python -m unittest discover -s tests          # logic tests (they don't touch your real settings)
ruff check --select E9,F --per-file-ignores "ui.py:F821" .
```

Extension: `for f in extension/*.js; do node --check "$f"; done` (CI also checks that every language in `i18n.js` has all keys).

## Conventions
- **File names are in English** (`help_gui.py`, `achievements_gui.py`, `install_linux.sh`, …). Comments and the default UI language are Spanish; everything user-visible goes through i18n.
- UI strings: es/en/fr/pt/zh in `desktop/i18n.py` (`NEW` dict, 5-tuples) and `strings_web.json`; de/it/nl/ru/ja/ko in `desktop/locales/<code>.json`. All versions must have the same keys and `{placeholders}` (checked by `tests/test_i18n.py`). To add a language: add the code to `LANGS`, `MONTHS`, `locale_date_format` and create its JSON.
- Data is always written atomically (`.tmp` + `os.replace`); config writes go through `config.save_config` (thread-safe).
- Anything that can weaken a study session (strict mode, blocking, extension port, quitting, restoring backups) must be locked while a session is running: see `guard.py` and its tests.
- UI changes: test with light/dark themes and the "Very large" text size. Pure logic goes in modules without tkinter so it can be unit-tested.
- Add a test for every bug you fix, and an entry in `CHANGELOG.md`.

## Where to go

- Repository: https://github.com/yopo3r/Focus-Relay
- Bugs: [open an issue](https://github.com/yopo3r/Focus-Relay/issues/new?template=bug_report.md)
- Ideas and improvements: [suggest one](https://github.com/yopo3r/Focus-Relay/issues/new?template=feature_request.md)
- Changes: fork, branch, and open a pull request (see the template).
- New versions: [Releases](https://github.com/yopo3r/Focus-Relay/releases). The desktop app has a *Check for updates* button in Settings → About.
