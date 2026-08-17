-- ============================================================
-- LEDGERGUARD SIMULATION & ANALYTICS EXTENSION
-- Migration 002
-- ============================================================

-- ============================================================
-- 1. TRANSACTION TYPES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.transaction_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    code VARCHAR(50) NOT NULL UNIQUE,

    name VARCHAR(100) NOT NULL,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 2. TRANSACTION CHANNELS
-- ============================================================

CREATE TABLE IF NOT EXISTS public.transaction_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    code VARCHAR(50) NOT NULL UNIQUE,

    name VARCHAR(100) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 3. SIMULATED CUSTOMERS
-- ============================================================

CREATE TABLE IF NOT EXISTS public.customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    customer_code VARCHAR(100) NOT NULL UNIQUE,

    name VARCHAR(255) NOT NULL,

    country VARCHAR(100) NOT NULL,

    currency VARCHAR(10) NOT NULL,

    risk_level VARCHAR(20) NOT NULL DEFAULT 'LOW'
        CHECK (
            risk_level IN (
                'LOW',
                'MEDIUM',
                'HIGH'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 4. SIMULATED VENDORS
-- ============================================================

CREATE TABLE IF NOT EXISTS public.vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    vendor_code VARCHAR(100) NOT NULL UNIQUE,

    name VARCHAR(255) NOT NULL,

    country VARCHAR(100) NOT NULL,

    currency VARCHAR(10) NOT NULL,

    category VARCHAR(100) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 5. TRANSACTION METADATA
--
-- This keeps analytical/simulation information separate
-- from the core accounting transaction.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.transaction_metadata (
    transaction_id UUID PRIMARY KEY
        REFERENCES public.transactions(id)
        ON DELETE RESTRICT,

    transaction_type_id UUID
        REFERENCES public.transaction_types(id)
        ON DELETE RESTRICT,

    channel_id UUID
        REFERENCES public.transaction_channels(id)
        ON DELETE RESTRICT,

    customer_id UUID
        REFERENCES public.customers(id)
        ON DELETE RESTRICT,

    vendor_id UUID
        REFERENCES public.vendors(id)
        ON DELETE RESTRICT,

    currency VARCHAR(10) NOT NULL DEFAULT 'USD',

    amount NUMERIC(19,4) NOT NULL
        CHECK (amount > 0),

    country VARCHAR(100),

    payment_method VARCHAR(50),

    simulation_source VARCHAR(30) NOT NULL DEFAULT 'SIMULATOR'
        CHECK (
            simulation_source IN (
                'REAL',
                'SIMULATOR',
                'TEST'
            )
        ),

    risk_score NUMERIC(5,2)
        CHECK (
            risk_score >= 0
            AND risk_score <= 100
        ),

    is_anomaly BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 6. SIMULATION RUNS
--
-- Allows us to group generated transactions into
-- simulation sessions.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.simulation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    run_name VARCHAR(255) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'RUNNING'
        CHECK (
            status IN (
                'RUNNING',
                'COMPLETED',
                'FAILED',
                'STOPPED'
            )
        ),

    transactions_generated INTEGER NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ
);


-- ============================================================
-- 7. SIMULATION EVENTS
--
-- Raw generated events before/around ledger posting.
--
-- This gives the data engineering layer something
-- meaningful to analyze.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.simulation_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    simulation_run_id UUID
        REFERENCES public.simulation_runs(id)
        ON DELETE RESTRICT,

    event_type VARCHAR(100) NOT NULL,

    source_system VARCHAR(100) NOT NULL,

    entity_type VARCHAR(100),

    entity_id UUID,

    payload JSONB NOT NULL,

    processed BOOLEAN NOT NULL DEFAULT FALSE,

    processing_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    processed_at TIMESTAMPTZ
);


-- ============================================================
-- 8. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_type
    ON public.transaction_metadata(transaction_type_id);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_channel
    ON public.transaction_metadata(channel_id);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_customer
    ON public.transaction_metadata(customer_id);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_vendor
    ON public.transaction_metadata(vendor_id);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_currency
    ON public.transaction_metadata(currency);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_country
    ON public.transaction_metadata(country);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_anomaly
    ON public.transaction_metadata(is_anomaly);

CREATE INDEX IF NOT EXISTS idx_transaction_metadata_created_at
    ON public.transaction_metadata(created_at);

CREATE INDEX IF NOT EXISTS idx_simulation_events_run
    ON public.simulation_events(simulation_run_id);

CREATE INDEX IF NOT EXISTS idx_simulation_events_processed
    ON public.simulation_events(processed);

CREATE INDEX IF NOT EXISTS idx_simulation_events_created_at
    ON public.simulation_events(created_at);

CREATE INDEX IF NOT EXISTS idx_simulation_runs_status
    ON public.simulation_runs(status);


-- ============================================================
-- 9. SEED TRANSACTION TYPES
-- ============================================================

INSERT INTO public.transaction_types
    (code, name, description)
VALUES
    (
        'SALE',
        'Sale',
        'Customer purchase or sale of goods/services.'
    ),
    (
        'PURCHASE',
        'Purchase',
        'Business purchase from a vendor.'
    ),
    (
        'PAYMENT',
        'Payment',
        'Payment against an outstanding balance.'
    ),
    (
        'REFUND',
        'Refund',
        'Refund issued to a customer.'
    ),
    (
        'TRANSFER',
        'Transfer',
        'Transfer between accounts.'
    ),
    (
        'PAYROLL',
        'Payroll',
        'Employee salary or payroll transaction.'
    ),
    (
        'FEE',
        'Processing Fee',
        'Bank, platform, or transaction processing fee.'
    ),
    (
        'TAX',
        'Tax',
        'Tax payment or tax-related transaction.'
    ),
    (
        'SUBSCRIPTION',
        'Subscription',
        'Recurring subscription transaction.'
    ),
    (
        'CHARGEBACK',
        'Chargeback',
        'Customer payment dispute or reversal.'
    ),
    (
        'FX',
        'Foreign Exchange',
        'Currency conversion transaction.'
    ),
    (
        'INVOICE',
        'Invoice',
        'Invoice issued to a customer.'
    ),
    (
        'LOAN',
        'Loan',
        'Loan disbursement or repayment.'
    )
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 10. SEED TRANSACTION CHANNELS
-- ============================================================

INSERT INTO public.transaction_channels
    (code, name)
VALUES
    ('CARD', 'Card Payment'),
    ('BANK_TRANSFER', 'Bank Transfer'),
    ('MOBILE_MONEY', 'Mobile Money'),
    ('ONLINE', 'Online Payment'),
    ('POS', 'Point of Sale'),
    ('DIRECT_DEBIT', 'Direct Debit'),
    ('CASH', 'Cash'),
    ('API', 'API Transaction'),
    ('INTERNAL', 'Internal System')
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 11. RLS
-- ============================================================

ALTER TABLE public.transaction_types
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.transaction_channels
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.customers
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.vendors
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.transaction_metadata
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.simulation_runs
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.simulation_events
ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 12. READ POLICIES
-- ============================================================

DROP POLICY IF EXISTS
    "Authenticated users can read transaction types"
ON public.transaction_types;

CREATE POLICY
    "Authenticated users can read transaction types"
ON public.transaction_types
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS
    "Authenticated users can read transaction channels"
ON public.transaction_channels;

CREATE POLICY
    "Authenticated users can read transaction channels"
ON public.transaction_channels
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS
    "Authenticated users can read customers"
ON public.customers;

CREATE POLICY
    "Authenticated users can read customers"
ON public.customers
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS
    "Authenticated users can read vendors"
ON public.vendors;

CREATE POLICY
    "Authenticated users can read vendors"
ON public.vendors
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS
    "Authenticated users can read transaction metadata"
ON public.transaction_metadata;

CREATE POLICY
    "Authenticated users can read transaction metadata"
ON public.transaction_metadata
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS
    "Authenticated users can read simulation runs"
ON public.simulation_runs;

CREATE POLICY
    "Authenticated users can read simulation runs"
ON public.simulation_runs
FOR SELECT
TO authenticated
USING (true);


DROP POLICY IF EXISTS
    "Authenticated users can read simulation events"
ON public.simulation_events;

CREATE POLICY
    "Authenticated users can read simulation events"
ON public.simulation_events
FOR SELECT
TO authenticated
USING (true);


-- ============================================================
-- END MIGRATION 002
-- ============================================================