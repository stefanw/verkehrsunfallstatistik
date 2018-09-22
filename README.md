# Parser for Berlin's yearly accident reports

[Some accident reports of Berlin](https://www.berlin.de/polizei/aufgaben/verkehrssicherheit/verkehrsunfallstatistik/) contain tables with rough locations of all accidents of certain types (e.g. involving bikes or pedestrians). This repository contains code to extract this data and geocode it.


The following `make` targets are available for bike accidents (pattern match with year):

- `make data/accidents_points_%.geojson`
- `make data/accidents_streets_%.geojson`


## Prerequisites

  - Python3
  - Java to run Tabula on the command line
  - GDAL with ogr2ogr
  - Some shell utilities make, wget, perl
  - PostgreSQL server with PostGIS enabled database, configure in Makefile

## Resulting Data

- `csvs/` - tables from PDFs
- `data/` - geocoded and augmented data

## Map / Visualization

- [Map of data for 2017](https://stefanwehrmeyer.carto.com/viz/4fc39e13-8dbb-4d3f-a181-b2918861b6de/public_map)
- [Map of data for 2016](https://stefanwehrmeyer.carto.com/viz/5eae5a82-366a-11e7-a26a-0e233c30368f/public_map)
- [Map of data for 2015](https://stefanwehrmeyer.carto.com/viz/06889e1a-21b4-11e6-a734-0ea31932ec1d/public_map)
