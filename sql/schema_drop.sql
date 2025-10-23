-- cleanup

-- Drop foreign key constraints first to avoid dependency issues
ALTER TABLE pharma_dose_regimens DROP CONSTRAINT fk_pharma_dose_regimens_event;
ALTER TABLE pharma_notes_attach DROP CONSTRAINT fk_pharma_notes_attach_regimen;

-- Drop indexes
DROP INDEX idx_pharma_dose_regimens_event;
DROP INDEX idx_pharma_notes_attach_regimen;

-- Drop tables in reverse order of creation (to handle any remaining dependencies)
DROP TABLE pharma_notes_attach;
DROP TABLE pharma_dose_regimens;
DROP TABLE pharma_event;
