all:

PG_ENGINE = postgresql://bikeccidents:bikeccidents@localhost/bikeccidents
TABULA=tabula-0.9.2-jar-with-dependencies.jar

out/accidents_points_%.geojson: csvs/%.csv geo/berlin_streets.geojson geo/polizeidirektionen.geojson
	mkdir -p out
	python generate.py accident_points --engine $(PG_ENGINE) --year $* > $@

out/accidents_streets_%.geojson: csvs/%.csv geo/berlin_streets.geojson geo/polizeidirektionen.geojson
	mkdir -p out
	python generate.py accident_streets --engine $(PG_ENGINE) --year $* > $@

out/accidents_%.geojson: csvs/%.csv geo/berlin_streets.geojson geo/polizeidirektionen.geojson
	mkdir -p out
	python generate.py accidents --engine $(PG_ENGINE) --year $* > $@

out/accidents_list_%.csv: csvs/%.csv geo/berlin_streets.geojson geo/polizeidirektionen.geojson
	mkdir -p out
	python generate.py accident_list --engine $(PG_ENGINE) --year $* > $@

tabula-0.9.2-jar-with-dependencies.jar:
	wget "https://github.com/tabulapdf/tabula-java/releases/download/0.9.2/tabula-0.9.2-jar-with-dependencies.jar"

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

csvs/2016_raw.csv: pdfs/radfahrer2016.pdf $(TABULA)
	mkdir -p csvs
	java -jar ./$(TABULA) -p 35-46,48-59,61-72,74-85,87-99,101-112 -a 74,56,811,550 -c 98,130,505 -o $@ pdfs/radfahrer2016.pdf

csvs/2015_raw.csv: pdfs/radfahrer2015.pdf $(TABULA)
	mkdir -p csvs
	java -jar ./$(TABULA) -p 34-105 -a 50,83,811,550 -c 103,135,503 -o $@ pdfs/radfahrer2015.pdf

csvs/2014_raw.csv: pdfs/radfahrer2014.pdf $(TABULA)
	mkdir -p csvs
	java -jar ./$(TABULA) -p 34-102 -a 50,83,811,550 -c 108,134,500 -o $@ pdfs/radfahrer2014.pdf

csvs/2013_raw.csv: pdfs/radfahrer2013.pdf $(TABULA)
	java -jar ./$(TABULA) -p 34-101 -a 50,83,811,550 -c 116,143,500 -o $@ pdfs/radfahrer2013.pdf

csvs/2012_raw.csv: pdfs/radfahrer2012.pdf $(TABULA)
	java -jar ./$(TABULA) -p 34-103 -a 50,83,811,550 -c 132,165,475 -o $@ pdfs/radfahrer2012.pdf

csvs/2011_raw.csv: pdfs/radfahrer2011.pdf $(TABULA)
	java -jar ./$(TABULA) -p 34-102 -a 50,83,811,550 -c 130,190,497 -o $@ pdfs/radfahrer2011.pdf

csvs/2010_raw.csv: pdfs/radfahrer2010.pdf $(TABULA)
	java -jar ./$(TABULA) -p 34-46 -a 50,83,811,550 -c 145,204,497 -o csvs/2010_raw_1.csv pdfs/radfahrer2010.pdf
	java -jar ./$(TABULA) -p 47-57 -a 50,83,811,550 -c 127,188,497 -o csvs/2010_raw_2.csv pdfs/radfahrer2010.pdf
	java -jar ./$(TABULA) -p 48-102 -a 50,83,811,550 -c 115,176,488 -o csvs/2010_raw_3.csv pdfs/radfahrer2010.pdf
	cat csvs/2010_raw_1.csv csvs/2010_raw_2.csv csvs/2010_raw_3.csv > $@
	rm csvs/2010_raw_*.csv

