-- ============================================================
-- LedgerGuard: Transaction Reversal Function
-- Migration: 007
-- ============================================================

CREATE OR REPLACE FUNCTION public.reverse_transaction(
    p_transaction_id UUID,
    p_idempotency_key VARCHAR,
    p_reason TEXT DEFAULT 'Transaction reversal'
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$

DECLARE
    v_original_transaction RECORD;
    v_reversal_transaction_id UUID;
    v_existing_reversal UUID;
    v_existing_hash TEXT;
    v_request_hash TEXT;
    v_entry RECORD;
    v_entry_count INTEGER;

BEGIN

    -- ========================================================
    -- BASIC VALIDATION
    -- ========================================================

    IF p_transaction_id IS NULL THEN
        RAISE EXCEPTION
            'Original transaction ID cannot be NULL.';
    END IF;

    IF p_idempotency_key IS NULL
       OR LENGTH(TRIM(p_idempotency_key)) = 0 THEN
        RAISE EXCEPTION
            'Reversal idempotency key cannot be empty.';
    END IF;

    IF p_reason IS NULL
       OR LENGTH(TRIM(p_reason)) = 0 THEN
        RAISE EXCEPTION
            'Reversal reason cannot be empty.';
    END IF;


    -- ========================================================
    -- IDEMPOTENCY HASH
    --
    -- md5() is built into PostgreSQL and avoids dependency
    -- resolution issues with pgcrypto.digest().
    -- ========================================================

    v_request_hash :=
        md5(
            p_transaction_id::TEXT
            || '|'
            || p_reason
        );


    -- ========================================================
    -- IDEMPOTENCY CHECK
    --
    -- Same key + same request = return existing reversal.
    -- Same key + different request = reject.
    -- ========================================================

    SELECT
        id,
        request_hash
    INTO
        v_reversal_transaction_id,
        v_existing_hash
    FROM public.transactions
    WHERE idempotency_key = p_idempotency_key
    FOR SHARE;

    IF v_reversal_transaction_id IS NOT NULL THEN

        IF v_existing_hash = v_request_hash THEN
            RETURN v_reversal_transaction_id;
        END IF;

        RAISE EXCEPTION
            'IDEMPOTENCY VIOLATION: Reversal idempotency key % has already been used with different data.',
            p_idempotency_key;

    END IF;


    -- ========================================================
    -- LOCK AND LOAD ORIGINAL TRANSACTION
    -- ========================================================

    SELECT *
    INTO v_original_transaction
    FROM public.transactions
    WHERE id = p_transaction_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Transaction % does not exist.',
            p_transaction_id;
    END IF;


    -- ========================================================
    -- ONLY POSTED TRANSACTIONS CAN BE REVERSED
    -- ========================================================

    IF v_original_transaction.status <> 'POSTED' THEN
        RAISE EXCEPTION
            'Transaction % cannot be reversed because its status is %.',
            p_transaction_id,
            v_original_transaction.status;
    END IF;


    -- ========================================================
    -- CHECK WHETHER TRANSACTION WAS ALREADY REVERSED
    -- ========================================================

    SELECT id
    INTO v_existing_reversal
    FROM public.transactions
    WHERE reversal_of_transaction_id = p_transaction_id
    LIMIT 1;

    IF v_existing_reversal IS NOT NULL THEN
        RAISE EXCEPTION
            'Transaction % has already been reversed by transaction %.',
            p_transaction_id,
            v_existing_reversal;
    END IF;


    -- ========================================================
    -- VERIFY ORIGINAL HAS DOUBLE-ENTRY LEDGER
    -- ========================================================

    SELECT COUNT(*)
    INTO v_entry_count
    FROM public.entries
    WHERE transaction_id = p_transaction_id;

    IF v_entry_count < 2 THEN
        RAISE EXCEPTION
            'Transaction % cannot be reversed because it does not contain a valid double-entry ledger.',
            p_transaction_id;
    END IF;


    -- ========================================================
    -- CREATE REVERSAL TRANSACTION
    -- ========================================================

    INSERT INTO public.transactions (
        description,
        reference_id,
        idempotency_key,
        request_hash,
        status,
        event_type,
        customer_id,
        amount,
        currency,
        payment_method,
        risk_level,
        anomaly_score,
        anomaly_reason,
        occurred_at,
        event_status,
        reversal_of_transaction_id
    )
    VALUES (
        'REVERSAL: ' || v_original_transaction.description,
        'REV-' || p_transaction_id::TEXT,
        p_idempotency_key,
        v_request_hash,
        'POSTED',
        'REVERSAL',
        v_original_transaction.customer_id,
        v_original_transaction.amount,
        v_original_transaction.currency,
        v_original_transaction.payment_method,
        v_original_transaction.risk_level,
        v_original_transaction.anomaly_score,
        p_reason,
        CURRENT_TIMESTAMP,
        'SUCCESS',
        p_transaction_id
    )
    RETURNING id
    INTO v_reversal_transaction_id;


    -- ========================================================
    -- CREATE OPPOSITE LEDGER ENTRIES
    --
    -- Original DEBIT  -> Reversal CREDIT
    -- Original CREDIT -> Reversal DEBIT
    -- ========================================================

    FOR v_entry IN
        SELECT
            account_id,
            amount,
            direction
        FROM public.entries
        WHERE transaction_id = p_transaction_id
    LOOP

        INSERT INTO public.entries (
            transaction_id,
            account_id,
            amount,
            direction
        )
        VALUES (
            v_reversal_transaction_id,
            v_entry.account_id,
            v_entry.amount,
            CASE
                WHEN v_entry.direction = 'DEBIT'
                    THEN 'CREDIT'
                ELSE 'DEBIT'
            END
        );

    END LOOP;


    -- ========================================================
    -- RETURN REVERSAL TRANSACTION ID
    -- ========================================================

    RETURN v_reversal_transaction_id;

END;
$function$;