#!/usr/bin/env python3

import csv

if __name__ == '__main__':
    with open("tau-vendors.csv") as fp:
        cr = csv.DictReader(fp)
        slugs = set()
        for entry in cr:
            slug = entry['slug']
            slugs.add(slug)
    for slug in slugs:
        print(slug)

