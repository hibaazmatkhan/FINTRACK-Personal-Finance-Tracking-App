"""Login screen — email/password sign in via Firebase, with email
verification enforced before dashboard access. (Flet edition)"""
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, neo_button, neo_input_slot
from services.firebase_auth import FirebaseAuthService, AuthError


def LoginScreen(page: ft.Page, on_login_success, on_go_register,
                 prefill_email: str = "", notice: str = "") -> ft.Control:
    c = theme.colors

    email_box, email_field = neo_input_slot("Email", width=360)
    pw_box, pw_field = neo_input_slot("Password", password=True, width=360)
    if prefill_email:
        email_field.value = prefill_email

    error_text = ft.Text(notice, color=Palette.INCOME if notice else Palette.EXPENSE,
                          size=12, visible=bool(notice))

    def show_error(msg: str, ok: bool = False):
        error_text.value = msg
        error_text.color = Palette.INCOME if ok else Palette.EXPENSE
        error_text.visible = bool(msg)
        page.update()

    def resend_verification(e=None):
        try:
            FirebaseAuthService.send_email_verification()
            show_error("Verification email resent. Check your inbox (spam folder if not visible).", ok=True)
        except AuthError as ex:
            show_error(str(ex))
        finally:
            FirebaseAuthService.sign_out()  # stay logged out either way

    def do_login(e=None):
        email = (email_field.value or "").strip()
        password = pw_field.value or ""
        show_error("")

        if not email or not password:
            show_error("Please fill in all fields.")
            return

        login_button.content = ft.Row(
            [ft.Text("Signing in...", color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14)],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        login_button.disabled = True
        page.update()

        try:
            FirebaseAuthService.sign_in(email, password)
            if not FirebaseAuthService.is_email_verified():
                # Signed in successfully at Firebase's level, but this
                # account hasn't completed verification yet — don't let
                # it through to the dashboard. Keep the session alive
                # just long enough for "Resend" to use it; resend_verification
                # signs out afterwards either way.
                error_text.value = "Please verify your email before signing in."
                error_text.color = Palette.EXPENSE
                error_text.visible = True
                resend_link.visible = True
                page.update()
                return
            resend_link.visible = False
            on_login_success()
        except AuthError as ex:
            show_error(str(ex))
        finally:
            login_button.content = ft.Row(
                [ft.Text("Sign in", color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14)],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            login_button.disabled = False
            page.update()

    def forgot_password(e=None):
        email = (email_field.value or "").strip()
        if not email:
            show_error("Enter your email above first, then tap 'Forgot password?'.")
            return
        try:
            FirebaseAuthService.send_password_reset(email)
            # Firebase's email-enumeration protection means this call
            # always reports success, even for an email with no account
            # — that's intentional (it stops attackers from being able to
            # tell which emails are registered), but it means we genuinely
            # can't confirm anything was sent. Say so honestly instead of
            # promising "check your inbox" for an email that may not exist.
            show_error(f"If an account exists for {email}, a reset link has been sent (check spam if not visible).", ok=True)
        except AuthError as ex:
            show_error(str(ex))

    pw_field.on_submit = do_login

    login_button = neo_button("Sign in", on_click=do_login, width=360, height=48)

    resend_link = ft.TextButton(
        content=ft.Text("Resend verification email", size=12, weight=ft.FontWeight.BOLD, color=Palette.PRIMARY),
        on_click=resend_verification,
        visible=False,
    )

    card_content = ft.Column(
        [
            ft.Container(
                width=64, height=64, border_radius=18,
                bgcolor=Palette.PRIMARY,
                alignment=ft.alignment.Alignment.CENTER,
                content=ft.Text("💰", size=26),
            ),
            ft.Container(height=18),
            ft.Text("Welcome back", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.Text("Sign in to continue tracking your finances",
                    size=13, color=c["text_mid"]),
            ft.Container(height=22),
            email_box,
            ft.Container(height=12),
            pw_box,
            ft.Container(height=6),
            ft.Row(
                [ft.TextButton(
                    content=ft.Text("Forgot password?", size=12, weight=ft.FontWeight.BOLD, color=Palette.PRIMARY),
                    on_click=forgot_password,
                )],
                alignment=ft.MainAxisAlignment.END,
            ),
            error_text,
            resend_link,
            ft.Container(height=4),
            login_button,
            ft.Container(height=18),
            ft.Row(
                [
                    ft.Text("Don't have an account? ", size=13, color=c["text_mid"]),
                    ft.TextButton(
                        content=ft.Text("Sign up", size=13, weight=ft.FontWeight.BOLD, color=Palette.PRIMARY),
                        on_click=lambda e: on_go_register(),
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
