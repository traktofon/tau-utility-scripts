#!/usr/bin/env python3

import json
import sys

try:
    tauheadjson = sys.argv[1]
except:
    tauheadjson = 'tauhead-items.json'

with open(tauheadjson) as fp:
    items = json.load(fp)
itemlist = items['items']

for item in itemlist:
    slug = item['slug']
    print(slug)

