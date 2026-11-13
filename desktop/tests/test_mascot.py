import importlib
import random
import sys
import time
import types
import unittest
from unittest import mock


class FakeCanvas:
    """Canvas mínimo: acepta cualquier create_* y cuenta las formas (así se prueba el dibujo sin tkinter)."""

    def __init__(self):
        self.items = 0
        self.kinds = {}
        self.calls = []

    def delete(self, *_):
        self.items = 0
        self.kinds = {}
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("create_"):
            def make(*args, **kw):
                self.items += 1
                self.kinds[name] = self.kinds.get(name, 0) + 1
                self.calls.append((name, args))
                return self.items
            return make
        raise AttributeError(name)


def _stub_ui():
    ui = types.ModuleType("ui")
    ui.CANVAS, ui.SURFACE, ui.INK, ui.MUTED, ui.PRIMARY = "#f4f5fb", "#ffffff", "#111111", "#666666", "#5b5bd6"
    ui.mix = lambda a, b, t: a
    ui.F = lambda name: ("TkDefaultFont", 10)
    return ui


class MascotLogicTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(sys.modules, {"ui": _stub_ui()})
        patcher.start()
        self.addCleanup(patcher.stop)
        sys.modules.pop("mascot", None)
        self.m = importlib.import_module("mascot")
        self.addCleanup(lambda: sys.modules.pop("mascot", None))

    def test_bubble_seconds_scales_with_text(self):
        self.assertGreaterEqual(self.m.bubble_seconds("hola"), self.m.BUBBLE_SECONDS)
        self.assertGreater(self.m.bubble_seconds("x" * 150), self.m.bubble_seconds("x" * 30))

    def test_every_palette_draws_and_unknown_falls_back(self):
        for name in list(self.m.PALETTES) + ["no-existe", None]:
            c = FakeCanvas()
            self.m.draw(c, "idle", 1, 1, palette=name)
            self.assertTrue(c.items)
        self.assertEqual(self.m.palette_for("no-existe"), self.m.PALETTES["peach"])

    def test_wary_mood_and_flag(self):
        self.assertEqual(self.m.mood_for({"ejecutando": True, "modo": "T"}, wary=True), "wary")
        self.assertEqual(self.m.mood_for(None, party_until=time.time() + 5, wary=True), "party")
        self.assertFalse(self.m.is_wary())
        self.m.set_wary(True)
        self.assertTrue(self.m.is_wary())
        self.m.set_wary(False)
        self.assertFalse(self.m.is_wary())
        c = FakeCanvas()
        self.m.draw(c, "wary", 30, 0)
        self.assertTrue(c.items)

    def test_anim_delay_adapts(self):
        m = self.m
        self.assertLess(m.anim_delay("party"), m.anim_delay("idle"))
        self.assertLess(m.anim_delay("idle", poke_left=5), m.anim_delay("idle"))
        self.assertGreaterEqual(m.anim_delay("idle", eco=True), 700)
        self.assertGreater(m.anim_delay("idle", draw_ms=60), m.anim_delay("idle"))      # equipo lento: espacia los cuadros
        self.assertLessEqual(m.anim_delay("idle", draw_ms=10_000), 1500)

    def test_invite_face_draws(self):
        c = FakeCanvas()
        self.m.draw(c, "invite", 7, 1)
        self.assertTrue(c.items)

    def test_greeting_by_time_of_day_and_name(self):
        import random as _r
        tx = {"hello_m": "buen día|hola m", "hello_t": "tarde", "hello_n": "noche", "hello_name": "Hola, {name}!|{name}, ¡aquí!"}
        g = self.m.greeting_pool
        self.assertEqual(g(tx, "", hour=8), ["buen día", "hola m"])
        self.assertEqual(g(tx, "", hour=15), ["tarde"])
        self.assertEqual(g(tx, "", hour=23), ["noche"])
        self.assertEqual(g(tx, "", hour=3), ["noche"])

        class Always(_r.Random):
            def random(self):
                return 0.0
        self.assertEqual(g(tx, "Yopo", hour=8, rng=Always()), ["Hola, Yopo!", "Yopo, ¡aquí!"])

    def test_growth_levels(self):
        g = self.m.growth_level
        self.assertEqual([g(0), g(1), g(2), g(3), g(4), g(6), g(7), g(100)], [0, 0, 1, 1, 2, 2, 3, 3])

    def test_mood(self):
        f = self.m.mood_for
        run = {"ejecutando": True, "modo": "T"}
        self.assertEqual(f(run, now=10, hour=12), "focus")
        self.assertEqual(f({"ejecutando": True, "modo": "P", "fase": "D"}, now=10, hour=12), "break")
        self.assertEqual(f({"ejecutando": True, "modo": "P", "fase": "W"}, now=10, hour=12), "focus")
        self.assertEqual(f(None, now=10, hour=12), "idle")
        self.assertEqual(f(None, now=10, hour=3), "sleepy")
        self.assertEqual(f(run, party_until=20, now=10, hour=12), "party")      # la fiesta gana
        self.assertEqual(f(run, party_until=5, now=10, hour=12), "focus")

    def test_pools_and_pick(self):
        texts = {"idle": "a|b |", "focus": "x", "streak": "{n} días"}
        self.assertEqual(self.m.message_pool("idle", texts, custom=["mía"], streak=3), ["a", "b", "mía", "3 días"])
        self.assertEqual(self.m.message_pool("focus", texts, custom=["mía"]), ["x", "mía"])
        self.assertEqual(self.m.message_pool("break", texts, custom=["mía"]), [])
        rng = random.Random(1)
        self.assertEqual(self.m.pick(["solo"], "solo", rng), "solo")
        for _ in range(20):
            self.assertNotEqual(self.m.pick(["a", "b"], "a", rng), "a")
        self.assertEqual(self.m.pick([], "x"), "")

    def test_draw_all_states_without_errors(self):
        for mood in self.m.MOODS:
            for level in range(4):
                for frame in (0, 1, 7, 50):
                    c = FakeCanvas()
                    self.m.draw(c, mood, frame, level, blink=bool(frame % 2), poke=frame % 5)
                    self.assertGreater(c.items, 10)

    def test_scaled_canvas_scales_coordinates_widths_and_fonts(self):
        seen = []

        class Rec:
            def delete(self, *a):
                pass

            def create_line(self, *a, **kw):
                seen.append(("line", a, kw))

            def create_text(self, *a, **kw):
                seen.append(("text", a, kw))
        sc = self.m.Scaled(Rec(), 192)                      # el doble de la cuadrícula de 96
        sc.create_line(1, 2, 3, 4, width=2, fill="#000")
        sc.create_text(10, 10, text="z", font=("TkDefaultFont", 12, "bold"))
        self.assertEqual(seen[0][1], (2.0, 4.0, 6.0, 8.0))
        self.assertEqual(seen[0][2]["width"], 4)
        self.assertEqual(seen[1][2]["text"], "z")
        self.assertEqual(seen[1][2]["font"], ("TkDefaultFont", 24, "bold"))

    def test_draw_scaled_at_every_size(self):
        for px in (self.m.MIN_PX, self.m.DEFAULT_PX, self.m.MAX_PX):
            c = FakeCanvas()
            self.m.draw(self.m.Scaled(c, px), "focus", 3, 2, shadow="#bbbbbb")
            self.assertGreater(c.items, 10)

    def test_clamps(self):
        self.assertEqual(self.m.clamp_size(5), self.m.MIN_PX)
        self.assertEqual(self.m.clamp_size(9999), self.m.MAX_PX)
        self.assertEqual(self.m.clamp_size("x"), self.m.DEFAULT_PX)
        self.assertEqual(self.m.clamp_pos(-50, 5000, 100, 100, 1920, 1080), (0, 980))
        self.assertEqual(self.m.clamp_pos(1900, 10, 100, 100, 1920, 1080), (1820, 10))
        self.assertEqual(self.m.clamp_pos(10, 10, 3000, 100, 1920, 1080), (0, 10))      # más grande que la pantalla

    def test_messages_exist_in_every_language(self):
        import i18n
        keys = ("mascotaIdle", "mascotaFoco", "mascotaDescanso", "mascotaFiesta", "mascotaSueno", "mascotaToque")
        for code in i18n.LANGS if hasattr(i18n, "LANGS") else ["es", "en"]:
            code = code[0] if isinstance(code, (tuple, list)) else code
            for k in keys:
                self.assertGreaterEqual(len(self.m.split_pool(i18n.get(k, code))), 3, (code, k))
            self.assertIn("{n}", i18n.get("mascotaRacha", code))


