"""Task Manager - Kivy version (Android + desktop) of the daily tasks app.

All task logic lives in task_store.py. This file is only the interface.
Tasks are saved in App.user_data_dir, which is the app's private writable
folder on Android (no storage permission needed) and a normal per-user
folder on desktop.
"""
import os
import re
from datetime import date, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import escape_markup, get_color_from_hex as hexc, platform

from task_store import TaskStore, day_key

# ------------------------------------------------------------------ fonts
# Bundled DejaVu Sans: has Arabic, Hebrew, Persian, Urdu glyphs plus the check
# marks used below. Registering it as "Roboto" makes it the default everywhere,
# so no Windows font path (or any system font) is needed.
HERE = os.path.dirname(os.path.abspath(__file__))
_REG = os.path.join(HERE, "assets", "fonts", "DejaVuSans.ttf")
_BOLD = os.path.join(HERE, "assets", "fonts", "DejaVuSans-Bold.ttf")
if os.path.exists(_REG):
    LabelBase.register(name="Roboto", fn_regular=_REG,
                       fn_bold=_BOLD if os.path.exists(_BOLD) else _REG)

# ------------------------------------------------- Arabic/Hebrew display
# Kivy's Android text engine does not join Arabic letters or order mixed text.
# These optional pure-Python helpers fix the *display* only; stored text is
# never changed. Without them the app still works.
try:
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover - optional dependency
    reshape = get_display = None

_RTL = re.compile("[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]")


def is_rtl(text):
    return bool(_RTL.search(text))


def shape(text):
    if reshape and get_display and is_rtl(text):
        try:
            return get_display(reshape(text))
        except Exception:
            return text
    return text


# ---------------------------------------------------------------- palette
HEADER, HEADER_DARK = "#6C5CE7", "#4B3FC4"
BG, CARD, TEXT, MUTED = "#F5F3FF", "#FFFFFF", "#2D2A55", "#8C89B0"
GREEN, GREEN_D = "#00B894", "#00977A"
RED, RED_D = "#E17055", "#C75A40"
BLUE, BLUE_D = "#0984E3", "#0770BE"
ORANGE, ORANGE_D = "#F39C12", "#D68910"
PURPLE, PURPLE_D = "#6C5CE7", "#5648C9"
ROW_DAILY, ROW_ONCE, ROW_DONE, ROW_SELECTED = (
    ("#EDE9FE", "#4C3FB1"), ("#E0F2FE", "#075985"), ("#DCFCE7", "#6B8F7B"), ("#FFEAA7", "#2D2A55"))


