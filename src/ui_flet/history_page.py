"""History page — searchable, filterable transaction list with delete. (Flet edition)"""
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, hoverable, confirm_dialog, format_amount
from services.firebase_auth import FirebaseAuthService
from services.supabase_service import SupabaseService, SupabaseError
from models.data_models import Transaction, icon_for
from datetime import datetime


def HistoryPage(page: ft.Page) -> ft.Control:
    c = theme.colors
    state = {"transactions": [], "filter": "All"}

    list_column = ft.Column(spacing=8)

    search_field = ft.TextField(
        hint_text="🔍 Search category, amount, date (e.g. Jan, Monday, 1500)...", width=360, height=42,
        text_size=13, color=c["text_dark"],
        hint_style=ft.TextStyle(color=c["text_light"], size=13),
        bgcolor="transparent", border=ft.InputBorder.NONE,
        content_padding=ft.Padding(14, 8, 14, 8),
    )
    search_box = ft.Container(
        content=search_field,
        border_radius=12, bgcolor=c["neo_base"],
        shadow=[
            ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(3, 3)),
            ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-3, -3)),
        ],
    )

    filter_chips = {}

    def style_filter_chip(name: str):
        chip = filter_chips[name]
        active = state["filter"] == name
        chip.bgcolor = Palette.PRIMARY if active else c["neo_base"]
        chip.content.color = Palette.WHITE if active else c["text_mid"]

    def set_filter(name: str):
        state["filter"] = name
        for n in filter_chips:
            style_filter_chip(n)
        render_list()
        page.update()

    def make_filter_chip(name: str) -> ft.Container:
        text = ft.Text(name, size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"])
        chip = ft.Container(
            content=text, padding=ft.Padding(16, 8, 16, 8), border_radius=16,
            bgcolor=c["neo_base"],
        )
        hoverable(chip, hover_scale=1.01, on_click=lambda e, n=name: set_filter(n))
        filter_chips[name] = chip
        return chip

    filter_row = ft.Row([make_filter_chip(n) for n in ["All", "Income", "Expense"]], spacing=8)
    style_filter_chip("All")

    def confirm_delete(t: Transaction):
        def do_delete():
            try:
                SupabaseService.delete_transaction(t.id)
                refresh()
            except SupabaseError as ex:
                page.show_dialog(ft.AlertDialog(
                    modal=True, bgcolor=c["surface"],
                    shape=ft.RoundedRectangleBorder(radius=20),
                    title=ft.Text("Error", color=Palette.EXPENSE, weight=ft.FontWeight.BOLD),
                    content=ft.Text(str(ex), color=c["text_mid"]),
                    actions=[ft.TextButton(
                        content=ft.Text("OK", color=Palette.PRIMARY, weight=ft.FontWeight.BOLD),
                        on_click=lambda e: page.pop_dialog(),
                    )],
                ))

        confirm_dialog(
            page, "Delete transaction", "Are you sure you want to delete this?",
            confirm_label="Delete", confirm_color=Palette.EXPENSE, on_confirm=do_delete,
        )

    def build_tile(t: Transaction) -> ft.Control:
        color = Palette.INCOME if t.is_income else Palette.EXPENSE
        sign = "+" if t.is_income else "-"
        desc = t.description if t.description and t.description != "—" else ""
        sub = f"{desc} • {t.date.strftime('%b %d, %Y')}" if desc else t.date.strftime("%b %d, %Y")

        return glass_card(
            ft.Row(
                [
                    ft.Container(
                        width=42, height=42, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.5, c["glass_tint"]),
                        alignment=ft.alignment.Alignment.CENTER,
                        content=ft.Text(icon_for(t.category), size=18),
                    ),
                    ft.Column(
                        [
                            ft.Text(t.category, size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                            ft.Text(sub, size=11, color=c["text_light"]),
                        ],
                        spacing=2, expand=True,
                    ),
                    ft.Text(f"{sign} {format_amount(t.amount)}", size=13, weight=ft.FontWeight.BOLD, color=color),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE, icon_color=Palette.EXPENSE, icon_size=18,
                        on_click=lambda e, tx=t: confirm_delete(tx),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12,
            ),
            padding=12, radius=16,
        )

    def filtered() -> list[Transaction]:
        data = state["transactions"]
        if state["filter"] == "Income":
            data = [t for t in data if t.is_income]
        elif state["filter"] == "Expense":
            data = [t for t in data if not t.is_income]

        query = (search_field.value or "").strip().lower()
        if not query:
            return data

        # Parse query for different match types
        try:
            query_num = float(query.replace(",", ""))
        except ValueError:
            query_num = None

        # Build date-matching helpers
        def _match_date(t: Transaction) -> bool:
            d = t.date
            # Exact date match: "2024-01-15" or "Jan 15 2024"
            for fmt in ("%Y-%m-%d", "%b %d %Y", "%d %b %Y", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(query, fmt).date()
                    if d == parsed:
                        return True
                except ValueError:
                    continue

            # Month name: "january", "jan"
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
                "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            }
            if query in month_names:
                return d.month == month_names[query]

            # Day of week: "monday", "mon"
            day_names = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6,
                "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
            }
            if query in day_names:
                return d.weekday() == day_names[query]

            # Year: "2024"
            if query.isdigit() and len(query) == 4:
                return d.year == int(query)

            return False

        def _match_amount(t: Transaction) -> bool:
            if query_num is None:
                return False
            return t.amount == query_num

        def _match_text(t: Transaction) -> bool:
            return (query in t.category.lower()
                    or query in (t.description or "").lower())

        result = []
        for t in data:
            if _match_date(t) or _match_amount(t) or _match_text(t):
                result.append(t)
        return result

    def render_list():
        data = filtered()
        list_column.controls.clear()
        if not data:
            list_column.controls.append(
                ft.Text("No transactions found.", size=13, color=c["text_light"])
            )
        else:
            for t in data:
                list_column.controls.append(build_tile(t))

    def refresh():
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return
        try:
            rows = SupabaseService.fetch_transactions(uid)
            state["transactions"] = [Transaction.from_row(r) for r in rows]
        except SupabaseError:
            state["transactions"] = []
        render_list()
        page.update()

    search_field.on_change = lambda e: (render_list(), page.update())

    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("History", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                    search_box,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Container(height=16),
            filter_row,
            ft.Container(height=16),
            list_column,
        ],
        scroll=ft.ScrollMode.AUTO,
        spacing=0, expand=True,
    )

    page_view = ft.Stack(
        controls=[mesh_background(), ft.Container(content=content, padding=48, expand=True, clip_behavior=ft.ClipBehavior.NONE)],
        expand=True,
    )
    page_view.refresh = refresh
    return page_view
