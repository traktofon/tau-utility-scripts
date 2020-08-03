#!/usr/bin/env python3

import sys
import re
import os.path
import csv
from glob import glob
from bs4 import BeautifulSoup

def slurp_vendor(vfile, system):
    # get fuel price
    fp = os.path.dirname(vfile) + "/fuel-price"
    f = open(fp)
    fuelprice = f.read().strip()
    f.close()
    # read vendor page HTML
    f = open(vfile)
    html = f.read()
    f.close()
    phtml = BeautifulSoup(html, "lxml")
    head = phtml.head
    body = phtml.body
    # extract station
    title = head.find('title')
    match = re.match(r'Vendors/(.+) — τ', title.text)
    station = match.group(1) if match else None
    # extract vendor
    tag = body.find('h2', attrs={'class':"vendor-details-heading"})
    vendor = tag.text
    # extract inventory
    inventory = body.find('div', attrs={'class':"inventory"})
    items = []
    for item in inventory.findAll('button', attrs={'class':"item modal-toggle"}):
        slug = item.attrs['data-item-name']
        # category = item.attrs['data-item-type']
        span = item.find('span', attrs={'class':'name'})
        lines = [ x.strip() for x in filter(lambda x: x and not x.isspace(), span.text.split('\n')) ]
        category = lines[0].rstrip(':')
        name = lines[1]
        itemprice = lines[3].replace(',', '')
        currency = lines[4]
        items.append({
            'ItemName': name,
            'ItemPrice': itemprice,
            'Currency': currency,
            'Category': category,
            'Vendor': vendor,
            'Station': station,
            'FuelPrice': fuelprice,
            'System': system,
            'slug': slug
            })
    return items


if __name__ == '__main__':
    systems = sys.argv[1:]
    items = []
    for system in systems:
        system = system.rstrip('/')
        vendors = glob(system + "/*/*.html")
        for vendor in vendors:
            items.extend(slurp_vendor(vendor, system))
    with open("tau-vendors.csv", "w") as cf:
        fieldnames = ['ItemName', 'ItemPrice', 'Currency', 'Category', 'Vendor', 'Station', 'FuelPrice', 'System', 'slug']
        cw = csv.DictWriter(cf, fieldnames)
        cw.writeheader()
        for item in items:
            cw.writerow(item)



