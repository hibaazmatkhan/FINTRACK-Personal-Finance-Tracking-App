"""Main application shell — sidebar nav + page switching, post-login. (Flet edition)"""
import flet as ft
from ui_flet.theme import (
    theme, Palette, hoverable, mesh_background,
    screen_transition, mount, confirm_dialog,
)
from services.firebase_auth import FirebaseAuthService


NAV_ITEMS = [
    ("Home", "🏠", "Overview"),
    ("History", "📋", "History"),
    ("Reports", "📊", "Reports"),
    ("Budgets", "💵", "Budgets"),
    ("Categories", "🏷️", "Categories"),
    ("Settings", "⚙️", "Settings"),
]


def DashboardScreen(page: ft.Page, on_logout) -> ft.Control:
    c = theme.colors

    page_built = {}     # name -> built Control, built lazily on first visit
    page_refresh = {}   # name -> that page's refresh() callable (if any)
    nav_row_refs = {}   # name -> the nav Container, so we can re-style on select
    current = {"name": None}

    content_area = ft.Container(expand=True, padding=28)
    body_stack = ft.Stack(controls=[mesh_background(), content_area], expand=True)

    # Custom categories used to only get loaded as a side effect of
    # visiting the Categories page first — meaning a custom category
    # could be invisible in Add Transaction / Budgets for an entire
    # session if you never happened to open Categories. Load them once,
    # right here, before any page (including Home's FAB) can possibly
    # need them.
    _uid = FirebaseAuthService.get_uid()
    if _uid:
        from models.data_models import load_custom_categories
        load_custom_categories(_uid)
        # Sync currency from profile (overrides local if different)
        from services.supabase_service import SupabaseService
        try:
            profile = SupabaseService.get_profile(_uid)
            pc = profile.get("currency")
            if pc:
                theme.sync_currency(pc)
        except Exception:
            pass

    def open_add_dialog():
        from ui_flet.add_transaction_dialog import AddTransactionDialog
        AddTransactionDialog(page, on_saved=on_transaction_added)

    def on_transaction_added():
        if current["name"] and current["name"] in page_refresh:
            page_refresh[current["name"]]()

    def build_page(name: str) -> ft.Control:
        if name == "Home":
            from ui_flet.home_page import HomePage
            ctl = HomePage(page, on_add=open_add_dialog)
            page_refresh[name] = ctl.refresh
            return ctl
        if name == "History":
            from ui_flet.history_page import HistoryPage
            ctl = HistoryPage(page)
            page_refresh[name] = ctl.refresh
            return ctl
        if name == "Reports":
            from ui_flet.reports_page import ReportsPage
            ctl = ReportsPage(page)
            page_refresh[name] = ctl.refresh
            return ctl
        if name == "Budgets":
            from ui_flet.budgets_page import BudgetsPage
            ctl = BudgetsPage(page, on_changed=on_transaction_added)
            page_refresh[name] = ctl.refresh
            return ctl
        if name == "Categories":
            from ui_flet.categories_page import CategoriesPage
            ctl = CategoriesPage(page)
            page_refresh[name] = ctl.refresh
            return ctl
        if name == "Settings":
            from ui_flet.settings_page import SettingsPage
            ctl = SettingsPage(page, on_logout=sign_out, on_theme_changed=apply_theme,
                                on_profile_changed=lambda: refresh_sidebar_profile(force_avatar_refresh=True))
            page_refresh[name] = ctl.refresh
            return ctl
        raise ValueError(f"Unknown page: {name}")

    def show_page(name: str):
        if name not in page_built:
            page_built[name] = build_page(name)

        content_area.content = page_built[name]
        current["name"] = name

        pal = theme.colors
        for key, nav_box in nav_row_refs.items():
            nav_box.bgcolor = Palette.PRIMARY if key == name else "transparent"
            nav_box.shadow = (
                [
                    ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(pal["neo_light_alpha"], pal["neo_light"]), offset=ft.Offset(-4, -4)),
                    ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(pal["neo_dark_alpha"], pal["neo_dark"]), offset=ft.Offset(4, 4)),
                ]
                if key == name else None
            )
            nav_accent_refs[key].bgcolor = Palette.WHITE if key == name else "transparent"
            try:
                nav_box.update()
            except RuntimeError:
                pass  # initial build pass — not attached to the page yet

        try:
            page.update()
        except RuntimeError:
            pass
        if name in page_refresh:
            page_refresh[name]()
        refresh_sidebar_profile()

    def sign_out():
        from services.supabase_service import set_auth_token
        set_auth_token(None)
        FirebaseAuthService.sign_out()
        on_logout()

    def apply_theme():
        """Live theme update — updates page theme_mode, mesh background,
        and rebuilds the current page content in-place. Avoids the old
        page.clean() + full shell rebuild that caused a visible refresh
        flash every time the dark/light toggle was used.
        """
        page.theme_mode = ft.ThemeMode.DARK if theme.is_dark else ft.ThemeMode.LIGHT
        page.bgcolor = theme.colors["surface"]
        # Rebuild mesh background inside body_stack
        body_stack.controls[0] = mesh_background()
        # Rebuild current page with fresh theme colors
        page_built.clear()
        page_refresh.clear()
        if current["name"]:
            page_built[current["name"]] = build_page(current["name"])
            content_area.content = page_built[current["name"]]
        # Update sidebar nav item active styling using fresh theme colors
        pal = theme.colors
        for key, nav_box in nav_row_refs.items():
            is_active = key == current["name"]
            nav_box.bgcolor = Palette.PRIMARY if is_active else "transparent"
            nav_box.shadow = (
                [
                    ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(pal["neo_light_alpha"], pal["neo_light"]), offset=ft.Offset(-4, -4)),
                    ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(pal["neo_dark_alpha"], pal["neo_dark"]), offset=ft.Offset(4, 4)),
                ]
                if is_active else None
            )
            nav_accent_refs[key].bgcolor = Palette.WHITE if is_active else "transparent"
        try:
            page.update()
        except RuntimeError:
            pass
        if current["name"] and current["name"] in page_refresh:
            page_refresh[current["name"]]()
        refresh_sidebar_profile()

    # ── Sidebar ──────────────────────────────────────────────
    nav_accent_refs = {}  # name -> the small left accent-bar Container

    def nav_item(key: str, emoji: str, label: str) -> ft.Container:
        accent = ft.Container(width=3, height=18, border_radius=2, bgcolor="transparent")
        nav_accent_refs[key] = accent
        box = ft.Container(
            content=ft.Row(
                [
                    accent,
                    ft.Text(emoji, size=15),
                    ft.Text(label, size=14, color="#F5DCD2", weight=ft.FontWeight.W_500),
                ],
                spacing=10,
            ),
            padding=ft.Padding(14, 11, 14, 11),
            border_radius=12,
            bgcolor="transparent",
            tooltip=f"{label}  (Ctrl+{NAV_ITEMS.index((key, emoji, label)) + 1})",
        )
        hoverable(box, hover_scale=1.02, on_click=lambda e: show_page(key))
        nav_row_refs[key] = box
        return box

    nav_controls = [nav_item(key, emoji, label) for key, emoji, label in NAV_ITEMS]

    sign_out_item = ft.Container(
        content=ft.Row(
            [ft.Text("🚪", size=14), ft.Text("Sign Out", size=13, weight=ft.FontWeight.BOLD, color=Palette.WHITE)],
            spacing=10,
        ),
        padding=ft.Padding(14, 11, 14, 11),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.85, "#7A2E1A"),  # deliberately darker/red, distinct from the rest of the sidebar
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, Palette.WHITE)),
    )
    hoverable(sign_out_item, hover_scale=1.02, on_click=lambda e: confirm_dialog(
        page, "Sign Out", "Are you sure you want to sign out?",
        confirm_label="Sign Out", on_confirm=sign_out,
    ))

    logo = ft.Container(
        content=ft.Text("💰 FinTrack", size=18, weight=ft.FontWeight.BOLD, color=Palette.WHITE),
        padding=ft.Padding(6, 0, 0, 28),
        tooltip="Go to Overview",
    )
    hoverable(logo, hover_scale=1.03, on_click=lambda e: show_page("Home"))

    # ── Profile card (replaces the old "Add Transaction" sidebar
    # button — adding a transaction is still one click away via the
    # FAB on the Home page itself). Tapping this jumps to Settings,
    # the same pattern as most apps use for "manage your account".
    sidebar_avatar_text = ft.Text("👤", size=20)
    sidebar_avatar = ft.Container(
        width=40, height=40, border_radius=12, bgcolor=ft.Colors.with_opacity(0.18, Palette.WHITE),
        alignment=ft.alignment.Alignment.CENTER, content=sidebar_avatar_text,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    sidebar_username = ft.Text("User", size=13, weight=ft.FontWeight.BOLD, color=Palette.WHITE)
    sidebar_email = ft.Text("", size=10, color="#F5DCD2")

    profile_card = ft.Container(
        padding=ft.Padding(10, 10, 10, 10),
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.12, Palette.WHITE),
        content=ft.Row(
            [
                sidebar_avatar,
                ft.Column([sidebar_username, sidebar_email], spacing=1, expand=True),
            ],
            spacing=10,
        ),
        tooltip="Open Settings",
    )
    hoverable(profile_card, hover_scale=1.02, on_click=lambda e: show_page("Settings"))

    _avatar_loaded = {"done": False}

    def refresh_sidebar_profile(force_avatar_refresh: bool = False):
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return
        from services.supabase_service import SupabaseService
        profile = SupabaseService.get_profile(uid)
        sidebar_username.value = profile.get("username") or "User"
        sidebar_email.value = FirebaseAuthService.get_email() or ""
        avatar_url = profile.get("avatar_url")
        if avatar_url:
            # The avatar upload always overwrites the same storage path, so
            # the URL never changes even when the photo does — that's why
            # the cache-busting "?t=" timestamp exists. But rebuilding this
            # Image (and re-fetching over the network) on every nav click
            # was what caused the blank -> reload -> reappear flicker. Only
            # do it the first time it's shown, or when we're explicitly
            # told the photo just changed.
            if force_avatar_refresh or not _avatar_loaded["done"]:
                import time
                sidebar_avatar.content = ft.Image(
                    src=f"{avatar_url}?t={int(time.time())}",
                    width=40, height=40, fit=ft.BoxFit.COVER, border_radius=12,
                    error_content=ft.Text("👤", size=20),
                )
                _avatar_loaded["done"] = True
        else:
            sidebar_avatar.content = sidebar_avatar_text
            _avatar_loaded["done"] = False
        try:
            profile_card.update()
        except RuntimeError:
            pass

    sidebar = ft.Container(
        width=220,
        bgcolor=Palette.PRIMARY_DARK,
        padding=ft.Padding(18, 28, 18, 20),
        content=ft.Column(
            [
                logo,
                *nav_controls,
                ft.Container(height=16),
                profile_card,
                ft.Container(expand=True),  # spacer pushes sign-out to bottom
                sign_out_item,
            ],
            expand=True,
        ),
    )

    # ── Keyboard shortcuts: Ctrl+1..6 jump between pages ───────
    def on_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key in "123456":
            idx = int(e.key) - 1
            if 0 <= idx < len(NAV_ITEMS):
                show_page(NAV_ITEMS[idx][0])

    page.on_keyboard_event = on_keyboard

    show_page("Home")

    return ft.Row(
        [sidebar, ft.Container(content=body_stack, expand=True)],
        spacing=0, expand=True,
    )