csvs/2009_raw.csv: pdfs/radfahrer2009.pdf $(TABULA)
	java -jar ./$(TABULA) -p 34-47 -a 50,83,811,550 -c 146,205,483 -o csvs/2009_raw_1.csv pdfs/radfahrer2009.pdf
	java -jar ./$(TABULA) -p 48-60 -a 50,83,811,550 -c 130,189,487 -o csvs/2009_raw_2.csv pdfs/radfahrer2009.pdf
	java -jar ./$(TABULA) -p 61-71 -a 50,83,811,550 -c 115,176,480 -o csvs/2009_raw_3.csv pdfs/radfahrer2009.pdf
	java -jar ./$(TABULA) -p 72-83 -a 50,83,811,550 -c 115,176,493 -o csvs/2009_raw_4.csv pdfs/radfahrer2009.pdf
	java -jar ./$(TABULA) -p 84-108 -a 50,83,811,550 -c 115,175,500 -o csvs/2009_raw_5.csv pdfs/radfahrer2009.pdf
	cat csvs/2009_raw_*.csv > $@
	rm csvs/2009_raw_*.csv

csvs/2008_raw.csv: pdfs/radfahrer2008.pdf $(TABULA)
	java -jar ./$(TABULA) -p 34-50 -a 50,83,811,550 -c 130,187,498 -o csvs/2008_raw_1.csv pdfs/radfahrer2008.pdf
	perl -pi -e  's/,,OSTSEESTR,/,,OSTSEESTR,1/g' csvs/2008_raw_1.csv
	java -jar ./$(TABULA) -p 51-65 -a 50,83,811,550 -c 118,178,497 -o csvs/2008_raw_2.csv pdfs/radfahrer2008.pdf
	java -jar ./$(TABULA) -p 66-80 -a 50,83,811,550 -c 140,200,484 -o csvs/2008_raw_3.csv pdfs/radfahrer2008.pdf
	perl -pi -e  's|,,"JULIE-WOLFTHORN-STR. / AM NORDBAHNHOF / ",|,,"JULIE-WOLFTHORN-STR. / AM NORDBAHNHOF / ",1|g' csvs/2008_raw_3.csv
	perl -pi -e  's|"",,"AM LUSTGARTEN / KARL-LIEBKNECHT-STR. / ",|"",,"AM LUSTGARTEN / KARL-LIEBKNECHT-STR. / ",1|g' csvs/2008_raw_3.csv
	perl -pi -e  's|"",,"JANNOWITZBRÜCKE / ALEXANDERSTR. / ",|"",,"JANNOWITZBRÜCKE / ALEXANDERSTR. / ",1|g' csvs/2008_raw_3.csv
	perl -pi -e  's|"",,"FENNSTR. / REINICKENDORFER STR. / SCHÖNWALDER ",|"",,"FENNSTR. / REINICKENDORFER STR. / SCHÖNWALDER ",1|g' csvs/2008_raw_3.csv
	java -jar ./$(TABULA) -p 81-97 -a 50,83,811,550 -c 157,215,479 -o csvs/2008_raw_4.csv pdfs/radfahrer2008.pdf
	java -jar ./$(TABULA) -p 98-112 -a 50,83,811,550 -c 130,190,482 -o csvs/2008_raw_5.csv pdfs/radfahrer2008.pdf
	java -jar ./$(TABULA) -p 113-130 -a 50,83,811,550 -c 142,208,475 -o csvs/2008_raw_6.csv pdfs/radfahrer2008.pdf
	cat csvs/2008_raw_*.csv > $@
	rm csvs/2008_raw_*.csv

csvs/2007_raw.csv: pdfs/radfahrer2007.pdf $(TABULA)
	java -jar ./$(TABULA) -p 35-117 -a 50,83,811,550 -c 129,184,500 -n -o csvs/2007_raw.csv pdfs/radfahrer2007.pdf
	java -jar ./$(TABULA) -p 35-111 -a 50,83,811,550 -c 122,184,498 -n -o csvs/2006_raw.csv pdfs/radfahrer2006.pdf
	java -jar ./$(TABULA) -p 35-102 -a 50,83,811,550 -g -c 60,110,184,500 -n -o csvs/2005_raw.csv pdfs/radfahrer2005.pdf
	java -jar ./$(TABULA) -p 35-110 -a 50,83,811,550 -c 115,180,500 -n -o csvs/2004_raw.csv pdfs/radfahrer2004.pdf

csvs/2003_raw.csv: pdfs/radfahrer2003.pdf $(TABULA)
	java -jar ./$(TABULA) -p 35-103 -a 50,83,811,550 -c 115,180,500 -n -o csvs/2003_raw.csv pdfs/radfahrer2003.pdf

csvs/%.csv: csvs/%_raw.csv
	python parser.py "$*" < "csvs/$*_raw.csv" > $@
