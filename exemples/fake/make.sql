CREATE DATABASE fake;
\c fake
CREATE EXTENSION postgis;

CREATE TABLE carreaux AS 
SELECT *, random()*1000 as pop, random()*2500 as rev FROM ST_CreateFishnet(2000, 2000, 50, 50, 3753000,2880000);
SELECT UpdateGeometrySRID('carreaux','geom',3035);

select * from carreaux limit 10;
