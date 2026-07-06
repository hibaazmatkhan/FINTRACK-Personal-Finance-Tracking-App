"""Home / Overview page. (Flet edition)"""
from datetime import datetime
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, glass_hero, neo_fab, hoverable, confirm_dialog, show_error_dialog, format_amount
from services.firebase_auth import FirebaseAuthService
from services.supabase_service import SupabaseService, SupabaseError
from models.data_models import Transaction, icon_for


def HomePage(page: ft.Page, on_add) -> ft.Control:
    c = theme.colors

    greeting_text = ft.Text("", size=13, color=c["text_mid"])
    username_text = ft.Text("User", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"])

    balance_label = ft.Text(format_amount(0), size=30, weight=ft.FontWeight.BOLD, color=Palette.WHITE)
    savings_label = ft.Text("Savings rate: 0%", size=12, color=ft.Colors.with_opacity(0.85, Palette.WHITE))

    income_value = ft.Text(format_amount(0), size=16, weight=ft.FontWeight.BOLD, color=Palette.INCOME)
    expense_value = ft.Text(format_amount(0), size=16, weight=ft.FontWeight.BOLD, color=Palette.EXPENSE)

    recent_list = ft.Column(spacing=8)

    def confirm_delete(t: Transaction):
        def do_delete():
            try:
                SupabaseService.delete_transaction(t.id)
                refresh()
            except SupabaseError as ex:
                show_error_dialog(page, str(ex))

        confirm_dialog(
            page, "Delete transaction", "Are you sure you want to delete this?",
            confirm_label="Delete", confirm_color=Palette.EXPENSE, on_confirm=do_delete,
        )

    def build_tile(t: Transaction) -> ft.Control:
        color = Palette.INCOME if t.is_income else Palette.EXPENSE
        sign = "+" if t.is_income else "-"
        return glass_card(
            ft.Row(
                [
                    ft.Container(
                        width=40, height=40, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.5, c["glass_tint"]),
                        alignment=ft.alignment.Alignment.CENTER,
                        content=ft.Text(icon_for(t.category), size=17),
                    ),
                    ft.Column(
                        [
                            ft.Text(t.category, size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                            ft.Text(t.date.strftime("%b %d, %Y"), size=11, color=c["text_light"]),
                        ],
                        spacing=2, expand=True,
                    ),
                    ft.Text(f"{sign} {format_amount(t.amount)}", size=13, weight=ft.FontWeight.BOLD, color=color),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=Palette.EXPENSE,
                        icon_size=18,
                        on_click=lambda e, tx=t: confirm_delete(tx),
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            padding=12, radius=16,
        )

    def refresh():
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return

        hour = datetime.now().hour
        greeting_text.value = (
            "Good morning," if hour < 12 else "Good afternoon," if hour < 17 else "Good evening,"
        )

        profile = SupabaseService.get_profile(uid)
        username_text.value = profile.get("username") or "User"

        try:
            totals = SupabaseService.fetch_totals(uid)
            income = totals["income"]
            expense = totals["expense"]
        except SupabaseError:
            income = 0.0
            expense = 0.0

        balance = income - expense
        savings_rate = ((income - expense) / income * 100) if income > 0 else 0
        savings_rate = max(0, min(100, savings_rate))

        balance_label.value = format_amount(balance)
        savings_label.value = f"Savings rate: {savings_rate:.0f}%"
        income_value.value = format_amount(income)
        expense_value.value = format_amount(expense)

        try:
            rows = SupabaseService.fetch_transactions(uid, limit=5)
            recent = [Transaction.from_row(r) for r in rows]
        except SupabaseError:
            recent = []

        recent_list.controls.clear()
        if not recent:
            recent_list.controls.append(
                ft.Text("No transactions yet. Tap + to add your first one!",
                        size=13, color=c["text_light"])
            )
        else:
            for t in recent:
                recent_list.controls.append(build_tile(t))

        page.update()

    hero = glass_hero(
        ft.Column(
            [
                ft.Text("TOTAL BALANCE", size=12, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.with_opacity(0.8, Palette.WHITE)),
                balance_label,
                savings_label,
            ],
            spacing=4,
        ),
        height=130,
    )
    hoverable(hero, hover_scale=1.01)

    fab = neo_fab("Add Transaction", icon=ft.Icons.ADD, on_click=lambda e: on_add(), width=200)

    income_card = glass_card(
        ft.Column(
            [ft.Text("📈 Income", size=12, color=c["text_mid"]), income_value],
            spacing=8,
        ),
        height=90, expand=True,
    )
    expense_card = glass_card(
        ft.Column(
            [ft.Text("📉 Expenses", size=12, color=c["text_mid"]), expense_value],
            spacing=8,
        ),
        height=90, expand=True,
    )

    content = ft.ListView(
        [
            ft.Row(
                [
                    ft.Column([greeting_text, username_text], spacing=0, expand=True),
                    fab,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            ft.Container(height=16),
            hero,
            ft.Container(height=16),
            ft.Row([income_card, expense_card], spacing=16),
            ft.Container(height=20),
            ft.Text("RECENT TRANSACTIONS", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=8),
            recent_list,
        ],
        # ListView (unlike Column) exposes clip_behavior, so we can turn off
        # the default hard-edge clip that was slicing off the hover-zoom on
        # the "Add Transaction" button and the total balance hero card.
        clip_behavior=ft.ClipBehavior.NONE,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        expand=True,
    )

    page_view = ft.Stack(
        controls=[
            mesh_background(),
            ft.Container(content=content, padding=48, expand=True, clip_behavior=ft.ClipBehavior.NONE),
        ],
        expand=True,
    )

    page_view.refresh = refresh  # exposed so the dashboard can call it on page-switch
    return page_view