CREATE EXTENSION postgis;


CREATE TABLE carreaux(
	ID varchar(200),
	IDINSPIRE varchar(200),
	IDK varchar(200),
	IND_C float,
	NBCAR float
);

\COPY carreaux FROM 'data/200m-carreaux-reunion/car_r04.csv' WITH delimiter ',';