if __name__ == "__main__":
    unittest.main()


class _W:
    """Widget falso: acepta cualquier método y recuerda configuración básica."""
    def __init__(self, *a, **kw):
        self.opts, self._mapped, self._after = dict(kw), False, []
        self.geom = None
        self.geom_at_map = "nunca"
        self.calls_made = []

    def __getattr__(self, name):
        def any_method(*a, **kw):
            if name == "destroy":
                self._dead = True
            if name in ("pack", "pack_configure"):
                self._mapped = True           # como Tk real: pack_configure también empaca un widget oculto
            elif name in ("pack_forget", "withdraw"):
                self._mapped = False
            elif name == "deiconify":
                self._mapped = True
            elif name == "after":
                self._after.append(a)
            elif name == "geometry":
                self.geom = a[0]
            self.calls_made.append(name)
            if name == "deiconify":
                self.geom_at_map = self.geom
            elif name == "configure":
                self.opts.update(kw)
            return None
        return any_method

    def winfo_ismapped(self):
        return self._mapped

    _dead = False

    def winfo_exists(self):
        return not self._dead

    def winfo_viewable(self):
        return self._mapped

    def winfo_manager(self):
        return "pack" if self._mapped else ""

    def _xy(self):
        g = getattr(self, "geom", None) or ""
        return [int(v) for v in g.split("+")[-2:]] if g.count("+") >= 2 else [0, 0]

    def winfo_rootx(self):
        return self._xy()[0]

    def winfo_rooty(self):
        return self._xy()[1]

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def winfo_reqwidth(self):
        return max(self.opts.get("width", 0), 230 if self._mapped else 0, 110)

    def winfo_reqheight(self):
        return 110 + (40 if self._mapped else 0)


