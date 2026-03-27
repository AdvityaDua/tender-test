-- PostgreSQL Schema for GeM Tender Management
-- Run this file manually or let getData.py auto-create tables on startup.

CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    keyword TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS tenders (
    bid_no TEXT PRIMARY KEY,
    start_date TEXT,
    end_date TEXT,
    items TEXT,
    quantity TEXT,
    department_name_and_address TEXT,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS representations (
    id SERIAL PRIMARY KEY,
    bid_no TEXT NOT NULL REFERENCES tenders(bid_no) ON DELETE CASCADE,
    section TEXT,
    query TEXT,
    reply TEXT,
    UNIQUE(bid_no, section, query, reply)
);

CREATE TABLE IF NOT EXISTS corrigendums (
    id SERIAL PRIMARY KEY,
    bid_no TEXT NOT NULL REFERENCES tenders(bid_no) ON DELETE CASCADE,
    modified_on TEXT,
    file_name TEXT,
    message TEXT,
    opening_date TEXT,
    extended_date TEXT,
    UNIQUE(bid_no, modified_on)
);

CREATE TABLE IF NOT EXISTS updates (
    id SERIAL PRIMARY KEY,
    bid_no TEXT NOT NULL REFERENCES tenders(bid_no) ON DELETE CASCADE,
    status TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    message TEXT,
    by TEXT
);

CREATE TABLE IF NOT EXISTS bad_tenders (
    bid_no TEXT PRIMARY KEY,
    page_no INTEGER,
    idx INTEGER,
    message TEXT
);

CREATE TABLE IF NOT EXISTS rejected_tenders (
    id SERIAL PRIMARY KEY,
    bid_no TEXT NOT NULL,
    keyword TEXT NOT NULL,
    items TEXT,
    start_date TEXT,
    end_date TEXT,
    rejected_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(bid_no, keyword)
);

-- Seed keywords
INSERT INTO keywords (keyword) VALUES
    ('CCTV'),
    ('Camera'),
    ('Surveillance'),
    ('LAN'),
    ('Network'),
    ('Firewall'),
    ('Fire Alarm'),
    ('Fire detection'),
    ('Perimeter'),
    ('UPS'),
    ('Access Control'),
    ('Biometric')
ON CONFLICT (keyword) DO NOTHING;
