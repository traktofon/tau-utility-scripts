#!/usr/bin/env python3

import sys
import math
import json
import requests
from copy import deepcopy
from bs4 import BeautifulSoup

from diskcache import Cache
from datetime import date


DEBUG = True
INTERVAL_THRESHOLD = 0.5


def debug_print(*msg):
    if DEBUG:
        sys.stderr.write(" ".join(map(str, msg)) + "\n")


def _get_minmax(slug):
    # print('_get_minmax({})'.format(slug))
    url = "https://taustation.space/item/" + slug
    req = requests.get(url)
    if req.status_code != 200:
        raise Exception('Cannot get {}: {}'.format(url, req.text))
    phtml = BeautifulSoup(req.text, "lxml")
    tag = phtml.body.find('span', attrs={'class':"currency"})
    children = list(tag.children)
    price_range = children[0]
    a,b = price_range.split(" - ")
    mn = float(a)
    mx = float(b)
    return (mn,mx)

def get_minmax(cache, slug):
    day = str(date.today())
    cache_key = '{}/{}'.format(day, slug)
    result = cache.get(cache_key)
    if result:
        return result
    result = _get_minmax(slug)
    cache.set(cache_key, result)
    return result


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


def equals_approx(a, b, tolerance=1.0):
    """
    Returns True if a==b within the given absolute tolerance.
    """
    return abs(a-b) <= tolerance


