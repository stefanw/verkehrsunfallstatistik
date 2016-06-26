import csv
import sys
import re


STREET_RE = re.compile('^([A-Z\dÖÄÜß\-\(]{2,}|\s*/\s*)[^a-z]+[A-ZÖÄÜß-]{2}[^a-z]*$')
SHORT_STREET_RE = re.compile('^[^a-z]+$')
NUM_RE = re.compile('^\s*(\d+)\s*')
LONG_LINE_LENGTH = 35
DEFAULT_VALUE = 1

MULTI_SPACE_RE = re.compile('\s{2,}')


def clean(val):
    return MULTI_SPACE_RE.sub(' ', val.strip())


def parse_lines(reader):
    back_log = []
    current = None
    directorate = None
    for lineno, line in enumerate(reader, start=1):
        is_num = False
        if line[0]:
            is_num = NUM_RE.match(line[0])
            if is_num is not None:
                direct_val = int(is_num.group(1).strip())
                if 0 < direct_val < 70 and (directorate is None or
                                            direct_val > directorate):
                    directorate = direct_val
                    if back_log:
                        for a, b, _ in back_log:
                            yield a, b, directorate
                        back_log = []
                    if isinstance(current, tuple) and current[2]  is None:
                        yield current[0], current[1], directorate
                        current = None
        if line[0] and not is_num:
            continue

        cell = line[2].lstrip()
        is_street = False
        if cell:
            if current is not None and (isinstance(current, tuple) or
                                        len(current) > LONG_LINE_LENGTH):
                is_street = SHORT_STREET_RE.match(cell)
            else:
                is_street = STREET_RE.match(cell)
            if is_street is None and current is not None:
                if cell.startswith('in der Direktion'):
                    yield current, DEFAULT_VALUE, directorate
                    current = None
                    continue
                else:
                    raise ValueError('%s: %s (%s)' % (lineno, line, current))
            if is_street is None:
                continue
            if current is not None:
                yield_now = None
                if isinstance(current, tuple):
                    yield_now = current
                    current = current[0]
                current = current + ' ' + is_street.group(0)
                if yield_now:
                    if directorate is None:
                        back_log.append((clean(current), yield_now[1], yield_now[2]))
                    else:
                        yield clean(current), yield_now[1], yield_now[2]
                    current = None
                    continue
            else:
                current = is_street.group(0)

        num_cell = line[3]
        is_count = NUM_RE.match(num_cell)
        if is_count is not None and current:
            if not cell and current:
                current = current, int(is_count.group(0).strip()), directorate
            else:
                if directorate is None:
                    back_log.append((clean(current), int(is_count.group(0).strip()), directorate))
                else:
                    yield clean(current), int(is_count.group(0).strip()), directorate
                current = None

        if cell and not is_count and is_street and not current:
            raise ValueError('%s: %s (%s)' % (lineno, line, current))


def main():
    reader = csv.reader(sys.stdin)
    writer = csv.DictWriter(sys.stdout, ('year', 'directorate', 'street', 'count'))
    writer.writeheader()
    for item in parse_lines(reader):
        writer.writerow({'year': sys.argv[1], 'directorate': item[2], 'street': item[0], 'count': item[1]})


if __name__ == '__main__':
    main()