# ---------------------------------------------------------------- widgets
class ColorBox(BoxLayout):
    """BoxLayout with a rounded, coloured background."""

    def __init__(self, bg, radius=0, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            self._color = Color(*hexc(bg))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size

    def set_bg(self, bg):
        self._color.rgba = hexc(bg)


class RoundButton(Button):
    """Flat coloured button that darkens while pressed."""

    def __init__(self, bg, bg_down, radius=12, **kw):
        kw.setdefault("font_size", sp(15))
        kw.setdefault("bold", True)
        kw.setdefault("color", (1, 1, 1, 1))
        super().__init__(**kw)
        self.background_normal = self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self._bg, self._bg_down = hexc(bg), hexc(bg_down)
        with self.canvas.before:
            self._color = Color(*self._bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
        self.bind(pos=self._sync, size=self._sync, state=self._sync)

    def set_colors(self, bg, bg_down):
        self._bg, self._bg_down = hexc(bg), hexc(bg_down)
        self._sync()

    def _sync(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size
        self._color.rgba = self._bg_down if self.state == "down" else self._bg


class ProgressBar(Widget):
    value = NumericProperty(0)   # 0..100

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw, value=self._draw)

    def _draw(self, *_):
        self.canvas.clear()
        r = self.height / 2
        with self.canvas:
            Color(*hexc("#DDD9F5"))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            if self.value > 0:
                Color(*hexc(GREEN))
                RoundedRectangle(pos=self.pos, size=(max(self.height, self.width * self.value / 100.0),
                                                     self.height), radius=[r])


class GlyphButton(ButtonBehavior, Label):
    """Tap target showing the done / not-done mark."""


class TaskRow(ButtonBehavior, BoxLayout):
    """One task: [mark] title [Daily|Once]. Tap = select, double tap or mark = toggle."""

    def __init__(self, task, done, on_select, on_toggle, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(58),
                         padding=[dp(4), 0, dp(10), 0], spacing=dp(4), **kw)
        self.task_id, self.done, self.daily = task["id"], done, task["daily"]
        self._on_select, self._on_toggle = on_select, on_toggle
        self.base_bg, self.fg = (ROW_DONE if done else ROW_DAILY if self.daily else ROW_ONCE)
        with self.canvas.before:
            self._color = Color(*hexc(self.base_bg))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._sync, size=self._sync)

        self.glyph = GlyphButton(text="✔" if done else "○", font_size=sp(24), color=hexc(self.fg),
                                 size_hint_x=None, width=dp(46))
        self.glyph.bind(on_release=lambda *_: self._on_toggle(self.task_id))

        title = task["title"]
        rtl = is_rtl(title)
        shown = escape_markup(shape(title))
        self.title = Label(text=f"[s]{shown}[/s]" if done else shown, markup=True, color=hexc(self.fg),
                           font_size=sp(16), halign="right" if rtl else "left", valign="middle",
                           shorten=True, shorten_from="left" if rtl else "right", max_lines=1)
        self.title.bind(size=lambda w, s: setattr(w, "text_size", s))

        self.kind = Label(text="Daily" if self.daily else "Once", color=hexc(self.fg), font_size=sp(12),
                          size_hint_x=None, width=dp(52))
        for w in (self.glyph, self.title, self.kind):
            self.add_widget(w)

    def _sync(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size

    def set_selected(self, selected):
        self._color.rgba = hexc(ROW_SELECTED[0] if selected else self.base_bg)

    def on_touch_down(self, touch):
        if (self.collide_point(*touch.pos) and touch.is_double_tap
                and not self.glyph.collide_point(*touch.pos)):
            self._on_toggle(self.task_id)
            return True
        return super().on_touch_down(touch)

    def on_release(self):
        self._on_select(self.task_id)


# -------------------------------------------------------------------- app
class TaskManagerApp(App):
    title = "Task Manager"

    def build(self):
        Window.clearcolor = hexc(BG)
        Window.softinput_mode = "below_target"      # keep the input field above the keyboard
        if platform in ("win", "linux", "macosx"):  # phone-shaped window on desktop only
            Window.size = (dp(400), dp(760))

        data_dir = self.user_data_dir               # private, writable app folder on Android
        os.makedirs(data_dir, exist_ok=True)
        self.store = TaskStore(os.path.join(data_dir, "tasks.json"))

        self.current_day = date.today()
        self.following_today = True
        self.selected_id = None
        self.rows = {}
        self.daily_on = False
        self.popup = None

        root = BoxLayout(orientation="vertical", spacing=dp(10))

        # ---- header: date navigation + progress text
        header = ColorBox(HEADER, orientation="vertical", size_hint_y=None, height=dp(132),
                          padding=[dp(12), dp(10), dp(12), dp(8)], spacing=dp(6))
        nav = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        prev_b = RoundButton(HEADER_DARK, "#3A30A0", text="‹", font_size=sp(24), size_hint_x=None, width=dp(52))
        next_b = RoundButton(HEADER_DARK, "#3A30A0", text="›", font_size=sp(24), size_hint_x=None, width=dp(52))
        prev_b.bind(on_release=lambda *_: self.shift_day(-1))
        next_b.bind(on_release=lambda *_: self.shift_day(1))
        self.date_label = Label(color=(1, 1, 1, 1), bold=True, font_size=sp(17), halign="center",
                                valign="middle")
        self.date_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        nav.add_widget(prev_b); nav.add_widget(self.date_label); nav.add_widget(next_b)
        info = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.progress_label = Label(color=hexc("#E4E0FF"), font_size=sp(14), halign="left", valign="middle")
        self.progress_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        today_b = RoundButton(ORANGE, ORANGE_D, text="Today", size_hint_x=None, width=dp(92))
        today_b.bind(on_release=lambda *_: self.go_today())
        info.add_widget(self.progress_label); info.add_widget(today_b)
        header.add_widget(nav); header.add_widget(info)
        root.add_widget(header)

        body = BoxLayout(orientation="vertical", spacing=dp(8), padding=[dp(12), 0, dp(12), dp(10)])
        self.progress = ProgressBar(size_hint_y=None, height=dp(12))
        body.add_widget(self.progress)

        # ---- add row
        add_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        field = ColorBox(CARD, radius=dp(12), padding=[dp(2), dp(2)])
        self.entry = TextInput(hint_text="Add a task…", multiline=False, font_size=sp(17),
                               background_color=(0, 0, 0, 0), background_normal="", background_active="",
                               foreground_color=hexc(TEXT), cursor_color=hexc(HEADER),
                               hint_text_color=hexc(MUTED), padding=[dp(12), dp(13), dp(12), dp(10)],
                               write_tab=False)
        self.entry.bind(on_text_validate=lambda *_: self.add_task())
        field.add_widget(self.entry)
        add_b = RoundButton(GREEN, GREEN_D, text="+ Add", size_hint_x=None, width=dp(90))
        add_b.bind(on_release=lambda *_: self.add_task())
        add_row.add_widget(field); add_row.add_widget(add_b)
        body.add_widget(add_row)

        self.daily_btn = RoundButton("#E4E0FF", "#D3CEF7", text="○  Repeat every day", color=hexc(HEADER_DARK),
                                     bold=False, size_hint_y=None, height=dp(40), font_size=sp(14))
        self.daily_btn.bind(on_release=lambda *_: self.toggle_daily_option())
        body.add_widget(self.daily_btn)

        # ---- task list
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.list = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=[0, dp(2)])
        self.list.bind(minimum_height=self.list.setter("height"))
        self.scroll.add_widget(self.list)
        body.add_widget(self.scroll)

        # ---- bottom actions
        bar = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        done_b = RoundButton(BLUE, BLUE_D, text="✔ Done / Undo")
        del_b = RoundButton(RED, RED_D, text="Delete")
        clr_b = RoundButton(PURPLE, PURPLE_D, text="Clear done")
        done_b.bind(on_release=lambda *_: self.toggle_selected())
        del_b.bind(on_release=lambda *_: self.delete_selected())
        clr_b.bind(on_release=lambda *_: self.clear_completed())
        for b in (done_b, del_b, clr_b):
            bar.add_widget(b)
        body.add_widget(bar)
        root.add_widget(body)

        Window.bind(on_keyboard=self._on_keyboard)
        self.refresh()
        return root

    # ------------------------------------------------------ lifecycle (Android)
    def on_pause(self):
        return True            # keep the app alive in the background (data is saved on every change)

    def on_resume(self):
        if self.following_today and self.current_day != date.today():
            self.current_day = date.today()     # app was open past midnight
        self.refresh()

    def _on_keyboard(self, window, key, *args):
        if key == 27 and self.popup is not None:    # Android back button closes a dialog first
            self.popup.dismiss()
            return True
        return False

    # ------------------------------------------------------------- helpers
    @property
    def day(self):
        return day_key(self.current_day)

    def message(self, title, text):
        self.confirm(title, text, None)

    def confirm(self, title, text, on_yes, yes_label="Yes", yes_color=(RED, RED_D)):
        box = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))
        label = Label(text=shape(text), halign="center", valign="middle")
        label.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        box.add_widget(label)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        close = RoundButton("#7A77A8", "#625F8F", text="Cancel" if on_yes else "OK")
        row.add_widget(close)
        popup = Popup(title=title, content=box, size_hint=(0.9, None), height=dp(250),
                      separator_color=hexc(HEADER))
        close.bind(on_release=lambda *_: popup.dismiss())
        if on_yes:
            yes = RoundButton(*yes_color, text=yes_label)

            def accept(*_):
                popup.dismiss()
                on_yes()
            yes.bind(on_release=accept)
            row.add_widget(yes)
        box.add_widget(row)
        popup.bind(on_dismiss=lambda *_: setattr(self, "popup", None))
        self.popup = popup
        popup.open()

    def _guard(self, action):
        """Run a storage action; show a message instead of crashing if saving fails."""
        try:
            return action()
        except OSError as exc:
            self.message("Could not save", f"Your change could not be written to storage.\n{exc}")
            self.store.load()
            return None

    # ---------------------------------------------------------------- views
    def refresh(self):
        day = self.day
        d = self.current_day
        today = date.today()
        suffix = "  ·  Today" if d == today else ""
        self.date_label.text = f"{d.strftime('%A')}\n{d.day:02d} {d.strftime('%B %Y')}{suffix}"

        shown = self.store.visible(day)
        self.list.clear_widgets()
        self.rows = {}
        for task in shown:
            row = TaskRow(task, self.store.is_done(task, day), self.select, self.toggle)
            self.rows[task["id"]] = row
            self.list.add_widget(row)
        if self.selected_id not in self.rows:
            self.selected_id = None
        elif self.selected_id in self.rows:
            self.rows[self.selected_id].set_selected(True)

        if not shown:
            self.list.add_widget(Label(text="Nothing planned for this day", color=hexc(MUTED),
                                       size_hint_y=None, height=dp(80)))
        done, total = self.store.progress(day)
        self.progress.value = (done / total * 100) if total else 0
        self.progress_label.text = f"{done} of {total} completed" if total else "No tasks for this day"

    def select(self, task_id):
        if self.selected_id in self.rows:
            self.rows[self.selected_id].set_selected(False)
        self.selected_id = task_id
        if task_id in self.rows:
            self.rows[task_id].set_selected(True)

    # -------------------------------------------------------------- actions
    def shift_day(self, delta):
        self.current_day += timedelta(days=delta)
        self.following_today = self.current_day == date.today()
        self.selected_id = None
        self.refresh()

    def go_today(self):
        self.current_day = date.today()
        self.following_today = True
        self.selected_id = None
        self.refresh()

    def toggle_daily_option(self):
        self.daily_on = not self.daily_on
        self.daily_btn.text = ("✔" if self.daily_on else "○") + "  Repeat every day"
        if self.daily_on:
            self.daily_btn.set_colors(HEADER, HEADER_DARK)
            self.daily_btn.color = (1, 1, 1, 1)
        else:
            self.daily_btn.set_colors("#E4E0FF", "#D3CEF7")
            self.daily_btn.color = hexc(HEADER_DARK)

    def add_task(self):
        title = self.entry.text.strip()
        if not title:
            return
        if self._guard(lambda: self.store.add(title, self.daily_on, self.day)) is None:
            return
        self.entry.text = ""
        self.refresh()
        Clock.schedule_once(lambda _dt: setattr(self.entry, "focus", True), 0.05)

    def toggle(self, task_id):
        self.selected_id = task_id
        self._guard(lambda: self.store.toggle(task_id, self.day))
        self.refresh()

    def toggle_selected(self):
        if self.selected_id:
            self.toggle(self.selected_id)
        else:
            self.message("Done / Undo", "Tap a task first to select it.")

    def delete_selected(self):
        task = self.store.get(self.selected_id) if self.selected_id else None
        if task is None:
            return self.message("Delete", "Tap a task first to select it.")
        text = f'Delete "{task["title"]}"?'
        if task["daily"]:
            text += "\n\nThis is a daily task. It will be removed from all days."

        def do_delete():
            self._guard(lambda: self.store.delete(task["id"]))
            self.selected_id = None
            self.refresh()
        self.confirm("Delete task", text, do_delete, "Delete")

    def clear_completed(self):
        day = self.day
        count = sum(1 for t in self.store.tasks
                    if not t["daily"] and t["date"] == day and t["done"])
        if not count:
            return self.message("Clear done", "There are no completed one-time tasks on this day.\n"
                                              "Daily tasks are always kept.")

        def do_clear():
            self._guard(lambda: self.store.clear_completed(day))
            self.refresh()
        self.confirm("Clear done", f"Remove {count} completed task(s)?", do_clear, "Remove",
                     (PURPLE, PURPLE_D))


if __name__ == "__main__":
    TaskManagerApp().run()
