"""Budgets page — set & track monthly category spending limits. (Flet edition)"""
from datetime import date
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, neo_button, dialog_title_with_close, confirm_dialog, format_amount, get_max_amount, CURRENCY_CONFIG
from services.firebase_auth import FirebaseAuthService
from services.supabase_service import SupabaseService, SupabaseError
from models.data_models import Transaction, Budget, icon_for, DEFAULT_EXPENSE_CATEGORIES, custom_categories_for_type


def BudgetsPage(page: ft.Page, on_changed=None) -> ft.Control:
    c = theme.colors
    state = {"budgets": [], "transactions": []}

    list_column = ft.Column(spacing=10)

    def spent_this_month(category: str) -> float:
        today = date.today()
        return sum(
            t.amount for t in state["transactions"]
            if not t.is_income and t.category == category
            and t.date.month == today.month and t.date.year == today.year
        )

    def confirm_delete(b: Budget):
        def do_delete():
            try:
                SupabaseService.delete_budget(b.id)
                refresh()
                if on_changed:
                    on_changed()
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
            page, "Remove Budget", f'Remove budget for "{b.category}"?',
            confirm_label="Remove", confirm_color=Palette.EXPENSE, on_confirm=do_delete,
        )

    def open_budget_dialog(existing: Budget = None):
        custom_expense_cats = custom_categories_for_type("expense")
        all_cats = list(DEFAULT_EXPENSE_CATEGORIES) + [
            n for n in custom_expense_cats if n not in DEFAULT_EXPENSE_CATEGORIES
        ]
        used = {b.category for b in state["budgets"] if not existing or b.category != existing.category}
        available = [cat for cat in all_cats if cat not in used] if not existing else all_cats

        category_dropdown = ft.Dropdown(
            value=existing.category if existing else (available[0] if available else None),
            options=[
                ft.DropdownOption(
                    key=cat, text=f"{icon_for(cat)}  {cat}",
                    style=ft.ButtonStyle(color=c["text_dark"], bgcolor=c["neo_base"]),
                )
                for cat in (available or [])
            ],
            width=340, disabled=bool(existing),
            color=c["text_dark"], text_style=ft.TextStyle(color=c["text_dark"], size=14),
            border_radius=12, border_color=c["border"], filled=True, fill_color=c["neo_base"],
            menu_style=ft.MenuStyle(bgcolor=c["surface"]),
        )

        cur_symbol = CURRENCY_CONFIG.get(theme.currency, {}).get("symbol", "$")
        cur_prefix = CURRENCY_CONFIG.get(theme.currency, {}).get("prefix", True)
        budget_currency_label = ft.Text(f"{cur_symbol} " if cur_prefix else "", size=14,
                                         color=c["text_dark"], weight=ft.FontWeight.BOLD)

        amount_field = ft.TextField(
            hint_text="0.00", value=str(int(existing.monthly_limit)) if existing else "",
            width=340, height=46, text_size=14, color=c["text_dark"],
            hint_style=ft.TextStyle(color=c["text_light"]),
            bgcolor="transparent", border=ft.InputBorder.NONE,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=ft.Padding(14, 10, 14, 10),
        )
        amount_box = ft.Container(
            content=ft.Row([budget_currency_label, amount_field], spacing=4,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border_radius=12, bgcolor=c["neo_base"],
            padding=ft.Padding(14, 10, 14, 10),
            shadow=[
                ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(3, 3)),
                ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-3, -3)),
            ],
        )

        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        def save(e):
            if not category_dropdown.value:
                error_text.value = "Please select a category."
                error_text.visible = True
                dialog.update()
                return
            try:
                amount = float(amount_field.value or 0)
                if amount <= 0:
                    raise ValueError
                max_amt = get_max_amount()
                if amount > max_amt:
                    error_text.value = f"Maximum allowed is {format_amount(max_amt)} per budget."
                    error_text.visible = True
                    dialog.update()
                    return
            except ValueError:
                error_text.value = "Please enter a valid amount."
                error_text.visible = True
                dialog.update()
                return

            uid = FirebaseAuthService.get_uid()
            try:
                SupabaseService.upsert_budget(uid, category_dropdown.value, amount)
                page.pop_dialog()
                refresh()
                if on_changed:
                    on_changed()
            except SupabaseError as ex:
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()
                return

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=c["surface"],
            shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close("Edit Budget" if existing else "Set a Budget", page),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    [
                        ft.Text("Category", size=12, color=c["text_mid"]),
                        category_dropdown,
                        ft.Container(height=16),
                        ft.Text("Monthly Limit", size=12, color=c["text_mid"]),
                        amount_box,
                        ft.Container(height=12),
                        error_text,
                        ft.Container(height=8),
                        neo_button("Update Budget" if existing else "Set Budget",
                                   on_click=save, width=340, height=48),
                    ],
                    spacing=6, tight=True,
                ),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    def build_card(b: Budget) -> ft.Control:
        spent = spent_this_month(b.category)
        pct = (spent / b.monthly_limit * 100) if b.monthly_limit > 0 else 0
        exceeded = spent > b.monthly_limit
        near = pct >= 80 and not exceeded
        color = Palette.EXPENSE if exceeded else (Palette.ACCENT if near else Palette.INCOME)

        tag = None
        if exceeded:
            tag = ft.Container(
                content=ft.Text("Over Budget", size=10, weight=ft.FontWeight.BOLD, color=Palette.EXPENSE),
                bgcolor=Palette.ROSE, border_radius=8, padding=ft.Padding(8, 3, 8, 3),
            )
        elif near:
            tag = ft.Container(
                content=ft.Text("Near Limit", size=10, weight=ft.FontWeight.BOLD, color=Palette.ACCENT),
                bgcolor=Palette.PRIMARY_LIGHT, border_radius=8, padding=ft.Padding(8, 3, 8, 3),
            )

        top_right = []
        if tag:
            top_right.append(tag)
        top_right.append(
            ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_size=16, icon_color=c["text_mid"],
                          on_click=lambda e, bb=b: open_budget_dialog(bb))
        )
        top_right.append(
            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=Palette.EXPENSE,
                          on_click=lambda e, bb=b: confirm_delete(bb))
        )

        return glass_card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(f"{icon_for(b.category)}  {b.category}", size=14,
                                     weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                            ft.Row(top_right, spacing=2),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ProgressBar(value=min(pct / 100, 1.0), bar_height=10, border_radius=5,
                                   color=color, bgcolor=c["border"]),
                    ft.Row(
                        [
                            ft.Text(f"{format_amount(spent)} spent", size=12, weight=ft.FontWeight.BOLD, color=color),
                            ft.Text(f"of {format_amount(b.monthly_limit)}", size=12, color=c["text_mid"]),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
            padding=18,
        )

    def render():
        list_column.controls.clear()
        if not state["budgets"]:
            list_column.controls.append(
                ft.Text("No budgets set yet. Tap '+ New Budget' to get started.",
                        size=13, color=c["text_light"])
            )
        else:
            for b in state["budgets"]:
                list_column.controls.append(build_card(b))

    def refresh():
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return
        try:
            state["budgets"] = [Budget.from_row(r) for r in SupabaseService.fetch_budgets(uid)]
        except SupabaseError:
            state["budgets"] = []
        try:
            state["transactions"] = [Transaction.from_row(r) for r in SupabaseService.fetch_transactions(uid)]
        except SupabaseError:
            state["transactions"] = []
        render()
        page.update()

    add_button = neo_button("+ New Budget", on_click=lambda e: open_budget_dialog(), width=150, height=42)

    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Budgets", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                    add_button,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
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
