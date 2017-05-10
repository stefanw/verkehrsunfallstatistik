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
                 mapping=None, district_history=None):
        with open(filename) as f:
            js = json.load(f)
        with open(district_filename) as f:
            districts = json.load(f)

        self.engine = create_engine(engine_config)

        self.features = js['features']

        district_history = district_history or {}
        self.district_history = {}
        for k in district_history:
            self.district_history[k] = shape({
                "type": "Point",
                "coordinates": district_history[k]
            })

        mapping = mapping or {}
        self.mapping = {}
        for k in mapping:
            if isinstance(mapping[k], list):
                self.features.append({
                    "type": "Feature",
                    'properties': {'name': k, 'osmid': -1},
                    'geometry': {'type': 'Point', 'coordinates': mapping[k]}
                })
            else:
                self.mapping[make_name(k)] = make_name(mapping[k])

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

    def find_by_name(self, original_name, district=None, year=None):
        if district:
            if district not in self.districts and district not in self.district_history:
                raise Exception('Missing district %s' % district)

            if district in self.districts:
                district = self.districts[district]
            else:
                district = self.district_history[district]
        else:
            district = None

        name = make_name(original_name)

        if name in self.mapping:
            name = self.mapping[name]

        if name in self.names:
            candidates = [i for i in self.names[name]]
            if len(candidates) > 1:
                return self.get_best_for_district(candidates, district)
            if candidates:
                return candidates[0]
        self.lost_streets[original_name] += 1
        return None

    def get_best_for_district(self, candidates, district=None):
        if district is None and len(candidates) > 1:
            raise Exception('More than one candidate, but no district: %s' %
                [self.features[x]['properties']['name'] for x in candidates])
        new_candidates = []
        for candidate in candidates:
            candidate_shape = self.shapes[candidate]
            if district is None:
                new_candidates.append((float('infinity'), candidate))
            else:
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

    def get_georeference(self, streets, district=None, year=None):
        len_streets = len(streets)

        features = [self.find_by_name(street, district, year) for street in streets]
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
            geo_data = self.get_georeference(streets,
                                             district=line['directorate'],
                                             year=year)
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


def time_compare(idx, accidents):
    YEAR_COUNT = 4.0
    year_stats = defaultdict(lambda: defaultdict(int))
    for accident in accidents:
        for feat_id in accident['feature_idx']:
            year = int(accident['year'])
            year_stats[feat_id][year] += int(accident['count'])

    for feat_id, year_stat in year_stats.items():
        feat = idx.features[feat_id]
        length = idx.shapes[feat_id].length or 1
        old_years_count = sum(year_stat[y] for y in range(2008, 2012))
        new_years_count = sum(year_stat[y] for y in range(2012, 2017))
        difference = new_years_count - old_years_count
        old_mean = old_years_count / YEAR_COUNT
        new_mean = new_years_count / YEAR_COUNT
        mean_difference = new_mean - old_mean
        mean_difference_percent = 100
        if old_mean > 0:
            mean_difference_percent = mean_difference / float(old_mean) * 100
        percent_change = 100
        if old_years_count > 0:
            percent_change = difference / float(old_years_count) * 100

        old_relative = old_years_count / length
        new_relative = new_years_count / length
        relative_difference = new_relative - old_relative
        relative_difference_percent = 100
        if old_relative > 0:
            relative_difference_percent = relative_difference / float(old_relative) * 100

        yield {
            "type": "Feature",
            "properties": {
                "name": feat['properties']['name'],
                "length": length,
                "relative_difference": relative_difference,
                "relative_difference_percent": relative_difference_percent,
                "old_accident_relative": old_relative,
                "new_accident_relative": new_relative,
                "old_count": old_years_count,
                "new_count": new_years_count,
                "old_mean": old_mean,
                "new_mean": new_mean,
                "mean_difference": mean_difference,
                "mean_difference_percent": mean_difference_percent,
                "difference": difference,
                "difference_percent": percent_change
            },
            "geometry": feat['geometry']
        }
time_compare.format = 'geojson'


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
    'missing': get_missing,
    'time_compare': time_compare
}


def main(name, year, engine=None):
    engine = engine or os.environ.get('DATABASE')
    idx = GeoIndex('geo/berlin_streets.geojson',
                   'geo/polizeidirektionen.geojson',
                   engine_config=engine,
                   mapping=json.load(open('geo/missing_mapping.json')),
                   district_history=json.load(open('geo/policedistrict_historic.json')))
    if not year:
        year = range(2008, 2017)
    accident_generator = idx.get_accidents(year)
    processor = GENERATORS[name]
    processed = processor(idx, accident_generator)
    if getattr(processor, 'format', 'csv') == 'csv':
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
