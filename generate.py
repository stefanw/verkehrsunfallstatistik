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
            streets = json.load(f)
        with open(district_filename) as f:
            districts = json.load(f)

        self.engine = create_engine(engine_config)

        self.features = streets['features']

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
        print('Calculating lengths...', file=sys.stderr)
        self.shape_lengths = [self.get_shape_length(s) for s in self.shapes]
        print('Done Calculating lengths...', file=sys.stderr)
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

    def get_shape_length(self, shape):
        result = self.engine.execute('''SELECT ST_Length(the_geog) As length_spheroid,
                                               ST_Length(the_geog, false) As length_sphere
                        FROM (
                            SELECT ST_GeographyFromText(
                            'SRID=4326;%s')
                        As the_geog)
                        As foo;''' % (shape.wkt)).fetchall()

        return result[0][0]

    def get_georeference(self, streets, district=None, year=None):
        len_streets = len(streets)

        features = [self.find_by_name(street, district, year) for street in streets]
        features = [feature for feature in features if feature is not None]

        center = self.get_center(features, len_streets)
        return {
            'streets': streets,
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
    fh.write('{"type":"FeatureCollection","features":[')
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


def get_accident_feature(accident):
    return {
        "type": "Feature",
        "properties": {
            "name": accident['street'],
            "year": int(accident['year']),
            "count": int(accident['count']),
            "directorate": accident['directorate']
        }
    }


def get_accidents_as_points(idx, accidents):
    for accident in accidents:
        center = accident['center']
        if center is None:
            continue
        acc_feat = get_accident_feature(accident)
        acc_feat['geometry'] = {
              "type": "Point",
              "coordinates": [center.x, center.y]
        }
        yield acc_feat


def get_accidents_as_lines(idx, accidents):
    accidents_by_feature = defaultdict(int)
    for accident in accidents:
        for feat_id in accident['feature_idx']:
            accidents_by_feature[feat_id] += int(accident['count'])

    for feat_id, count in accidents_by_feature.items():
        feat = idx.features[feat_id]
        length = idx.shape_lengths[feat_id]
        if not length:
            count_by_length = None
        else:
            count_by_length = count / length
        yield {
            "type": "Feature",
            "properties": {
                "name": feat['properties']['name'],
                "length": length,
                "count": count,
                "count_by_length": count_by_length
            },
            "geometry": feat['geometry']
        }
    #
    # for accident in accidents:
    #     for feat_id, feat in zip(accident['feature_idx'], accident['features']):
    #         acc_feat = get_accident_feature(accident)
    #         acc_feat['geometry'] = feat['geometry']
    #         yield acc_feat


def get_accidents_as_features(idx, accidents):
    for accident in accidents:
        if len(accident['features']) > 1:
            yield from get_accidents_as_points(idx, [accident])
        else:
            yield from get_accidents_as_lines(idx, [accident])


def get_accident_list(idx, accidents):
    for accident in accidents:
        center = accident['center']
        if center is None:
            continue

        oneway_ratio = None
        ride_length = None
        shape_length = None
        if len(accident['features']) == 1:
            props = idx.features[accident['feature_idx'][0]]['properties']
            oneway_ratio = props.get('oneway_length', 0) / props.get('total_length', 1)
            shape_length = idx.shape_lengths[accident['feature_idx'][0]]
            # Count full non-oneway street as double (both directions)
            ride_length = (2 - oneway_ratio) * shape_length

        yield {
            'street': accident['street'],
            'count': accident['count'],
            'year': accident['year'],
            'directorate': accident['directorate'],
            'lat': center.x,
            'lng': center.y,
            'oneway_ratio': oneway_ratio,
            'feature_count': len(accident['features']),
            'feature_length': shape_length,
            'ride_length': ride_length,
            'features': '-'.join(str(x) for x in sorted(int(x['properties']['osmid']) for x in accident['features']))
        }


def get_accident_list_split(idx, accidents):
    for accident in accidents:
        center = accident['center']
        if center is None:
            continue

        count = len(accident['features'])

        for feat in accident['feature_idx']:
            props = idx.features[feat]['properties']
            oneway_ratio = props.get('oneway_length', 0) / props.get('total_length', 1)
            shape_length = idx.shape_lengths[feat]
            # Count full non-oneway street as double (both directions)
            ride_length = (2 - oneway_ratio) * shape_length

            yield {
                'street': accident['street'],
                'single_street': idx.features[feat]['properties']['name'],
                'count': int(accident['count']) / count,
                'year': accident['year'],
                'directorate': accident['directorate'],
                'lat': center.x,
                'lng': center.y,
                'oneway_ratio': oneway_ratio,
                'feature_count': count,
                'feature_length': shape_length,
                'ride_length': ride_length,
                'features': '-'.join(str(x) for x in sorted(int(x['properties']['osmid']) for x in accident['features'])),
                'single_feature': idx.features[feat]['properties']['osmid']
            }


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
                'length': idx.shape_lengths[feat_id]
            }
            break


def time_compare(idx, accidents):
    YEAR_COUNT = 3.0
    year_stats = defaultdict(lambda: defaultdict(int))
    for accident in accidents:
        for feat_id in accident['feature_idx']:
            year = int(accident['year'])
            year_stats[feat_id][year] += int(accident['count'])

    for feat_id, year_stat in year_stats.items():
        feat = idx.features[feat_id]
        length = idx.shape_lengths[feat_id]
        old_years_count = sum(year_stat[y] for y in range(2011, 2014))
        new_years_count = sum(year_stat[y] for y in range(2014, 2017))
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
    'accident_points': (get_accidents_as_points, 'geojson'),
    'accident_streets': (get_accidents_as_lines, 'geojson'),
    'accidents': (get_accidents_as_features, 'geojson'),
    'accident_list': (get_accident_list, 'csv'),
    'accident_list_split': (get_accident_list_split, 'csv'),
    'street_list': (get_accident_street_list, 'csv'),
    'missing': (get_missing, 'csv'),
    'time_compare': (time_compare, 'geojson'),
}

OUTPUT_WRITER = {
    'csv': write_csv,
    'geojson': write_geojson
}


def main(name, years, engine=None):
    engine = engine or os.environ.get('DATABASE_URL')
    idx = GeoIndex('geo/berlin_streets.geojson',
                   'geo/polizeidirektionen.geojson',
                   engine_config=engine,
                   mapping=json.load(open('geo/missing_mapping.json')),
                   district_history=json.load(open('geo/policedistrict_historic.json')))

    if not years:
        years = list(range(2008, 2018))
    else:
        years = [int(y) for y in years.split(',')]

    accident_generator = idx.get_accidents(years)
    processor, format = GENERATORS[name]
    processed = processor(idx, accident_generator)
    OUTPUT_WRITER[format](sys.stdout, processed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate different output files from bike accident data.')
    parser.add_argument('name', choices=list(GENERATORS.keys()))
    parser.add_argument('--engine', help='PostGIS engine URL')
    parser.add_argument('--years', help='years')

    args = parser.parse_args()
    main(args.name, args.years, engine=args.engine)
