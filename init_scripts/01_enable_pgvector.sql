-- init_scripts/01_enable_pgvector.sql
-- PostgreSQL 초기화 시 pgvector 확장 활성화

CREATE EXTENSION IF NOT EXISTS vector;
