-- 003_users.sql — User management with tiered access
-- Tiers: registered, pro, max, admin

-- ══════════════════════════════════════════════════════
-- 1. Users table
-- ══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.users (
    id          uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       text NOT NULL,
    tier        text NOT NULL DEFAULT 'registered'
                CHECK (tier IN ('registered', 'pro', 'max', 'admin')),
    ai_calls_today  integer NOT NULL DEFAULT 0,
    last_reset      date NOT NULL DEFAULT CURRENT_DATE,
    ai_credits      integer NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);

-- ══════════════════════════════════════════════════════
-- 2. Auto-create user row on signup (trigger)
-- ══════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (id, email)
    VALUES (NEW.id, NEW.email)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

-- Drop if exists to avoid duplicate trigger errors
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ══════════════════════════════════════════════════════
-- 3. RLS policies
-- ══════════════════════════════════════════════════════
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Users can read their own row
CREATE POLICY users_select_own ON public.users
    FOR SELECT USING (auth.uid() = id);

-- Users can update their own row (but tier is protected server-side)
CREATE POLICY users_update_own ON public.users
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Service role can do everything (for backend calls)
CREATE POLICY users_service_all ON public.users
    FOR ALL USING (auth.role() = 'service_role');

-- ══════════════════════════════════════════════════════
-- 4. increment_ai_calls RPC
-- ══════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.increment_ai_calls(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Reset counter if it's a new day
    UPDATE public.users
    SET ai_calls_today = CASE
            WHEN last_reset < CURRENT_DATE THEN 1
            ELSE ai_calls_today + 1
        END,
        last_reset = CURRENT_DATE
    WHERE id = p_user_id;
END;
$$;
