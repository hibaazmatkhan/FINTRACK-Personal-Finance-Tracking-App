"""Register screen — creates a Firebase auth account + Supabase profile row,
sends an email verification link, then signs the person back out so they
must verify before they can actually log in. (Flet edition)"""
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, neo_button, neo_input_slot
from services.firebase_auth import FirebaseAuthService, AuthError
from services.supabase_service import SupabaseService


def RegisterScreen(page: ft.Page, on_register_success, on_go_login) -> ft.Control:
    c = theme.colors

    username_box, username_field = neo_input_slot("Username", width=360)
    email_box, email_field = neo_input_slot("Email", width=360)
    pw_box, pw_field = neo_input_slot("Password (min 6 characters)", password=True, width=360)
    confirm_box, confirm_field = neo_input_slot("Confirm Password", password=True, width=360)

    error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

    def show_error(msg: str, ok: bool = False):
        error_text.value = msg
        error_text.color = Palette.INCOME if ok else Palette.EXPENSE
        error_text.visible = bool(msg)
        page.update()

    def do_register(e=None):
        username = (username_field.value or "").strip()
        email = (email_field.value or "").strip()
        password = pw_field.value or ""
        confirm = confirm_field.value or ""
        show_error("")

        if not username or not email or not password:
            show_error("Please fill in all fields.")
            return
        if password != confirm:
            show_error("Passwords do not match.")
            return
        if len(password) < 6:
            show_error("Password must be at least 6 characters.")
            return

        register_button.content = ft.Row(
            [ft.Text("Creating account...", color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14)],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        register_button.disabled = True
        page.update()

        try:
            user = FirebaseAuthService.sign_up(email, password)
            uid = user["localId"]
            try:
                SupabaseService.upsert_profile(uid, username=username)
            except Exception:
                pass  # profile can be completed later in Settings; not a blocker

            try:
                FirebaseAuthService.send_email_verification()
            except AuthError:
                pass  # account exists either way; they can resend from the login screen

            # sign_up() leaves the new account signed in — sign back out
            # immediately so an unverified account can't reach the
            # dashboard. on_register_success() routes to login with a
            # "check your email" message, not straight into the app.
            FirebaseAuthService.sign_out()
            on_register_success(email)
        except AuthError as ex:
            show_error(str(ex))
            register_button.content = ft.Row(
                [ft.Text("Create Account", color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14)],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            register_button.disabled = False
            page.update()

    confirm_field.on_submit = do_register

    register_button = neo_button("Create Account", on_click=do_register, width=360, height=48)

    card_content = ft.Column(
        [
            ft.Container(
                width=64, height=64, border_radius=18,
                bgcolor=Palette.PRIMARY,
                alignment=ft.alignment.Alignment.CENTER,
                content=ft.Text("✨", size=26),
            ),
            ft.Container(height=18),
            ft.Text("Create account", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.Text("Start tracking your finances today", size=13, color=c["text_mid"]),
            ft.Container(height=22),
            username_box,
            ft.Container(height=12),
            email_box,
            ft.Container(height=12),
            pw_box,
            ft.Container(height=12),
            confirm_box,
            ft.Container(height=8),
            error_text,
            ft.Container(height=4),
            register_button,
            ft.Container(height=18),
            ft.Row(
                [
                    ft.Text("Already have an account? ", size=13, color=c["text_mid"]),
                    ft.TextButton(
                        content=ft.Text("Sign In", size=13, weight=ft.FontWeight.BOLD, color=Palette.PRIMARY),
                        on_click=lambda e: on_go_login(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.START,
        spacing=0,
        width=360,
    )

    return ft.Stack(
        controls=[
            mesh_background(),
            ft.Container(
                content=glass_card(card_content, width=420, padding=32, radius=28),
                alignment=ft.alignment.Alignment.CENTER,
                expand=True,
            ),
        ],
        expand=True,
    )
