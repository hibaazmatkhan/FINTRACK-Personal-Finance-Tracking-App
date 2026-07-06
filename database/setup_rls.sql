-- ════════════════════════════════════════════════════════════════
-- FinTrack — Supabase RLS + Firebase JWT Integration
-- ════════════════════════════════════════════════════════════════
-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor)
-- AFTER configuring Supabase to accept Firebase JWTs (see below).
--
-- STEP 1: Configure Firebase JWT in Supabase Dashboard
--   a) Go to Authentication → Settings → JWT Verification
--   b) Add a custom JWKS URL:
--      https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com
--   c) Set JWT Audience to your Firebase project ID: fintrack-c9347
--   d) Save
--
-- STEP 2: Run this SQL to enable RLS on all tables
-- ════════════════════════════════════════════════════════════════

-- Enable RLS on each table
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_categories ENABLE ROW LEVEL SECURITY;

-- Profiles: users can only read/update their own
CREATE POLICY "profiles_own" ON profiles
    FOR ALL
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Transactions: users can only CRUD their own
CREATE POLICY "transactions_own" ON transactions
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Budgets: users can only CRUD their own
CREATE POLICY "budgets_own" ON budgets
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Custom categories: users can only CRUD their own
CREATE POLICY "custom_categories_own" ON custom_categories
    FOR ALL
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
