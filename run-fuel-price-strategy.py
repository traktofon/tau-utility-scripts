#!/usr/bin/env python3

import csv
from bs4 import BeautifulSoup
import requests
import sys

verbose = False


def read_strategy(fname):
    with open(fname) as fp:
        cr = csv.DictReader(fp)
        strats = list(cr)
    return strats


def get_minmax(slug):
    req = requests.get("https://taustation.space/item/" + slug)
    if req.status_code != 200:
        print("FATAL: failed to get data for '%s'" % slug)
        sys.exit(1)
    html = req.text
    phtml = BeautifulSoup(html, "lxml")
    body = phtml.body
    tag = body.find('span', attrs={'class':"currency"})
    children = list(tag.children)
    price_range = children[0]
    a,b = price_range.split(" - ")
    mn = float(a)
    mx = float(b)
    return (mn,mx)


def is_close(a,b):
    tolerance = 0.001
    return abs(a/b - 1.0) < tolerance


def run_strategy(strat, fuel_prices):
    station = strat['Station']
    slug = strat['slug']
    fpc = float(strat['FuelPriceCoefficient'])
    other_station = strat['OtherStation']
    other_fpc = float(strat['OtherFPC'])
    itemprice_min, itemprice_max = get_minmax(slug)
    if not other_station:
        # if no comparison station, price should be unique
        if itemprice_min != itemprice_max:
            print("FATAL: item price for '%s' is not unique but %f--%f" % (slug, itemprice_min, itemprice_max))
            sys.exit(1)
        itemprice = itemprice_min
        if verbose:
            print("%s: using '%s', price=%.2f, fpc=%.5f => fuelprice=%.2f"
                % (station, slug, itemprice, fpc, itemprice / fpc))
    else:
        # estimate the item price on the comparison station
        if verbose:
            print("%s: using '%s', price=%.2f-%.2f, fpc=%.5f"
                % (station, slug, itemprice_min, itemprice_max, fpc))
            blank = " " * len(station)
        itemprice_other = fuel_prices[other_station] * other_fpc
        if verbose:
            print("%s  comparing with %s with fpc=%.5f, estimated price %.2f"
                % (blank, other_station, other_fpc, itemprice_other))
        if is_close(itemprice_other, itemprice_min):
            itemprice = itemprice_max
            if verbose:
                print("%s  other station's price matches minimum => price=%.2f => fuelprice=%.2f"
                    % (blank, itemprice, itemprice / fpc))
        elif is_close(itemprice_other, itemprice_max):
            itemprice = itemprice_min
            if verbose:
                print("%s  other station's price matches maximum => price=%.2f => fuelprice=%.2f"
                    % (blank, itemprice, itemprice / fpc))
        else:
            print("FATAL: other station's item price for slug '%s' is %f, can't reconcile with %f--%f"
                % (slug, itemprice_other, itemprice_min, itemprice_max))
            sys.exit(1)
    # item price resolved, now calcuate fuel price
    fp = itemprice / fpc
    # store result
    fuel_prices[station] = fp


if __name__ == '__main__':
    # verbose flag?
    if len(sys.argv)>1 and sys.argv[1]=='-v':
        verbose = True
    strategies = read_strategy("fuel-price-strategy.csv")
    fuel_prices = {}
    for strat in strategies:
        run_strategy(strat, fuel_prices)
    # print result
    if verbose: print()
    stations_ascending = sorted(fuel_prices.keys(), key = lambda k: fuel_prices[k])
    for station in stations_ascending:
        print("%8.2f  %s" % (fuel_prices[station], station))

