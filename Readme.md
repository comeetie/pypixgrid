# Pypixgrid

Fork de https://github.com/SNCFdevelopers/Pypixgrid pour des données statique et pour python 3.


*Pypixgrid* est un script python qui permet de générer des tuiles vectorielles pour l'exploration de jeux de données massifs.

Il est spécialisé dans la gestion des carroyages.
Il permet de travailler avec n'importe quel système de projection et de contrôler le type d'agrégation utilisé ainsi que les paliers d'agrégation.

Pour permettre une exploration efficace du jeu de données, le carroyage initial est progressivement agrégé de manière à construire des carroyages visibles aux différentes échelles.
L'information temporelle est stockée de manière brute au sein des tuiles produites.
Deux formats de tuiles vectorielles sont disponibles, ce qui permet d'interfacer les tuiles avec différentes libariries de cartographie web tel que leaflet ou mapboxGL-js.

Ce code est mis à disposition sous licence [Cecill-C](http://www.cecill.info/licences/Licence_CeCILL-C_V1-fr.html).

## Voir aussi  

https://github.com/CartoDB/torque-tiles/blob/master/2.0/spec.md

https://github.com/CartoDB/torque

https://github.com/mapbox/tippecanoe

## Format des données d'entrée

Les données d'entrées sont supposées être hébergées dans une base postgre/postgis possédant le schéma suivant :

- table de géométrie (identifiant ligne, identifiant colonne, géometrie et variables de contexte ne présentant pas de variation temporelle)

    L'identifiant du carreau sur la grille est un couple d'entier permettant de recontruire le coin en haut à gauche du carreau (de coordonnées x,y) dans la projection utilisée ie :
soit i l'identifiant de ligne et j l'identifiant de colonne et x, y les coordonnées du coin en haut à gauche du carreau, on a alors :

    x = j*c + x0

    y = i*c + y0

    avec c la taille d'un carreau et x0, y0 des constantes

## Paramètres du script de génération de tuiles

Les paramètres de connexion à la base, les noms des tables (données et géométrie) doivent être fournis à l'aide d'un fichier json (voir les exemples).

En plus de ces données de bases, le paramétrage permet de spécifier le nom des variables à exporter et l'opération d'agrégation à utiliser (SUM,MEAN,MIN,MAX).

Enfin, la liaison entre l'échelle (tel que spécifiée dans  [Slippy_map_tilenames](http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames) et le niveau d'agrégation du carroyage intial doit être défini.

Pour ce faire nous proposons de partir de l'échelle la plus précise et de remonter vers les échelles plus grossières en définissant des paliers d'aggrégations.
Le fichier de paramètrage contient alors:

 - l'échelle de début : ex 15 à laquelle les données initiales sont utilisées telles quelles
 - des paliers d'agrégation sous forme de couple (échelle, nombre de pixels) : ex (12,2) qui est compris comme le paramétrage suivant : à partir de l'échelle 12 utiliser le carroyage dont la résolution a été diminuée par 2 par rapport à la précédente
 - l'échelle de fin : ex 7

Un exemple de fichier de configuration (json) est disponible config_horodateurs.json.
Ce fichier est structuré autour de trois attributs principaux :
- *pg_connection* qui contient les paramètres permettant au programme de se connecter à la base postgres
- *data_format* qui décrit la structure des tables servant à la production des tuiles ainsi que les spécifications des opérations d'agrégation a effectuer pour passer d'une échelle à l'autre
- *output* qui contient les options permettant de contrôler le format des tuiles et des meta-données générées par le programme


Il doit utiliser la structure suivante :

- *pg_connection* (paramètres de connexion à la base postgres):
	* "user" : nom d'utilisateur
	* "dbname" : nom de la base
	* "host" : adresse du serveur postgres
	* "password" : mot de passe

- *data_format* (structure de la base et définition des opérations d'agrégation):
	* "data_table": nom de la table contenant les données temporelles
	* "geom_table": nom de la table contenant les données de géometrie et les variables n'évoluant pas avec le temps
	* "time_column": nom de la colonne indiquant le temps dans la table de données
	* "geom_column": nom de la colonne contenant la géometrie dans la table de géométrie
	* "row_column": nom de la colonne contenant l'identitiant de ligne
	* "col_column": nom de la colonne contenant l'identifiant de colonne
	* "temporal_variables": tableau contenant la liste des variables ayant une évolution temporelle à agréger
		ex : [{"name":"residents","aggregation":"SUM"},{"name":"rotatif","aggregation":"SUM"}],
	* "context_variables": tableau contenant la liste des variables sans évolution temporelle à agréger
		ex : [{"name":"population","aggregation":"SUM"},{"name":"emploi","aggregation":"SUM"}],
	* "scale_operations": tableau contenant la liste des échelles à exporter et le degré d'agrégation par rapport à l'échelle précédente,
		ex : [[16,1],[15,1],[14,2],[13,2],[12,2],[11,2]],

- *output* (spécification du format de sorties):
	* "format": (json|pbf) format des tuiles à générer
	* "storage": (files|mbtiles) type de stockage arborescence de fichier (files) ou base mbtiles (mbtiles)
	* "verbose": (true|false) calcul et affichage de statistiques sur le carroyage et sur les variables du jeu de données aux différentes échelles
	* "directory": nom du répertoire où écrire les tuiles (utilisé seulement pour l'export sous forme de fichiers)
	* "layername": nom de la couche (utilisé uniquement pour l'export au format pbf)
	* "nbquantiles": nombre de quantiles à calculer par variable et disponibles dans les meta-données des tuiles


## Format de sortie

Les tuiles peuvent être générées soit en geojson, soit en pbf.

Pour les tuiles générées en geojson, les données temporelles sont stockées dans des vecteurs accessibles via les propriétés associées au carreau.
La géométrie des carreaux est résumé par un point unique situé au centre du carreau et les données sont fournies en WGS 84.
Les données sont stockées sous forme de vecteurs dans les propriétés des objets (un vecteur par variable et un pour le temps, cf [CartoDB/torque-tiles](https://github.com/CartoDB/torque-tiles/blob/master/2.0/spec.md).


Pour les tuiles en pbf, elles respectent le format défini par [mapbox]( https://github.com/mapbox/vector-tile-spec), l'encodage est réalisé par la librairie [mapzen/mapbox-vector-tile](https://github.com/mapzen/mapbox-vector-tile) (cette libraire nécessite l'installation de quelques dépendances et est distribuée sous licence MIT).


Pour ce qui est du stockage des tuiles, elles peuvent être stockées  dans une arborescence de fichiers respectant les conventions de nommage ou exportées au format mbtiles (base [sqlite](https://github.com/mapbox/mbtiles-spec) pouvant par exemple être servies par ce [serveur de tuiles](https://github.com/infostreams/mbtiles-php)).
Dans les deux cas de figures, des méta-données sont générées automatiquement et stockées à la racine de l'arborescence dans le cas de l'export sous forme de fichiers ou dans la table metadata dans le cas de l'export mbtiles.




## Dépendances

python 2.7, postgres, postgis

librairies python :

* psycopg2 (Licence: LGPL with exceptions or ZPL)

## Utilisation
```
python pypixgrid.py config.json
```


## Exemple

Pour tester la mise en œuvre du code (NB : nécessite la librairie GDAL/OGR) :

```shell
cd ./exemple/fake/
# Verifier la configuration de la connexion a la base dans le fichier
# Executer make.sh pour construire une base postgis a partir des donnees brutes
./make.sh
# créer les tuiles
# modification des paramètres de connexion dans ./exemple/config_horodateur.json
cd ../..
# execution du code
python pypixgrid.py ./exemple/fake/config_fake.json
```
