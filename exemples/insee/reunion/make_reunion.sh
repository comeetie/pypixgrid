#!/bin/bash
# verifier les paramètres de connexion à la base postgres
USER=come
DB=reunion
HOST=127.0.0.1
# a modifier et decommenter en cas d'identification par mots de passe
export PGPASSWORD=XXX
psql -c "create database $DB" -U $USER -h $HOST
psql -d $DB -v DIR="$PWD" -f init_reunion.sql -U $USER -h $HOST
ogr2ogr -f PostgreSQL PG:"dbname=$DB user=$USER host=$HOST" ./data/200m-carreaux-reunion/car_r04.mif
csvsql --db postgresql:///reunion --insert data/200m-rectangles-reunion/rect_r04.csv
psql -d $DB -f make_reunion.sql -U $USER -h $HOST
