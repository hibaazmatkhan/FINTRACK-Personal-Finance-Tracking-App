<div align="center">
  <img src="app_icon.png" width="80" alt="FinTrack logo"/>
  <h1>FinTrack — Personal Finance Tracker</h1>
  <p>
    <strong>Desktop app</strong> · Python + Flet · Firebase Auth · Supabase
  </p>
</div>

---

## 🔹 For End Users — Just Use the App

**Download the latest installer from the [Releases](https://github.com/hibaazmatkhan/FINTRACK-Personal-Finance-Tracking-App/releases) page.**

- ✅ No Python, no command line, no setup
- ✅ Double-click and it runs
- ✅ **Pre-configured** with the app author's credentials (works immediately)

### First run

1. Launch FinTrack
2. **Sign up** with your email and password
3. Verify your email (check spam if not visible)
4. Sign in and start tracking!

### Features

| Screen | What you can do |
|---|---|
| **Home** | See your total balance, income, expenses, and recent transactions |
| **History** | Search, filter (All / Income / Expense), delete transactions |
| **Reports** | Monthly / Quarterly / Annual / Custom period summaries with charts |
| **Budgets** | Set monthly spending limits per category with progress bars |
| **Categories** | Add custom income/expense categories with emoji icons |
| **Settings** | Profile photo, username, change email/password, dark mode, currency |

### Currency support

Switch between PKR (₨), USD ($), EUR (€), GBP (£), INR (₹), AED (د.إ),
SAR (﷼), CAD (CA$) in **Settings → Currency**. Live exchange rates are
fetched automatically from the internet.

---

## 🔹 For Developers — Build from Source

### What you need

- **Python 3.10+**
- Your own **Firebase** project (free tier)
- Your own **Supabase** project (free tier)

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/FINTRACK-Personal-Finance-Tracking-App.git
cd FINTRACK-Personal-Finance-Tracking-App
pip install -r requirements.txt
```

### 2. Set up Firebase

1. Go to **[console.firebase.google.com](https://console.firebase.google.com)** and create a project.
2. **Authentication → Sign-in method** → enable **Email/Password**.
3. In **Project Settings → General**, copy your Web App's config values.

### 3. Set up Supabase

1. Go to **[supabase.com](https://supabase.com)** and create a project.
2. Open the **SQL Editor**, paste the entire contents of `database/schema.sql`, and click **Run**.
3. Go to **Project Settings → API** and copy your `Project URL` and `anon public key`.

### 4. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and paste in **your own** Firebase and Supabase values:

```bash
# Firebase (from Project Settings → General → Your apps → Web)
FIREBASE_API_KEY=your_firebase_api_key
FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_STORAGE_BUCKET=your_project.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your_sender_id
FIREBASE_APP_ID=your_app_id
FIREBASE_DATABASE_URL=https://your_project.firebaseio.com
FIREBASE_SERVICE_ACCOUNT_PATH=firebase_service_account.json

# Supabase (from Project Settings → API)
SUPABASE_URL=https://your_project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
```

> ⚠️ **Never commit `.env`** — it's already in `.gitignore`.

### 5. Run (development)

```bash
python main_flet.py
```

### 6. Build a standalone .exe

```bash
python scripts/build_exe.py
```

The output is at `dist/FinTrack/FinTrack.exe` — a self-contained folder
you can zip and share (no Python required on the target machine).

### 7. Build an installer (optional)

Install **[Inno Setup](https://jrsoftware.org/isdl.php)**, then
right-click `installer/FinTrack_Setup.iss` and choose **Compile**.

---

## 🔒 Security

### Will my API keys leak if I clone the repo?

**No.** The actual keys are stored in `.env`, which is in `.gitignore`.
The cloned repo contains **zero credentials**:

| File | Contains | Goes to GitHub? |
|---|---|---|
| `.env` | Your real Firebase & Supabase keys | ❌ Gitignored |
| `.env.example` | Placeholder values only | ✅ Safe to commit |
| `firebase_service_account.json` | Firebase Admin private key | ❌ Gitignored |
| `.fintrack_session.json` | Auth session tokens | ❌ Gitignored |
| `theme_settings.json` | Local preferences | ❌ Gitignored |
| All `.py` files in `src/` | Code only (uses `os.getenv()`) | ✅ Safe to commit |

### The pre-built .exe has keys inside it?

**Yes.** The published `.exe` on the Releases page contains the author's
Firebase API key and Supabase anon key. This is **normal** — every
mobile app, web app, and desktop app bundles the same kind of
client-safe keys. Server-side security controls access:

- **Firebase Auth** handles authentication (sign-in, password, email)
- **Supabase Row Level Security (RLS)** is available via `database/setup_rls.sql` for additional data isolation

### If I fork this repo

1. `.env` and `firebase_service_account.json` are already gitignored.
2. **Create your own Firebase and Supabase projects.** The original
   author's credentials won't work for your fork.
3. Build your own `.exe` with `python scripts/build_exe.py` — it will
   bundle **your** credentials from your `.env`.

---

## 📁 Project structure

```
FinTrack/
├── main_flet.py                       # Entry point — just run it
├── src/                               # All source code
│   ├── models/
│   │   └── data_models.py             # Transaction, Budget, CustomCategory
│   ├── services/
│   │   ├── connectivity.py            # Internet reachability monitor
│   │   ├── firebase_auth.py           # Firebase auth operations
│   │   └── supabase_service.py        # Supabase database operations
│   └── ui_flet/
│       ├── theme.py                   # Theme, animations, currency
│       ├── login_screen.py
│       ├── register_screen.py
│       ├── dashboard_screen.py
│       ├── home_page.py
│       ├── history_page.py
│       ├── reports_page.py
│       ├── budgets_page.py
│       ├── categories_page.py
│       ├── settings_page.py
│       └── add_transaction_dialog.py
├── scripts/
│   └── build_exe.py                   # PyInstaller build script
├── database/
│   ├── schema.sql                     # Complete Supabase schema
│   └── setup_rls.sql                  # Optional RLS policies for Firebase JWT
├── installer/
│   └── FinTrack_Setup.iss             # Inno Setup installer script
├── .env.example                       # Placeholder credentials template
├── .gitignore
├── requirements.txt
├── app_icon.ico / .png
├── README.md
└── RELEASE_NOTES.txt                  # Info for end users who find the .exe
```

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| GUI framework | **Flet** (Flutter-powered Python) |
| Authentication | **Firebase Auth** (email/password) |
| Database | **Supabase** (PostgreSQL) |
| Charts | **flet-charts** |
| Currency rates | **open.er-api.com** (free, no key needed) |
| Icons | Emoji via system font |
| Packaging | **PyInstaller** → **Inno Setup** |

## 📚 Course

**Object-Oriented Programming** — 2nd Semester project.
