import argparse
import json
from collections import defaultdict, Counter, OrderedDict
import re
import csv
import os
import sys

from sqlalchemy import create_engine

from shapely.geometry import shape, MultiPoint
from shapely import wkt


NON_LOWER_RE = re.compile('[^a-z]|aße$|asse$')


def make_name(name):
    if '(' in name:
        name = name[:name.index('(')].strip()
    return NON_LOWER_RE.sub('', name.lower().replace('ß', 'ss'))


def clean_street(street):
    parts = street.split(' / ')
    return list(OrderedDict([(p.strip(), None) for p in parts]).keys())


class GeoIndex(object):
    def __init__(self, filename, district_filename, engine_config,
                 mapping=None):
        with open(filename) as f:
            js = json.load(f)
        with open(district_filename) as f:
            districts = json.load(f)

        self.engine = create_engine(engine_config)

        self.features = js['features']

        self.mapping = mapping or {}
        for k in self.mapping:
            self.features.append({
                "type": "Feature",
                'properties': {'name': k, 'osmid': -1},
                'geometry': {'type': 'Point', 'coordinates': self.mapping[k]}
            })

        self.lost_streets = Counter()

        self.districts = {}
        for feature in districts['features']:
            self.districts[feature['properties']['spatial_name']] = shape(feature['geometry'])

        self.shapes = [shape(feature['geometry']) for feature in self.features]
        self.names = defaultdict(list)
        for i, feature in enumerate(self.features):
            self.names[make_name(feature['properties']['name'])].append(i)

    def get_weighted_streets(self, year):
        for feat, count in self.street_counter.items():
            yield {
                "type": "Feature",
                "properties": {
                    "name": self.features[feat]['properties']['name'],
                    "year": int(year),
                    "count": count,
                    "weighted_count": count / self.shapes[feat].length
                },
                "geometry": self.features[feat]['geometry']
            }

    def find_by_name(self, original_name, district=None):
        if district not in self.districts:
            raise Exception('Missing district')
        name = make_name(original_name)

        if name in self.names:
            candidates = [i for i in self.names[name]]
            if len(candidates) > 1:
                return self.get_best_for_district(candidates, district)
            if candidates:
                return candidates[0]
        self.lost_streets[original_name] += 1
        return None

    def get_best_for_district(self, candidates, district):
        district = self.districts[district]
        new_candidates = []
        for candidate in candidates:
            candidate_shape = self.shapes[candidate]
            new_candidates.append((district.distance(candidate_shape), candidate))
        new_candidates.sort(key=lambda x: x[0])
        return new_candidates[0][1]

    def get_st_closest_point(self, a, b):
        result = self.engine.execute('''SELECT
            ST_AsText(ST_ClosestPoint(foo.a, foo.b)) AS a_b,
            ST_AsText(ST_ClosestPoint(foo.b, foo.a)) As b_a
            FROM (
                SELECT '%s'::geometry As a, '%s'::geometry As b
                ) AS foo;''' % (
            a.wkt, b.wkt
        )).fetchall()
        return wkt.loads(result[0][0]), wkt.loads(result[0][1])

    def get_georeference(self, streets, district=None):
        len_streets = len(streets)

        features = [self.find_by_name(street, district) for street in streets]
        features = [feature for feature in features if feature is not None]

        center = self.get_center(features, len_streets)
        return {
            'center': center,
            'features': [self.features[f] for f in features],
            'feature_idx': features
        }

    def get_center(self, features, len_streets):
        if len(features) > 1:
            mid_points = []
            # FIXME: make this more robust
            for a, b in zip(features[:-1], features[1:]):
                closest_a, closest_b = self.get_st_closest_point(self.shapes[a], self.shapes[b])
                mid_points.append(((closest_a.x + closest_b.x) / 2, (closest_a.y + closest_b.y) / 2))
            center = MultiPoint(mid_points).centroid
            return center

        if not features:
            return None

        feat = features[0]

        if len_streets == 1:
            center = self.shapes[feat].centroid
            a, _ = self.get_st_closest_point(self.shapes[feat], center)
            return a

        if len_streets > 1:
            mid_point = self.shapes[feat].centroid
            return mid_point

    def get_accidents_for_year(self, year):
        reader = csv.DictReader(open('csvs/%d.csv' % year))
        for lineno, line in enumerate(reader, start=1):
            if not line['directorate']:
                print(year, lineno, line, file=sys.stderr)
            streets = clean_street(line['street'])
            geo_data = self.get_georeference(streets, district=line['directorate'])
            geo_data['year'] = year
            geo_data.update(line)
            yield geo_data

    def get_accidents(self, years):
        for year in years:
            yield from self.get_accidents_for_year(year)


