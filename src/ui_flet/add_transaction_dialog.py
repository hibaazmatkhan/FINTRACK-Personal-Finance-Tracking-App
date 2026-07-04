"""Add Transaction dialog — with date-aware balance check + budget limit warning. (Flet edition)"""
from datetime import date, datetime
import flet as ft
from ui_flet.theme import theme, Palette, neo_button, hoverable, dialog_title_with_close, confirm_dialog, format_amount
from services.firebase_auth import FirebaseAuthService
from services.supabase_service import SupabaseService, SupabaseError
from models.data_models import (
    Transaction, Budget, icon_for,
    DEFAULT_INCOME_CATEGORIES, DEFAULT_EXPENSE_CATEGORIES, custom_categories_for_type,
)


def AddTransactionDialog(page: ft.Page, on_saved):
    c = theme.colors

    uid = FirebaseAuthService.get_uid()
    try:
        all_transactions = [Transaction.from_row(r) for r in SupabaseService.fetch_transactions(uid)]
    except SupabaseError:
        all_transactions = []
    try:
        budgets = [Budget.from_row(r) for r in SupabaseService.fetch_budgets(uid)]
    except SupabaseError:
        budgets = []

    state = {"txn_type": "expense", "category": None, "date": date.today()}

    amount_field = ft.TextField(
        hint_text="0.00", width=380, height=46, text_size=14,
        color=c["text_dark"], hint_style=ft.TextStyle(color=c["text_light"]),
        bgcolor="transparent", border=ft.InputBorder.NONE,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.Padding(14, 10, 14, 10),
    )
    desc_field = ft.TextField(
        hint_text="What was this for?", width=380, height=46, text_size=14,
        color=c["text_dark"], hint_style=ft.TextStyle(color=c["text_light"]),
        bgcolor="transparent", border=ft.InputBorder.NONE,
        content_padding=ft.Padding(14, 10, 14, 10),
    )

    balance_text = ft.Text("", size=11, color=c["text_mid"])
    warning_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)
    error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)
    date_label = ft.Text(date.today().strftime("%b %d, %Y"), size=13, color=c["text_dark"], weight=ft.FontWeight.BOLD)

    category_chips_row = ft.Row(wrap=True, spacing=8, run_spacing=8)

    def neo_inset(content, *, width=None, height=46, radius=12, padding=0):
        return ft.Container(
            content=content, width=width, height=height, padding=padding,
            border_radius=radius, bgcolor=c["neo_base"],
            shadow=[
                ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(3, 3)),
                ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-3, -3)),
            ],
        )

    def balance_on_date(target: date) -> float:
        inc = sum(t.amount for t in all_transactions if t.is_income and t.date <= target)
        exp = sum(t.amount for t in all_transactions if not t.is_income and t.date <= target)
        return inc - exp

    def spent_in_category_month(category: str, target: date) -> float:
        return sum(
            t.amount for t in all_transactions
            if not t.is_income and t.category == category
            and t.date.month == target.month and t.date.year == target.year
        )

    def check_warnings():
        try:
            amount = float(amount_field.value or 0)
        except ValueError:
            amount = 0

        target_date = state["date"]
        balance = balance_on_date(target_date)
        balance_text.value = f"Balance on {target_date.strftime('%b %d, %Y')}: {format_amount(balance)}"

        warnings = []
        if state["txn_type"] == "expense" and amount > 0 and amount > balance:
            warnings.append(
                f"This expense ({format_amount(amount)}) exceeds your balance on that date ({format_amount(balance)})."
            )

        if state["txn_type"] == "expense" and state["category"] and amount > 0:
            budget = next((b for b in budgets if b.category == state["category"]), None)
            if budget:
                projected = spent_in_category_month(state["category"], target_date) + amount
                if projected > budget.monthly_limit:
                    over = projected - budget.monthly_limit
                    warnings.append(
                        f'"{state["category"]}" would reach {format_amount(projected)} of your '
                        f"{format_amount(budget.monthly_limit)} monthly budget — over by {format_amount(over)}."
                    )

        warning_text.value = " ".join(warnings)
        warning_text.visible = bool(warnings)
        try:
            dialog.update()
        except RuntimeError:
            pass  # dialog not yet attached to the page (initial build pass)

    def select_category(cat: str):
        state["category"] = cat
        rebuild_chips()
        check_warnings()

    def rebuild_chips():
        defaults = DEFAULT_EXPENSE_CATEGORIES if state["txn_type"] == "expense" else DEFAULT_INCOME_CATEGORIES
        custom_for_this_type = custom_categories_for_type(state["txn_type"])
        categories = defaults + [n for n in custom_for_this_type if n not in defaults]

        category_chips_row.controls.clear()
        for cat in categories:
            selected = state["category"] == cat
            chip = ft.Container(
                content=ft.Text(f"{icon_for(cat)} {cat}", size=12,
                                 color=Palette.WHITE if selected else c["text_dark"],
                                 weight=ft.FontWeight.BOLD if selected else ft.FontWeight.NORMAL),
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=10,
                bgcolor=Palette.PRIMARY if selected else c["neo_base"],
            )
            hoverable(chip, hover_scale=1.025, on_click=lambda e, cc=cat: select_category(cc))
            category_chips_row.controls.append(chip)

    def set_type(t: str):
        state["txn_type"] = t
        state["category"] = None
        expense_toggle.bgcolor = Palette.EXPENSE if t == "expense" else "transparent"
        expense_toggle_text.color = Palette.WHITE if t == "expense" else c["text_light"]
        income_toggle.bgcolor = Palette.INCOME if t == "income" else "transparent"
        income_toggle_text.color = Palette.WHITE if t == "income" else c["text_light"]
        rebuild_chips()
        check_warnings()
        try:
            dialog.update()
        except RuntimeError:
            pass

    expense_toggle_text = ft.Text("↑ Expense", size=13, weight=ft.FontWeight.BOLD, color=Palette.WHITE)
    income_toggle_text = ft.Text("↓ Income", size=13, color=c["text_light"])

    expense_toggle = ft.Container(
        content=expense_toggle_text, padding=ft.Padding(0, 10, 0, 10),
        border_radius=10, bgcolor=Palette.EXPENSE, expand=True,
        alignment=ft.alignment.Alignment.CENTER,
    )
    hoverable(expense_toggle, hover_scale=1.02, on_click=lambda e: set_type("expense"))

    income_toggle = ft.Container(
        content=income_toggle_text, padding=ft.Padding(0, 10, 0, 10),
        border_radius=10, bgcolor="transparent", expand=True,
        alignment=ft.alignment.Alignment.CENTER,
    )
    hoverable(income_toggle, hover_scale=1.02, on_click=lambda e: set_type("income"))

    type_toggle_row = neo_inset(
        ft.Row([expense_toggle, income_toggle], spacing=4),
        width=380, height=58, padding=4, radius=14,
    )

    # ── Date picker ───────────────────────────────────────────
    date_picker = ft.DatePicker(
        value=date.today(),
        first_date=date(2000, 1, 1),
        last_date=date.today(),
    )

    def on_date_change(e):
        if date_picker.value:
            picked = date_picker.value
            state["date"] = picked.date() if isinstance(picked, datetime) else picked
            date_label.value = state["date"].strftime("%b %d, %Y")
            check_warnings()
            try:
                dialog.update()
            except RuntimeError:
                pass

    date_picker.on_change = on_date_change
    page.overlay.append(date_picker)

    date_row = neo_inset(
        ft.Row(
            [date_label, ft.Icon(ft.Icons.CALENDAR_MONTH, size=18, color=c["text_mid"])],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        width=380, padding=ft.Padding(14, 12, 14, 12),
    )
    hoverable(date_row, hover_scale=1.01, on_click=lambda e: page.show_dialog(date_picker))

    def submit(e=None):
        error_text.visible = False
        try:
            amount = float(amount_field.value or 0)
            if amount <= 0:
                raise ValueError
        except ValueError:
            error_text.value = "Please enter a valid positive amount."
            error_text.visible = True
            dialog.update()
            return

        if not state["category"]:
            error_text.value = "Please select a category."
            error_text.visible = True
            dialog.update()
            return

        if warning_text.value:
            confirm_and_submit()
            return

        do_save(amount)

    def confirm_and_submit():
        def proceed():
            try:
                amount = float(amount_field.value or 0)
            except ValueError:
                amount = 0
            do_save(amount)

        confirm_dialog(
            page, "Heads up", warning_text.value + "\n\nAdd anyway?",
            confirm_label="Add anyway", on_confirm=proceed,
        )

    def do_save(amount: float):
        save_button.content = ft.Row(
            [ft.Text("Saving...", color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14)],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        save_button.disabled = True
        try:
            dialog.update()
        except RuntimeError:
            pass
        try:
            SupabaseService.add_transaction(
                uid, state["txn_type"], state["category"], amount,
                (desc_field.value or "").strip(), state["date"],
            )
            page.pop_dialog()
            on_saved()
        except SupabaseError as ex:
            error_text.value = str(ex)
            error_text.visible = True
            save_button.content = ft.Row(
                [ft.Text("Save Transaction", color=Palette.WHITE, weight=ft.FontWeight.BOLD, size=14)],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            save_button.disabled = False
            try:
                dialog.update()
            except RuntimeError:
                pass

    save_button = neo_button("Save Transaction", on_click=submit, width=380, height=48)

    dialog_content = ft.Container(
        width=420,
        content=ft.Column(
            [
                type_toggle_row,
                ft.Container(height=16),
                ft.Text("Amount", size=12, color=c["text_mid"]),
                neo_inset(amount_field, width=380),
                ft.Container(height=4),
                balance_text,
                warning_text,
                ft.Container(height=12),
                ft.Text("Category", size=12, color=c["text_mid"]),
                ft.Container(height=8),
                category_chips_row,
                ft.Container(height=16),
                ft.Text("Description (optional)", size=12, color=c["text_mid"]),
                neo_inset(desc_field, width=380),
                ft.Container(height=16),
                ft.Text("Date", size=12, color=c["text_mid"]),
                date_row,
                ft.Container(height=12),
                error_text,
                ft.Container(height=8),
                save_button,
            ],
            spacing=4, tight=True,
        ),
        padding=8,
    )

    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=c["surface"],
        shape=ft.RoundedRectangleBorder(radius=24),
        title=dialog_title_with_close("Add Transaction", page),
        content=dialog_content,
        scrollable=True,
    )

    amount_field.on_change = lambda e: check_warnings()
    rebuild_chips()
    check_warnings()

    page.show_dialog(dialog)
    return dialog
