-- 013_alter_packages_duration.sql
-- Renames duration_days to duration_minutes to support time-based packages (hours, minutes)
-- and converts existing packages (multiply by 1440).

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='packages' AND column_name='duration_days'
    ) THEN
        ALTER TABLE packages RENAME COLUMN duration_days TO duration_minutes;
        UPDATE packages SET duration_minutes = duration_minutes * 1440;
    END IF;
END $$;

COMMIT;
