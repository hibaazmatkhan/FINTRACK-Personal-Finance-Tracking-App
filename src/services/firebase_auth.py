"""
Firebase authentication service.
Handles: email/password signup & login, password reset emails,
email change, phone number linking, and session/token management.
"""
import os
import sys
import json
import requests
import pyrebase
import firebase_admin
from firebase_admin import auth as admin_auth, credentials as admin_creds
from pathlib import Path
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    _dotenv_path = Path(sys._MEIPASS) / ".env"
else:
    _dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_dotenv_path)

FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL", ""),
}

_firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
_auth = _firebase.auth()

API_KEY = FIREBASE_CONFIG["apiKey"]
IDENTITY_BASE = "https://identitytoolkit.googleapis.com/v1"

# ── Firebase Admin SDK (lazy init) ──────────────────────────
_admin_app = None

def _get_admin_app():
    global _admin_app
    if _admin_app is not None:
        return _admin_app
    try:
        sa_rel = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase_service_account.json")
        if getattr(sys, 'frozen', False):
            sa_path = Path(sys._MEIPASS) / sa_rel
        else:
            sa_path = Path(__file__).resolve().parent.parent.parent / sa_rel
        if not sa_path.exists():
            return None
        cred = admin_creds.Certificate(str(sa_path))
        _admin_app = firebase_admin.initialize_app(cred)
        return _admin_app
    except Exception:
        return None


class AuthError(Exception):
    """Raised with a human-readable message for any auth failure."""
    pass


def _friendly_error(raw: str) -> str:
    """Translate Firebase's error codes into readable messages."""
    mapping = {
        "EMAIL_EXISTS": "An account with this email already exists.",
        "EMAIL_NOT_FOUND": "No account found with this email.",
        "INVALID_PASSWORD": "Incorrect password. Please try again.",
        "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password.",
        "USER_DISABLED": "This account has been disabled.",
        "WEAK_PASSWORD": "Password must be at least 6 characters.",
        "INVALID_EMAIL": "Please enter a valid email address.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please wait and try again.",
        "CREDENTIAL_TOO_OLD_LOGIN_AGAIN": "Please log in again to continue.",
    }
    for code, msg in mapping.items():
        if code in raw:
            return msg
    return "Something went wrong. Please try again."


