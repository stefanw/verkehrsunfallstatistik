# Parser for Berlin's yearly accident reports

[Some accident reports of Berlin](https://www.berlin.de/polizei/aufgaben/verkehrssicherheit/verkehrsunfallstatistik/) contain tables with rough locations of all accidents of certain types (e.g. involving bikes or pedestrians). This repository contains code to extract this data and geocode it.


The following `make` targets are available for bike accidents (pattern match with year):

- `make out/accidents_points_%.geojson`
- `make out/accidents_streets_%.geojson`


## Prerequisites

  - Python3
  - Java to run Tabula on the command line
  - GDAL with ogr2ogr
  - Some shell utilities make, wget, perl
  - PostgreSQL server with PostGIS enabled database, configure in Makefile
