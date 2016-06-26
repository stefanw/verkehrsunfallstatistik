import csv
import sys
import re


STREET_RE = re.compile('^([A-Z\dÖÄÜß\-\(]{2,}|\s*/\s*)[^a-z]+[A-ZÖÄÜß-]{2}[^a-z]*$')
SHORT_STREET_RE = re.compile('^[^a-z]+$')
NUM_RE = re.compile('^\s*(\d+)\s*')
LONG_LINE_LENGTH = 70

MULTI_SPACE_RE = re.compile('\s{2,}')


def clean(val):
    return MULTI_SPACE_RE.sub(' ', val.strip())


def parse_lines(reader):
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
        if line[0] and not is_num:
            continue
        cell = line[2]
        if current is not None and len(current) > LONG_LINE_LENGTH:
            is_street = SHORT_STREET_RE.match(cell)
        else:
            is_street = STREET_RE.match(cell)
        if is_street is None and current is not None:
            raise ValueError('%s: %s (%s)' % (lineno, line, current))
        if is_street is None:
            continue
        if current is not None:
            current = current + ' ' + is_street.group(0)
        else:
            current = is_street.group(0)

        num_cell = line[3]
        is_num = NUM_RE.match(num_cell)
        if is_num is not None:
            yield clean(current), int(is_num.group(0).strip()), directorate
            current = None


def main():
    reader = csv.reader(sys.stdin)
    writer = csv.DictWriter(sys.stdout, ('year', 'directorate', 'street', 'count'))
    writer.writeheader()
    for item in parse_lines(reader):
        writer.writerow({'year': sys.argv[1], 'directorate': item[2], 'street': item[0], 'count': item[1]})


if __name__ == '__main__':
    main()
