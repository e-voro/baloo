\set ON_ERROR_STOP on
LOAD :'module';
CREATE FUNCTION xid64_parse(text, boolean, boolean) RETURNS bigint
AS :'module', 'xid64_parse' LANGUAGE c STRICT;
CREATE FUNCTION xid64_reloption(text[]) RETURNS bigint
AS :'module', 'xid64_reloption' LANGUAGE c STRICT;
CREATE FUNCTION xid64_serialize() RETURNS boolean
AS :'module', 'xid64_serialize' LANGUAGE c;
DO $$
DECLARE h boolean; r record; n bigint;
BEGIN
  FOREACH h IN ARRAY ARRAY[false,true] LOOP
    FOR r IN SELECT * FROM (VALUES
      ('9223372036854775807', 9223372036854775807::bigint),
      ('-9223372036854775808', (-9223372036854775807::bigint-1)),
      ('9223372036854775807  ', 9223372036854775807::bigint),
      ('1.6', 2::bigint), ('-1.6', -2::bigint), ('1e3', 1000::bigint),
      ('0x100000000', 4294967296::bigint)) AS t(input, expected)
    LOOP
      n := xid64_parse(r.input, false, h);
      IF n IS DISTINCT FROM r.expected THEN
        RAISE EXCEPTION 'parse %: got %, expected %', r.input, n, r.expected;
      END IF;
    END LOOP;
    IF xid64_parse('2s', true, h) IS DISTINCT FROM 2000::bigint OR
       xid64_parse('1.5s', true, h) IS DISTINCT FROM 1500::bigint THEN
      RAISE EXCEPTION 'unit conversion failed';
    END IF;
    FOR r IN SELECT unnest(ARRAY['9223372036854775808','-9223372036854775809',
        '1e20','NaN','Infinity','junk','1junk','']) AS input LOOP
      IF xid64_parse(r.input, false, h) IS NOT NULL THEN
        RAISE EXCEPTION 'accepted invalid input %', r.input;
      END IF;
    END LOOP;
  END LOOP;
  PERFORM set_config('xid64_probe.value','9223372036854775807',false);
  IF current_setting('xid64_probe.value') <> '9223372036854775807' THEN
    RAISE EXCEPTION 'GUC loses precision';
  END IF;
  SELECT * INTO r FROM pg_settings WHERE name='xid64_probe.value';
  IF r.min_val <> '-9223372036854775808' OR r.max_val <> '9223372036854775807'
     OR r.boot_val <> '0' OR r.reset_val <> '0' THEN
    RAISE EXCEPTION 'bad pg_settings row %', r;
  END IF;
  PERFORM set_config('xid64_probe.ms','1.5s',false);
  IF (SELECT setting FROM pg_settings WHERE name='xid64_probe.ms') <> '1500' THEN
    RAISE EXCEPTION 'GUC units lost';
  END IF;
  IF xid64_reloption(ARRAY['probe_value=9223372036854775807']) <> 9223372036854775807::bigint
     OR xid64_reloption(ARRAY['probe_value=-9223372036854775808']) <> (-9223372036854775807::bigint-1) THEN
    RAISE EXCEPTION 'reloption loses precision';
  END IF;
  BEGIN
    PERFORM xid64_reloption(ARRAY['probe_value=1e20']);
    RAISE EXCEPTION 'invalid reloption accepted';
  EXCEPTION WHEN invalid_parameter_value THEN NULL;
  END;
END $$;
BEGIN;
SET LOCAL xid64_probe.value = '-9223372036854775808';
DO $$ BEGIN
  PERFORM xid64_serialize();
  IF current_setting('xid64_probe.value') <> '-9223372036854775808' THEN
    RAISE EXCEPTION 'SET LOCAL failed';
  END IF;
END $$;
ROLLBACK;
DO $$ BEGIN
  IF current_setting('xid64_probe.value') <> '9223372036854775807' THEN
    RAISE EXCEPTION 'rollback restoration failed';
  END IF;
END $$;
RESET xid64_probe.value;
DO $$ BEGIN
  IF current_setting('xid64_probe.value') <> '0' THEN
    RAISE EXCEPTION 'RESET failed';
  END IF;
END $$;
SELECT 'xid64 GUC and reloption checks passed' AS result;
