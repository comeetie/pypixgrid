import os
import base64
import json
import sys
import argparse
import psycopg2
import psycopg2.extras
import sqlite3
from pprint import pprint
from math import sqrt
import zlib

def deflate(data, compresslevel=9):
	compress = zlib.compressobj(
			compresslevel,
			zlib.DEFLATED,
			16 + zlib.MAX_WBITS,
			zlib.DEF_MEM_LEVEL,0)
	deflated = compress.compress(data)
	deflated += compress.flush()
	return deflated

def inflate(data):
	decompress = zlib.decompressobj(
			16 + zlib.MAX_WBITS  # see above
	)
	inflated = decompress.decompress(data)
	inflated += decompress.flush()
	return inflated

class PostGISProvider:
	def __init__(self, options):
		conn_string = "host='%s' dbname='%s' user='%s'" % (options['pg_connection']['host'], options['pg_connection']['dbname'], options['pg_connection']['user'])
		if options['pg_connection']['password']:
			conn_string += " password='%s'" % options['pg_connection']['password']

		conn = psycopg2.connect(conn_string)
		DEC2FLOAT = psycopg2.extensions.new_type(psycopg2.extensions.DECIMAL.values, 'DEC2FLOAT', lambda value, curs: float(value) if value is not None else None)
		psycopg2.extensions.register_type(DEC2FLOAT)
		self.conn = conn
		self.cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
		self.cursor.execute(open("postgis_functions.sql", "r").read())
		self.conn.commit()

	def request(self, sql):
		# execute sql request over PostgreSQL connection
		self.cursor.execute(sql)
		return [dict(x) for x in self.cursor.fetchall()]

	def execute(self, sql):
		# execute sql request over PostgreSQL connection
		self.cursor.execute(sql)
		self.conn.commit()
		return 1



class MbTileWriter:
	def __init__(self,options,dbprovider):
		self.options = options["output"]
		self.config  = options 
		self.conn = sqlite3.connect(self.options["layername"]+'.mbtiles')
		self.cursor = self.conn.cursor()
		
		

		# creation de la table avec les metadonnees
		try:
			self.cursor.execute("CREATE TABLE metadata (name text, value text);")
		except:
			pprint("Un fichier mbtiles de meme nom existe deja.")
			return 0
		self.cursor.execute("INSERT INTO metadata VALUES ('name','{name}')".format(name=self.options["layername"]))
		self.cursor.execute("INSERT INTO metadata VALUES ('type','overlay')")
		if("version" in self.options):
			version = self.options["version"];
		else:
			version = 0.2
		self.cursor.execute("INSERT INTO metadata VALUES ('version','{version}')".format(version=version))
		if("description" in self.options):
			description = self.options["description"];
		else:
			description = "generated by pypixgrad"
		self.cursor.execute("INSERT INTO metadata VALUES ('description','{descr}')".format(descr=description))
		self.cursor.execute("INSERT INTO metadata VALUES ('format','{fo}')".format(fo=self.options["format"]))
		if("attribution" in self.options):
			attribution = self.options["attribution"];
			self.cursor.execute("INSERT INTO metadata VALUES ('description','{attr}')".format(attr=attribution))
		
		nbsop=len(options["scale_operations"])-1
		self.cursor.execute("INSERT INTO metadata VALUES ('maxzoom', {maz})".format(maz=options["scale_operations"][0][0]))
		self.cursor.execute("INSERT INTO metadata VALUES ('minzoom', {miz})".format(miz=options["scale_operations"][nbsop][0]))
		center_request = """select AVG(ST_X(ST_centroid(ST_transform(g.{col},4326)))) as long, 
			AVG(ST_Y(ST_centroid(ST_transform(g.{col},4326)))) as lat from {table} as g""".format(col=options["data_format"]["geom_column"],table=options["data_format"]["geom_table"])
		center=dbprovider.request(center_request) 
		pprint(center)
		self.cursor.execute("INSERT INTO metadata VALUES ('center', {center})".format(center="'"+','.join(map(str,[center[0]["long"],center[0]["lat"],options["scale_operations"][nbsop][0]]))+"'"))
		fields = dict(sum([ list(map( lambda d: (d["name"],"Number"),options["data_format"]["context_variables"]) ),[("id","String"),("geosjon","String"),("area","Number")]],[]))	
		jsonmeta = {"vector_layers":[{"id":self.options["layername"], "fields" :fields}]}
		bounds_request = """SELECT ST_AsGeoJSON(ST_Extent(ST_transform({col},4326))) as bounds FROM {table};""".format(col=options["data_format"]["geom_column"],table=options["data_format"]["geom_table"])
		bounds = dbprovider.request(bounds_request) 
		coords = json.loads(bounds[0]["bounds"])["coordinates"]
		jsonmeta["bounds"]=[coords[0][0][0], coords[0][0][1], coords[0][2][0], coords[0][2][1]]
		

		self.cursor.execute("INSERT INTO metadata VALUES ('json', {meta})".format(meta = "'"+ json.dumps(jsonmeta) +"'"))

		print("Metadata writed")
		# creation de la table des tuiles
		self.cursor.execute("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);")
		self.conn.commit()

	def writerangeinmeta(self,rangeo,sc,vname):
		self.cursor.execute("INSERT INTO metadata VALUES ('{vname} variables ranges zoom {z}', {v})".format(v="'"+json.dumps(list(map(lambda r:r["value"],rangeo)))+"'",vname=vname,z=sc))

	def write(self, tile,x,y,z):
		sql = '''INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES(?, ?, ?, ?);'''
		if(self.options["format"]=='pbf'):
			yfliped = 2**z-1-y 
			self.cursor.execute(sql,[z,x,yfliped,sqlite3.Binary(deflate(tile["tile"]))])
	def commit(self):
		self.conn.commit()
		
