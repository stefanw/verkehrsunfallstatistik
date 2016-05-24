# -*- encoding: utf-8 -*-
'''
Reads in OSM export Shapefile (e.g. from http://download.geofabrik.de/),
clusters by street name and distance and outputs a geojson FeatureCollection
with MultiLineStrings.
python cluster_streets.json berlin.roads.shp
(c) Stefan Wehrmeyer, 2015
License: MIT
'''
import math
import json
from collections import defaultdict
import sys

import fiona


R = 6371
DEG_RAD = math.pi / 180


def get_distance_in_km(lat1, lng1, lat2, lng2):
    try:
        return math.acos(math.sin(lat1 * DEG_RAD) * math.sin(lat2 * DEG_RAD) +
                         math.cos(lat1 * DEG_RAD) * math.cos(lat2 * DEG_RAD) *
                         math.cos((lng2 - lng1) * DEG_RAD)) * R
    except ValueError:
        return 10000  # arbitrary high value


def distance(a, b):
    return get_distance_in_km(a[0], a[1], b[0], b[1])


class StreetSegment(object):
    def __init__(self, osmid, name, geometry):
        self.osmid = osmid
        self.name = name
        self.geometries = [geometry]

    def __str__(self):
        return u'%s (%s)' % (self.name, len(self.geometry))

    def __repr__(self):
        return self.__str__()

    def try_merge(self, other):
        if self.distance(other) < 0.5:
            self.geometries.extend(other.geometries)
            return self
        return None

    def distance(self, other):
        mind = float('inf')
        for geoms in self.geometries:
            for g in geoms:
                for ogeoms in other.geometries:
                    for o in ogeoms:
                        mind = min(mind, distance(g, o))
        return mind

    def geojson(self):
        return {
            "type": "Feature",
            "properties": {
                "name": self.name,
                "osmid": self.osmid
            },
            "geometry": {
                "type": "MultiLineString",
                "coordinates": self.geometries
            }
        }


def collect_streets(shp):
    streets = defaultdict(list)
    i = 0
    for pt in shp:
        name = pt['properties']['name']
        osmid = pt['properties']['osm_id']
        if name:
            streets[name].append(StreetSegment(osmid, name, pt['geometry']['coordinates']))
            i += 1
            if i % 1000 == 0:
                sys.stderr.write('Loading %d\n' % i)
    return streets


def cluster_streets(streets):
    '''
    Self-made clustering, certainly bad. But works.
    '''
    for s in streets:
        sys.stderr.write(u'Clustering %s\n' % s)
        merging = True
        cluster = list(streets[s])
        new_cluster = []
        while merging:
            merging = False
            i = 0
            while i < len(cluster):
                a = cluster[i]
                new_cluster = cluster[:(i + 1)]
                for b in cluster[(i + 1):]:
                    merged = a.try_merge(b)
                    if merged is not None:
                        merging = True
                    else:
                        new_cluster.append(b)
                cluster = new_cluster
                i += 1
        yield (s, cluster)


def main(shapefile):
    with fiona.open(shapefile, 'r') as shp:
        streets = collect_streets(shp)

    sys.stderr.write(u'Dumping...\n')
    sys.stdout.write('''{"type":"FeatureCollection","features":[''')

    first = True
    for street, segments in cluster_streets(streets):
        for segment in segments:
            if first:
                first = False
            else:
                sys.stdout.write(',')
            json.dump(segment.geojson(), sys.stdout)
    sys.stdout.write(']}')


if __name__ == '__main__':
    main(sys.argv[1])
