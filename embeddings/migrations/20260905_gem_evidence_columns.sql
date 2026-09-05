-- R-3 근거 기반 발굴 지수 컬럼 (docs/decisions_0905.md R-3)
-- 멱등. gem_potential / gem_percentile 은 건드리지 않는다 (I-1 원본 보존).
-- 로컬:  docker compose exec batch python -m embeddings.migrate --file 20260905_gem_evidence_columns.sql
-- 운영:  Railway Postgres 에 같은 파일 (psql, 또는 DATABASE_URL 을 운영으로 두고 같은 명령)
ALTER TABLE game_metrics ADD COLUMN IF NOT EXISTS gem_evidence_score      DOUBLE PRECISION;
ALTER TABLE game_metrics ADD COLUMN IF NOT EXISTS gem_evidence_status     VARCHAR(20);
ALTER TABLE game_metrics ADD COLUMN IF NOT EXISTS gem_evidence_updated_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_game_metrics_gem_evidence ON game_metrics (gem_evidence_score DESC NULLS LAST);
