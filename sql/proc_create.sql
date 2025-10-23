
-- Stored procedure to generate test data
CREATE OR REPLACE PROCEDURE generate_trial_data (
  p_duration_seconds IN NUMBER DEFAULT 10
) AS
  TYPE varchar_list IS TABLE OF VARCHAR2(500) INDEX BY PLS_INTEGER;
  TYPE number_list IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
  v_event_types varchar_list;
  v_frequencies varchar_list;
  v_statuses varchar_list;
  v_note_sentences varchar_list;
  v_attachment_types varchar_list;
  v_event_ids number_list;
  v_regimen_ids number_list;
  v_large_note CLOB; -- For generating large note content

  -- Function to generate large note text (removed - will generate inline)
  -- FUNCTION generate_large_note RETURN CLOB IS ...
BEGIN
  -- Initialize sample data arrays
  v_event_types(1) := 'baseline';
  v_event_types(2) := 'follow-up';
  v_event_types(3) := 'adverse_event';
  v_event_types(4) := 'dose_administered';
  v_event_types(5) := 'lab_visit';

  v_frequencies(1) := 'once daily';
  v_frequencies(2) := 'twice daily';
  v_frequencies(3) := 'every 8 hours';
  v_frequencies(4) := 'every 12 hours';
  v_frequencies(5) := 'as needed';

  v_statuses(1) := 'scheduled';
  v_statuses(2) := 'missed';
  v_statuses(3) := 'completed';
  v_statuses(4) := 'active';
  v_statuses(5) := 'completed';

  v_note_sentences(1) := 'Patient reported mild headache after taking the medication.';
  v_note_sentences(2) := 'Dosage adjustment made based on recent lab results.';
  v_note_sentences(3) := 'Patient compliance has been excellent throughout the trial.';
  v_note_sentences(4) := 'Adverse event documented and reported to regulatory authorities.';
  v_note_sentences(5) := 'Follow-up appointment scheduled for next week.';
  v_note_sentences(6) := 'Medication batch number verified and recorded.';
  v_note_sentences(7) := 'Patient education provided regarding proper administration.';
  v_note_sentences(8) := 'Vital signs within normal range during visit.';
  v_note_sentences(9) := 'Query regarding side effects addressed satisfactorily.';
  v_note_sentences(10) := 'Progress notes updated in patient record.';

  v_attachment_types(1) := 'pdf';
  v_attachment_types(2) := 'image';
  v_attachment_types(3) := 'document';
  v_attachment_types(4) := 'spreadsheet';
  v_attachment_types(5) := 'presentation';

  FOR sec IN 1..p_duration_seconds LOOP
    -- Insert 15 events and capture their IDs
    FOR i IN 1..15 LOOP
      -- Generate large long_description for event (~340KB)
      v_large_note := '';
      FOR p IN 1..TRUNC(DBMS_RANDOM.VALUE(30, 41)) LOOP -- 30-40 paragraphs for base block
        FOR s IN 1..TRUNC(DBMS_RANDOM.VALUE(8, 13)) LOOP -- 8-12 sentences per paragraph
          v_large_note := v_large_note || v_note_sentences(TRUNC(DBMS_RANDOM.VALUE(1, 11)));
          v_large_note := v_large_note || ' ';
        END LOOP;
        v_large_note := v_large_note || CHR(10) || CHR(10);
      END LOOP;
      FOR j IN 1..TRUNC(DBMS_RANDOM.VALUE(50, 101)) LOOP -- 50-100 additional details
        v_large_note := v_large_note || 'Event detail: Patient ' || TRUNC(DBMS_RANDOM.VALUE(1000, 9999)) || ' at site ' || TRUNC(DBMS_RANDOM.VALUE(10, 99)) || '. ';
      END LOOP;
      -- Repeat the base block 17 times to reach ~500KB
      DECLARE
        v_base_block CLOB := v_large_note;
      BEGIN
        FOR k IN 2..17 LOOP
          v_large_note := v_large_note || v_base_block;
        END LOOP;
      END;

      INSERT INTO pharma_event (
        patient_id,
        trial_id,
        event_type,
        event_date,
        description,
        status,
        site_id,
        investigator_id,
        long_description
      ) VALUES (
        TRUNC(DBMS_RANDOM.VALUE(1000, 9999)), -- random patient_id
        TRUNC(DBMS_RANDOM.VALUE(100, 999)),   -- random trial_id
        v_event_types(TRUNC(DBMS_RANDOM.VALUE(1, 6))),
        SYSTIMESTAMP - INTERVAL '30' DAY + INTERVAL '1' SECOND * TRUNC(DBMS_RANDOM.VALUE(0, 2592000)), -- random date within last 30 days
        'Generated event for testing purposes',
        v_statuses(TRUNC(DBMS_RANDOM.VALUE(1, 3))), -- exclusive, does not use completed
        TRUNC(DBMS_RANDOM.VALUE(10, 99)),     -- random site_id
        TRUNC(DBMS_RANDOM.VALUE(100, 999)),    -- random investigator_id
        v_large_note -- Generated long_description
      ) RETURNING event_id INTO v_event_ids(i);
    END LOOP;

    -- Insert 15 dose_regimens using the actual event_ids that were just inserted
    FOR i IN 1..15 LOOP
      -- Generate large long_description for dose_regimens (~120KB)
      v_large_note := '';
      FOR p IN 1..TRUNC(DBMS_RANDOM.VALUE(15, 21)) LOOP -- 15-20 paragraphs for base block
        FOR s IN 1..TRUNC(DBMS_RANDOM.VALUE(8, 13)) LOOP -- 8-12 sentences per paragraph
          v_large_note := v_large_note || v_note_sentences(TRUNC(DBMS_RANDOM.VALUE(1, 11)));
          v_large_note := v_large_note || ' ';
        END LOOP;
        v_large_note := v_large_note || CHR(10) || CHR(10);
      END LOOP;
      FOR j IN 1..TRUNC(DBMS_RANDOM.VALUE(25, 51)) LOOP -- 25-50 additional notes
        v_large_note := v_large_note || 'Regimen note: Medication ' || TRUNC(DBMS_RANDOM.VALUE(100, 999)) || ' dosage ' || TRUNC(DBMS_RANDOM.VALUE(10, 500)) || 'mg. ';
      END LOOP;
      -- Repeat the base block 35 times to reach ~500KB
      DECLARE
        v_base_block CLOB := v_large_note;
      BEGIN
        FOR k IN 2..35 LOOP
          v_large_note := v_large_note || v_base_block;
        END LOOP;
      END;

      INSERT INTO pharma_dose_regimens (
        event_id,
        patient_id,
        medication_id,
        trial_id,
        frequency,
        dosage_amount,
        start_date,
        end_date,
        instructions,
        status,
        long_description
      ) VALUES (
        v_event_ids(TRUNC(DBMS_RANDOM.VALUE(1, 6))), -- use actual event_id from inserted events
        TRUNC(DBMS_RANDOM.VALUE(1000, 9999)),
        TRUNC(DBMS_RANDOM.VALUE(100, 999)),
        TRUNC(DBMS_RANDOM.VALUE(100, 999)),
        v_frequencies(TRUNC(DBMS_RANDOM.VALUE(1, 6))),
        TRUNC(DBMS_RANDOM.VALUE(10, 500)) || 'mg',
        SYSDATE + TRUNC(DBMS_RANDOM.VALUE(0, 30)),
        SYSDATE + TRUNC(DBMS_RANDOM.VALUE(30, 365)),
        'Take with food. Do not crush tablets.',
        v_statuses(TRUNC(DBMS_RANDOM.VALUE(4, 6))),
        v_large_note -- Generated long_description
      ) RETURNING regimen_id INTO v_regimen_ids(i);
    END LOOP;

    -- Insert 5 notes_attach using the actual regimen_ids that were just inserted
    FOR i IN 1..15 LOOP
      -- Generate large note content (~340KB)
      v_large_note := '';
      FOR p IN 1..TRUNC(DBMS_RANDOM.VALUE(30, 41)) LOOP -- 30-40 paragraphs for base block
        FOR s IN 1..TRUNC(DBMS_RANDOM.VALUE(8, 13)) LOOP -- 8-12 sentences per paragraph
          v_large_note := v_large_note || v_note_sentences(TRUNC(DBMS_RANDOM.VALUE(1, 11)));
          v_large_note := v_large_note || ' ';
        END LOOP;
        v_large_note := v_large_note || CHR(10) || CHR(10); -- Add paragraph breaks
      END LOOP;
      -- Add some additional random text to make it even larger
      FOR j IN 1..TRUNC(DBMS_RANDOM.VALUE(50, 101)) LOOP -- 50-100 additional observations
        v_large_note := v_large_note || 'Additional clinical observation: ' ||
                        'Patient ID ' || TRUNC(DBMS_RANDOM.VALUE(1000, 9999)) || ' ' ||
                        'Trial phase ' || TRUNC(DBMS_RANDOM.VALUE(1, 4)) || ' ' ||
                        'Measurement value ' || TRUNC(DBMS_RANDOM.VALUE(1, 1000)) || '. ';
      END LOOP;
      -- Repeat the base block 17 times to reach ~500KB
      DECLARE
        v_base_block CLOB := v_large_note;
      BEGIN
        FOR k IN 2..17 LOOP
          v_large_note := v_large_note || v_base_block;
        END LOOP;
      END;

      INSERT INTO pharma_notes_attach (
        regimen_id,
        note_text,
        attachment_path,
        attachment_type,
        created_by
      ) VALUES (
        v_regimen_ids(TRUNC(DBMS_RANDOM.VALUE(1, 16))), -- use actual regimen_id from inserted regimens
        v_large_note, -- Use the generated large CLOB content
        '/attachments/trial_' || TRUNC(DBMS_RANDOM.VALUE(1000, 9999)) || '.' || v_attachment_types(TRUNC(DBMS_RANDOM.VALUE(1, 6))),
        v_attachment_types(TRUNC(DBMS_RANDOM.VALUE(1, 6))),
        TRUNC(DBMS_RANDOM.VALUE(100, 999))
      );
    END LOOP;

    COMMIT;
    DBMS_LOCK.SLEEP(1);
  END LOOP;
END;
/

-- To execute:
-- EXEC generate_trial_data(50);
