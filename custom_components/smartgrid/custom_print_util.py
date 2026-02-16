from datetime import datetime
from decimal import Decimal


def print_results(results: list[dict]):
    columns = []
    widths = []

    # initialise the list with the number of columns

    for col in results[0]:
        columns.append(col)
        widths.append(len(col))

    # iterate through the results and overwrite each index with the maximum data length
    # can't seem to access this through the 'display_size" property of the dbapi as it is None
    for row in results:
        index = 0
        for item in row:

            data = row[item]

            if isinstance(data, datetime):
                length = len(data.isoformat())
            elif isinstance(data, Decimal):
                length = len(str(Decimal(data)))
            else:
                length = len(str(data))

            if length > widths[index]:
                widths[index] = length

            index += 1

    tavnit = '|'
    separator = '+'
    for w in widths:
        tavnit += " %-" + "%ss |" % (w,)
        separator += '-' * w + '--+'

    print(separator)
    print(tavnit % tuple(columns))
    print(separator)
    for row in results:
        try:
            print(tavnit % tuple(row.values()))
        except Exception as e:
            print(str(e))

    print(separator)
