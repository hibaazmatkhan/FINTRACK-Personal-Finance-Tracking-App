"""
Centralized theme system for FinTrack (Flet edition).

Two visual languages, used deliberately for different purposes:
  - GLASS  → things you read (cards, summaries, tiles). Frosted, blurred,
             tinted, floats over the gradient-mesh background.
  - NEO    → things you press (buttons, nav items, switches). Flat fill,
             soft dual offset shadow simulating a single light source.

Glass only reads as "glass" when there's something soft and colorful
behind it to blur, so every screen sits on a gradient-mesh background
(a few large, very-low-opacity blurred color blobs). Flat chrome areas
(sidebar) sit on the plain surface color with no mesh behind them, so
neo buttons there get a clean, undistracting shadow.
"""
import json
import os
import sys
import time
import requests
import flet as ft

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(os.environ.get("APPDATA", _BASE), "FinTrack", "theme_settings.json")

# ── Currency configuration ──────────────────────────────────

CURRENCY_CONFIG = {
    "PKR": {"symbol": "₨", "prefix": True,  "thousand_sep": ",", "decimal_sep": ".", "places": 2},
    "USD": {"symbol": "$", "prefix": True,  "thousand_sep": ",", "decimal_sep": ".", "places": 2},
    "EUR": {"symbol": "€", "prefix": True,  "thousand_sep": ".", "decimal_sep": ",", "places": 2},
    "GBP": {"symbol": "£", "prefix": True,  "thousand_sep": ",", "decimal_sep": ".", "places": 2},
    "INR": {"symbol": "₹", "prefix": True,  "thousand_sep": ",", "decimal_sep": ".", "places": 2},
    "AED": {"symbol": "د.إ", "prefix": False, "thousand_sep": ",", "decimal_sep": ".", "places": 2},
    "SAR": {"symbol": "﷼", "prefix": False, "thousand_sep": ",", "decimal_sep": ".", "places": 2},
    "CAD": {"symbol": "$", "prefix": True,  "thousand_sep": ",", "decimal_sep": ".", "places": 2, "prefix_code": "CA"},
}

CURRENCY_LIST = sorted(CURRENCY_CONFIG.keys())

# Fallback rates if the live API is unreachable.
_FALLBACK_RATES = {
    "PKR": 280.0, "USD": 1.0, "EUR": 0.92, "GBP": 0.79,
    "INR": 83.5, "AED": 3.67, "SAR": 3.75, "CAD": 1.36,
}

# ── Live exchange-rate fetching ─────────────────────────────

_API_URL = "https://open.er-api.com/v6/latest/USD"
_live_rates: dict[str, float] | None = None
_live_rates_timestamp: float = 0
_LIVE_CACHE_TTL = 3600  # 1 hour