class FileWriter:
	def __init__(self,options,dbprovider):
		self.config  = options
		self.options = options["output"]
		self.directory = self.options["directory"]
		if self.directory != '':
			if not os.path.exists(self.directory):
				os.makedirs(self.directory)


	# metadonnees
		nbsop=len(options["scale_operations"])-1
		metadata = {"maxzoom":options["scale_operations"][0][0],'minzoom':options["scale_operations"][nbsop][0]}
		metadata["ranges"]={}
		self.metadata = metadata;

	def writerangeinmeta(self,rangeo,sc,vname):
		if sc in self.metadata["ranges"]:
			self.metadata["ranges"][sc][vname]=rangeo
		else:
			self.metadata["ranges"][sc]={vname:rangeo}
	

	def write(self, tile,x,y,z):
		self.z = str(z)
		self.zdir = str(z)
		if self.directory != '':
			self.zdir = self.directory + '/' + self.zdir
		if self.zdir != '':
			if not os.path.exists(self.zdir):
				os.makedirs(self.zdir)
		self.x = str(x)
		self.xdir = self.zdir + '/' + self.x
		if not os.path.exists(self.xdir):
			os.makedirs(self.xdir)
		self.y = str(y)
	
		if(self.options["format"]=='json'):
			ct = GeoJSONTile(tile)
			filename = self.xdir + '/' + self.y + '.json'
			with open(filename, 'w') as outfile:
					json.dump(ct.getContent(), outfile, sort_keys=True, indent=4, separators=(',', ': '))
					# pretty print
					#json.dump(ct.getContent(), outfile, sort_keys=True, indent=4, separators=(',', ': '))
		if(self.options["format"]=='pbf'):
			ct = MVTile(tile,self.options["layername"],self.config)
			filename = self.xdir + '/' + self.y + '.pbf'
			with open(filename, 'wb') as outfile:
					# json.dump(self.content, outfile)
					# pretty print
				outfile.write(mapbox_vector_tile.encode(ct.getContent()))
	def commit(self):
		filename = self.directory + "/metadata.json" 
		with open(filename, 'w') as outfile:	
			json.dump(self.metadata,outfile)
		print("Metadata writed")
		return 1

class GeoJSONTile:
	def __init__(self, data):
		self.content = {"type":"FeatureCollection"}
		features = []
		for o in data:
			#pprint(o["geometry"])
			geo = json.loads(o.pop("geometry"))
			o.pop("x")
			o.pop("y")
			o.pop("z")
			no = {"type" : "Feature", "geometry" : geo,"properties":o}
			features.append(no)
		self.content["features"]=features


	def getContent(self):
		return self.content;



class MVTile:
	def __init__(self, data, layername,config):
		self.content = {"name":layername}
		features = []
		for o in data:
			geom = o.pop("geometry")
			po = []
			if ("context_variables" in  config["data_format"]):
				for vc in config["data_format"]["context_variables"]:
					po.append((vc["name"],o.pop(vc["name"])))
			po.append(("area",o.pop("area")))
			po.append(("area_projected",o.pop("area_projected")))
			no = {"geometry" : geom,"properties":dict(po)}
			features.append(no)
		self.content["features"]=features

	def getContent(self):
		return self.content;



