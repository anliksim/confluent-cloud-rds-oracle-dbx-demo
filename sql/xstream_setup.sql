-- !!! log in with the admin user

-- enable suppelmental logging
begin
    rdsadmin.rdsadmin_util.alter_supplemental_logging(
        p_action => 'ADD',
        p_type   => 'ALL');
end;
/

-- enable archivelog retention
begin
    rdsadmin.rdsadmin_util.set_configuration(
        name  => 'archivelog retention hours',
        value => '24');
end;
/

-- create tablespaces (encrypted)
CREATE TABLESPACE xstream_adm_tbs DATAFILE SIZE 25M AUTOEXTEND ON MAXSIZE UNLIMITED ENCRYPTION USING 'AES256' ENCRYPT;
CREATE TABLESPACE xstream_tbs DATAFILE SIZE 25M AUTOEXTEND ON MAXSIZE UNLIMITED ENCRYPTION USING 'AES256' ENCRYPT;

-- create the cfltadmin user
CREATE USER cfltadmin IDENTIFIED BY changethis
  DEFAULT TABLESPACE xstream_adm_tbs
  QUOTA UNLIMITED ON xstream_adm_tbs;

-- grant session privilege to cfltadmin
GRANT CREATE SESSION TO cfltadmin;

-- grant capture for xstream to cfltadmin
BEGIN
  DBMS_XSTREAM_AUTH.GRANT_ADMIN_PRIVILEGE(
    grantee                 => 'cfltadmin',
    privilege_type          => 'CAPTURE',
    grant_select_privileges => TRUE);
END;
/

-- create the cfltuser user
-- make sure "tobedefined" matches config rds:cfltUserPassword in Pulumi.yaml
CREATE USER cfltuser IDENTIFIED BY tobedefined
  DEFAULT TABLESPACE xstream_tbs
  QUOTA UNLIMITED ON xstream_tbs;

-- grant privileges
GRANT CREATE SESSION TO cfltuser;
GRANT SELECT_CATALOG_ROLE TO cfltuser;
GRANT SELECT ANY TABLE TO cfltuser;
GRANT LOCK ANY TABLE TO cfltuser;
GRANT FLASHBACK ANY TABLE TO cfltuser;

-- !!! change user to cfltadmin here
-- setup xstream outbound with the tables you want to xstream
-- make sure the server_name matches config rds:xoutServerName in Pulumi.yaml
DECLARE
  tables  DBMS_UTILITY.UNCL_ARRAY;
  schemas DBMS_UTILITY.UNCL_ARRAY;
BEGIN
  tables(1)  := 'ADMIN.pharma_dose_regimens';
  tables(2)  := 'ADMIN.pharma_event';
  tables(3)  := 'ADMIN.pharma_notes_attach';
  tables(4)  := NULL;
  schemas(1) := NULL;
  DBMS_XSTREAM_ADM.CREATE_OUTBOUND(
     server_name           =>  'xout',
     table_names           =>  tables,
     schema_names          =>  schemas);
END;
/

-- !!! change to the admin user here
-- set the xout connect user to cfltuser
BEGIN
  DBMS_XSTREAM_ADM.ALTER_OUTBOUND(
     server_name  => 'xout',
     connect_user => 'cfltuser');
END;
