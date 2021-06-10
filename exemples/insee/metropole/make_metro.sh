#!/bin/bash
# verifier les paramètres de connexion à la base postgres
USER=come
DB=metropole
HOST=localhost
# a modifier et decommenter en cas d'identification par mots de passe
export PGPASSWORD=XXX
psql -c "create database $DB" -U $USER -h $HOST
psql -d $DB -v DIR="$PWD" -f init_metro.sql -U $USER -h $HOST
#ogr2ogr -f PostgreSQL PG:"dbname=$DB user=$USER host=$HOST" ./data/200m-carreaux-metropole/car_m.mif
csvsql --db postgresql:///metropole --insert data/200m-rectangles-metropole/rect_m.csv
psql -d $DB -f make_metro.sql -U $USER -h $HOST

