BEGIN;
INSERT INTO "customer_profiles" ("first_name", "last_name", "email", "city", "postal_code", "mobile_phone", "insz", "active", "loyalty_points", "created_on") VALUES
  ('Ellen', 'Bauwens', 'julian21@example.net', 'Sommethonne', '2433', '+32468196001', '690813-239-03', TRUE, 588509, 'blij'),
  ('Celine', 'Beernaert', 'de-ridderwilly@example.org', 'Tavigny', '4379', '+32472654235', '590304-095-75', FALSE, 101415, 'eten'),
  ('Isabelle', 'Staelens', 'lde-ridder@example.com', 'Aiseau-Presles', '6940', '+32486184959', '670402-722-71', TRUE, 48051, 'terug'),
  ('Lucienne', 'Somers', 'lennert35@example.org', 'Burcht', '4131', '+32487525534', '080220-074-22', TRUE, 560087, 'koers'),
  ('Eddy', 'Vandenbussche', 'luna78@example.org', 'Mirwart', '4764', '+32495030564', '551209-217-73', FALSE, 222956, 'bijna'),
  ('Anne', 'Van den Eynde', 'britt10@example.net', 'Hastière-par-Delà', '8724', '+32468849696', '820623-225-73', TRUE, 534278, 'traan');
COMMIT;
