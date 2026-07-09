"""Settings page — profile, dark mode toggle, password/email/phone via Firebase. (Flet edition)"""
import io
import re
import asyncio
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, neo_button, hoverable, dialog_title_with_close, format_amount, CURRENCY_LIST, CURRENCY_CONFIG, get_conversion_rate
from services.firebase_auth import FirebaseAuthService, AuthError
from services.supabase_service import SupabaseService, SupabaseError


def _pick_local_image_path() -> str | None:
    """Opens a native OS file-browse dialog (via tkinter, NOT Flet's
    FilePicker service control — that one proved unreliable: it needs a
    client/server handshake that kept timing out). This runs entirely
    synchronously in a background thread and returns a plain file path,
    or None if cancelled. Tkinter is already a dependency of this
    project (the CustomTkinter version uses it), so no new
    dependency is introduced."""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(
            title="Select profile photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return path or None


def SettingsPage(page: ft.Page, on_logout, on_theme_changed=None, on_profile_changed=None) -> ft.Control:
    c = theme.colors

    username_text = ft.Text("User", size=17, weight=ft.FontWeight.BOLD, color=Palette.WHITE)
    email_text = ft.Text("", size=12, color="#FFE3D6")
    avatar_text = ft.Text("👤", size=24)

    snack_text = ft.Text("")

    def notify(message: str, ok: bool = True):
        page.show_dialog(ft.AlertDialog(
            modal=True,
            bgcolor=c["surface"],
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text("Success" if ok else "Error", color=c["text_dark"], weight=ft.FontWeight.BOLD),
            content=ft.Text(message, color=c["text_mid"]),
            actions=[ft.TextButton(
                content=ft.Text("OK", color=Palette.PRIMARY, weight=ft.FontWeight.BOLD),
                on_click=lambda e: page.pop_dialog(),
            )],
        ))

    def confirm(title: str, message: str, on_yes):
        def yes(e):
            page.pop_dialog()
            on_yes()

        def no(e):
            page.pop_dialog()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            bgcolor=c["surface"],
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text(title, color=c["text_dark"], weight=ft.FontWeight.BOLD),
            content=ft.Text(message, color=c["text_mid"]),
            actions=[
                ft.TextButton(content=ft.Text("Cancel", color=c["text_mid"]), on_click=no),
                ft.TextButton(content=ft.Text("Yes", color=Palette.PRIMARY, weight=ft.FontWeight.BOLD), on_click=yes),
            ],
        ))

    def neo_inset(field, width=320):
        return ft.Container(
            content=field, width=width, border_radius=12, bgcolor=c["neo_base"],
            shadow=[
                ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(3, 3)),
                ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-3, -3)),
            ],
        )

    def themed_field(hint, password=False, disabled=False):
        return ft.TextField(
            hint_text=hint, password=password, can_reveal_password=password, disabled=disabled,
            height=46, text_size=14, color=c["text_dark"],
            hint_style=ft.TextStyle(color=c["text_light"]),
            bgcolor="transparent", border=ft.InputBorder.NONE,
            content_padding=ft.Padding(14, 10, 14, 10),
        )

    # ── Change photo (native local file dialog → resize → upload) ──
    async def change_photo(e=None):
        path = await asyncio.to_thread(_pick_local_image_path)
        if not path:
            return  # cancelled

        try:
            from PIL import Image
            img = Image.open(path).convert("RGB")
            img.thumbnail((512, 512))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)

            uid = FirebaseAuthService.get_uid()
            url = await asyncio.to_thread(SupabaseService.upload_avatar, uid, buf.getvalue(), "jpg")
            try:
                SupabaseService.upsert_profile(uid, avatar_url=url)
            except SupabaseError:
                notify("Photo uploaded but profile could not be updated.", ok=False)
                return
            notify("Profile photo updated!")
            refresh()
            if on_profile_changed:
                on_profile_changed()
        except Exception as ex:
            notify(f"Could not upload photo: {ex}", ok=False)

    # ── Edit username dialog ───────────────────────────────────
    def open_username_dialog():
        uid = FirebaseAuthService.get_uid()
        try:
            current = SupabaseService.get_profile(uid).get("username", "")
        except SupabaseError:
            current = ""
        field = themed_field("Username")
        field.value = current
        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        def save(e):
            name = (field.value or "").strip()
            if not name:
                error_text.value = "Username cannot be empty."
                error_text.visible = True
                dialog.update()
                return
            try:
                SupabaseService.upsert_profile(uid, username=name)
                page.pop_dialog()
                refresh()
                if on_profile_changed:
                    on_profile_changed()
            except SupabaseError as ex:
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()

        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Edit Username", page, size=16),
            content=ft.Container(
                width=320,
                content=ft.Column([
                    neo_inset(field), ft.Container(height=12), error_text,
                    ft.Container(height=8), neo_button("Save", on_click=save, width=300, height=46),
                ], spacing=4, tight=True),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    # ── Change email dialog ─────────────────────────────────────
    def open_email_dialog():
        pw_field = themed_field("Current Password", password=True)
        new_email_field = themed_field("New Email")
        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        def save(e):
            password = pw_field.value or ""
            new_email = (new_email_field.value or "").strip()
            if not password or not new_email:
                error_text.value = "Please fill in all fields."
                error_text.visible = True
                dialog.update()
                return

            current_email = FirebaseAuthService.get_email()

            if not re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                error_text.value = "Please enter a valid email address."
                error_text.visible = True
                dialog.update()
                return

            if new_email == current_email:
                error_text.value = "You are already signed in with this email."
                error_text.visible = True
                dialog.update()
                return

            if FirebaseAuthService.check_email_exists(new_email):
                error_text.value = "This email is already registered."
                error_text.visible = True
                dialog.update()
                return

            try:
                if not FirebaseAuthService.reauthenticate(current_email, password):
                    error_text.value = "Incorrect password."
                    error_text.visible = True
                    dialog.update()
                    return
            except AuthError as ex:
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()
                return
            try:
                FirebaseAuthService.update_email(new_email)
                page.pop_dialog()
                notify(f"Verification email is being sent to {new_email}")
            except AuthError as ex:
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()

        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Change Email", page, size=16),
            content=ft.Container(
                width=320,
                content=ft.Column([
                    ft.Text("We'll send a verification link to your new email — "
                            "it only takes effect once you click it there.",
                            size=12, color=c["text_mid"]),
                    ft.Container(height=12),
                    neo_inset(pw_field), ft.Container(height=10), neo_inset(new_email_field),
                    ft.Container(height=12), error_text,
                    ft.Container(height=8), neo_button("Update Email", on_click=save, width=300, height=46),
                ], spacing=4, tight=True),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    # ── Change password dialog ──────────────────────────────────
    def open_password_dialog():
        current_field = themed_field("Current Password", password=True)
        new_field = themed_field("New Password", password=True)
        confirm_field = themed_field("Confirm New Password", password=True)
        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        def save(e):
            current = current_field.value or ""
            new = new_field.value or ""
            confirm_val = confirm_field.value or ""

            if not current or not new or not confirm_val:
                error_text.value = "Please fill in all fields."
            elif new != confirm_val:
                error_text.value = "Passwords do not match."
            elif len(new) < 8:
                error_text.value = "Password must be at least 8 characters."
            elif not re.search(r"\d", new):
                error_text.value = "Password must contain at least one number."
            elif not re.search(r"[a-zA-Z]", new):
                error_text.value = "Password must contain at least one letter."
            else:
                email = FirebaseAuthService.get_email()
                try:
                    reauthenticated = FirebaseAuthService.reauthenticate(email, current)
                except AuthError as ex:
                    error_text.value = str(ex)
                    error_text.visible = True
                    dialog.update()
                    return
                if not reauthenticated:
                    error_text.value = "Current password is incorrect."
                else:
                    try:
                        FirebaseAuthService.change_password(new)
                        page.pop_dialog()
                        notify("Password updated successfully.")
                        return
                    except AuthError as ex:
                        error_text.value = str(ex)

            error_text.visible = True
            dialog.update()

        def send_reset(e):
            try:
                FirebaseAuthService.send_password_reset(FirebaseAuthService.get_email())
                error_text.color = Palette.INCOME
                error_text.value = "Reset link sent to your email (check spam if not visible)."
            except AuthError as ex:
                error_text.color = Palette.EXPENSE
                error_text.value = str(ex)
            error_text.visible = True
            dialog.update()

        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Change Password", page, size=16),
            content=ft.Container(
                width=320,
                content=ft.Column([
                    neo_inset(current_field), ft.Container(height=10),
                    neo_inset(new_field), ft.Container(height=10),
                    neo_inset(confirm_field), ft.Container(height=12),
                    error_text, ft.Container(height=8),
                    neo_button("Update Password", on_click=save, width=300, height=46),
                    ft.Container(height=8),
                    neo_button("Send reset link instead", on_click=send_reset, width=300, height=42, filled=False),
                ], spacing=4, tight=True),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    # ── Phone number dialog ──────────────────────────────────────
    def open_delete_account_dialog():
        confirm_field = themed_field('Type "DELETE" to confirm')
        pw_field = themed_field("Current Password", password=True)
        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        def do_delete(e):
            if (confirm_field.value or "").strip().upper() != "DELETE":
                error_text.color = Palette.EXPENSE
                error_text.value = 'Please type "DELETE" exactly to confirm.'
                error_text.visible = True
                dialog.update()
                return

            password = pw_field.value or ""
            if not password:
                error_text.color = Palette.EXPENSE
                error_text.value = "Please enter your password to confirm."
                error_text.visible = True
                dialog.update()
                return

            email = FirebaseAuthService.get_email()
            try:
                if not FirebaseAuthService.reauthenticate(email, password):
                    error_text.color = Palette.EXPENSE
                    error_text.value = "Incorrect password."
                    error_text.visible = True
                    dialog.update()
                    return
            except AuthError as ex:
                error_text.color = Palette.EXPENSE
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()
                return

            uid = FirebaseAuthService.get_uid()
            try:
                # Wipe Supabase data first — once the Firebase account
                # is gone there's no idToken left to identify "whose
                # data" for the delete calls.
                SupabaseService.delete_all_user_data(uid)
                FirebaseAuthService.delete_account()
                page.pop_dialog()
                on_logout()
            except AuthError as ex:
                error_text.color = Palette.EXPENSE
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()

        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Delete Account", page, size=16),
            content=ft.Container(
                width=340,
                content=ft.Column([
                    ft.Text(
                        "This permanently deletes your account and ALL of your "
                        "data. Are you sure? ",
                        size=12, color=Palette.EXPENSE, weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(height=14),
                    neo_inset(confirm_field), ft.Container(height=10),
                    neo_inset(pw_field), ft.Container(height=12),
                    error_text, ft.Container(height=8),
                    neo_button("Permanently Delete My Account", on_click=do_delete,
                               width=300, height=46, filled=True),
                ], spacing=4, tight=True),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    # ── Account tiles ──────────────────────────────────────────
    def account_tile(emoji: str, title: str, subtitle: str, on_click, danger: bool = False) -> ft.Control:
        title_color = Palette.EXPENSE if danger else c["text_dark"]
        return glass_card(
            ft.Row(
                [
                    ft.Text(emoji, size=18),
                    ft.Column(
                        [
                            ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=title_color),
                            ft.Text(subtitle, size=11, color=c["text_light"]),
                        ],
                        spacing=2, expand=True,
                    ),
                    ft.Text("›", size=18, color=c["text_light"]),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14,
            ),
            padding=14, radius=14, on_click=lambda e: on_click(),
            hover_scale=1.01,
        )

    # ── Currency selector ─────────────────────────────────────────
    currency_label = ft.Text(f"{theme.currency}  ({CURRENCY_CONFIG.get(theme.currency, {}).get('symbol', '')})",
                             size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"])

    def open_currency_dialog():
        old_currency = theme.currency
        uid = FirebaseAuthService.get_uid()

        dropdown = ft.Dropdown(
            value=old_currency,
            options=[ft.DropdownOption(key=code, text=f"{code}  {cfg['symbol']}",
                     style=ft.ButtonStyle(color=c["text_dark"], bgcolor=c["neo_base"]))
                     for code, cfg in CURRENCY_CONFIG.items()],
            width=340, color=c["text_dark"], text_style=ft.TextStyle(color=c["text_dark"], size=14),
            border_radius=12, border_color=c["border"], filled=True,
            fill_color=c["neo_base"], menu_style=ft.MenuStyle(bgcolor=c["surface"]),
        )
        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        info_text = ft.Text("", size=12, color=c["text_mid"], visible=False)
        fetching_label = ft.Text("Fetching live rates...", size=11, color=c["text_light"], visible=False)

        def on_currency_change(e):
            new_cur = dropdown.value
            if new_cur and new_cur != old_currency:
                info_text.visible = False
                fetching_label.visible = True
                error_text.visible = False
                try: dialog.update()
                except RuntimeError: pass

                rate = get_conversion_rate(old_currency, new_cur)
                info_text.value = (f"1 {new_cur} = {rate:,.2f} {old_currency}\n"
                                   f"All existing data will be converted automatically.")
                info_text.visible = True
                fetching_label.visible = False
            else:
                info_text.visible = False
                fetching_label.visible = False
            try: dialog.update()
            except RuntimeError: pass

        dropdown.on_change = on_currency_change

        def save(e):
            new_cur = dropdown.value
            if not new_cur:
                return
            if new_cur == old_currency:
                page.pop_dialog()
                return
            rate = get_conversion_rate(old_currency, new_cur)
            try:
                SupabaseService.convert_all_user_data(uid, rate)
                SupabaseService.update_profile_currency(uid, new_cur)
                theme.currency = new_cur
                page.pop_dialog()
                currency_label.value = f"{new_cur}  ({CURRENCY_CONFIG[new_cur]['symbol']})"
                page.update()
            except Exception as ex:
                error_text.value = f"Conversion failed: {ex}"
                error_text.visible = True
                dialog.update()

        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Change Currency", page, size=16),
            content=ft.Container(
                width=380,
                content=ft.Column([
                    ft.Text("Display Currency", size=12, color=c["text_mid"]),
                    dropdown,
                    ft.Container(height=8),
                    info_text,
                    fetching_label,
                    ft.Container(height=12),
                    error_text,
                    ft.Container(height=8),
                    neo_button("Save", on_click=save, width=340, height=48),
                ], spacing=6, tight=True),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    currency_tile = glass_card(
        ft.Row(
            [
                ft.Text("💱", size=18),
                ft.Column(
                    [ft.Text("Currency", size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]), currency_label],
                    spacing=2, expand=True,
                ),
                ft.Text("›", size=18, color=c["text_light"]),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14,
        ),
        padding=14, radius=14, on_click=lambda e: open_currency_dialog(),
        hover_scale=1.01,
    )

    # ── Dark mode toggle ─────────────────────────────────────────
    dark_switch = ft.Switch(value=theme.is_dark, active_color=Palette.PRIMARY)
    dark_sub_text = ft.Text("Currently dark" if theme.is_dark else "Currently light", size=11, color=c["text_light"])

    def toggle_dark_mode(e):
        theme.toggle()
        if on_theme_changed:
            on_theme_changed()  # shell rebuilds everything with fresh colors

    dark_switch.on_change = toggle_dark_mode

    dark_mode_tile = glass_card(
        ft.Row(
            [
                ft.Text("🌙" if theme.is_dark else "🌓", size=18),
                ft.Column(
                    [ft.Text("Dark Mode", size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]), dark_sub_text],
                    spacing=2, expand=True,
                ),
                dark_switch,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14,
        ),
        padding=14, radius=14,
    )

    def sign_out():
        FirebaseAuthService.sign_out()
        on_logout()

    def confirm_sign_out(e=None):
        confirm("Sign Out", "Are you sure you want to sign out?", sign_out)

    _avatar_url_store = {"url": None}

    def open_avatar_view(e=None):
        url = _avatar_url_store["url"]
        if not url:
            return
        import time
        page.show_dialog(ft.AlertDialog(
            modal=True,
            bgcolor=c["surface"],
            shape=ft.RoundedRectangleBorder(radius=24),
            title=ft.Row(
                [
                    ft.Text("Profile Photo", size=16, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE, icon_size=20, icon_color=c["text_mid"],
                        on_click=lambda e: page.pop_dialog(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            content=ft.Container(
                width=320, height=320,
                content=ft.Image(
                    src=f"{url}?t={int(time.time())}",
                    width=320, height=320, fit=ft.BoxFit.CONTAIN,
                    border_radius=16,
                    error_content=ft.Text("👤", size=64),
                ),
            ),
        ))

    avatar_circle = ft.Container(
        width=56, height=56, border_radius=16, bgcolor="#E08870",
        alignment=ft.alignment.Alignment.CENTER, content=avatar_text,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    hoverable(avatar_circle, hover_scale=1.03, on_click=open_avatar_view)

    change_photo_btn = ft.Container(
        content=ft.Text("Change Photo", size=11, weight=ft.FontWeight.BOLD, color=Palette.WHITE),
        padding=ft.Padding(14, 8, 14, 8), border_radius=10, bgcolor="#E08870",
    )
    hoverable(change_photo_btn, hover_scale=1.025, on_click=change_photo)

    profile_card = ft.Container(
        border_radius=20, bgcolor=Palette.PRIMARY, padding=20,
        content=ft.Row(
            [
                avatar_circle,
                ft.Column([username_text, email_text], spacing=2, expand=True),
                change_photo_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=16,
        ),
    )

    def show_avatar(avatar_url: str | None):
        _avatar_url_store["url"] = avatar_url
        if avatar_url:
            import time
            avatar_circle.content = ft.Image(
                src=f"{avatar_url}?t={int(time.time())}",
                width=56, height=56, fit=ft.BoxFit.COVER,
                border_radius=16,
                error_content=ft.Text("👤", size=24),
            )
        else:
            avatar_circle.content = avatar_text
            _avatar_url_store["url"] = None

    # ── Help dialog ──────────────────────────────────────────────
    def open_help_dialog():
        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Help", page, size=16),
            content=ft.Container(
                width=380,
                content=ft.Column([
                    _help_section("📥 Adding Transactions",
                        "Tap the + button on the Home page to open the Add Transaction dialog. "
                        "Choose Income or Expense type using the toggle, then pick a category "
                        "from the available chips (including your custom categories). "
                        "Enter the amount — the dialog shows your balance on the selected date "
                        "and warns if the expense exceeds it or goes over a budget limit. "
                        "Add an optional description, select the date (past dates only), "
                        "and tap Save. The transaction instantly updates your Home balance, "
                        "History, budgets, and reports."),
                    _help_section("📋 Viewing & Managing History",
                        "Open the History page to see all your transactions sorted by date "
                        "(newest first). Use the filter chips to view All, Income only, or "
                        "Expense only. The search bar lets you find transactions by category, "
                        "description, exact amount (e.g. 1500), date (e.g. \"Jan 15 2024\", "
                        "\"Monday\", \"January\", \"2024\"), or partial text matches. "
                        "Scroll down and tap \"Load More\" to paginate through older entries. "
                        "Tap the delete icon on any transaction to remove it."),
                    _help_section("💰 Setting & Tracking Budgets",
                        "Go to the Budgets page and tap \"+ New Budget\". Select an expense "
                        "category and enter a monthly spending limit. Each budget card shows "
                        "a progress bar, the amount spent so far this month, and the limit. "
                        "A green bar means you're under 80%, orange warns you're near the "
                        "limit (80%+), and red means you've exceeded it with an \"Over Budget\" "
                        "badge. You can edit the limit or delete budgets anytime. Expenses "
                        "automatically update budget progress as you add them."),
                    _help_section("📊 Generating Reports",
                        "Open the Reports page to analyze your finances. Four period types:\n"
                        "• Monthly — navigate with arrow buttons\n"
                        "• Quarterly — view a 3-month quarter (Q1, Q2, Q3, Q4)\n"
                        "• Annually — full year overview\n"
                        "• Custom — pick any start/end date range\n\n"
                        "Each report shows: Balance Summary (opening balance, income, expenses, "
                        "closing balance), an Income vs Expense trend line chart, Income Breakdown "
                        "by category, and Expense Breakdown by category with percentage bars. "
                        "If you have budgets set, a budget vs spending bar chart also appears."),
                    _help_section("🏷️ Managing Custom Categories",
                        "Go to the Categories page. Switch between the Income and Expense tabs "
                        "to see the default categories (read-only chips) and your custom ones. "
                        "Tap \"+ Add Category\" to create a new one — enter a name and an emoji "
                        "icon (Tip: Win + . opens the emoji keyboard on Windows). Custom "
                        "categories appear everywhere: in Add Transaction, Budgets, and Reports. "
                        "You can delete custom categories, but built-in defaults are fixed."),
                    _help_section("⚙️ Account & Settings",
                        "In Settings you can manage your profile and app preferences:\n"
                        "• Profile Photo — upload a photo via the native file picker (auto-resized "
                        "to 512px); tap the avatar to view it full-size\n"
                        "• Username — tap to edit your display name\n"
                        "• Change Email — sends a verification link to the new address\n"
                        "• Change Password — update your password (min 8 chars, must contain "
                        "a letter and a number); or send a reset link instead\n"
                        "• Dark Mode — toggle between light and dark themes\n"
                        "• Currency — switch between PKR, USD, EUR, GBP, INR, AED, SAR, CAD "
                        "with live exchange rates; all existing data converts automatically\n"
                        "• Sign Out — sign out of your account\n"
                        "• Delete Account — permanently erases all data (type DELETE + password)"),
                    _help_section("⌨️ Keyboard Shortcuts",
                        "While on any page, press Ctrl+1 through Ctrl+6 to quickly jump between "
                        "screens:\n"
                        "Ctrl+1  Home ·  Ctrl+2  History ·  Ctrl+3  Reports\n"
                        "Ctrl+4  Budgets ·  Ctrl+5  Categories ·  Ctrl+6  Settings"),
                ], spacing=6, tight=True, scroll=ft.ScrollMode.AUTO),
                padding=ft.Padding(8, 4, 8, 4),
            ),
        )
        page.show_dialog(dialog)

    def _help_section(heading: str, body: str) -> ft.Column:
        return ft.Column([
            ft.Text(heading, size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.Text(body, size=12, color=c["text_mid"]),
            ft.Container(height=8),
        ], spacing=2)

    # ── FAQ dialog ────────────────────────────────────────────────
    def open_faq_dialog():
        faqs = [
            ("How do I reset my password?",
             "Go to Settings → Change Password. You have two options:\n"
             "1. If you know your current password, enter it along with your new password and tap Update Password. "
             "Your password must be at least 8 characters with at least one letter and one number.\n"
             "2. If you've forgotten your password, tap \"Send reset link instead\" — "
             "a password reset email will be sent to your registered email address. "
             "Follow the link in that email to create a new password."),
            ("How are my opening and closing balances calculated in reports?",
             "Opening Balance = sum of all transactions (income - expenses) before the selected period.\n"
             "Income = total income transactions within the period.\n"
             "Expenses = total expense transactions within the period.\n"
             "Closing Balance = Opening + Income - Expenses.\n"
             "The closing balance of one period becomes the opening balance of the next."),
            ("What happens when I delete my account?",
             "WARNING: This action is permanent and cannot be undone.\n"
             "All your data is deleted in this order:\n"
             "1. All transactions are permanently removed.\n"
             "2. All budgets and monthly limits are erased.\n"
             "3. All custom categories and their emoji icons are deleted.\n"
             "4. Your profile photo and username are removed.\n"
             "5. Your Firebase authentication account is deleted.\n\n"
             "You will be signed out immediately after deletion. "
             "There is no way to recover any of this data."),
            ("How are reports generated?",
             "Reports use your actual transaction dates — not the date you added them. "
             "Select a period type (Monthly, Quarterly, Annually, or Custom) and the "
             "page filters all your transactions to show only those within that date range.\n\n"
             "The Balance Summary computes opening/closing balances. The Income vs Expense "
             "chart divides the period into time buckets and plots income/expense lines. "
             "The Expense Breakdown aggregates expenses by category and shows each as a "
             "percentage of total spending. If you have budgets set, a budget vs spending "
             "bar chart also appears."),
            ("Can I have budgets for custom categories?",
             "Yes! Custom categories work exactly like built-in ones. Once you create a "
             "custom category in the Categories page (with your own emoji icon), you can "
             "immediately set a monthly budget for it on the Budgets page. The budget "
             "tracks spending just like any other category."),
             ("What currencies does FinTrack support?",
             "FinTrack fully supports multiple currencies. Go to Settings → Currency to "
             "choose your preferred currency from: PKR (₨), USD ($), EUR (€), GBP (£), "
             "INR (₹), AED (د.إ), SAR (﷼), CAD (CA$).\n\n"
             "When you switch currencies, FinTrack fetches the current live exchange rate "
             "from the internet (open.er-api.com) and automatically converts ALL your "
             "existing transactions and budgets to the new currency in the database — "
             "no manual rate entry needed. Future transactions will be stored in the new "
             "currency. If the live rate service is unreachable, a cached fallback rate "
             "is used instead."),
            ("Is my data backed up?",
             "Yes. All your data is stored securely in the cloud:\n"
             "• Firebase handles authentication (login, password, email)\n"
             "• Supabase stores your transactions, budgets, categories, and profile\n"
             "• Profile photos are stored in Supabase Storage\n\n"
             "Your data persists across sessions and devices — simply sign in with the "
             "same email and password to access everything."),
            ("What do the budget badges (Over Budget / Near Limit) mean?",
             "Budget cards show color-coded progress:\n"
             "• Green — you've spent less than 80% of your monthly limit\n"
             "• Orange (\"Near Limit\") — you've reached 80% or more of your limit\n"
             "• Red (\"Over Budget\") — you've exceeded your monthly limit\n\n"
             "These update automatically as you add new expense transactions."),
            ("Does FinTrack work offline?",
             "FinTrack requires an internet connection for most operations since "
             "your data is stored in the cloud (Firebase + Supabase). If your "
             "connection drops, a banner appears at the top of the screen saying "
             "\"No internet connection\". The app checks connectivity every few "
             "seconds and the banner disappears once you're back online."),
            ("Are there keyboard shortcuts?",
             "Yes! While on any page inside the app, use:\n"
             "Ctrl+1  →  Home    ·  Ctrl+4  →  Budgets\n"
             "Ctrl+2  →  History  ·  Ctrl+5  →  Categories\n"
             "Ctrl+3  →  Reports  ·  Ctrl+6  →  Settings"),
        ]
        dialog = ft.AlertDialog(
            modal=True, bgcolor=c["surface"], shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("FAQ", page, size=16),
            content=ft.Container(
                width=360,
                content=ft.Column([
                    *[
                        ft.Column([
                            ft.Text(q, size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                            ft.Text(a, size=12, color=c["text_mid"]),
                            ft.Container(height=10),
                        ], spacing=2)
                        for q, a in faqs
                    ],
                ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    def refresh():
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return
        try:
            profile = SupabaseService.get_profile(uid)
        except SupabaseError:
            profile = {}
        username_text.value = profile.get("username") or "User"
        email_text.value = FirebaseAuthService.get_email() or ""
        show_avatar(profile.get("avatar_url"))
        currency_label.value = f"{theme.currency}  ({CURRENCY_CONFIG.get(theme.currency, {}).get('symbol', '')})"
        page.update()

    content = ft.ListView(
        [
            ft.Text("Settings", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.Container(height=20),
            profile_card,
            ft.Container(height=24),
            ft.Text("ACCOUNT", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
            account_tile("👤", "Username", "Tap to edit your display name", open_username_dialog),
            account_tile("✉️", "Change Email", "Update via Firebase verification", open_email_dialog),
            account_tile("🔒", "Change Password", "Update your account password", open_password_dialog),
            ft.Container(height=24),
            ft.Text("APPEARANCE", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
            dark_mode_tile,
            ft.Container(height=10),
            currency_tile,
            ft.Container(height=24),
            ft.Text("SUPPORT", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
            account_tile("❓", "Help", "Learn how to use FinTrack", open_help_dialog),
            account_tile("📖", "FAQ", "Frequently asked questions", open_faq_dialog),
            ft.Container(height=24),
            neo_button("🚪  Sign Out", on_click=confirm_sign_out, width=200, height=44, filled=False,
                        hover_scale=1.01),
            ft.Container(height=28),
            ft.Text("DANGER ZONE", size=12, weight=ft.FontWeight.BOLD, color=Palette.EXPENSE),
            ft.Container(height=10),
            account_tile("🗑️", "Delete Account",
                         "Permanently erase your account and all data — cannot be undone",
                         open_delete_account_dialog, danger=True),
        ],
        # ListView (unlike Column) exposes clip_behavior, so we can turn off
        # the default hard-edge clip that was slicing off the hover-zoom on
        # the account tiles / sign out / delete account buttons.
        clip_behavior=ft.ClipBehavior.NONE,
        scroll=ft.ScrollMode.AUTO,
        spacing=6, expand=True,
    )

    page_view = ft.Stack(
        controls=[mesh_background(), ft.Container(content=content, padding=48, expand=True, clip_behavior=ft.ClipBehavior.NONE)],
        expand=True,
    )
    page_view.refresh = refresh
    return page_view