-- use to drop the xstream server using the admin user
BEGIN
  DBMS_XSTREAM_ADM.DROP_OUTBOUND('xout');
END;
