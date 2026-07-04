"""Reports page — monthly/quarterly/annual period breakdowns. (Flet edition)"""
from datetime import date, timedelta
from calendar import monthrange
import sys
import flet as ft
import flet_charts as fch
from ui_flet.theme import theme, Palette, mesh_background, glass_card, hoverable, format_amount
from services.firebase_auth import FirebaseAuthService
from services.supabase_service import SupabaseService, SupabaseError
from models.data_models import Transaction, Budget, icon_for


def _long_date_fmt(d: date) -> str:
    """Format as 'Tuesday, May 4, 2029' — cross-platform (no %-m)."""
    day_name = d.strftime("%A")
    month_name = d.strftime("%B")
    day_num = str(d.day)
    year = d.strftime("%Y")
    return f"{day_name}, {month_name} {day_num}, {year}"


def ReportsPage(page: ft.Page) -> ft.Control:
    c = theme.colors
    now = date.today()

    def _normalize_date(v):
        from datetime import datetime
        if isinstance(v, datetime):
            if v.tzinfo is not None:
                v = v.astimezone()
            return date(v.year, v.month, v.day)
        return v

    state = {
        "transactions": [],
        "budgets": [],
        "period": "Monthly",
        "year": now.year,
        "month": now.month,
        "custom_start": now,
        "custom_end": now,
    }

    body_column = ft.Column(spacing=0)
    period_label = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"])

    period_chips = {}

    def style_period_chip(name: str):
        chip = period_chips[name]
        active = state["period"] == name
        chip.bgcolor = Palette.PRIMARY if active else c["neo_base"]
        chip.content.color = Palette.WHITE if active else c["text_mid"]

    def set_period(name: str):
        state["period"] = name
        for n in period_chips:
            style_period_chip(n)
        is_custom = name == "Custom"
        custom_date_section.visible = is_custom
        
        period_control_row.animate_offset = ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC)
        period_control_row.offset = ft.Offset(0, 0)
        
        render()
        page.update()

    def make_period_chip(name: str) -> ft.Container:
        text = ft.Text(name, size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"])
        chip = ft.Container(content=text, padding=ft.Padding(16, 8, 16, 8), border_radius=16, bgcolor=c["neo_base"])
        hoverable(chip, hover_scale=1.01, on_click=lambda e, n=name: set_period(n))
        period_chips[name] = chip
        return chip

    def prev_period(e=None):
        if state["period"] == "Custom":
            return
        if state["period"] == "Monthly":
            state["month"] -= 1
            if state["month"] < 1:
                state["month"] = 12
                state["year"] -= 1
        elif state["period"] == "Quarterly":
            state["month"] -= 3
            if state["month"] < 1:
                state["month"] += 12
                state["year"] -= 1
        else:
            state["year"] -= 1
        render()
        page.update()

    def next_period(e=None):
        if state["period"] == "Custom":
            return
        if state["period"] == "Monthly":
            state["month"] += 1
            if state["month"] > 12:
                state["month"] = 1
                state["year"] += 1
        elif state["period"] == "Quarterly":
            state["month"] += 3
            if state["month"] > 12:
                state["month"] -= 12
                state["year"] += 1
        else:
            state["year"] += 1
        render()
        page.update()

    def period_range():
        if state["period"] == "Custom":
            start = _normalize_date(state["custom_start"])
            end = _normalize_date(state["custom_end"])
            if start > end:
                start, end = end, start
            label = f"{start.strftime('%b %d, %Y')} — {end.strftime('%b %d, %Y')}"
        elif state["period"] == "Monthly":
            start = date(state["year"], state["month"], 1)
            end_day = monthrange(state["year"], state["month"])[1]
            end = date(state["year"], state["month"], end_day)
            label = start.strftime("%B %Y")
        elif state["period"] == "Quarterly":
            q_start_month = ((state["month"] - 1) // 3) * 3 + 1
            start = date(state["year"], q_start_month, 1)
            end_month = q_start_month + 2
            end_day = monthrange(state["year"], end_month)[1]
            end = date(state["year"], end_month, end_day)
            q_num = (q_start_month - 1) // 3 + 1
            label = f"Q{q_num} {state['year']}"
        else:
            start = date(state["year"], 1, 1)
            end = date(state["year"], 12, 31)
            label = str(state["year"])
        return start, end, label

    # ── Custom date pickers ───────────────────────────────────
    start_date_text = ft.Text(_long_date_fmt(state["custom_start"]), size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"])
    end_date_text = ft.Text(_long_date_fmt(state["custom_end"]), size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"])

    start_date_picker = ft.DatePicker(
        current_date=state["custom_start"],
        first_date=date(2000, 1, 1),
        last_date=date(2100, 12, 31),
        on_change=lambda e: _on_start_date_changed(e.control.value),
    )
    end_date_picker = ft.DatePicker(
        current_date=state["custom_end"],
        first_date=date(2000, 1, 1),
        last_date=date(2100, 12, 31),
        on_change=lambda e: _on_end_date_changed(e.control.value),
    )

    def _on_start_date_changed(d):
        d = _normalize_date(d) if d is not None else state["custom_start"]
        state["custom_start"] = d
        if d > state["custom_end"]:
            state["custom_end"] = d
        start_date_text.value = _long_date_fmt(state["custom_start"])
        end_date_text.value = _long_date_fmt(state["custom_end"])
        render()
        page.update()

    def _on_end_date_changed(d):
        d = _normalize_date(d) if d is not None else state["custom_end"]
        state["custom_end"] = d
        if d < state["custom_start"]:
            state["custom_start"] = d
        start_date_text.value = _long_date_fmt(state["custom_start"])
        end_date_text.value = _long_date_fmt(state["custom_end"])
        render()
        page.update()

    def pick_start_date(e):
        start_date_picker.current_date = state["custom_start"]
        start_date_picker.open = True
        page.update()

    def pick_end_date(e):
        end_date_picker.current_date = state["custom_end"]
        end_date_picker.open = True
        page.update()

    start_date_btn = glass_card(
        ft.Row([
            ft.Text("📅", size=14),
            ft.Text("Start", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Text("  |  ", size=12, color=c["text_light"]),
            start_date_text,
        ], spacing=4, alignment=ft.MainAxisAlignment.START),
        padding=ft.Padding(14, 10, 14, 10), radius=12,
        on_click=pick_start_date, hover_scale=1.01,
    )
    end_date_btn = glass_card(
        ft.Row([
            ft.Text("📅", size=14),
            ft.Text("End", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Text("  |  ", size=12, color=c["text_light"]),
            end_date_text,
        ], spacing=4, alignment=ft.MainAxisAlignment.START),
        padding=ft.Padding(14, 10, 14, 10), radius=12,
        on_click=pick_end_date, hover_scale=1.01,
    )

    custom_date_row = ft.Container(
        content=ft.Row([start_date_btn, end_date_btn], spacing=16),
        padding=ft.Padding(0, 0, 0, 0),
    )

    custom_date_section = ft.Container(
        content=custom_date_row,
        visible=False,
    )

    def _format_amount_short(v: float) -> str:
        """Compact label for axis ticks: 150000 -> '150K', 1500000 -> '1.5M'."""
        av = abs(v)
        if av >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if av >= 1_000:
            return f"{v/1_000:.0f}K"
        return f"{v:.0f}"

    def build_trend_chart(start: date, end: date) -> ft.Control:
        all_txns = state["transactions"]

        # Bucket the period into ~8 evenly-spaced windows — few enough
        # that x-axis date labels stay readable, many enough to show real
        # shape rather than a single flat segment.
        span_days = (end - start).days + 1
        bucket_count = min(8, max(span_days, 1))
        bucket_days = max(1, span_days // bucket_count)

        bucket_edges = []
        d = start
        while d <= end:
            bucket_edges.append(d)
            d += timedelta(days=bucket_days)
        if bucket_edges[-1] != end:
            bucket_edges.append(end)

        income_points, expense_points = [], []
        x_labels = []
        for i in range(len(bucket_edges)):
            b_start = start if i == 0 else bucket_edges[i - 1] + timedelta(days=1)
            b_end = bucket_edges[i]
            bucket_income = sum(t.amount for t in all_txns if t.is_income and b_start <= t.date <= b_end)
            bucket_expense = sum(t.amount for t in all_txns if not t.is_income and b_start <= t.date <= b_end)

            income_points.append(fch.LineChartDataPoint(
                x=i, y=bucket_income, show_tooltip=True,
                tooltip=fch.LineChartDataPointTooltip(
                    text=f"Income: {format_amount(bucket_income)}",
                    text_style=ft.TextStyle(size=10, color=Palette.INCOME, weight=ft.FontWeight.W_500),
                ),
            ))
            expense_points.append(fch.LineChartDataPoint(
                x=i, y=bucket_expense, show_tooltip=True,
                tooltip=fch.LineChartDataPointTooltip(
                    text=f"Expense: {format_amount(bucket_expense)}",
                    text_style=ft.TextStyle(size=10, color=Palette.EXPENSE, weight=ft.FontWeight.W_500),
                ),
            ))
            x_labels.append(fch.ChartAxisLabel(
                value=i, label=ft.Text(b_end.strftime("%b %d"), size=10, color=c["text_light"]),
            ))

        all_values = [p.y for p in income_points] + [p.y for p in expense_points]
        y_max = max(all_values) if all_values else 0
        # More headroom above the highest value than before — the
        # previous 1.2x multiplier put the top gridline/label close
        # enough to the container's top edge that it could clip.
        y_max = y_max * 1.35 if y_max > 0 else 100
        y_interval = y_max / 4

        y_labels = [
            fch.ChartAxisLabel(
                value=y_interval * i,
                label=ft.Text(_format_amount_short(y_interval * i), size=10, color=c["text_light"]),
            )
            for i in range(5)
        ]

        # With more than ~5 buckets, every-label crowds the x-axis —
        # thin them out by only labelling every other tick instead of
        # shrinking text further (already at a sensible minimum size).
        bottom_labels = x_labels if len(x_labels) <= 5 else [
            lbl for i, lbl in enumerate(x_labels) if i % 2 == 0
        ]

        chart = fch.LineChart(
            data_series=[
                fch.LineChartData(
                    points=income_points,
                    color=Palette.INCOME,
                    stroke_width=3,
                    curved=True,
                    below_line_bgcolor=ft.Colors.with_opacity(0.10, Palette.INCOME),
                    point=True,
                ),
                fch.LineChartData(
                    points=expense_points,
                    color=Palette.EXPENSE,
                    stroke_width=3,
                    curved=True,
                    below_line_bgcolor=ft.Colors.with_opacity(0.08, Palette.EXPENSE),
                    point=True,
                ),
            ],
            min_y=0, max_y=y_max,
            min_x=0, max_x=len(income_points) - 1,
            horizontal_grid_lines=fch.ChartGridLines(interval=y_interval, color=c["border"], width=1),
            border=ft.Border.all(0, "transparent"),
            left_axis=fch.ChartAxis(labels=y_labels, label_size=46),
            bottom_axis=fch.ChartAxis(labels=bottom_labels, label_size=28),
            tooltip=fch.LineChartTooltip(
                bgcolor=ft.Colors.with_opacity(0.92, c["neo_base"]),
                padding=ft.Padding.symmetric(vertical=4, horizontal=10),
                max_width=150,
                border_radius=8,
                fit_inside_horizontally=True,
                fit_inside_vertically=True,
            ),
            margin=ft.Margin(left=4, top=16, right=12, bottom=4),
            expand=True,
        )
        return ft.Container(content=chart, height=240, padding=ft.Padding(0, 8, 8, 0))

    def build_budget_chart(start: date, end: date) -> ft.Control:
        budgets = [b for b in state["budgets"] if b.monthly_limit > 0]
        if not budgets:
            return ft.Text("Set up budgets to see this chart.", size=13, color=c["text_light"])

        groups = []
        labels = []
        for i, b in enumerate(budgets):
            spent = sum(
                t.amount for t in state["transactions"]
                if not t.is_income and t.category == b.category
                and start <= t.date <= end
            )
            pct = spent / b.monthly_limit if b.monthly_limit else 0
            color = Palette.EXPENSE if pct > 1 else (Palette.ACCENT if pct >= 0.8 else Palette.INCOME)
            groups.append(
                fch.BarChartGroup(
                    x=i,
                    group_vertically=False,
                    spacing=4,
                    rods=[
                        fch.BarChartRod(
                            from_y=0, to_y=spent, width=16, color=color,
                            border_radius=ft.BorderRadius(4, 4, 0, 0),
                            tooltip=fch.BarChartRodTooltip(
                                text=f"{b.category}: spent {format_amount(spent)}"
                            ),
                        ),
                        fch.BarChartRod(
                            from_y=0, to_y=b.monthly_limit, width=16,
                            color=ft.Colors.with_opacity(0.25, c["text_light"]),
                            border_radius=ft.BorderRadius(4, 4, 0, 0),
                            tooltip=fch.BarChartRodTooltip(
                                text=f"{b.category}: limit {format_amount(b.monthly_limit)}"
                            ),
                        ),
                    ],
                )
            )
            labels.append(fch.ChartAxisLabel(value=i, label=ft.Text(icon_for(b.category), size=14)))

        max_val = max(max(b.monthly_limit, 1) for b in budgets) * 1.35
        y_interval = max_val / 4
        y_labels = [
            fch.ChartAxisLabel(
                value=y_interval * i,
                label=ft.Text(_format_amount_short(y_interval * i), size=10, color=c["text_light"]),
            )
            for i in range(5)
        ]

        chart = fch.BarChart(
            groups=groups,
            min_y=0, max_y=max_val,
            bottom_axis=fch.ChartAxis(labels=labels, label_size=26),
            left_axis=fch.ChartAxis(labels=y_labels, label_size=46),
            horizontal_grid_lines=fch.ChartGridLines(interval=y_interval, color=c["border"], width=1),
            border=ft.Border.all(0, "transparent"),
            tooltip=fch.BarChartTooltip(bgcolor=ft.Colors.with_opacity(0.92, c["neo_base"])),
            margin=ft.Margin(left=4, top=16, right=12, bottom=4),
            expand=True,
        )
        return ft.Container(content=chart, height=240, padding=ft.Padding(0, 8, 8, 0))

    def summary_row(label_text: str, value: float, color: str) -> ft.Row:
        sign = "+" if value >= 0 and label_text != "Opening Balance" else ""
        return ft.Row(
            [
                ft.Text(label_text, size=13, color=c["text_mid"]),
                ft.Text(f"{sign}{format_amount(value)}", size=13, weight=ft.FontWeight.BOLD, color=color),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def breakdown_row(cat: str, amount: float, pct: float, bar_color: str = Palette.PRIMARY) -> ft.Column:
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(f"{icon_for(cat)}  {cat}", size=13, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
                        ft.Text(f"{format_amount(amount)}  ({pct:.0f}%)", size=12, color=c["text_mid"]),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ProgressBar(
                    value=min(pct / 100, 1.0), bar_height=8, border_radius=4,
                    color=bar_color, bgcolor=c["border"],
                ),
            ],
            spacing=6,
        )

    def render():
        start, end, label = period_range()
        period_label.value = label

        is_custom = state["period"] == "Custom"
        custom_date_section.visible = is_custom
        if is_custom:
            start_date_text.value = _long_date_fmt(state["custom_start"])
            end_date_text.value = _long_date_fmt(state["custom_end"])

        transactions = state["transactions"]
        period_txns = [t for t in transactions if start <= t.date <= end]
        opening = sum((t.amount if t.is_income else -t.amount) for t in transactions if t.date < start)
        income = sum(t.amount for t in period_txns if t.is_income)
        expense = sum(t.amount for t in period_txns if not t.is_income)
        closing = opening + income - expense

        summary_card = glass_card(
            ft.Column(
                [
                    summary_row("Opening Balance", opening, c["text_dark"]),
                    summary_row("Income", income, Palette.INCOME),
                    summary_row("Expenses", -expense, Palette.EXPENSE),
                    ft.Divider(height=1, color=c["border"]),
                    summary_row("Closing Balance", closing, Palette.PRIMARY),
                ],
                spacing=14,
            ),
            padding=20,
        )

        def legend_dot(color: str, label: str) -> ft.Row:
            return ft.Row(
                [
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                    ft.Text(label, size=12, color=c["text_mid"]),
                ],
                spacing=6,
            )

        trend_card = glass_card(
            ft.Column(
                [
                    ft.Row(
                        [legend_dot(Palette.INCOME, "Income"), legend_dot(Palette.EXPENSE, "Expense")],
                        spacing=20,
                    ),
                    ft.Container(height=10),
                    build_trend_chart(start, end),
                ],
                spacing=0,
            ),
            padding=16,
        )

        expense_cat_totals: dict[str, float] = {}
        income_cat_totals: dict[str, float] = {}
        for t in period_txns:
            if not t.is_income:
                expense_cat_totals[t.category] = expense_cat_totals.get(t.category, 0) + t.amount
            else:
                income_cat_totals[t.category] = income_cat_totals.get(t.category, 0) + t.amount

        body_column.controls.clear()
        body_column.controls.extend([
            ft.Text("BALANCE SUMMARY", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
            summary_card,
            ft.Container(height=16),
            ft.Text("INCOME VS EXPENSE TREND", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
            trend_card,
            ft.Container(height=24),
            ft.Text("INCOME BREAKDOWN", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
        ])

        if not income_cat_totals:
            body_column.controls.append(
                ft.Text("No income in this period.", size=13, color=c["text_light"])
            )
        else:
            total_income = sum(income_cat_totals.values()) or 1
            sorted_income = sorted(income_cat_totals.items(), key=lambda x: -x[1])
            rows = []
            for cat, amount in sorted_income:
                rows.append(breakdown_row(cat, amount, amount / total_income * 100, Palette.INCOME))
            body_column.controls.append(
                glass_card(ft.Column(rows, spacing=18), padding=20)
            )

        body_column.controls.extend([
            ft.Container(height=24),
            ft.Text("EXPENSE BREAKDOWN", size=12, weight=ft.FontWeight.BOLD, color=c["text_mid"]),
            ft.Container(height=10),
        ])

        if not expense_cat_totals:
            body_column.controls.append(
                ft.Text("No expenses in this period.", size=13, color=c["text_light"])
            )
        else:
            total_expense = sum(expense_cat_totals.values()) or 1
            sorted_cats = sorted(expense_cat_totals.items(), key=lambda x: -x[1])
            rows = []
            for cat, amount in sorted_cats:
                rows.append(breakdown_row(cat, amount, amount / total_expense * 100))
            body_column.controls.append(
                glass_card(ft.Column(rows, spacing=18), padding=20)
            )

    def refresh():
        uid = FirebaseAuthService.get_uid()
        if not uid:
            return
        try:
            rows = SupabaseService.fetch_transactions(uid)
            state["transactions"] = [Transaction.from_row(r) for r in rows]
        except SupabaseError:
            state["transactions"] = []
        try:
            state["budgets"] = [Budget.from_row(r) for r in SupabaseService.fetch_budgets(uid)]
        except SupabaseError:
            state["budgets"] = []
        render()
        page.update()

    period_row = ft.Row([make_period_chip(n) for n in ["Monthly", "Quarterly", "Annually", "Custom"]], spacing=8)
    style_period_chip("Monthly")

    nav_row = ft.Row(
        [
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=prev_period, icon_color=c["text_mid"]),
            period_label,
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=next_period, icon_color=c["text_mid"]),
        ],
        spacing=0,
    )

    right_controls = ft.Container(content=nav_row)

    period_control_row = ft.Row(
        [period_row, right_controls],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    content = ft.ListView(
        [
            ft.Text("Reports", size=24, weight=ft.FontWeight.BOLD, color=c["text_dark"]),
            ft.Container(height=12),
            period_control_row,
            ft.Container(height=8),
            custom_date_section,
            ft.Container(height=8),
            body_column,
        ],
        # ListView (unlike Column) exposes clip_behavior, so we can turn off
        # the default hard-edge clip that was slicing off the hover-zoom on
        # the period chips (Monthly etc.) and the Start/End date buttons.
        clip_behavior=ft.ClipBehavior.NONE,
        scroll=ft.ScrollMode.AUTO,
        spacing=0, expand=True,
    )

    page.overlay.append(start_date_picker)
    page.overlay.append(end_date_picker)
    page.update()

    page_view = ft.Stack(
        controls=[mesh_background(), ft.Container(content=content, padding=48, expand=True, clip_behavior=ft.ClipBehavior.NONE)],
        expand=True,
    )
    page_view.refresh = refresh
    return page_view