def median(numbers):
    """
    Returns the median of a list of already sorted numbers.
    """
    l = len(numbers)
    if l % 2 == 1:
        return numbers[ l // 2 + 1]
    else:
        return (numbers[l // 2] + numbers[l // 2 + 1]) / 2


def find_most_common_number(l, ACCURACY=0.05):
    """
    In a list of numbers, find one number that is the most common,
    barring some wiggle room for inaccuracies.
    Returns the most common number, or None if there is not one
    clear most common number.
    """
    previous = None
    current_streak = []
    streaks = []
    for n in sorted(l):
        if previous is None:
            previous = n
            current_streak = [n]
            continue
        diff = (n - previous) / n
        if diff <= ACCURACY:
            current_streak.append(n)
        else:
            streaks.append(current_streak)
            current_streak = [n]
        previous = n
    streaks.append(current_streak)

    sorted_streaks = sorted(streaks, key=lambda s: -len(s))
    winning_streak = sorted_streaks[0]

    if len(winning_streak) == 1:
        # seems we have no similar numbers at all
        return None
    if len(sorted_streaks) > 1 and len(winning_streak) == len(sorted_streaks[1]):
        # we have two clusters of similar numbers with the same size,
        # so don't assume we have a winner
        return None

    return median(winning_streak)


class Interval:
    def __init__(self):
        self.min = -math.inf
        self.max = math.inf
        self.prices_seen = []

    def update(self, a, b):
        self.prices_seen.append(a)
        self.prices_seen.append(b)
        if a > self.min:
            self.min = a
        if b < self.max:
            self.max = b

    def guess(self):
        return find_most_common_number(self.prices_seen)

    def length(self):
        return (self.max - self.min)
    def is_converged(self):
        return self.length() < INTERVAL_THRESHOLD
    def __str__(self):
        return "[%.2f, %.2f]" % (self.min, self.max)
    def midpoint(self):
        return 0.5 * (self.min + self.max)
    def contains(self, a):
        return (a >= self.min - INTERVAL_THRESHOLD) and (a <= self.max + INTERVAL_THRESHOLD)


with Cache(directory='item-price-cache') as cache:

    # ingest correlation data from file or URL
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            stations_json = json.load(f)
    else:
        url = "https://tracker.tauguide.de/v1/special/fuel-vendor-correlation"
        req = requests.get(url)
        if req.status_code != 200:
            raise Exception('Cannot get {}: {}'.format(url, req.text))
        stations_json = json.loads(req.text)

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
    nstations = len(stations)
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
    nconverged = 0
    fuelprice_by_station = {}
    considered_slugs_by_station = {}
    debug_print("### PHASE 1 ###")
    for station in stations:

        debug_print("STATION =", station)

        # remember the slugs that are considered for fuel price prediction
        considered_slugs_by_station[station] = []

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

            # remember
            considered_slugs_by_station[station].append(slug)
            
            # update potential fuel price range
            fpc = station_entries_by_slug[slug][0]['FuelPriceCoefficient']
            itemprice_min, itemprice_max = get_minmax(cache, slug)
            fuelprice_min = itemprice_min / fpc
            fuelprice_max = itemprice_max / fpc
            fuelprice_interval.update(fuelprice_min, fuelprice_max)
            debug_print("  after '%s': fuelprice = %s" % (slug, fuelprice_interval))
            if fuelprice_interval.is_converged():
                nconverged += 1
                debug_print("  converged!")
                break

        # store result
        fuelprice_by_station[station] = fuelprice_interval

    # run over all stations again, if necessary multiple times
    iteration = 0
    while nconverged < nstations:
        iteration += 1
        debug_print("### PHASE 2 # Iteration=%d ###" % iteration)
        prev_nconverged = nconverged # to check progress

        for station in stations:
            # skip station if converged
            if fuelprice_by_station[station].is_converged(): continue

            debug_print("STATION =", station)

            # get the current interval
            fuelprice_interval = fuelprice_by_station[station]

            for slug in considered_slugs_by_station[station]:
                debug_print("  slug =", slug)
                itemprice_min, itemprice_max = get_minmax(cache, slug)
                debug_print("    itemprice range = %.2f — %.2f" % (itemprice_min, itemprice_max))

                # keep track of which stations are compatible with the min/max itemprice
                # the goal is to reduce either of them to just one station
                stations_compatible_with_min = deepcopy( available_on_station_by_slug[slug] )
                stations_compatible_with_max = deepcopy( available_on_station_by_slug[slug] )

                # run over the other stations where this item is available
                for other_station in available_on_station_by_slug[slug]:
                    if other_station == station: continue
                    if not fuelprice_by_station[other_station].is_converged():
                        debug_print("    available on %s, but fuelprice not known" % other_station)
                        continue
                    # get other station's itemprice
                    other_fuelprice = fuelprice_by_station[other_station].midpoint()
                    other_station_entries = entries_by_station[other_station]
                    other_station_entries_by_slug = entries_by_key(other_station_entries, 'slug')
                    other_fpc = other_station_entries_by_slug[slug][0]['FuelPriceCoefficient']
                    other_itemprice = other_fpc * other_fuelprice
                    debug_print("    available on %s for %.2f" % (other_station, other_itemprice))
                    # now check compatibility
                    if not equals_approx(other_itemprice, itemprice_min):
                        stations_compatible_with_min.remove(other_station)
                    if not equals_approx(other_itemprice, itemprice_max):
                        stations_compatible_with_max.remove(other_station)

                # get this item's FPC on this station
                station_entries = entries_by_station[station]
                station_entries_by_slug = entries_by_key(station_entries, 'slug')
                fpc = station_entries_by_slug[slug][0]['FuelPriceCoefficient']

                fuelprice = None
                # is the min price only compatible with one station? (it will be the current station)
                if len(stations_compatible_with_min) == 1:
                    assert(stations_compatible_with_min.pop() == station)
                    itemprice = itemprice_min
                    fuelprice = itemprice_min / fpc
                    if not fuelprice_interval.contains(fuelprice):
                        debug_print("    WARNING: min price %.2f only compatible here" % itemprice_min)
                        debug_print("             but fuelprice %.2f not inside %s" % (fuelprice, fuelprice_interval))
                        fuelprice = None

                # same check for max price (unless resolved)
                if (not fuelprice) and len(stations_compatible_with_max) == 1:
                    assert(stations_compatible_with_max.pop() == station)
                    itemprice = itemprice_max
                    fuelprice = itemprice_max / fpc
                    if not fuelprice_interval.contains(fuelprice):
                        debug_print("    WARNING: max price %.2f only compatible here" % itemprice_max)
                        debug_print("             but fuelprice %.2f not inside %s" % (fuelprice, fuelprice_interval))
                        fuelprice = None

                if (not fuelprice): continue # move on to next item
                debug_print("    => itemprice here = %.2f" % itemprice)
                debug_print("  => fuelprice = %.2f" % fuelprice)

                # store result
                nconverged += 1
                fuelprice_interval.update(fuelprice, fuelprice)
                # don't need to consider more items
                break
        
        # check progress
        if nconverged == prev_nconverged:
            # no :(
            debug_print("no progress, giving up")
            break

    debug_print("resolved %d/%d stations after %d iterations" % (nconverged, nstations, iteration))

    # print result
    # sort stations by fuelprice midpoint
    for station in sorted(stations, key = lambda station: fuelprice_by_station[station].midpoint() ):
        fp = fuelprice_by_station[station]
        if fp.is_converged():
            fuel_string = '%.2f' % fp.midpoint()
        else:
            guess = fp.guess()
            if guess:
                fuel_string = '%.2f (guessed by frequency)' % guess
            else:
                fuel_string = str(fp)
            
        print( "%-12s%s" % ( shortname_by_station[station], fuel_string))