def fetch_live_rates() -> dict[str, float]:
    """Fetch exchange rates against USD from the live API.
    Cached for 1 hour to avoid hammering the free tier.
    Returns a dict like {"PKR": 280.0, "EUR": 0.92, ...} or
    the fallback dict on failure.
    """
    global _live_rates, _live_rates_timestamp
    now = time.time()
    if _live_rates is not None and (now - _live_rates_timestamp) < _LIVE_CACHE_TTL:
        return _live_rates
    try:
        resp = requests.get(_API_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        all_rates = data.get("rates", {})
        # Only keep rates we actually use
        _live_rates = {code: float(all_rates[code]) for code in CURRENCY_LIST if code in all_rates}
        _live_rates_timestamp = now
        return _live_rates
    except Exception:
        return dict(_FALLBACK_RATES)


def get_conversion_rate(from_cur: str, to_cur: str) -> float:
    """Live exchange rate: how many `from_cur` equal 1 `to_cur`.
    Falls back to hardcoded rates if the API is unreachable.
    """
    rates = fetch_live_rates()
    rate_from = rates.get(from_cur) or _FALLBACK_RATES.get(from_cur, 1.0)
    rate_to = rates.get(to_cur) or _FALLBACK_RATES.get(to_cur, 1.0)
    return rate_from / rate_to


def format_amount(amount: float, currency_code: str | None = None) -> str:
    """Format a monetary amount for display.
    
    If currency_code is omitted, uses the current theme currency.
    No conversion factor is applied — amounts are already stored
    in the user's chosen currency.
    """
    if currency_code is None:
        currency_code = theme.currency
    cfg = CURRENCY_CONFIG.get(currency_code, CURRENCY_CONFIG["USD"])
    formatted = f"{amount:,.{cfg['places']}f}"
    formatted = formatted.replace(",", "X").replace(cfg["decimal_sep"], "T")
    formatted = formatted.replace("X", cfg["thousand_sep"]).replace("T", cfg["decimal_sep"])
    prefix_code = cfg.get("prefix_code", "")
    if cfg["prefix"]:
        return f"{prefix_code}{cfg['symbol']}{formatted}"
    else:
        return f"{formatted} {cfg['symbol']}"


# ── Motion language ─────────────────────────────────────────
# Classy-first, funky-as-accent: restrained EASE_OUT_CUBIC/QUART for
# almost everything (hover lift, press dip, screen transitions); a
# touch of spring/overshoot reserved for exactly one element per
# screen (the primary FAB) so it reads as a deliberate accent, not
# noise. No rotation/tilt anywhere — hover lift is scale + rise only.

class Motion:
    HOVER_SCALE = 1.02
    PRESS_SCALE = 0.97
    FAB_HOVER_SCALE = 1.04
    FAB_PRESS_SCALE = 0.95

    FAST = ft.Animation(120, ft.AnimationCurve.EASE_OUT_CUBIC)
    NORMAL = ft.Animation(180, ft.AnimationCurve.EASE_OUT_CUBIC)
    LIFT = ft.Animation(200, ft.AnimationCurve.EASE_OUT_QUART)
    SPRING = ft.Animation(280, ft.AnimationCurve.EASE_OUT_BACK)
    TRANSITION = ft.Animation(280, ft.AnimationCurve.EASE_OUT_QUART)


def _is_enter(e) -> bool:
    """on_hover's e.data has carried both bool and 'true'/'false' string
    across Flet versions — check both so this keeps working either way."""
    return e.data is True or str(e.data).lower() == "true"


def hoverable(control: ft.Container, *, hover_scale: float = Motion.HOVER_SCALE,
              press_scale: float = Motion.PRESS_SCALE, on_click=None,
              hover_offset: ft.Offset = None) -> ft.Container:
    """Wires the standard hover-lift / press-dip behavior onto a
    container in place, and returns it for chaining. Scale only — no
    rotation/tilt anywhere in the app.

    When hover_offset is set (e.g. ft.Offset(0, -3)), the control will
    translate vertically on hover in addition to the scale. Use this
    for items inside scroll views where scale overflow would get clipped.

    on_click may be a regular function or an `async def` (e.g. a photo
    upload that awaits a file picker) — both are handled correctly.

    Use on anything clickable: nav items, buttons, cards, tiles.
    """
    import inspect

    control.scale = 1.0
    control.animate_scale = Motion.LIFT
    control.offset = ft.Offset(0, 0)
    if hover_offset is not None:
        control.animate_offset = Motion.LIFT
    control.ink = on_click is not None
    control.clip_behavior = ft.ClipBehavior.NONE

    def _safe_update():
        try:
            control.update()
        except RuntimeError:
            pass  # not attached to a page yet

    def on_hover(e):
        enter = _is_enter(e)
        control.scale = hover_scale if enter else 1.0
        if hover_offset is not None:
            control.offset = hover_offset if enter else ft.Offset(0, 0)
        _safe_update()

    async def on_click_wrapped(e):
        control.scale = press_scale
        _safe_update()
        if on_click:
            result = on_click(e)
            if inspect.isawaitable(result):
                await result
        control.scale = hover_scale
        if hover_offset is not None:
            control.offset = hover_offset
        _safe_update()

    control.on_hover = on_hover
    if on_click:
        control.on_click = on_click_wrapped
    return control


def breathing(control: ft.Container, page: ft.Page, *,
              scale_amplitude: float = 0.015, glow_amplitude: float = 10,
              period_seconds: float = 3.5):
    """A soft 'breathing' pulse — gentle scale grow/shrink combined with
    a matching shadow glow, like a slow heartbeat. Used on the balance
    hero as the one signature idle-motion touch on that screen.

    Deliberately not animating shadow continuously on its own (Flutter
    guidance: opacity/shadow animations are comparatively expensive,
    so they shouldn't run as their own independent continuous loop) —
    instead the shadow's blur_radius is driven by the *same* sparse
    keyframe schedule as the scale change, so it's only ever
    transitioning between a few eased steps, not recomputed every
    frame. Same lesson learned from floating()'s pixelation issue:
    few keyframes, let Flet's own animator interpolate between them.
    """
    import math
    keyframes = 6
    fractions = [i / keyframes for i in range(keyframes + 1)]
    # 0 -> 1 -> 0 smooth bump, peaking at the half-cycle point.
    bumps = [0.5 - 0.5 * math.cos(2 * math.pi * f) for f in fractions]
    hop_duration = int((period_seconds * 1000) / keyframes)

    base_shadow = control.shadow
    base_blur = base_shadow.blur_radius if isinstance(base_shadow, ft.BoxShadow) else 24

    control.animate_scale = ft.Animation(hop_duration, ft.AnimationCurve.EASE_IN_OUT_SINE)
    control.animate = ft.Animation(hop_duration, ft.AnimationCurve.EASE_IN_OUT_SINE)

    async def loop():
        import asyncio
        i = 0
        while True:
            try:
                _ = control.page  # raises once control is detached
                bump = bumps[i % len(bumps)]
                control.scale = 1.0 + scale_amplitude * bump
                if isinstance(base_shadow, ft.BoxShadow):
                    control.shadow = ft.BoxShadow(
                        blur_radius=base_blur + glow_amplitude * bump,
                        spread_radius=base_shadow.spread_radius,
                        color=base_shadow.color,
                        offset=base_shadow.offset,
                    )
                control.update()
            except Exception:
                break  # detached or torn down — stop quietly
            i += 1
            await asyncio.sleep(hop_duration / 1000)

    page.run_task(loop)


def floating(control: ft.Container, page: ft.Page, amplitude: float = 0.012,
             period_seconds: float = 4.0):
    """Starts a slow, continuous idle float — position-based motion,
    kept around for other potential uses. The balance hero itself
    currently uses neither this nor breathing() — just a plain
    hover-triggered zoom via hoverable(), no idle motion at all.

    Two earlier versions of this both had real problems:
      1. Animating between just 2 fixed points with Flet's easing had
         to fully reverse direction at each extreme — that reversal is
         what reads as mechanical/robotic.
      2. Driving the position from Python at ~12 updates/second (one
         offset value per frame) fixed the motion curve, but every
         .update() forces the client to recomposite the whole subtree
         — including blur and shadow layers on a glass card, which are
         expensive to redraw that often. At that rate the *rendering*
         itself can't keep up smoothly and looks stepped/pixelated,
         even though the underlying motion math is correct.

    This version takes a middle path: only a handful of keyframes per
    cycle (not 2, not ~50), each given a properly long, eased
    transition via Flet's own animate_offset — so Flet's renderer (not
    Python) handles the actual frame-by-frame interpolation, which is
    what it's built to do efficiently, while still tracing a smooth
    curve overall rather than snapping between two extremes.
    """
    # Quarter-cycle keyframes of a cosine curve: starts and ends slow,
    # fastest through the middle — still a true smooth curve shape,
    # just sampled coarsely enough that each hop is cheap to render.
    import math
    keyframes = 6
    fractions = [i / keyframes for i in range(keyframes + 1)]
    offsets = [-amplitude * (0.5 - 0.5 * math.cos(2 * math.pi * f)) for f in fractions]
    hop_duration = int((period_seconds * 1000) / keyframes)
    control.animate_offset = ft.Animation(hop_duration, ft.AnimationCurve.EASE_IN_OUT_SINE)

    async def loop():
        import asyncio
        i = 0
        while True:
            try:
                _ = control.page  # raises once control is detached
                control.offset = ft.Offset(0, offsets[i % len(offsets)])
                control.update()
            except Exception:
                break  # detached or torn down — stop quietly
            i += 1
            await asyncio.sleep(hop_duration / 1000)

    page.run_task(loop)


def screen_transition(control: ft.Control) -> ft.Container:
    """Wraps a freshly-built screen so it fades + slides up on mount
    instead of snapping into place. Caller should set opacity/offset
    back to resting values right after adding it to the page."""
    wrapper = ft.Container(
        content=control,
        opacity=0,
        offset=ft.Offset(0, 0.03),
        animate_opacity=Motion.TRANSITION,
        animate_offset=Motion.TRANSITION,
        expand=True,
    )
    return wrapper


def dialog_title_with_close(text: str, page: ft.Page, size: int = 18) -> ft.Row:
    """Standard title row for form dialogs (add/edit something): the
    title on the left, an X on the right that closes without saving.
    Use for dialogs the person fills in; skip it for simple confirm/
    info dialogs that already have clear Cancel/OK actions."""
    c = theme.colors
    return ft.Row(
        [
            ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.IconButton(
                icon=ft.Icons.CLOSE, icon_size=20, icon_color=c["text_mid"],
                on_click=lambda e: page.pop_dialog(),
                tooltip="Close without saving",
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )


def confirm_dialog(page: ft.Page, title: str, message: str, *,
                    confirm_label: str = "Yes", confirm_color: str = None,
                    on_confirm=None) -> ft.AlertDialog:
    """Standard themed Yes/No confirmation dialog — explicit bgcolor and
    text colors throughout, since plain ft.AlertDialog/ft.Text with no
    color set falls back to Flutter's default dialog theme rather than
    reliably tracking our light/dark palette (this was the cause of
    invisible text in dark mode on every 'Are you sure?' dialog)."""
    c = theme.colors

    def do_confirm(e):
        page.pop_dialog()
        if on_confirm:
            on_confirm()

    def do_cancel(e):
        page.pop_dialog()

    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=c["surface"],
        shape=ft.RoundedRectangleBorder(radius=20),
        title=ft.Text(title, color=c["text_dark"], weight=ft.FontWeight.BOLD),
        content=ft.Text(message, color=c["text_mid"]),
        actions=[
            ft.TextButton(content=ft.Text("Cancel", color=c["text_mid"]), on_click=do_cancel),
            ft.TextButton(
                content=ft.Text(confirm_label, color=confirm_color or Palette.PRIMARY, weight=ft.FontWeight.BOLD),
                on_click=do_confirm,
            ),
        ],
    )
    page.show_dialog(dialog)
    return dialog


def mount(wrapper: ft.Container, page: ft.Page):
    """Call right after adding a screen_transition()-wrapped control to
    the page — flips it to its resting state so the transition plays."""
    wrapper.opacity = 1
    wrapper.offset = ft.Offset(0, 0)
    page.update()


class Palette:
    # ── Brand colors (shared across themes) ──────────────
    PRIMARY       = "#D96B4D"   # terracotta
    PRIMARY_DARK  = "#B8512F"
    PRIMARY_LIGHT = "#FFE3D6"
    ACCENT        = "#E8A06E"
    INCOME        = "#8FA888"   # sage green
    EXPENSE       = "#D64B3C"
    ROSE          = "#F9D8CC"
    WHITE         = "#FFFFFF"
    BLACK         = "#000000"

    LIGHT = {
        "surface":      "#F3EDE6",
        "text_dark":    "#2D211D",
        "text_mid":     "#74645E",
        "text_light":   "#A9958C",
        "border":       "#DCD3C9",
        # Glass
        "glass_tint":   WHITE,
        "glass_alpha":  0.55,
        "glass_border": WHITE,
        "glass_border_alpha": 0.45,
        "glass_shadow": BLACK,
        "glass_shadow_alpha": 0.10,
        # Neo (flat base + soft dual shadow)
        "neo_base":     "#EDE6DF",
        "neo_light":    WHITE,
        "neo_light_alpha": 0.9,
        "neo_dark":     "#B8AEA2",
        "neo_dark_alpha": 0.45,
        # Gradient mesh blobs (color, opacity)
        "mesh_blobs": [
            (PRIMARY, 0.16),
            (INCOME, 0.10),
            (ACCENT, 0.12),
        ],
    }

    DARK = {
        "surface":      "#191613",
        "text_dark":    "#F7EFE9",
        "text_mid":     "#B7A39B",
        "text_light":   "#80706A",
        "border":       "#332E2B",
        # Glass
        "glass_tint":   "#2A2522",
        "glass_alpha":  0.45,
        "glass_border": WHITE,
        "glass_border_alpha": 0.10,
        "glass_shadow": BLACK,
        "glass_shadow_alpha": 0.35,
        # Neo
        "neo_base":     "#211D1A",
        "neo_light":    "#3A332E",
        "neo_light_alpha": 0.7,
        "neo_dark":     BLACK,
        "neo_dark_alpha": 0.6,
        # Gradient mesh blobs
        "mesh_blobs": [
            (PRIMARY, 0.13),
            (INCOME, 0.07),
            ("#7A5AA8", 0.08),
        ],
    }


class ThemeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        data = self._load_settings()
        self.mode = data.get("mode", "light")
        self._currency = data.get("currency", "PKR")
        self._listeners = []
        self._currency_listeners = []

    def _load_settings(self) -> dict:
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        # First run — copy bundled default or create fresh
        bundled = os.path.join(_BASE, "theme_settings.json")
        if os.path.exists(bundled):
            try:
                with open(bundled, "r") as f:
                    data = json.load(f)
                os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(data, f)
                return data
            except Exception:
                pass
        return {}

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, "w") as f:
                json.dump({"mode": self.mode, "currency": self._currency}, f)
        except Exception:
            pass

    @property
    def is_dark(self) -> bool:
        return self.mode == "dark"

    @property
    def colors(self) -> dict:
        return Palette.DARK if self.is_dark else Palette.LIGHT

    @property
    def currency(self) -> str:
        return self._currency

    @currency.setter
    def currency(self, code: str):
        if code in CURRENCY_CONFIG and code != self._currency:
            self._currency = code
            self._save_settings()
            for cb in list(self._currency_listeners):
                try:
                    cb()
                except Exception:
                    pass

    def sync_currency(self, code: str):
        """Called after fetching the user's profile from Supabase.
        Updates locally without notifying (the UI isn't built yet)."""
        if code in CURRENCY_CONFIG:
            self._currency = code
            self._save_settings()

    def add_currency_listener(self, callback):
        self._currency_listeners.append(callback)

    def remove_currency_listener(self, callback):
        if callback in self._currency_listeners:
            self._currency_listeners.remove(callback)

    def toggle(self):
        self.mode = "dark" if self.mode == "light" else "light"
        self._save_settings()
        self._notify()

    def add_listener(self, callback):
        self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass


theme = ThemeManager()


# ── Page chrome ────────────────────────────────────────────

def _build_theme(is_dark: bool) -> ft.Theme:
    """A full ft.Theme for the given mode — primarily so DatePicker (and
    any other 'service' control that pulls from Flutter's default
    Material theme rather than per-instance properties) actually
    matches our palette instead of Flutter's stock blue/white."""
    p = Palette.DARK if is_dark else Palette.LIGHT
    color_scheme = ft.ColorScheme(
        primary=Palette.PRIMARY,
        on_primary=Palette.WHITE,
        secondary=Palette.ACCENT,
        on_secondary=p["text_dark"],
        surface=p["surface"],
        on_surface=p["text_dark"],
        on_surface_variant=p["text_mid"],
        outline=p["border"],
        error=Palette.EXPENSE,
        on_error=Palette.WHITE,
    )
    date_picker_theme = ft.DatePickerTheme(
        bgcolor=p["surface"],
        header_bgcolor=Palette.PRIMARY,
        header_foreground_color=Palette.WHITE,
        day_foreground_color=p["text_dark"],
        day_overlay_color=ft.Colors.with_opacity(0.12, Palette.PRIMARY),
        today_bgcolor=ft.Colors.with_opacity(0.15, Palette.PRIMARY),
        today_foreground_color=Palette.PRIMARY,
        divider_color=p["border"],
        year_foreground_color=p["text_dark"],
        year_overlay_color=ft.Colors.with_opacity(0.12, Palette.PRIMARY),
        weekday_text_style=ft.TextStyle(color=p["text_mid"]),
        confirm_button_style=ft.ButtonStyle(color=Palette.PRIMARY),
        cancel_button_style=ft.ButtonStyle(color=p["text_mid"]),
    )
    return ft.Theme(color_scheme=color_scheme, date_picker_theme=date_picker_theme)


def configure_page(page: ft.Page):
    """One-time + per-toggle page setup: window size, fonts, theme_mode."""
    page.title = "FinTrack — Personal Finance Tracker"
    _icon_base = getattr(sys, '_MEIPASS', os.path.dirname(_BASE))
    _icon = os.path.join(_icon_base, "app_icon.ico")
    if os.path.exists(_icon):
        page.window.icon = _icon
    page.window.width = 1100
    page.window.height = 700
    page.window.min_width = 900
    page.window.min_height = 600
    page.padding = 0
    page.bgcolor = theme.colors["surface"]
    page.theme = _build_theme(is_dark=False)
    page.dark_theme = _build_theme(is_dark=True)
    page.theme_mode = ft.ThemeMode.DARK if theme.is_dark else ft.ThemeMode.LIGHT
    page.fonts = {}


def mesh_background() -> ft.Stack:
    """A few large, very soft, blurred color blobs behind the content —
    this is what glass containers actually frost/tint against."""
    c = theme.colors
    blobs = []
    positions = [
        {"left": -160, "top": -120},
        {"right": -200, "top": 120},
        {"left": 280, "bottom": -220},
    ]
    for (color, alpha), pos in zip(c["mesh_blobs"], positions):
        blobs.append(
            ft.Container(
                width=520, height=520,
                border_radius=260,
                bgcolor=ft.Colors.with_opacity(alpha, color),
                blur=ft.Blur(90, 90),
                **pos,
            )
        )
    return ft.Stack(
        controls=[ft.Container(bgcolor=c["surface"], expand=True), *blobs],
        expand=True,
    )


# ── GLASS — frosted readable surfaces ──────────────────────

def glass_card(content, *, width=None, height=None, padding=20, radius=24,
                expand=False, on_click=None, hover_scale: float = None,
                hover_offset: ft.Offset = None) -> ft.Container:
    """Pass on_click to make this card tappable — it'll get the standard
    hover-lift / press-dip treatment. Leave it None for purely
    informational cards (e.g. the income/expense mini-cards) so they
    stay still and don't suggest they're interactive."""
    c = theme.colors
    card = ft.Container(
        content=content,
        width=width, height=height, padding=padding,
        border_radius=radius,
        bgcolor=ft.Colors.with_opacity(c["glass_alpha"], c["glass_tint"]),
        blur=ft.Blur(20, 20),
        border=ft.Border.all(1, ft.Colors.with_opacity(c["glass_border_alpha"], c["glass_border"])),
        shadow=ft.BoxShadow(
            blur_radius=28, spread_radius=0,
            color=ft.Colors.with_opacity(c["glass_shadow_alpha"], c["glass_shadow"]),
            offset=ft.Offset(0, 10),
        ),
        expand=expand,
    )
    if on_click:
        kwargs = {"on_click": on_click, "hover_offset": hover_offset}
        if hover_scale is not None:
            kwargs["hover_scale"] = hover_scale
        hoverable(card, **kwargs)
    return card


def glass_hero(content, *, width=None, height=130, radius=26) -> ft.Container:
    """Solid-terracotta variant of the glass card for the one signature
    element per screen (e.g. the balance hero) — same blur/border/shadow
    recipe, but tinted with the brand color instead of white/charcoal so
    it reads as the one bold moment on the page."""
    return ft.Container(
        content=content,
        width=width, height=height, padding=22,
        border_radius=radius,
        bgcolor=ft.Colors.with_opacity(0.88, Palette.PRIMARY),
        blur=ft.Blur(16, 16),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, Palette.WHITE)),
        shadow=ft.BoxShadow(
            blur_radius=32, spread_radius=0,
            color=ft.Colors.with_opacity(0.30, Palette.PRIMARY_DARK),
            offset=ft.Offset(0, 12),
        ),
    )


