#!/usr/bin/env python3

import csv
import sys


def read_items(fname):
    """Read the vendor entries from CSV file with the given filename.
    Filter out everything not available for credits."""
    with open(fname) as fp:
        cr = csv.DictReader(fp)
        entries = []
        # go through all csv entries
        for entry in cr:
            # skip anything not available for credits
            if entry['Currency'] != 'credits': continue
            # augment with additional info
            entry['FuelPriceCoefficient'] = float(entry['ItemPrice']) / float(entry['FuelPrice'])
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


def remove_ambiguous(slug_entries):
    """If there are entries for a slug with different prices 
    on the same station, remove them."""
    entries_by_station = entries_by_key(slug_entries, 'Station')
    cleaned_entries = []
    for station, entries in entries_by_station.items():
        if len(entries)==1:
            cleaned_entries.extend(entries)
        else:
            prices = set(e['ItemPrice'] for e in entries)
            if len(prices)==1:
                cleaned_entries.extend(entries)
            else:
                print("ambiguous pricing: discarding %d entries for '%s' on %s"
                    % (len(entries), entries[0]['slug'], station))
    return cleaned_entries


class Strategy:
    def __init__(self, station):
        self.station = station
        self.slug = None
        self.fpc  = None
        self.parent = None
        self.parentfpc = 0.0
        self.level = 0
    def update(self, slug, fpc, parent=None, parentfpc=0.0, level=None):
        if level is None:
            level = self.level
        if (level < self.level) or (not self.fpc) or (fpc > self.fpc):
            self.slug = slug
            self.fpc = fpc
            self.parent = parent
            self.parentfpc = parentfpc
            self.level = level


if __name__ == '__main__':
    # read all entries
    entries = read_items("tau-vendors.csv")
    # first collect by slug
    slug_entries = entries_by_key(entries, 'slug')
    # find the slugs only available at a single vendor
    unique_slugs = [ slug for slug,se in slug_entries.items() if len(se)==1 ]
    # find the slugs only available at two vendors
    dual_slugs = [ slug for slug,se in slug_entries.items() if len(se)==2 ]
    # filter out ambiguous data
    slug_entries = { slug: remove_ambiguous(se)  for slug,se in slug_entries.items() }

    # initialize strategy via unique_slugs
    # if there are multiple unique_slugs on a station, select the more expensive one
    # hopefully resulting in more accurate estimates
    print("Initializing strategies from items with unique availability...")
    strategies = {}
    for slug in unique_slugs:
        entry = slug_entries[slug][0]
        station = entry['Station']
        fpc = entry['FuelPriceCoefficient']
        if not station in strategies: strategies[station] = Strategy(station)
        strat = strategies[station]
        strat.update(slug, fpc)
    print("  Resolved stations:", len(strategies))

    # extend strategy via dual_slugs
    # first get a list of all stations, and entries available per station
    print("Extending strategies from items with dual availability...")
    stations = set(e['Station'] for e in entries)
    station_entries = entries_by_key(entries, 'Station')
    niter = 0
    # iterate until done
    while True:
        nresolved_prev = len(strategies)
        for station in stations:
            if station in strategies: continue # already resolved
            # get all entries at this station, collected by slug
            sse = entries_by_key(station_entries[station], 'slug')
            # collect dual_slugs available at this station and at an already resolved station
            best_strategy = None
            for slug in dual_slugs:
                if not slug in sse: continue # not available at this station
                # get all entries for this slug
                se = slug_entries[slug]
                assert(len(se)==2)
                # remove the entries for this station
                se = [ e for e in se if e['Station'] != station ]
                assert(len(se)<2)
                if len(se)==0: continue # both entries at this station?!?
                # see if other station already resolved
                other_entry = se[0]
                other_station = other_entry['Station']
                if not other_station in strategies: continue # nope
                # YES!
                other_level = strategies[other_station].level
                other_fpc = float(other_entry['FuelPriceCoefficient'])
                entry = sse[slug][0]
                fpc = float(entry['FuelPriceCoefficient'])
                if best_strategy is None:
                    # first hit, just store it
                    best_strategy = Strategy(station)
                    best_strategy.update(slug, fpc, other_station, other_fpc, other_level+1)
                else:
                    # see if this strategy is better
                    # first, prefer strategies with smaller level
                    if other_level+1 > best_strategy.level: continue
                    if other_level+1 < best_strategy.level:
                        best_strategy.update(slug, fpc, other_station, other_fpc, other_level+1)
                    else:
                        # same level, prefer more expensive item
                        best_strategy.update(slug, fpc, other_station, other_fpc)
            # did we find any item for strategy?
            if best_strategy is None: continue # nope
            # yes, store the strategy
            strategies[station] = best_strategy

        print("  Resolved stations:", len(strategies))
        # any progress on strategies?
        nresolved = len(strategies)
        if nresolved == nresolved_prev:
            # no :(
            print("No progress, giving up")
            sys.exit(1)
        # finished?
        if nresolved == len(stations):
            break

    # all done, print result
    maxlevel = max(s.level for k,s in strategies.items())
    result = []
    for level in range(0,maxlevel+1):
        print("Phase", level)
        for station,strat in strategies.items():
            if strat.level != level : continue
            print("  %s, slug=%s fpc=%f, compare with %s" % (station, strat.slug, strat.fpc, strat.parent))
            result.append({
                'Station': station,
                'slug': strat.slug,
                'FuelPriceCoefficient': strat.fpc,
                'OtherStation': strat.parent,
                'OtherFPC': strat.parentfpc
                })
    with open("fuel-price-strategy.csv", "w") as fp:
        fieldnames = ['Station', 'slug', 'FuelPriceCoefficient', 'OtherStation', 'OtherFPC']
        cw = csv.DictWriter(fp, fieldnames)
        cw.writeheader()
        for line in result:
            cw.writerow(line)


