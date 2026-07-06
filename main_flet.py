"""
FinTrack — Personal Finance Tracker (Flet edition)
Run with:  python main_flet.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import flet as ft
from ui_flet.theme import theme, configure_page, screen_transition, mount
from ui_flet.login_screen import LoginScreen
from ui_flet.register_screen import RegisterScreen
from ui_flet.dashboard_screen import DashboardScreen


def main(page: ft.Page):
    configure_page(page)

    def show(control: ft.Control):
        """Every screen switch goes through here so the fade+slide-up
        mount transition plays consistently, in one place."""
        page.clean()
        page.bgcolor = theme.colors["surface"]
        wrapped = screen_transition(control)
        page.add(wrapped)
        mount(wrapped, page)
        return wrapped

    def show_login(prefill_email: str = "", notice: str = ""):
        show(LoginScreen(page, on_login_success=show_dashboard, on_go_register=show_register,
                          prefill_email=prefill_email, notice=notice))

    def show_register():
        show(RegisterScreen(page, on_register_success=on_registered, on_go_login=show_login))

    def on_registered(email: str):
        show_login(
            prefill_email=email,
            notice="Account created! Check your email for a verification link, then sign in. If not visible, check your spam folder as well!",
        )

    def show_dashboard():
        from services.firebase_auth import FirebaseAuthService
        from services.supabase_service import set_auth_token
        token = FirebaseAuthService.get_id_token()
        if token:
            set_auth_token(token)
        show(DashboardScreen(page, on_logout=show_login))

    show_login()


if __name__ == "__main__":
    ft.run(main)
