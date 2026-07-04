"""Categories page — manage custom income/expense categories with emoji. (Flet edition)"""
import re
import flet as ft
from ui_flet.theme import theme, Palette, mesh_background, glass_card, neo_button, hoverable, dialog_title_with_close, confirm_dialog
from services.firebase_auth import FirebaseAuthService
from services.supabase_service import SupabaseService, SupabaseError
from models.data_models import (
    CustomCategory, icon_for, load_custom_categories,
    DEFAULT_INCOME_CATEGORIES, DEFAULT_EXPENSE_CATEGORIES,
)

EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF]+"
)


def CategoriesPage(page: ft.Page) -> ft.Control:
    c = theme.colors
    state = {"custom": [], "tab": "expense"}

    body_column = ft.Column(spacing=0)
    tab_chips = {}

    def style_tab(key: str):
        chip = tab_chips[key]
        active = state["tab"] == key
        chip.bgcolor = Palette.PRIMARY if active else c["neo_base"]
        chip.content.color = Palette.WHITE if active else c["text_mid"]

    def set_tab(key: str):
        state["tab"] = key
        for k in tab_chips:
            style_tab(k)
        render()
        page.update()

    def make_tab(label: str, key: str) -> ft.Container:
        text = ft.Text(label, size=13, weight=ft.FontWeight.BOLD, color=c["text_mid"])
        chip = ft.Container(content=text, padding=ft.Padding(18, 9, 18, 9), border_radius=17, bgcolor=c["neo_base"])
        hoverable(chip, hover_scale=1.025, on_click=lambda e, k=key: set_tab(k))
        tab_chips[key] = chip
        return chip

    def confirm_delete(cat: CustomCategory):
        def do_delete():
            try:
                SupabaseService.delete_custom_category(cat.id)
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
            page, "Delete Category", f'Delete "{cat.name}"?',
            confirm_label="Delete", confirm_color=Palette.EXPENSE, on_confirm=do_delete,
        )

    def open_add_dialog():
        preview_text = ft.Text("🙂", size=28)
        preview_circle = ft.Container(
            width=64, height=64, border_radius=18, bgcolor=Palette.PRIMARY_LIGHT,
            alignment=ft.alignment.Alignment.CENTER, content=preview_text,
        )

        emoji_field = ft.TextField(
            hint_text="Paste or type an emoji", width=340, height=46, text_size=14,
            color=c["text_dark"], hint_style=ft.TextStyle(color=c["text_light"]),
            bgcolor="transparent", border=ft.InputBorder.NONE,
            content_padding=ft.Padding(14, 10, 14, 10),
        )
        name_field = ft.TextField(
            hint_text="e.g. Pet Care, Side Hustle", width=340, height=46, text_size=14,
            color=c["text_dark"], hint_style=ft.TextStyle(color=c["text_light"]),
            bgcolor="transparent", border=ft.InputBorder.NONE,
            content_padding=ft.Padding(14, 10, 14, 10),
        )

        def neo_inset(field):
            return ft.Container(
                content=field, border_radius=12, bgcolor=c["neo_base"],
                shadow=[
                    ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_dark_alpha"], c["neo_dark"]), offset=ft.Offset(3, 3)),
                    ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(c["neo_light_alpha"], c["neo_light"]), offset=ft.Offset(-3, -3)),
                ],
            )

        def on_emoji_change(e):
            val = (emoji_field.value or "").strip()
            preview_text.value = val if val else "🙂"
            dialog.update()

        emoji_field.on_change = on_emoji_change

        error_text = ft.Text("", size=12, color=Palette.EXPENSE, visible=False)

        def save(e):
            name = (name_field.value or "").strip()
            emoji = (emoji_field.value or "").strip()

            if not name:
                error_text.value = "Please enter a category name."
                error_text.visible = True
                dialog.update()
                return
            if not emoji:
                error_text.value = "Please add an emoji for this category."
                error_text.visible = True
                dialog.update()
                return
            if not EMOJI_PATTERN.search(emoji):
                error_text.value = "That doesn't look like an emoji — try again."
                error_text.visible = True
                dialog.update()
                return

            all_defaults = DEFAULT_EXPENSE_CATEGORIES + DEFAULT_INCOME_CATEGORIES
            if name.lower() in [n.lower() for n in all_defaults]:
                error_text.value = "This category already exists."
                error_text.visible = True
                dialog.update()
                return

            uid = FirebaseAuthService.get_uid()
            try:
                SupabaseService.add_custom_category(uid, name, emoji, state["tab"])
                page.pop_dialog()
                refresh()
            except SupabaseError as ex:
                error_text.value = str(ex)
                error_text.visible = True
                dialog.update()
                return

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=c["surface"],
            shape=ft.RoundedRectangleBorder(radius=24),
            title=dialog_title_with_close(f"New {state['tab'].capitalize()} Category", page, size=17),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    [
                        ft.Row([preview_circle], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=12),
                        ft.Text("Emoji", size=12, color=c["text_mid"]),
                        neo_inset(emoji_field),
                        ft.Container(height=4),
                        ft.Text("Tip: Win + . opens the emoji keyboard on Windows. You can also paste one.",
                                size=11, color=c["text_light"]),
                        ft.Container(height=12),
                        ft.Text("Category Name", size=12, color=c["text_mid"]),
                        neo_inset(name_field),
                        ft.Container(height=12),
                        error_text,
                        ft.Container(height=8),
                        neo_button("Add Category", on_click=save, width=340, height=48),
                    ],
                    spacing=4, tight=True,
                ),
                padding=8,
            ),
        )
        page.show_dialog(dialog)

    def default_chip(cat: str) -> ft.Container:
        return ft.Container(
            content=ft.Text(f"{icon_for(cat)}  {cat}", size=12, color=c["text_dark"]),
            padding=ft.Padding(14, 9, 14, 9), border_radius=12,
            bgcolor=c["neo_base"],
        )

    def custom_row(cat: CustomCategory) -> ft.Control:
        return glass_card(
            ft.Row(
                [
                    ft.Text(f"{cat.emoji}  {cat.name}", size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=Palette.EXPENSE, icon_size=18,
                                  on_click=lambda e, cc=cat: confirm_delete(cc)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=14, radius=14,
        )

    def render():
        defaults = DEFAULT_EXPENSE_CATEGORIES if state["tab"] == "expense" else DEFAULT_INCOME_CATEGORIES
        custom = [cat for cat in state["custom"] if cat.type == state["tab"]]

        body_column.controls.clear()
        body_column.controls.extend([
            ft.Text("DEFAULT CATEGORIES", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
            ft.Row([default_chip(cat) for cat in defaults], wrap=True, spacing=8, run_spacing=8),
            ft.Container(height=24),
            ft.Text("YOUR CUSTOM CATEGORIES", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
        ])

        if not custom:
            body_column.controls.append(
                ft.Text("No custom categories yet.", size=13, color=c["text_light"])
            )
        else:
            body_column.controls.append(ft.Column([custom_row(cat) for cat in custom], spacing=8))

        body_column.controls.extend([
            ft.Container(height=20),
            neo_button(f"+ Add {state['tab'].capitalize()} Category",
                       on_click=lambda e: open_add_dialog(), width=260, height=44),
        ])

    def refresh():
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return
        try:
            rows = SupabaseService.fetch_custom_categories(uid)
            state["custom"] = [CustomCategory.from_row(r) for r in rows]
        except SupabaseError:
            state["custom"] = []
        load_custom_categories(uid, force=True)  # keep the shared dicts in sync too
        render()
        page.update()

    tab_row = ft.Row([make_tab("Expense", "expense"), make_tab("Income", "income")], spacing=8)
    style_tab("expense")

    content = ft.Column(
        [
            ft.Text("Categories", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.Container(height=16),
            tab_row,
            ft.Container(height=16),
            body_column,
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
