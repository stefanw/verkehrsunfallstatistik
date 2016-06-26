import csv
import sys
import re


STREET_RE = re.compile('^([A-Z\dÖÄÜß\-\(]{2,}|\s*/\s*)[^a-z]+[A-ZÖÄÜß-]{2}[^a-z]*$')
SHORT_STREET_RE = re.compile('^([A-Z\dÖÄÜß\-\(]{2,}|\s*/\s*)[^a-z]*$')
NUM_RE = re.compile('^\s*(\d+)\s*')
LONG_LINE_LENGTH = 70

MULTI_SPACE_RE = re.compile('\s{2,}')


def clean(val):
    return MULTI_SPACE_RE.sub(' ', val.strip())


def parse_lines(reader):
    MAX_DIRECTORATE_CELL = 1
    current = None
    directorate = None
    for lineno, line in enumerate(reader, start=1):
        for i, cell in enumerate(line):
            if not cell:
                continue
            if current is not None and len(current) > LONG_LINE_LENGTH:
                is_street = SHORT_STREET_RE.match(cell)
            else:
                is_street = STREET_RE.match(cell)
            if is_street is None and current is None:
                is_num = NUM_RE.match(cell)
                if is_num is not None and i <= MAX_DIRECTORATE_CELL:
                    direct_val = int(is_num.group(1).strip())
                    if 0 < direct_val < 70 and (directorate is None or
                                                direct_val > directorate):
                        directorate = direct_val
                continue
            if is_street is None:
                raise ValueError('%s: %s (%s)' % (lineno, line, current))
            if current is not None:
                current = current + ' ' + is_street.group(0)
            else:
                current = is_street.group(0)
            for x in range(i + 1, len(line)):
                num_cell = line[x]
                is_num = NUM_RE.match(num_cell)
                if is_num is not None:
                    yield clean(current), int(is_num.group(0).strip()), directorate
                    current = None
                    break
            break


def main():
    reader = csv.reader(sys.stdin)
    writer = csv.DictWriter(sys.stdout, ('year', 'directorate', 'street', 'count'))
    writer.writeheader()
    for item in parse_lines(reader):
        writer.writerow({'year': sys.argv[1], 'directorate': item[2], 'street': item[0], 'count': item[1]})


if __name__ == '__main__':
    main()
