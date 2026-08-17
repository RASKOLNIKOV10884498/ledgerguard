-- ============================================================
-- SUPABASE / POSTGRES DOUBLE-ENTRY ACCOUNTING LEDGER
-- ============================================================

-- ============================================================
-- 0. EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ============================================================
-- 1. CHART OF ACCOUNTS
-- ============================================================

CREATE TABLE IF NOT EXISTS public.accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    name VARCHAR(255) NOT NULL UNIQUE,

    type VARCHAR(50) NOT NULL
        CHECK (
            type IN (
                'ASSET',
                'LIABILITY',
                'EQUITY',
                'REVENUE',
                'EXPENSE'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 2. TRANSACTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    description TEXT NOT NULL,

    reference_id VARCHAR(255) UNIQUE,

    /*
       Idempotency key prevents the same transaction
       from accidentally being posted twice.
    */
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,

    /*
       Hash of the original request.

       This prevents someone from doing:

       idempotency_key = ABC
       transaction = $100

       and later:

       idempotency_key = ABC
       transaction = $10,000
    */
    request_hash TEXT NOT NULL,

    /*
       For this architecture, transactions are immutable
       once inserted.

       POSTED is the normal state.

       VOID should not be achieved by UPDATE.
       A reversal transaction should be created instead.
    */
    status VARCHAR(50) NOT NULL DEFAULT 'POSTED'
        CHECK (
            status IN (
                'POSTED',
                'VOID'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 3. LEDGER ENTRIES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    transaction_id UUID NOT NULL
        REFERENCES public.transactions(id)
        ON DELETE RESTRICT,

    account_id UUID NOT NULL
        REFERENCES public.accounts(id)
        ON DELETE RESTRICT,

    /*
       Never store negative money values.
       Direction determines whether money is debited
       or credited.
    */
    amount NUMERIC(19,4) NOT NULL
        CHECK (amount > 0),

    direction VARCHAR(10) NOT NULL
        CHECK (
            direction IN (
                'DEBIT',
                'CREDIT'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 4. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_entries_transaction_id
    ON public.entries(transaction_id);

CREATE INDEX IF NOT EXISTS idx_entries_account_id
    ON public.entries(account_id);

CREATE INDEX IF NOT EXISTS idx_entries_created_at
    ON public.entries(created_at);

CREATE INDEX IF NOT EXISTS idx_transactions_created_at
    ON public.transactions(created_at);

CREATE INDEX IF NOT EXISTS idx_transactions_status
    ON public.transactions(status);

CREATE INDEX IF NOT EXISTS idx_transactions_reference_id
    ON public.transactions(reference_id);


-- ============================================================
-- 5. BALANCE VALIDATION
--
-- Every transaction must have:
--
--      SUM(DEBITS) = SUM(CREDITS)
--
-- The trigger is deferred until transaction commit.
-- This is important because a transaction may contain
-- multiple ledger entries.
-- ============================================================

CREATE OR REPLACE FUNCTION public.verify_transaction_balance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_net_sum NUMERIC(19,4);
    v_entry_count INTEGER;
BEGIN

    SELECT
        COUNT(*),
        COALESCE(
            SUM(
                CASE
                    WHEN direction = 'DEBIT'
                        THEN amount
                    ELSE
                        -amount
                END
            ),
            0
        )
    INTO
        v_entry_count,
        v_net_sum
    FROM public.entries
    WHERE transaction_id = NEW.transaction_id;


    /*
       A transaction must have at least two ledger entries.
    */
    IF v_entry_count < 2 THEN

        RAISE EXCEPTION
            'INVARIANT VIOLATION: Transaction % must contain at least two ledger entries.',
            NEW.transaction_id;

    END IF;


    /*
       Debit total must equal credit total.
    */
    IF v_net_sum <> 0 THEN

        RAISE EXCEPTION
            'INVARIANT VIOLATION: Transaction % is unbalanced. Net sum is %. Total debits must equal total credits.',
            NEW.transaction_id,
            v_net_sum;

    END IF;


    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS check_ledger_balance_constraint
ON public.entries;


CREATE CONSTRAINT TRIGGER check_ledger_balance_constraint
AFTER INSERT OR UPDATE ON public.entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION public.verify_transaction_balance();


-- ============================================================
-- 6. IMMUTABILITY
--
-- Once financial records exist:
--
-- UPDATE = prohibited
-- DELETE = prohibited
--
-- Corrections should be performed using reversal transactions.
-- ============================================================

CREATE OR REPLACE FUNCTION public.enforce_ledger_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    RAISE EXCEPTION
        'SECURITY VIOLATION: Ledger records are immutable. UPDATE and DELETE operations are permanently prohibited. Create a reversal transaction instead.';

END;
$$;


DROP TRIGGER IF EXISTS block_transaction_tampering
ON public.transactions;


CREATE TRIGGER block_transaction_tampering
BEFORE UPDATE OR DELETE
ON public.transactions
FOR EACH ROW
EXECUTE FUNCTION public.enforce_ledger_immutability();


DROP TRIGGER IF EXISTS block_entry_tampering
ON public.entries;


CREATE TRIGGER block_entry_tampering
BEFORE UPDATE OR DELETE
ON public.entries
FOR EACH ROW
EXECUTE FUNCTION public.enforce_ledger_immutability();


-- ============================================================
-- 7. PREVENT INSERTING ENTRIES INTO VOID TRANSACTIONS
-- ============================================================

CREATE OR REPLACE FUNCTION public.validate_entry_transaction()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_status VARCHAR(50);
BEGIN

    SELECT status
    INTO v_status
    FROM public.transactions
    WHERE id = NEW.transaction_id
    FOR SHARE;


    IF v_status IS NULL THEN

        RAISE EXCEPTION
            'Transaction % does not exist.',
            NEW.transaction_id;

    END IF;


    IF v_status <> 'POSTED' THEN

        RAISE EXCEPTION
            'Cannot add ledger entries to transaction % because its status is %.',
            NEW.transaction_id,
            v_status;

    END IF;


    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS validate_entry_transaction_trigger
ON public.entries;


CREATE TRIGGER validate_entry_transaction_trigger
BEFORE INSERT
ON public.entries
FOR EACH ROW
EXECUTE FUNCTION public.validate_entry_transaction();


-- ============================================================
-- 8. POST TRANSACTION RPC
--
-- This is the ONLY intended way for the application
-- to create a financial transaction.
--
-- The application supplies:
--
-- description
-- idempotency key
-- optional reference
-- entries
--
-- Example entries JSON:
--
-- [
--   {
--     "account_id": "...",
--     "amount": 100.00,
--     "direction": "DEBIT"
--   },
--   {
--     "account_id": "...",
--     "amount": 100.00,
--     "direction": "CREDIT"
--   }
-- ]
--
-- Everything happens atomically.
-- ============================================================

CREATE OR REPLACE FUNCTION public.post_transaction(
    p_description TEXT,
    p_idempotency_key VARCHAR(255),
    p_entries JSONB,
    p_reference_id VARCHAR(255) DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE

    v_transaction_id UUID;

    v_existing_hash TEXT;

    v_request_hash TEXT;

    v_entry JSONB;

    v_account_id UUID;

    v_amount NUMERIC(19,4);

    v_direction VARCHAR(10);

    v_entry_count INTEGER;

    v_debit_total NUMERIC(19,4);

    v_credit_total NUMERIC(19,4);

BEGIN

    -- ========================================================
    -- BASIC VALIDATION
    -- ========================================================

    IF p_description IS NULL
       OR LENGTH(TRIM(p_description)) = 0 THEN

        RAISE EXCEPTION
            'Transaction description cannot be empty.';

    END IF;


    IF p_idempotency_key IS NULL
       OR LENGTH(TRIM(p_idempotency_key)) = 0 THEN

        RAISE EXCEPTION
            'Idempotency key cannot be empty.';

    END IF;


    IF p_entries IS NULL
       OR jsonb_typeof(p_entries) <> 'array' THEN

        RAISE EXCEPTION
            'Entries must be a JSON array.';

    END IF;


    -- ========================================================
    -- REQUIRE AT LEAST TWO ENTRIES
    -- ========================================================

    SELECT COUNT(*)
    INTO v_entry_count
    FROM jsonb_array_elements(p_entries);


    IF v_entry_count < 2 THEN

        RAISE EXCEPTION
            'A double-entry transaction requires at least two entries.';

    END IF;


    -- ========================================================
    -- REQUEST HASH
    --
    -- JSONB normalizes object key ordering, which makes this
    -- suitable for detecting reuse of an idempotency key
    -- with different transaction data.
    -- ========================================================

    v_request_hash :=
        encode(
            digest(
                convert_to(
                    COALESCE(p_description, '')
                    || '|'
                    || COALESCE(p_reference_id, '')
                    || '|'
                    || p_entries::TEXT,
                    'UTF8'
                ),
                'SHA256'
            ),
            'HEX'
        );


    -- ========================================================
    -- IDEMPOTENCY CHECK
    -- ========================================================

    SELECT
        id,
        request_hash
    INTO
        v_transaction_id,
        v_existing_hash
    FROM public.transactions
    WHERE idempotency_key = p_idempotency_key
    FOR SHARE;


    IF v_transaction_id IS NOT NULL THEN

        /*
           Same idempotency key + same request
           = safely return original transaction.
        */
        IF v_existing_hash = v_request_hash THEN

            RETURN v_transaction_id;

        END IF;


        /*
           Same idempotency key + different request
           = security/data integrity violation.
        */
        RAISE EXCEPTION
            'IDEMPOTENCY VIOLATION: Idempotency key % has already been used with different transaction data.',
            p_idempotency_key;

    END IF;


    -- ========================================================
    -- VALIDATE EACH ENTRY
    -- ========================================================

    FOR v_entry IN
        SELECT value
        FROM jsonb_array_elements(p_entries)
    LOOP

        BEGIN

            v_account_id :=
                (v_entry ->> 'account_id')::UUID;

        EXCEPTION
            WHEN invalid_text_representation THEN

                RAISE EXCEPTION
                    'Invalid account_id in ledger entry.';

        END;


        BEGIN

            v_amount :=
                (v_entry ->> 'amount')::NUMERIC(19,4);

        EXCEPTION
            WHEN invalid_text_representation THEN

                RAISE EXCEPTION
                    'Invalid amount in ledger entry.';

        END;


        v_direction :=
            UPPER(v_entry ->> 'direction');


        IF v_amount IS NULL OR v_amount <= 0 THEN

            RAISE EXCEPTION
                'Ledger entry amount must be greater than zero.';

        END IF;


        IF v_direction NOT IN ('DEBIT', 'CREDIT') THEN

            RAISE EXCEPTION
                'Ledger entry direction must be DEBIT or CREDIT.';

        END IF;


        IF NOT EXISTS (
            SELECT 1
            FROM public.accounts
            WHERE id = v_account_id
        ) THEN

            RAISE EXCEPTION
                'Account % does not exist.',
                v_account_id;

        END IF;

    END LOOP;


    -- ========================================================
    -- CALCULATE TOTALS
    -- ========================================================

    SELECT
        COALESCE(
            SUM(
                CASE
                    WHEN UPPER(value ->> 'direction') = 'DEBIT'
                        THEN (value ->> 'amount')::NUMERIC(19,4)
                    ELSE 0
                END
            ),
            0
        ),

        COALESCE(
            SUM(
                CASE
                    WHEN UPPER(value ->> 'direction') = 'CREDIT'
                        THEN (value ->> 'amount')::NUMERIC(19,4)
                    ELSE 0
                END
            ),
            0
        )

    INTO
        v_debit_total,
        v_credit_total

    FROM jsonb_array_elements(p_entries);


    -- ========================================================
    -- ENFORCE DOUBLE ENTRY
    -- ========================================================

    IF v_debit_total <> v_credit_total THEN

        RAISE EXCEPTION
            'UNBALANCED TRANSACTION: Debits = %, Credits = %.',
            v_debit_total,
            v_credit_total;

    END IF;


    -- ========================================================
    -- CREATE TRANSACTION
    -- ========================================================

    INSERT INTO public.transactions (
        description,
        reference_id,
        idempotency_key,
        request_hash,
        status
    )
    VALUES (
        p_description,
        p_reference_id,
        p_idempotency_key,
        v_request_hash,
        'POSTED'
    )
    RETURNING id
    INTO v_transaction_id;


    -- ========================================================
    -- CREATE LEDGER ENTRIES
    -- ========================================================

    FOR v_entry IN
        SELECT value
        FROM jsonb_array_elements(p_entries)
    LOOP

        INSERT INTO public.entries (
            transaction_id,
            account_id,
            amount,
            direction
        )
        VALUES (
            v_transaction_id,
            (v_entry ->> 'account_id')::UUID,
            (v_entry ->> 'amount')::NUMERIC(19,4),
            UPPER(v_entry ->> 'direction')
        );

    END LOOP;


    -- ========================================================
    -- RETURN TRANSACTION ID
    -- ========================================================

    RETURN v_transaction_id;

END;
$$;


-- ============================================================
-- 9. RLS
-- ============================================================

ALTER TABLE public.accounts
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.transactions
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.entries
ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 10. READ POLICIES
--
-- Users can read ledger information.
--
-- Writes are intentionally NOT exposed through normal
-- Supabase table operations.
-- ============================================================

DROP POLICY IF EXISTS "Authenticated users can read accounts"
ON public.accounts;


CREATE POLICY "Authenticated users can read accounts"
ON public.accounts
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS "Authenticated users can read transactions"
ON public.transactions;


CREATE POLICY "Authenticated users can read transactions"
ON public.transactions
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS "Authenticated users can read entries"
ON public.entries;


CREATE POLICY "Authenticated users can read entries"
ON public.entries
FOR SELECT
TO authenticated
USING (true);


-- ============================================================
-- 11. NO DIRECT CLIENT WRITES
--
-- We intentionally DO NOT create:
--
-- INSERT policies
-- UPDATE policies
-- DELETE policies
--
-- for transactions or entries.
--
-- The application must call post_transaction().
-- ============================================================


-- ============================================================
-- 12. RPC PERMISSIONS
--
-- Authenticated users may execute the controlled posting
-- function.
--
-- Anonymous users cannot.
-- ============================================================

REVOKE ALL
ON FUNCTION public.post_transaction(
    TEXT,
    VARCHAR,
    JSONB,
    VARCHAR
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION public.post_transaction(
    TEXT,
    VARCHAR,
    JSONB,
    VARCHAR
)
FROM anon;


GRANT EXECUTE
ON FUNCTION public.post_transaction(
    TEXT,
    VARCHAR,
    JSONB,
    VARCHAR
)
TO authenticated;


-- ============================================================
-- 13. ACCOUNT MANAGEMENT
--
-- For now, accounts are read-only through the API.
-- Account creation should happen through a controlled
-- administrative workflow rather than arbitrary client INSERTs.
-- ============================================================


-- ============================================================
-- 14. OPTIONAL: VIEW FOR ACCOUNT BALANCES
--
-- This makes reporting much easier.
-- ============================================================

CREATE OR REPLACE VIEW public.account_balances AS

SELECT
    a.id,
    a.name,
    a.type,

    COALESCE(
        SUM(
            CASE
                WHEN e.direction = 'DEBIT'
                    THEN e.amount
                ELSE
                    -e.amount
            END
        ),
        0
    ) AS balance

FROM public.accounts a

LEFT JOIN public.entries e
    ON e.account_id = a.id

GROUP BY
    a.id,
    a.name,
    a.type;


-- ============================================================
-- 15. VIEW SECURITY
-- ============================================================

GRANT SELECT
ON public.account_balances
TO authenticated;


-- ============================================================
-- END OF ACCOUNTING LEDGER SCHEMA
-- ============================================================



-- Seed Core Chart of Accounts
INSERT INTO public.accounts (name, type) VALUES
    ('1000 - Operating Cash', 'ASSET'),
    ('1100 - Accounts Receivable', 'ASSET'),
    ('2000 - Accounts Payable', 'LIABILITY'),
    ('3000 - Owner Equity', 'EQUITY'),
    ('4000 - Flight Booking Revenue', 'REVENUE'),
    ('5000 - Transaction Processing Expense', 'EXPENSE')
ON CONFLICT (name) DO NOTHING;