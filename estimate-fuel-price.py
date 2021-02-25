#!/usr/bin/env python3

import sys
import math
import json
import urllib.request
from bs4 import BeautifulSoup


DEBUG = True
INTERVAL_THRESHOLD = 0.5


def debug_print(*msg):
    if DEBUG:
        sys.stderr.write(" ".join(map(str, msg)) + "\n")


minmax_cache = {}
def get_minmax(slug):
    if slug in minmax_cache:
        return minmax_cache[slug]
    try:
        req = urllib.request.urlopen("https://taustation.space/item/" + slug)
    except urllib.error.HTTPError:
        print("FATAL: failed to get data for '%s'" % slug)
        sys.exit(1)
    html = req.read()
    phtml = BeautifulSoup(html, "lxml")
    body = phtml.body
    tag = body.find('span', attrs={'class':"currency"})
    children = list(tag.children)
    price_range = children[0]
    a,b = price_range.split(" - ")
    mn = float(a)
    mx = float(b)
    minmax_cache[slug] = (mn,mx)
    return (mn,mx)


def read_items(jsondata):
    """Read the vendor entries from the given JSON data."""
    entries = []
    for station_info in jsondata:
        station = station_info['station']['name']
        system  = station_info['station']['system']
        if station_info.get('missing_data', False):
            print("incomplete data on %s (%s)" % (station, system))
            return []
        fuelprice = station_info['fuel_price_per_g']
        for (vendor,inventory) in station_info['vendors'].items():
            for (slug,itemprice) in inventory.items():
                entry = {
                    'slug'     : slug,
                    'ItemPrice': itemprice,
                    'Vendor'   : vendor,
                    'Station'  : station,
                    'System'   : system,
                    'FuelPrice': fuelprice,
                    'FuelPriceCoefficient': itemprice/fuelprice
                }
                entries.append(entry)
    return entries


def entries_by_key(entries, key):
    """Collect entries by the given key."""
    collected_entries = {}
    for e in entries:
        k = e[key]
        if not k in collected_entries:
            collected_entries[k] = []
        collected_entries[k].append(e)
    return collected_entries


class Interval:
    def __init__(self):
        self.min = -math.inf
        self.max = math.inf
    def update(self, a, b):
        if a > self.min:
            self.min = a
        if b < self.max:
            self.max = b
    def length(self):
        return (self.max - self.min)
    def is_converged(self):
        return self.length() < INTERVAL_THRESHOLD
    def __str__(self):
        return "[%.2f, %.2f]" % (self.min, self.max)
    def midpoint(self):
        return 0.5 * (self.min + self.max)


if __name__ == '__main__':

    # ingest correlation data from file or URL
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            stations_json = json.load(f)
    else:
        url = "https://tracker.tauguide.de/v1/special/fuel-vendor-correlation"
        with urllib.request.urlopen(url) as response:
            stations_json = json.load(response)

    # read all entries
    entries = read_items(stations_json)
    if not entries:
        print("Not enough data, giving up")
        sys.exit(1)
    # each entry has: slug, ItemPrice, Vendor, Station, System, FuelPrice, FuelPriceCoefficient

    # map stations to short names
    shortname_by_station = { info['station']['name'] : info['station']['short'] for info in stations_json }

    # get list of stations (having vendors), and entries available per station
    stations = set( e['Station'] for e in entries)
    entries_by_station = entries_by_key(entries, 'Station')

    # for each slug, get the list of stations where it is available
    available_on_station_by_slug = {}
    for entry in entries:
        slug = entry['slug']
        station = entry['Station']
        if not slug in available_on_station_by_slug:
            available_on_station_by_slug[slug] = set()
        available_on_station_by_slug[slug].add(station)

    # run over all stations
    fuelprice_by_station = {}
    for station in stations:

        debug_print("STATION =", station)
        # collect vendor entries for this station
        station_entries = entries_by_station[station]
        # get items available on this station
        station_entries_by_slug = entries_by_key(station_entries, 'slug')
        debug_print("  items available: ", len(station_entries_by_slug))
        # remove slugs with ambiguous pricing
        cleaned_entries = {}
        for slug, slug_entries in station_entries_by_slug.items():
            if len(slug_entries) != 1:
                prices = set(e['ItemPrice'] for e in slug_entries)
                if len(prices) != 1:
                    debug_print("  ambiguous pricing: discarding '%s' on %s" % (slug, station))
                    continue
            cleaned_entries[slug] = slug_entries
        station_entries_by_slug = cleaned_entries
        debug_print("  items left: ", len(station_entries_by_slug))

        # sort slugs by low availabilty, then high price
        station_slugs = list(station_entries_by_slug.keys())
        station_slugs.sort(key = lambda slug: station_entries_by_slug[slug][0]['ItemPrice'], reverse=True)
        station_slugs.sort(key = lambda slug: len(available_on_station_by_slug[slug]))

        fuelprice_interval = Interval()
        station_combinations = []
        for slug in station_slugs:
            # if this item is available on other stations...
            if len(available_on_station_by_slug[slug]) > 1:
                # then check if this combination of stations has already been considered previously
                station_combination = "++".join(sorted(available_on_station_by_slug[slug]))
                if station_combination in station_combinations:
                    debug_print("  skip '%s', no new station combination" % slug)
                    continue # no new combination, move on to next item
                station_combinations.append(station_combination)

            fpc = station_entries_by_slug[slug][0]['FuelPriceCoefficient']
            itemprice_min, itemprice_max = get_minmax(slug)
            fuelprice_min = itemprice_min / fpc
            fuelprice_max = itemprice_max / fpc
            fuelprice_interval.update(fuelprice_min, fuelprice_max)
            debug_print("  after '%s': fuelprice = %s" % (slug, fuelprice_interval))
            if fuelprice_interval.is_converged():
                debug_print("  converged!")
                break

        # store result
        fuelprice_by_station[station] = fuelprice_interval
            
    # print result
    # sort stations by fuelprice midpoint
    for station in sorted(stations, key = lambda station: fuelprice_by_station[station].midpoint() ):
        fp = fuelprice_by_station[station]
        print( "%-12s%s" % ( shortname_by_station[station],
                             ("%.2f" % fp.midpoint()) if fp.is_converged() else str(fp) ) )

