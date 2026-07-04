"""
Supabase data service.
Handles all app data: transactions, budgets, custom categories,
and user profile (username, avatar). Auth identity comes from Firebase;
the Firebase UID is used as the user_id key across all Supabase tables.
"""
import os
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


class SupabaseError(Exception):
    pass


class SupabaseService:

    # ── Profile ───────────────────────────────────────────

    @staticmethod
    def get_profile(uid: str) -> dict:
        try:
            res = _client.table("profiles").select("*").eq("id", uid).single().execute()
            return res.data or {}
        except Exception:
            return {}

    @staticmethod
    def upsert_profile(uid: str, username: str = None, avatar_url: str = None):
        try:
            payload = {"id": uid}
            if username is not None:
                payload["username"] = username
            if avatar_url is not None:
                payload["avatar_url"] = avatar_url
            _client.table("profiles").upsert(payload).execute()
        except Exception as e:
            raise SupabaseError(f"Could not save profile: {e}")

    @staticmethod
    def upload_avatar(uid: str, file_bytes: bytes, file_ext: str = "jpg") -> str:
        path = f"{uid}/avatar.{file_ext}"
        try:
            _client.storage.from_("avatars").upload(
                path, file_bytes,
                file_options={"content-type": f"image/{file_ext}", "upsert": "true"},
            )
        except Exception as e:
            msg = str(e)
            if "row-level security" in msg or "Unauthorized" in msg or "403" in msg:
                raise SupabaseError(
                    "Photo upload was blocked by Supabase storage permissions. "
                    "Run setup_avatars_bucket.sql in your Supabase SQL Editor "
                    "to create the avatars bucket and allow uploads, then try again."
                )
            raise SupabaseError(f"Could not upload photo: {e}")
        try:
            return _client.storage.from_("avatars").get_public_url(path)
        except Exception as e:
            raise SupabaseError(f"Photo uploaded but could not get public URL: {e}")

    @staticmethod
    def delete_all_user_data(uid: str):
        """Wipes every row tied to this user across every table, plus
        their avatar file — everything in Supabase that
        delete_account() in Settings promises to remove. Best-effort
        per step: one table failing to delete (e.g. already empty,
        or a transient error) shouldn't block clearing the rest, since
        the overall goal is "delete everything that exists", not "fail
        the whole operation if any one piece was already gone."
        """
        for table in ("transactions", "budgets", "custom_categories"):
            try:
                _client.table(table).delete().eq("user_id", uid).execute()
            except Exception:
                pass

        try:
            files = _client.storage.from_("avatars").list(uid)
            if files:
                paths = [f"{uid}/{f['name']}" for f in files]
                _client.storage.from_("avatars").remove(paths)
        except Exception:
            pass

        try:
            _client.table("profiles").delete().eq("id", uid).execute()
        except Exception:
            pass

    # ── Transactions ──────────────────────────────────────

    @staticmethod
    def fetch_transactions(uid: str, limit: int = None, offset: int = 0) -> list[dict]:
        try:
            query = (
                _client.table("transactions")
                .select("*")
                .eq("user_id", uid)
                .order("date", desc=True)
            )
            if limit is not None:
                query = query.range(offset, offset + limit - 1)
            res = query.execute()
            return res.data or []
        except Exception as e:
            raise SupabaseError(f"Could not fetch transactions: {e}")

    @staticmethod
    def add_transaction(uid: str, type_: str, category: str, amount: float,
                         description: str, txn_date: date) -> dict:
        try:
            payload = {
                "user_id": uid,
                "type": type_,
                "category": category,
                "amount": amount,
                "description": description,
                "date": txn_date.isoformat(),
            }
            res = _client.table("transactions").insert(payload).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            raise SupabaseError(f"Could not save transaction: {e}")

    @staticmethod
    def delete_transaction(txn_id: str):
        try:
            _client.table("transactions").delete().eq("id", txn_id).execute()
        except Exception as e:
            raise SupabaseError(f"Could not delete transaction: {e}")

    # ── Custom Categories ─────────────────────────────────

    # ── Currency ───────────────────────────────────────────

    @staticmethod
    def update_profile_currency(uid: str, currency: str):
        try:
            payload = {"id": uid, "currency": currency}
            _client.table("profiles").upsert(payload).execute()
        except Exception as e:
            raise SupabaseError(f"Could not update currency: {e}")

    @staticmethod
    def convert_all_user_data(uid: str, rate: float):
        """Divides all stored amounts by `rate` to convert from the old
        currency to a new one. Updates transactions, budgets, and profile
        in a single batch (Supabase doesn't have multi-statement
        transactions for SQL over REST, so we execute sequentially and
        accept partial-failure risk — the app data is never critical
        enough to warrant a two-phase commit)."""
        if rate <= 0:
            raise SupabaseError("Conversion rate must be positive.")
        errors = []
        try:
            txns = _client.table("transactions").select("id,amount").eq("user_id", uid).execute()
            for row in (txns.data or []):
                new_amt = round(float(row["amount"]) / rate, 2)
                _client.table("transactions").update({"amount": new_amt}).eq("id", row["id"]).execute()
        except Exception as e:
            errors.append(f"transactions: {e}")
        try:
            budgets = _client.table("budgets").select("id,monthly_limit").eq("user_id", uid).execute()
            for row in (budgets.data or []):
                new_lim = round(float(row["monthly_limit"]) / rate, 2)
                _client.table("budgets").update({"monthly_limit": new_lim}).eq("id", row["id"]).execute()
        except Exception as e:
            errors.append(f"budgets: {e}")
        if errors:
            raise SupabaseError("Currency conversion completed with errors: " + "; ".join(errors))

    # ── Custom Categories ─────────────────────────────────

    @staticmethod
    def fetch_custom_categories(uid: str) -> list[dict]:
        try:
            res = (
                _client.table("custom_categories")
                .select("*")
                .eq("user_id", uid)
                .order("created_at")
                .execute()
            )
            return res.data or []
        except Exception as e:
            raise SupabaseError(f"Could not fetch categories: {e}")

    @staticmethod
    def add_custom_category(uid: str, name: str, emoji: str, type_: str) -> dict:
        try:
            payload = {"user_id": uid, "name": name, "emoji": emoji, "type": type_}
            res = _client.table("custom_categories").insert(payload).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            raise SupabaseError(f"Could not save category: {e}")

    @staticmethod
    def delete_custom_category(cat_id: str):
        try:
            _client.table("custom_categories").delete().eq("id", cat_id).execute()
        except Exception as e:
            raise SupabaseError(f"Could not delete category: {e}")

    # ── Budgets ────────────────────────────────────────────

    @staticmethod
    def fetch_budgets(uid: str) -> list[dict]:
        try:
            res = _client.table("budgets").select("*").eq("user_id", uid).execute()
            return res.data or []
        except Exception as e:
            raise SupabaseError(f"Could not fetch budgets: {e}")

    @staticmethod
    def upsert_budget(uid: str, category: str, monthly_limit: float):
        try:
            payload = {
                "user_id": uid,
                "category": category,
                "monthly_limit": monthly_limit,
                "updated_at": datetime.now().isoformat(),
            }
            _client.table("budgets").upsert(payload, on_conflict="user_id,category").execute()
        except Exception as e:
            raise SupabaseError(f"Could not save budget: {e}")

    @staticmethod
    def delete_budget(budget_id: str):
        try:
            _client.table("budgets").delete().eq("id", budget_id).execute()
        except Exception as e:
            raise SupabaseError(f"Could not delete budget: {e}")
