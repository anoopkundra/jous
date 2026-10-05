-- NOT EXECUTED. Founder review is mandatory before any managed mutation.
-- Run only with separately authorized administrative credentials.
-- No password is embedded: runtime remains unusable until separately activated.
BEGIN;
DO $bootstrap$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname IN ('jous_runtime', 'jous_security_reader')) THEN
    RAISE EXCEPTION 'Existing Jous role state requires review; bootstrap refused';
  END IF;
  CREATE ROLE jous_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB
    NOCREATEROLE NOREPLICATION NOINHERIT;
  CREATE ROLE jous_security_reader NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB
    NOCREATEROLE NOREPLICATION NOINHERIT;
END
$bootstrap$;
COMMIT;
-- Do not grant runtime memberships. Do not alter Supabase-managed roles.
-- Migration/admin must own the four Jous tables and have authority to assign
-- function ownership to jous_security_reader. Determine that authority in the
-- read-only managed preflight; do not grant memberships here automatically.
