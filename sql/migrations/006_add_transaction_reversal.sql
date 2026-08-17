-- ============================================================
-- LedgerGuard: Transaction Reversal Relationship
-- Migration: 006
-- ============================================================

ALTER TABLE public.transactions
ADD COLUMN IF NOT EXISTS reversal_of_transaction_id UUID;

ALTER TABLE public.transactions
DROP CONSTRAINT IF EXISTS transactions_reversal_of_transaction_id_fkey;

ALTER TABLE public.transactions
ADD CONSTRAINT transactions_reversal_of_transaction_id_fkey
FOREIGN KEY (reversal_of_transaction_id)
REFERENCES public.transactions(id)
ON DELETE RESTRICT;

CREATE UNIQUE INDEX IF NOT EXISTS
transactions_one_reversal_per_transaction_idx
ON public.transactions(reversal_of_transaction_id)
WHERE reversal_of_transaction_id IS NOT NULL;