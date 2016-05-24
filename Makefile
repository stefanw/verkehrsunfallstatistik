all:

PG_ENGINE = postgresql://bikeccidents:bikeccidents@localhost/bikeccidents

out/accidents_points_%.geojson: csvs/%.csv geo/berlin_streets.geojson geo/polizeidirektionen.geojson
	mkdir -p out
	python generate.py accident_locations --engine $(PG_ENGINE) --year $* > $@

out/accidents_list_%.csv: csvs/%.csv geo/berlin_streets.geojson geo/polizeidirektionen.geojson
	mkdir -p out
	python generate.py accident_list --engine $(PG_ENGINE) --year $* > $@


tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar:
	wget "https://github.com/tabulapdf/tabula-java/releases/download/tabula-0.9.0/tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar"

geo/berlin-latest.shp/roads.shp:
	mkdir -p geo
	wget -O geo/berlin-latest.shp.zip "http://download.geofabrik.de/europe/germany/berlin-latest.shp.zip"
	unzip -d geo/berlin-latest.shp geo/berlin-latest.shp.zip

pdfs/radfahrer%.pdf:
	sh download.sh

geo/berlin_streets.geojson: geo/berlin-latest.shp/roads.shp
	python collect_streets.py geo/berlin-latest.shp/roads.shp > $@

geo/polizeidirektionen.geojson:
	ogr2ogr -t_srs EPSG:4326 -s_srs EPSG:25833 -f "geoJSON" $@ WFS:"http://fbinter.stadt-berlin.de/fb/wfs/geometry/senstadt/re_abschnitt" fis:re_abschnitt

csvs/2015_raw.csv: pdfs/radfahrer2015.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	mkdir -p csvs
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-105 -a 50,83,550,811 -g -n -o $@ pdfs/radfahrer2015.pdf

csvs/2014_raw.csv: pdfs/radfahrer2014.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	mkdir -p csvs
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-102 -a 50,83,550,811 -g -n -o csvs/2014_raw.csv pdfs/radfahrer2014.pdf

csvs/2013_raw.csv: pdfs/radfahrer2013.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-101 -a 50,83,550,811 -c 130.39,190.56,493 -n -g -o csvs/2013_raw.csv pdfs/radfahrer2013.pdf

csvs/2012_raw.csv: pdfs/radfahrer2012.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-103 -a 50,83,550,811 -c 132,165,475 -n -o csvs/2012_raw.csv pdfs/radfahrer2012.pdf

csvs/2011_raw.csv: pdfs/radfahrer2011.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-102 -a 50,83,550,811 -c 130.39,190.56,493 -n -o csvs/2011_raw.csv pdfs/radfahrer2011.pdf

csvs/2010_raw.csv: pdfs/radfahrer2010.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-102 -a 50,83,550,811 -c 130.39,190.56,493 -n -o csvs/2010_raw.csv pdfs/radfahrer2010.pdf

csvs/2009_raw.csv: pdfs/radfahrer2009.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-108 -a 50,83,550,811 -c 130.39,190.56,493 -n -o csvs/2009_raw.csv pdfs/radfahrer2009.pdf

csvs/2008_raw.csv: pdfs/radfahrer2008.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 34-130 -a 50,83,550,811 -c 130.39,190.56,493 -n -g -o csvs/2008_raw.csv pdfs/radfahrer2008.pdf

csvs/2007_raw.csv: pdfs/radfahrer2007.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 35-117 -a 50,83,550,811 -c 129,184,500 -n -o csvs/2007_raw.csv pdfs/radfahrer2007.pdf
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 35-111 -a 50,83,550,811 -c 122,184,498 -n -o csvs/2006_raw.csv pdfs/radfahrer2006.pdf
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 35-102 -a 50,83,550,811 -g -c 60,110,184,500 -n -o csvs/2005_raw.csv pdfs/radfahrer2005.pdf
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 35-110 -a 50,83,550,811 -c 115,180,500 -n -o csvs/2004_raw.csv pdfs/radfahrer2004.pdf

csvs/2003_raw.csv: pdfs/radfahrer2003.pdf tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar
	java -jar ./tabula-0.9.0-SNAPSHOT-jar-with-dependencies.jar -p 35-103 -a 50,83,550,811 -c 115,180,500 -n -o csvs/2003_raw.csv pdfs/radfahrer2003.pdf

csvs/%.csv: csvs/%_raw.csv
	python parser.py "$*" < "csvs/$*_raw.csv" > $@
