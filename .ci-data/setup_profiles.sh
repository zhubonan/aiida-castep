set -ev

# Here I create the actual DB for submission
psql -h "$DB_HOST" -c "CREATE DATABASE $TEST_AIIDA_BACKEND;" -U postgres
# Here I create the test DB
psql -h "$DB_HOST" -c "CREATE DATABASE test_$TEST_AIIDA_BACKEND;" -U postgres

# Here I setup the actual AiiDA profile, non-interactively
verdi -p $TEST_AIIDA_BACKEND setup --non-interactive --backend=$TEST_AIIDA_BACKEND --email="aiida@localhost" --db_host="$DB_HOST" --db_port=5432 --db_name="$TEST_AIIDA_BACKEND" --db_user=postgres --db_pass='' --repo="/tmp/test_repository_${TEST_AIIDA_BACKEND}/" --first-name=AiiDA --last-name=test --institution="AiiDA Team" --no-password

# Here I setup the test AiiDA profile, non-interactively
verdi -p test_$TEST_AIIDA_BACKEND setup --non-interactive --backend=$TEST_AIIDA_BACKEND --email="aiida@localhost" --db_host="$DB_HOST" --db_port=5432 --db_name="test_$TEST_AIIDA_BACKEND" --db_user=postgres --db_pass='' --repo="/tmp/test_repository_test_${TEST_AIIDA_BACKEND}/" --first-name=AiiDA --last-name=test --institution="AiiDA Team" --no-password

# Maybe not needed, but set this profile to be the default one for (at least) the daemon
verdi profile setdefault daemon $TEST_AIIDA_BACKEND
verdi profile setdefault verdi $TEST_AIIDA_BACKEND
