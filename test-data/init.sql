-- Demo: schema "legacy" = old system, schema "cloud" = migrated copy.
-- Deliberate defects (the auditor should find these):
--  1. phone_number renamed to primary_contact_cell      (rename, should map)
--  2. signup_date DATE -> text DD/MM/YYYY               (legit format change)
--  3. Row id=8 missing in target                        (dropped row)
--  4. Row id=3 email truncated                          (truncation)
--  5. Row id=5 balance 250.50 -> 250.05                 (value corruption)
CREATE SCHEMA legacy;
CREATE SCHEMA cloud;

CREATE TABLE legacy.customers (
  id int PRIMARY KEY, full_name text, email text,
  phone_number text, signup_date date, balance numeric(10,2));

INSERT INTO legacy.customers VALUES
 (1,'Ava Stone','ava.stone@example.com','555-0101','2021-01-15',100.00),
 (2,'Ben Ortiz','ben.ortiz@example.com','555-0102','2021-02-20',200.00),
 (3,'Cara Lin','cara.lin.longaddress@example.com','555-0103','2021-03-05',150.25),
 (4,'Dev Patel','dev.patel@example.com','555-0104','2021-04-11',75.00),
 (5,'Eli Moss','eli.moss@example.com','555-0105','2021-05-30',250.50),
 (6,'Fay Chen','fay.chen@example.com','555-0106','2021-06-18',300.00),
 (7,'Gus Hall','gus.hall@example.com','555-0107','2021-07-22',50.75),
 (8,'Hana Ito','hana.ito@example.com','555-0108','2021-08-09',410.10),
 (9,'Ivan Roy','ivan.roy@example.com','555-0109','2021-09-14',90.00),
 (10,'Jo Park','jo.park@example.com','555-0110','2021-10-01',120.00);

CREATE TABLE cloud.customers (
  id int PRIMARY KEY, full_name text, email text,
  primary_contact_cell text, signup_date text, balance numeric(10,2));

INSERT INTO cloud.customers VALUES
 (1,'Ava Stone','ava.stone@example.com','555-0101','15/01/2021',100.00),
 (2,'Ben Ortiz','ben.ortiz@example.com','555-0102','20/02/2021',200.00),
 (3,'Cara Lin','cara.lin.longaddr','555-0103','05/03/2021',150.25),
 (4,'Dev Patel','dev.patel@example.com','555-0104','11/04/2021',75.00),
 (5,'Eli Moss','eli.moss@example.com','555-0105','30/05/2021',250.05),
 (6,'Fay Chen','fay.chen@example.com','555-0106','18/06/2021',300.00),
 (7,'Gus Hall','gus.hall@example.com','555-0107','22/07/2021',50.75),
 (9,'Ivan Roy','ivan.roy@example.com','555-0109','14/09/2021',90.00),
 (10,'Jo Park','jo.park@example.com','555-0110','01/10/2021',120.00);
