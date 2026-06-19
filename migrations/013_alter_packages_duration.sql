-- 013_alter_packages_duration.sql
-- Renames duration_days to duration_minutes to support time-based packages (hours, minutes)
-- and converts existing packages (multiply by 1440).

BEGIN;

ALTER TABLE packages RENAME COLUMN duration_days TO duration_minutes;

-- Convert existing days to minutes (e.g., 1 day = 1440 minutes, 30 days = 43200 minutes)
UPDATE packages SET duration_minutes = duration_minutes * 1440;

COMMIT;
