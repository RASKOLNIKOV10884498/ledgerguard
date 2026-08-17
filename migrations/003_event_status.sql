ALTER TABLE public.transactions
ADD COLUMN IF NOT EXISTS event_status VARCHAR(20);