if __name__ == "__main__":

	try :
		with open(sys.argv[1]) as config_file:    
				config = json.load(config_file)
	except :
		pprint("Veuillez fournir un fichier de configuration valide")
		sys.exit(0)
	provider = PostGISProvider(config)
	

	# test de la grille d'entree et extraction des params geometrique
	re = """select ST_AsText(g.{geom_column}) as geom, g.{row} as row, g.{col} as col, ST_SRID(g.{geom_column}) as srid from {geom_table} as g limit 2;
	""".format(geom_column=config["data_format"]["geom_column"],
			row = config["data_format"]["row_column"],
			col = config["data_format"]["col_column"],
			geom_table=config["data_format"]["geom_table"])
	grid_sample=provider.request(re)
	geo_ex=grid_sample[0]["geom"]
	coli = grid_sample[0]["col"]
	rowj = grid_sample[0]["row"]
	# la grille doit etre constituee de polygones	
	if(geo_ex[0:7]!='POLYGON'):
		pprint('Probleme de geometrie, verifier la configuration')
		sys.exit(0)
	coords=geo_ex[9:-2].split(",")

	# la grille doit etre constituee de rectangles	
	if(len(coords)!=5):
		pprint('Probleme de geometrie, les geometries doivent etre des carres. Verifier la configuration')
		sys.exit(0)
	p = list(map(lambda c : list(map(float,c.split(' '))) ,coords))
	pprint(p)
	config["data_format"]["grid_cell_size"]=p[2][0]-p[0][0]	
	pprint(config["data_format"]["grid_cell_size"])
	xmin = min(map(lambda c: c[0],p))
	ymax = max(map(lambda c: c[1],p))
	if(p[0][0]!=xmin or p[0][1]!=ymax):
		pprint('Probleme de geometrie, le premier point de la geometrie doit etre le coin Nord-Ouest. Verifier la configuration')
		sys.exit(0)


	config["data_format"]["grid_origin"]=[p[0][0]-coli*config["data_format"]["grid_cell_size"],p[0][1]-rowj*config["data_format"]["grid_cell_size"]]

	config["data_format"]["grid_srid"]=grid_sample[0]["srid"]



	if ("context_variables" in  config["data_format"]):
		vcsql     = ','+', '.join([v["aggregation"]+'('+v["name"]+') as '+v["name"] for v in config["data_format"]["context_variables"]])
		vcnames   = ','+', '.join([v["name"] for v in config["data_format"]["context_variables"]])
	else:
		vcsql     = ''
		vcnames   = ''
	if("output" in config and config["output"]["storage"]=="mbtiles"):
		writer   = MbTileWriter(config,provider)
	if("output" in config and config["output"]["storage"]=="files"):
		writer   = FileWriter(config,provider)

	if("output" in config and not ("nbquantiles" in config["output"])):
		config["output"]["nbquantiles"]=6

	# creation des tables aggregees	
	print("Aggregated grids creation")
	for i in range(len(config["scale_operations"])):
		so = config["scale_operations"][i]
		pprint(so)
		if(i==0):
			current_geom_table=config["data_format"]["geom_table"]
			current_cell_size=config["data_format"]["grid_cell_size"]
		else :
			current_geom_table="geom_table_agg"+str(config["scale_operations"][i-1][0])
			current_cell_size=current_cell_size*config["scale_operations"][i][1]
		
		
		geom_table_sql = """create temp table geom_table_agg{scale} as
			with newgrid as (select ceil(g.{row}/{agg_factor}) as {row}, floor(g.{col}/{agg_factor}) as {col} {vcsql} from {geom_table} as g 
			group by ceil(g.{row}/{agg_factor}), floor(g.{col}/{agg_factor}))
			select {row}, {col},
			ST_GeomFromText('Polygon(('||{xc0}||' '|| {yc0}||','||{xc0}||' '||{yc1}||','||{xc1}||' '||{yc1}||','||{xc1}||' '||{yc0}||','||{xc0}||' '||{yc0}||'))',{srid}) 
			as {geom_column} {vcnames} from newgrid; 
		""".format(
			vcsql=vcsql,
			vcnames=vcnames,
			scale=so[0],
			agg_factor = so[1],
			geom_table = current_geom_table,
			row = config["data_format"]["row_column"],
			col = config["data_format"]["col_column"],			
			geom_column = config["data_format"]["geom_column"],
			srid = config["data_format"]["grid_srid"],
			yc0  = config["data_format"]["row_column"]+'*'+str(current_cell_size)+'+'+str(config["data_format"]["grid_origin"][1]),
			yc1  = "("+config["data_format"]["row_column"]+'-1)*'+str(current_cell_size)+'+'+str(config["data_format"]["grid_origin"][1]),
			xc0  = config["data_format"]["col_column"]+'*'+str(current_cell_size)+'+'+str(config["data_format"]["grid_origin"][0]),
			xc1  = "("+config["data_format"]["col_column"]+'+1)*'+str(current_cell_size)+'+'+str(config["data_format"]["grid_origin"][0]),
			)
		#pprint(geom_table_sql)
		provider.execute(geom_table_sql)
		index_sql="""CREATE INDEX geom_table_agg{scale}_geom_gist ON geom_table_agg{scale} USING GIST ({geom_column});""".format(scale=so[0],geom_column = config["data_format"]["geom_column"])
		provider.execute(index_sql)
		# a faire set des srid
	print("Aggregated grids created")

			

	if ("context_variables" in  config["data_format"]):
		vcnames   = ',' + ', '.join(['g.'+v["name"] for v in config["data_format"]["context_variables"]])
	else:
		vcnames   = ''

	# export des tuiles
	print("Tiles export")
	if("output" in config):
		for i in range(len(config["scale_operations"])):
			so = config["scale_operations"][i]
			pprint(so)
			# requetes pour recuperer les donnees mises en forme pour l'export
			if(config["output"]["format"]=="json"):
				tiles_table_sql = """select ToTileX(g.{geom_column},{scale}) as X, ToTileY(g.{geom_column},{scale}) as Y, cast({scale} as int) as Z, 
					ST_AsGeoJSON(ST_transform(g.{geom_column},4326)) as geometry, ST_Area(g.{geom_column}) as area_projected, ST_Area((ST_Transform(g.{geom_column},4326))::geography) as area {vcnames}
					from geom_table_agg{scale} as g
					group by g.{col}, g.{row}, g.{geom_column} {vcnames} order by X, Y, Z;
				""".format(
					vcnames= vcnames,
					scale=so[0],
					row = config["data_format"]["row_column"],
					col = config["data_format"]["col_column"],			
					geom_column = config["data_format"]["geom_column"]
					)
				tiles_table = provider.request(tiles_table_sql)
				xc = yc = zc = -1
				nbtiles = 0
				current_tile = []	
				for r in tiles_table:
					if (int(r["x"])!=xc or int(r["y"])!=yc or r["z"]!=zc):
						pprint(r);
						# on ecrit la tuile precedente
						if(nbtiles > 0 & len(current_tile)>0):
							pprint(current_tile)
							writer.write(current_tile,xc,yc,zc)
						nbtiles = nbtiles + 1;
	
						current_tile = []
					current_tile.append(r)
					xc=int(r["x"])
					yc=int(r["y"])
					zc=r["z"]	
				# ecriture de la derniere ligne
				if(len(current_tile)>0):
					writer.write(current_tile,xc,yc,zc)
				# recuperation des quantiles de toutes les variables
			else:

				tiles = """create temp table tiles{scale} as select distinct ToTileX({geom_column},{scale})::int as X, ToTileY({geom_column},{scale})::int as Y, TileBBox({scale},ToTileX({geom_column},{scale})::int, ToTileY({geom_column},{scale})::int,3857) as bbt from geom_table_agg{scale}""".format(
					scale=so[0],			
					geom_column = config["data_format"]["geom_column"])
				provider.execute(tiles)
				tiles_index = """CREATE INDEX tiles{scale}_geom_gist ON tiles{scale} USING GIST (bbt);""".format(scale=so[0])
				provider.execute(tiles_index)
				tiles_table_sql = """select x,y, {scale}::int as z, ST_AsMVT(tt,'{layername}') as tile from (select  X, Y, St_Area(g.{geom_column}) as area {vcnames}, ({scale}::text||'_'||({row})::text ||'_'||({col})::text) as id,ST_AsGeoJSON(ST_Transform(g.{geom_column},4326)) as geojson, ST_AsMVTGeom(ST_Transform(g.{geom_column},3857),bbt) as geom from geom_table_agg{scale} as g,  tiles{scale} as tiles where St_Intersects(St_transform(g.{geom_column},3857),tiles.bbt)) as tt group by x,y;""".format(
					vcnames= vcnames,
					scale=so[0],
					row = config["data_format"]["row_column"],
					col = config["data_format"]["col_column"],	
					layername = config["output"]["layername"],			
					geom_column = config["data_format"]["geom_column"]
					)
				tiles_table = provider.request(tiles_table_sql)
				for r in tiles_table:
					writer.write(r,r["x"],r["y"],r["z"])
			
			if ("context_variables" in  config["data_format"] and "nbquantiles" in config["output"]):
				for v in config["data_format"]["context_variables"]:
					quantiles="""WITH q AS (SELECT {v}, ntile({nbq}) over (order by {v}) AS quantile FROM geom_table_agg{scale})
					SELECT max({v}) as value, quantile as quantile FROM q GROUP BY quantile ORDER BY quantile""".format(scale=so[0],v=v["name"],nbq=config["output"]["nbquantiles"])
					vcranges=provider.request(quantiles)

					writer.writerangeinmeta(vcranges,so[0],v["name"])
	print("Tiles exported")
	writer.commit()