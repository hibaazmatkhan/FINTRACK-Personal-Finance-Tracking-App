"""Lightweight data models — thin wrappers around Supabase row dicts."""
from dataclasses import dataclass
from datetime import datetime, date

DEFAULT_INCOME_CATEGORIES = [
    "Salary", "Freelance", "Business", "Investment", "Gift", "Other",
]
DEFAULT_EXPENSE_CATEGORIES = [
    "Food", "Transport", "Shopping", "Bills", "Health",
    "Education", "Entertainment", "Rent", "Other",
]

DEFAULT_ICONS = {
    "Salary": "💼", "Freelance": "💻", "Business": "🏢",
    "Investment": "📈", "Gift": "🎁",
    "Food": "🍔", "Transport": "🚗", "Shopping": "🛍️",
    "Bills": "📄", "Health": "💊", "Education": "📚",
    "Entertainment": "🎮", "Rent": "🏠",
}

# Populated at runtime from the user's saved custom categories.
CUSTOM_ICONS: dict[str, str] = {}
# Tracks each custom category's type ("income"/"expense") so screens can
# filter correctly — CUSTOM_ICONS alone can't do this (it's just name ->
# emoji), which previously caused custom categories of either type to
# show up on both the income and expense tabs/pickers everywhere.
CUSTOM_CATEGORY_TYPES: dict[str, str] = {}

_loaded_for_uid: str | None = None


def icon_for(category: str) -> str:
    if category in CUSTOM_ICONS:
        return CUSTOM_ICONS[category]
    return DEFAULT_ICONS.get(category, "💰")


def custom_categories_for_type(category_type: str) -> list[str]:
    """Names of custom categories matching 'income' or 'expense'."""
    return [name for name, t in CUSTOM_CATEGORY_TYPES.items() if t == category_type]


def load_custom_categories(uid: str, force: bool = False) -> None:
    """Populates CUSTOM_ICONS / CUSTOM_CATEGORY_TYPES from Supabase.

    This used to only happen as a side effect of CategoriesPage.refresh()
    — meaning any custom category was invisible everywhere else (Add
    Transaction, Budgets) until you happened to visit the Categories
    page first in that session. Call this once at dashboard mount
    instead, so it's always loaded regardless of which page you open
    first. Cheap to call again (skips the network round-trip) unless
    the signed-in user changed or force=True.
    """
    global _loaded_for_uid
    if _loaded_for_uid == uid and not force:
        return
    from services.supabase_service import SupabaseService, SupabaseError
    try:
        rows = SupabaseService.fetch_custom_categories(uid)
    except SupabaseError:
        rows = []
    CUSTOM_ICONS.clear()
    CUSTOM_CATEGORY_TYPES.clear()
    for row in rows:
        cat = CustomCategory.from_row(row)
        CUSTOM_ICONS[cat.name] = cat.emoji
        CUSTOM_CATEGORY_TYPES[cat.name] = cat.type
    _loaded_for_uid = uid


@dataclass
class Transaction:
    id: str
    user_id: str
    type: str          # "income" | "expense"
    category: str
    amount: float
    description: str
    date: date
    created_at: datetime | None = None

    @property
    def is_income(self) -> bool:
        return self.type == "income"

    @classmethod
    def from_row(cls, row: dict) -> "Transaction":
        return cls(
            id=row.get("id") or "",
            user_id=row.get("user_id") or "",
            type=row.get("type") or "expense",
            category=row.get("category") or "",
            amount=float(row["amount"]) if row.get("amount") else 0.0,
            description=row.get("description") or "",
            date=date.fromisoformat(row["date"]) if row.get("date") else date.today(),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row.get("created_at") else None
            ),
        )


@dataclass
class CustomCategory:
    id: str
    user_id: str
    name: str
    emoji: str
    type: str  # "income" | "expense"

    @classmethod
    def from_row(cls, row: dict) -> "CustomCategory":
        return cls(
            id=row.get("id") or "", user_id=row.get("user_id") or "",
            name=row.get("name") or "", emoji=row.get("emoji") or "💰",
            type=row.get("type") or "expense",
        )


@dataclass
class Budget:
    id: str
    user_id: str
    category: str
    monthly_limit: float

    @classmethod
    def from_row(cls, row: dict) -> "Budget":
        return cls(
            id=row.get("id") or "", user_id=row.get("user_id") or "",
            category=row.get("category") or "",
            monthly_limit=float(row["monthly_limit"]) if row.get("monthly_limit") else 0.0,
        )