# ── NEO — flat, soft dual-shadow controls ──────────────────

def neo_box(content, *, width=None, height=None, padding=0, radius=16,
            pressed=False, bgcolor=None, on_click=None) -> ft.Container:
    """Raised by default (light shadow top-left, dark bottom-right).
    Pass pressed=True to invert the pair for an active/selected look."""
    c = theme.colors
    base = bgcolor or c["neo_base"]
    light = ft.BoxShadow(
        blur_radius=10, spread_radius=0,
        color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]),
        offset=ft.Offset(-5, -5) if not pressed else ft.Offset(4, 4),
    )
    dark = ft.BoxShadow(
        blur_radius=10, spread_radius=0,
        color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]),
        offset=ft.Offset(5, 5) if not pressed else ft.Offset(-4, -4),
    )
    box = ft.Container(
        content=content,
        width=width, height=height, padding=padding,
        border_radius=radius,
        bgcolor=base,
        shadow=[light, dark],
        alignment=ft.alignment.Alignment.CENTER,
    )
    if on_click:
        hoverable(box, on_click=on_click)
    return box


def neo_button(text, *, on_click=None, width=None, height=48, radius=16,
               filled=True, icon=None, hover_scale: float = None,
               hover_offset: ft.Offset = None) -> ft.Container:
    """Primary action button. filled=True -> solid terracotta fill with
    the same raised dual-shadow treatment; filled=False -> neo_base fill
    with terracotta text (secondary/outline style)."""
    c = theme.colors
    text_color = Palette.WHITE if filled else Palette.PRIMARY
    row_children = []
    if icon:
        row_children.append(ft.Icon(icon, color=text_color, size=16))
    row_children.append(ft.Text(text, color=text_color, weight=ft.FontWeight.BOLD, size=14))

    light = ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-5, -5))
    dark = ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(5, 5))

    btn = ft.Container(
        content=ft.Row(row_children, alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        width=width, height=height,
        border_radius=radius,
        bgcolor=Palette.PRIMARY if filled else c["neo_base"],
        shadow=[light, dark],
        alignment=ft.alignment.Alignment.CENTER,
    )
    if on_click:
        kwargs = {"on_click": on_click, "hover_offset": hover_offset}
        if hover_scale is not None:
            kwargs["hover_scale"] = hover_scale
        hoverable(btn, **kwargs)
    return btn


def neo_fab(text, *, on_click=None, icon=None, width=None, height=52, radius=18,
            hover_offset: ft.Offset = None) -> ft.Container:
    """The one deliberately playful element per screen — same recipe as
    neo_button but with a spring/overshoot curve instead of the usual
    restrained ease, so it stands out as the app's single 'funky' click
    target (the primary call-to-action, e.g. '+ Add Transaction')."""
    c = theme.colors
    row_children = []
    if icon:
        row_children.append(ft.Icon(icon, color=Palette.WHITE, size=18))
    row_children.append(ft.Text(text, color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14))

    light = ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-5, -5))
    dark = ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(5, 5))

    fab = ft.Container(
        content=ft.Row(row_children, alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        width=width, height=height,
        border_radius=radius,
        bgcolor=Palette.PRIMARY,
        shadow=[light, dark],
        alignment=ft.alignment.Alignment.CENTER,
        scale=1.0,
        animate_scale=Motion.SPRING,
        offset=ft.Offset(0, 0),
        animate_offset=Motion.SPRING if hover_offset is not None else None,
    )
    fab.ink = True
    fab.clip_behavior = ft.ClipBehavior.NONE

    def _fab_safe_update():
        try:
            fab.update()
        except RuntimeError:
            pass

    def on_hover(e):
        enter = _is_enter(e)
        fab.scale = Motion.FAB_HOVER_SCALE if enter else 1.0
        if hover_offset is not None:
            fab.offset = hover_offset if enter else ft.Offset(0, 0)
        _fab_safe_update()

    def on_click_wrapped(e):
        fab.scale = Motion.FAB_PRESS_SCALE
        _fab_safe_update()
        if on_click:
            on_click(e)
        fab.scale = Motion.FAB_HOVER_SCALE
        if hover_offset is not None:
            fab.offset = hover_offset
        _fab_safe_update()

    fab.on_hover = on_hover
    fab.on_click = on_click_wrapped
    return fab


def neo_input(hint, *, password=False, on_change=None, on_submit=None,
              width=360) -> ft.TextField:
    """Borderless TextField wrapped visually by a neo inset look — since
    TextField can't itself take a shadow list, we rely on a flat fill +
    no border, and let the caller wrap it in neo_box(pressed=True) for a
    'carved-in' input slot."""
    c = theme.colors
    return ft.TextField(
        hint_text=hint,
        password=password,
        can_reveal_password=password,
        on_change=on_change,
        on_submit=on_submit,
        width=width,
        height=48,
        text_size=13,
        color=c["text_dark"],
        hint_style=ft.TextStyle(color=c["text_light"], size=13),
        bgcolor="transparent",
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding(16, 12, 16, 12),
    )


def neo_input_slot(hint, **kwargs) -> tuple[ft.Container, ft.TextField]:
    """Convenience: a neo-inset container with a borderless input inside.
    Returns (container_to_place, textfield_to_read_value_from)."""
    c = theme.colors
    field = neo_input(hint, **kwargs)
    box = ft.Container(
        content=field,
        border_radius=14,
        bgcolor=c["neo_base"],
        shadow=[
            ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(3, 3)),
            ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-3, -3)),
        ],
    )
    return box, field