def write_geojson(fh, generator):
    fh.write('''{"type":"FeatureCollection","features":[''')
    first = True
    for feat in generator:
        if first:
            first = False
        else:
            fh.write(',')
        json.dump(feat, fh)

    fh.write(']}')


def write_csv(fh, generator):
    writer = None
    for x in generator:
        if writer is None:
            writer = csv.DictWriter(fh, list(x.keys()))
            writer.writeheader()
        writer.writerow(x)


def get_accident_locations(idx, accidents):
    for accident in accidents:
        center = accident['center']
        if center is None:
            continue
        yield {
            "type": "Feature",
            "properties": {
                "name": accident['street'],
                "year": int(accident['year']),
                "count": int(accident['count']),
                "directorate": accident['directorate']
            },
            "geometry": {
                  "type": "Point",
                  "coordinates": [center.x, center.y]
            }
        }


def get_accident_list(idx, accidents):
    for accident in accidents:
        center = accident['center']
        if center is None:
            continue
        yield {
            'street': accident['street'],
            'count': accident['count'],
            'year': accident['year'],
            'directorate': accident['directorate'],
            'lat': center.x,
            'lng': center.y,
            'features': '-'.join(str(x) for x in sorted(int(x['properties']['osmid']) for x in accident['features']))
        }
get_accident_list.format = 'csv'


def get_accident_street_list(idx, accidents):
    for accident in accidents:
        if not accident['features']:
            yield {
                'osmid': None,
                'name': accident['street'],
                'count': accident['count'],
                'year': accident['year'],
                'directorate': accident['directorate'],
                'length': None
            }
            continue
        for feat_id, feat in zip(accident['feature_idx'], accident['features']):
            yield {
                'osmid': feat['properties']['osmid'],
                'name': feat['properties']['name'],
                'count': accident['count'],
                'year': accident['year'],
                'directorate': accident['directorate'],
                'length': idx.shapes[feat_id].length
            }
            break
get_accident_street_list.format = 'csv'


def get_missing(idx, accidents):
    for a in accidents:
        pass
    for missing in idx.lost_streets.most_common():
        yield {
            'name': missing[0],
            'original_name': missing[0],
            'count': missing[1],
            'type': 'accidents',
            'osmid': None
        }
    # for feat in idx.features:
    #     yield {
    #         'name': feat['properties']['name'],
    #         'original_name': feat['properties']['name'],
    #         'count': 0,
    #         'type': 'osm',
    #         'osmid': feat['properties']['osmid'],
    #     }


GENERATORS = {
    'accident_locations': get_accident_locations,
    'accident_list': get_accident_list,
    'street_list': get_accident_street_list,
    'missing': get_missing
}


def main(name, year, engine=None):
    engine = engine or os.environ.get('DATABASE')
    idx = GeoIndex('geo/berlin_streets.geojson',
                   'geo/polizeidirektionen.geojson',
                   engine_config=engine,
                   mapping=json.load(open('geo/missing_mapping.json')))
    if not year:
        year = range(2003, 2016)
    accident_generator = idx.get_accidents(year)
    processor = GENERATORS[name]
    processed = processor(idx, accident_generator)
    if getattr(processor, 'format', 'csv'):
        write_csv(sys.stdout, processed)
    else:
        write_geojson(sys.stdout, processed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate GeoJSON from input.')
    parser.add_argument('name', choices=list(GENERATORS.keys()))
    parser.add_argument('--engine', help='PostGIS engine URL')
    parser.add_argument('--year', type=int, nargs='*', help='year')

    args = parser.parse_args()
    main(args.name, args.year, engine=args.engine)