class _Root(_W):
    def __init__(self):
        super().__init__()
        self.jobs = []

    def after(self, ms, fn=None, *a):
        self.jobs.append(fn)


class MascotWindowTests(unittest.TestCase):
    def setUp(self):
        fake = types.ModuleType("tkinter")
        fake.Toplevel = fake.Frame = fake.Label = fake.Canvas = fake.Menu = _W
        fake.TclError = type("TclError", (Exception,), {})
        patcher = mock.patch.dict(sys.modules, {"ui": _stub_ui(), "tkinter": fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        sys.modules.pop("mascot", None)
        self.m = importlib.import_module("mascot")
        self.addCleanup(lambda: sys.modules.pop("mascot", None))
        self.saved = {}
        self.cfg = {"mascot": True, "mascot_size": 110, "mascot_x": None, "mascot_y": None}
        self.estado = None
        self.celebrate = 0
        self.opened = []
        self.root = _Root()
        self.win = self.m.MascotWindow(
            self.root, lambda: (self.estado, self.celebrate), lambda: dict(self.cfg),
            lambda **kw: (self.saved.update(kw), self.cfg.update(kw)), lambda: {"idle": "hola|chao", "hello_m": "hm", "hello_t": "ht", "hello_n": "hn", "poke": "jiji|jaja",
                                                                                "party": "yay|bien"},
            lambda: 5, lambda: self.opened.append(1))

    def _ev(self, **kw):
        return types.SimpleNamespace(**kw)

    def test_create_default_position_and_destroy(self):
        self.root.jobs.pop()()                                   # primer ciclo (1 s)
        self.assertIsNotNone(self.win.top)
        self.assertEqual((self.win.mx, self.win.my), (1920 - 110 - 40, 1080 - 110 - 110))
        self.cfg["mascot"] = False
        self.win._tick()
        self.assertIsNone(self.win.top)

    def test_hidden_bubble_stays_hidden(self):
        self.win._tick()
        self.assertTrue(self.win._bubble_on)
        self.win.bubble_until = 0                                # el globo caduca
        for _ in range(5):
            self.win._anim()
            self.win._tick()
        self.assertFalse(self.win._bubble_on)       # no debe reaparecer vacío ni parpadear

    def test_mascot_window_never_resizes_with_bubble(self):
        self.win._tick()
        before = self.win.top.geom.split("+")[0]
        self.win.bubble_until = 0
        self.win._anim()
        self.assertFalse(self.win._bubble_on)
        self.win._say("idle")
        self.assertTrue(self.win._bubble_on)
        self.assertEqual(self.win.top.geom.split("+")[0], before)     # tamaño fijo: sin saltos al aparecer/desaparecer

    def test_double_click_opens_panel(self):
        self.win._tick()
        self.win._press(self._ev(x_root=10, y_root=10))
        self.win._double(self._ev(x_root=10, y_root=10))
        self.assertEqual(self.opened, [1])
        self.assertIsNone(self.win._drag)

    def test_click_shows_text_even_if_bubble_window_was_hidden(self):
        self.win._tick()
        self.win.bwin._mapped = False                  # el sistema ocultó la ventana del globo
        self.win._say("poke")
        self.assertTrue(self.win.bwin.winfo_viewable())

    def test_window_hidden_by_system_is_restored(self):
        self.win._tick()
        self.win.top._mapped = False
        self.win._tick()
        self.assertTrue(self.win.top.winfo_viewable())

    def test_font_size_applies_and_clamps(self):
        self.assertEqual(self.m.clamp_font(3), self.m.MIN_FONT)
        self.assertEqual(self.m.clamp_font(99), self.m.MAX_FONT)
        self.assertEqual(self.m.clamp_font("x"), self.m.DEFAULT_FONT)
        self.cfg["mascot_font"] = 16
        self.win._tick()
        self.assertEqual(self.win._font_pt, 16)

    def test_greets_once_on_first_window(self):
        self.win._tick()
        self.assertGreater(self.win.hello_until, 0)
        first = self.win.hello_until
        self.win._destroy()
        self.win._retry_at = 0
        self.win._tick()
        self.assertEqual(self.win.hello_until, first)          # al recrear la ventana no vuelve a saludar

    def test_recreated_after_being_destroyed_from_outside(self):
        self.win._tick()
        old = self.win.top
        old.destroy()                                   # p. ej. rebuild() al cambiar de tema cierra todas las ventanas
        self.win._retry_at = 0
        self.win._tick()
        self.assertIsNotNone(self.win.top)
        self.assertIsNot(self.win.top, old)
        self.assertTrue(self.win.top.winfo_exists())

    def test_windows_recreated_after_resume_from_sleep(self):
        self.win._tick()
        old = self.win.top
        self.win._last_tick = time.time() - 600            # el reloj saltó: el equipo estuvo suspendido
        self.win._retry_at = 0
        self.win._tick()
        self.assertIsNot(self.win.top, old)

    def test_windows_recreated_when_animation_stalls(self):
        self.win._tick()
        old = self.win.top
        self.win._anim_at = time.time() - 60               # el bucle de dibujo murió (p. ej. tras la «espera moderna»)
        self.win._tick()
        self.assertIsNot(self.win.top, old)

    def test_windows_recreated_when_clock_skews_from_monotonic(self):
        self.win._tick()
        old = self.win.top
        self.win._last_mono -= 0                           # el monotónico no avanzó, el reloj de pared sí (suspensión)
        self.win._last_tick = time.time() - 15
        self.win._tick()
        self.assertIsNot(self.win.top, old)

    def test_windows_recreated_on_unlock_and_screen_change(self):
        self.win._tick()
        old = self.win.top
        self.win._session_locked = lambda: True
        self.win._tick()
        self.assertIs(self.win.top, old)                   # bloqueada: aún no se toca
        self.win._session_locked = lambda: False
        self.win._tick()
        self.assertIsNone(self.win.top)                    # al desbloquear se destruye y espera unos segundos
        self.win._retry_at = 0
        self.win._tick()
        cur = self.win.top
        self.assertIsNot(cur, old)                         # ...y se vuelve a crear
        self.win._screen = (1, 1)
        self.win._tick()
        self.assertIsNone(self.win.top)                    # cambió la pantalla

    def test_position_recomputed_after_transient_small_screen(self):
        self.cfg["mascot_x"], self.cfg["mascot_y"] = 1500, 800
        self.win._tick()
        self.assertEqual((self.win.mx, self.win.my), (1500, 800))
        self.win._screen = (1, 1)
        self.win._screen_sig = lambda: (1, 1)               # aquí se prueba solo el recálculo de posición
        self.win.top.winfo_screenwidth = lambda: 300       # pantalla en transición: no se toca nada
        self.win._tick()
        self.assertEqual((self.win.mx, self.win.my), (1500, 800))
        self.win.top.winfo_screenwidth = lambda: 800       # pantalla más chica pero válida: se recorta...
        self.win.top.winfo_screenheight = lambda: 600
        self.win._tick()
        self.assertLess(self.win.mx, 800)
        self.win.top.winfo_screenwidth = lambda: 1920      # ...y al volver, regresa a la posición guardada
        self.win.top.winfo_screenheight = lambda: 1080
        self.win._tick()
        self.assertEqual((self.win.mx, self.win.my), (1500, 800))

    def test_first_bubble_is_placed_before_it_is_shown(self):
        self.win._tick()                                   # el saludo inicial se pide antes de conocer la posición
        self.assertTrue(self.win.bwin._mapped)
        self.assertNotIn(self.win.bwin.geom_at_map, (None, "nunca"))     # ya tenía su sitio cuando se mostró
        calls = self.win.bwin.calls_made
        self.assertLess(calls.index("geometry"), calls.index("deiconify"))
        self.assertIn("update_idletasks", calls[calls.index("geometry"):calls.index("deiconify")])

    def test_goodbye_waves_shows_text_and_returns_wait(self):
        self.win._tick()
        wait = self.win.say_goodbye()
        self.assertEqual(wait, self.m.BYE_SECONDS)
        self.assertTrue(self.win._bubble_on)
        self.assertTrue(self.win.message)
        said = self.win.message
        self.win._tick()                                   # el tick no pisa la despedida
        self.assertEqual(self.win.message, said)
        self.assertGreater(self.win._bye_until, time.time())

    def test_goodbye_respects_option_and_hidden_mascot(self):
        self.win._tick()
        self.cfg["mascot_bye"] = False
        self.assertEqual(self.win.say_goodbye(), 0.0)
        self.cfg["mascot_bye"] = True
        self.cfg["mascot"] = False
        self.win._tick()                                   # mascota oculta: destruida
        self.assertEqual(self.win.say_goodbye(), 0.0)

    def test_farewell_pool_uses_name_sometimes(self):
        texts = {"bye": "Chao|Hasta pronto", "bye_name": "Chao, {name}"}
        self.assertEqual(self.m.farewell_pool(texts, "", random.Random(1)), ["Chao", "Hasta pronto"])
        got = {tuple(self.m.farewell_pool(texts, "Yopo", random.Random(i))) for i in range(30)}
        self.assertIn(("Chao, Yopo",), got)
        self.assertIn(("Chao", "Hasta pronto"), got)

    def test_poke_while_focus_draws_only_two_hands(self):
        c = FakeCanvas()
        self.m.draw(c, "focus", 3, 0, poke=5)
        # los brazos levantados (fiesta/toque) son óvalos a la altura de la cabeza (y < 58) en los costados
        raised = [a for n, a in c.calls if n == "create_oval" and abs(a[0] - 48) > 24 and a[1] < 58 and a[2] - a[0] < 14 and a[3] - a[1] > 12]
        self.assertEqual(raised, [])

    def test_text_disabled_never_shows_bubble(self):
        self.cfg["mascot_text"] = False
        self.win._tick()
        self.win._anim()
        self.assertFalse(self.win._bubble_on)

    def test_drag_saves_position_and_click_pokes(self):
        self.win._tick()
        self.win._press(self._ev(x_root=500, y_root=500))
        self.win._motion(self._ev(x_root=520, y_root=550))
        self.win._release(self._ev())
        self.assertEqual((self.saved["mascot_x"], self.saved["mascot_y"]), (1770 + 20, 860 + 50))
        self.win._press(self._ev(x_root=10, y_root=10))
        self.win._release(self._ev())                           # sin mover: es un clic
        self.assertGreater(self.win.poke_left, 0)
        self.assertIn(self.win.message, ("jiji", "jaja"))

    def test_drag_clamped_inside_screen(self):
        self.win._tick()
        self.win._press(self._ev(x_root=0, y_root=0))
        self.win._motion(self._ev(x_root=-5000, y_root=-5000))
        self.assertEqual((self.win.mx, self.win.my), (0, 0))

    def test_wheel_resizes_within_limits(self):
        self.win._tick()
        self.win._wheel(self._ev(delta=120))
        self.assertEqual(self.saved["mascot_size"], 118)
        self.cfg["mascot_size"] = 240
        self.win._tick()
        self.win._resize(+8)
        self.assertEqual(self.win.size, 240)                    # no pasa del máximo

    def test_celebration_and_mood_from_state(self):
        self.win._tick()
        self.celebrate = 1
        self.estado = {"ejecutando": True, "modo": "T"}
        self.win._tick()
        self.assertEqual(self.win.mood, "party")
        self.assertIn(self.win.message, ("yay", "bien"))
        self.win.party_until = 0
        self.win._tick()
        self.assertEqual(self.win.mood, "focus")

    def test_failed_creation_does_not_leak_or_retry_every_second(self):
        self.win._destroy()
        calls = []

        class Boom(_W):
            def overrideredirect(self, *a):
                calls.append(1)
                raise RuntimeError("sin ventana")
        self.m.tk_boom = Boom
        sys.modules["tkinter"].Toplevel = Boom
        self.win._create()
        self.assertIsNone(self.win.top)
        self.win._tick()                                        # dentro de la espera: no reintenta
        self.assertEqual(len(calls), 1)

    def test_animation_survives_drawing_errors(self):
        self.win._tick()
        with mock.patch.object(self.m, "draw", side_effect=RuntimeError("x")):
            self.win._anim()
        self.assertIsNotNone(self.win.top)                       # sigue viva y reprogramada
        self.assertTrue(self.win.top._after)

    def test_animation_runs(self):
        self.win._tick()
        for _ in range(5):
            self.win._anim()
        self.assertGreater(self.win.frame_no, 4)