class FirebaseAuthService:
    """All authentication operations go through this class."""

    current_user: dict | None = None  # {'idToken','refreshToken','localId','email',...}

    @staticmethod
    def _ensure_fresh_token():
        """Refresh the Firebase idToken if we have a current session — called before
        any operation that sends the idToken to Firebase's REST API."""
        user = FirebaseAuthService.current_user
        if not user:
            return
        try:
            refreshed = _auth.refresh(user["refreshToken"])
            user.update(refreshed)
        except Exception:
            pass  # will get a real AuthError when the idToken is used

    # ── Email / Password ───────────────────────────────────

    @staticmethod
    def sign_up(email: str, password: str) -> dict:
        try:
            user = _auth.create_user_with_email_and_password(email, password)
            FirebaseAuthService.current_user = user
            return user
        except Exception as e:
            raise AuthError(_friendly_error(str(e)))

    @staticmethod
    def sign_in(email: str, password: str) -> dict:
        try:
            user = _auth.sign_in_with_email_and_password(email, password)
            FirebaseAuthService.current_user = user
            return user
        except Exception as e:
            raise AuthError(_friendly_error(str(e)))

    @staticmethod
    def send_password_reset(email: str):
        try:
            _auth.send_password_reset_email(email)
        except Exception as e:
            raise AuthError(_friendly_error(str(e)))

    @staticmethod
    def change_password(new_password: str):
        """Requires current_user to hold a valid idToken."""
        FirebaseAuthService._ensure_fresh_token()
        user = FirebaseAuthService.current_user
        if not user:
            raise AuthError("You must be signed in to change your password.")
        try:
            url = f"{IDENTITY_BASE}/accounts:update?key={API_KEY}"
            resp = requests.post(url, json={
                "idToken": user["idToken"],
                "password": new_password,
                "returnSecureToken": True,
            })
            data = resp.json()
            if "error" in data:
                raise AuthError(_friendly_error(json.dumps(data["error"])))
            FirebaseAuthService.current_user.update(data)
        except AuthError:
            raise
        except Exception:
            raise AuthError("Could not update password. Please try again.")

    @staticmethod
    def reauthenticate(email: str, current_password: str) -> bool:
        """Verify the current password before sensitive changes.

        Used to swallow every exception and just return False, so a
        real, specific failure (rate-limited after a few attempts,
        network error, etc.) looked identical to 'wrong password' —
        actively misleading, especially right after a password-reset
        email where the person may be unsure which password is
        current. Now raises AuthError with the real, friendly message;
        only an actual incorrect-password response is treated as a
        plain False so callers can show their own "incorrect" copy.
        """
        try:
            _auth.sign_in_with_email_and_password(email, current_password)
            return True
        except Exception as e:
            msg = str(e)
            if "INVALID_PASSWORD" in msg or "INVALID_LOGIN_CREDENTIALS" in msg:
                return False
            raise AuthError(_friendly_error(msg))

    @staticmethod
    def check_email_exists(email: str) -> bool:
        """Check if an email is already registered with Firebase.
        Uses the Firebase Admin SDK when available (most reliable);
        falls back to the signInWithPassword API otherwise."""
        app = _get_admin_app()
        if app is not None:
            try:
                admin_auth.get_user_by_email(email)
                return True
            except firebase_admin.auth.UserNotFoundError:
                return False
            except Exception:
                pass
        try:
            url = f"{IDENTITY_BASE}/accounts:signInWithPassword?key={API_KEY}"
            resp = requests.post(url, json={
                "email": email,
                "password": "___check_email_dummy___",
                "returnSecureToken": False,
            })
            data = resp.json()
            error_msg = data.get("error", {}).get("message", "")
            if "EMAIL_NOT_FOUND" in error_msg:
                return False
            return True
        except Exception:
            return False

    # ── Email change ────────────────────────────────────────

    @staticmethod
    def update_email(new_email: str):
        """Sends a 'verify your new email' link rather than changing
        the email immediately. The direct accounts:update email-change
        call is rejected outright (auth/operation-not-allowed —
        'Please verify the new email before changing email.') on any
        project with email enumeration protection on, which is the
        default for newer Firebase projects — this is the only
        approach that actually works on this project. The email
        address only actually changes once the person clicks the link
        sent to the NEW address; current_user/email here intentionally
        stays as the old address until then.
        """
        FirebaseAuthService._ensure_fresh_token()
        user = FirebaseAuthService.current_user
        if not user:
            raise AuthError("You must be signed in to change your email.")
        try:
            url = f"{IDENTITY_BASE}/accounts:sendOobCode?key={API_KEY}"
            resp = requests.post(url, json={
                "requestType": "VERIFY_AND_CHANGE_EMAIL",
                "idToken": user["idToken"],
                "newEmail": new_email,
            })
            data = resp.json()
            if "error" in data:
                raise AuthError(_friendly_error(json.dumps(data["error"])))
        except AuthError:
            raise
        except Exception:
            raise AuthError("Could not send the verification email. Please try again.")

    @staticmethod
    def send_email_verification():
        FirebaseAuthService._ensure_fresh_token()
        user = FirebaseAuthService.current_user
        if not user:
            raise AuthError("You must be signed in.")
        try:
            _auth.send_email_verification(user["idToken"])
        except Exception as e:
            raise AuthError(_friendly_error(str(e)))

    # ── Account deletion ──────────────────────────────────────

    @staticmethod
    def delete_account():
        """Deletes the Firebase Auth account itself. This is a
        'sensitive' operation — Firebase requires a fresh
        reauthenticate() call (not just any signed-in session) right
        before this, or it fails with CREDENTIAL_TOO_OLD_LOGIN_AGAIN.
        Callers are responsible for wiping Supabase data first, since
        once this succeeds the idToken used to identify "whose data"
        is gone.
        """
        FirebaseAuthService._ensure_fresh_token()
        user = FirebaseAuthService.current_user
        if not user:
            raise AuthError("You must be signed in to delete your account.")
        try:
            _auth.delete_user_account(user["idToken"])
            FirebaseAuthService.current_user = None
        except AuthError:
            raise
        except Exception as e:
            raise AuthError(_friendly_error(str(e)))

    # ── Session ──────────────────────────────────────────────

    @staticmethod
    def get_account_info() -> dict:
        FirebaseAuthService._ensure_fresh_token()
        user = FirebaseAuthService.current_user
        if not user:
            raise AuthError("Not signed in.")
        try:
            url = f"{IDENTITY_BASE}/accounts:lookup?key={API_KEY}"
            resp = requests.post(url, json={"idToken": user["idToken"]})
            data = resp.json()
            if "error" in data:
                raise AuthError(_friendly_error(json.dumps(data["error"])))
            return data["users"][0]
        except AuthError:
            raise
        except Exception:
            raise AuthError("Could not fetch account info.")

    @staticmethod
    def is_email_verified() -> bool:
        """Re-checks verification status directly with Firebase (not
        from a cached/stale value) — needed for the
        register -> verify -> re-login -> check -> dashboard flow."""
        try:
            info = FirebaseAuthService.get_account_info()
            return bool(info.get("emailVerified"))
        except AuthError:
            return False

    @staticmethod
    def refresh_session():
        user = FirebaseAuthService.current_user
        if not user:
            return
        try:
            refreshed = _auth.refresh(user["refreshToken"])
            FirebaseAuthService.current_user.update(refreshed)
        except Exception:
            pass

    @staticmethod
    def sign_out():
        FirebaseAuthService.current_user = None

    @staticmethod
    def is_logged_in() -> bool:
        return FirebaseAuthService.current_user is not None

    @staticmethod
    def get_id_token() -> str | None:
        FirebaseAuthService._ensure_fresh_token()
        user = FirebaseAuthService.current_user
        return user.get("idToken") if user else None

    @staticmethod
    def get_uid() -> str | None:
        user = FirebaseAuthService.current_user
        return user.get("localId") if user else None

    @staticmethod
    def get_email() -> str | None:
        user = FirebaseAuthService.current_user
        return user.get("email") if user else None
