#!/usr/bin/env python3

import sys
import csv
import re
from bs4 import BeautifulSoup
from glob import glob

def extract_stat(stats, cls):
    tag  = stats.find('li', attrs={'class':cls})
    if tag:
        span = tag.find('span')
        return span.text
    else:
        return None

def extract_boost(stats, what):
    for tag in stats.findAll('li', attrs={'class':'strength'}):
        if tag.text.startswith(what):
            span = tag.find('span')
            return span.text
    return None

def extract_food_stats(item):
    # "This food gives Colonists a small Stamina boost for 1 segment"
    match = re.search(r"This food gives (\w+)s a (\w+) (\w+) boost for (\d+) segment", item['desc'])
    if match:
        genotype, strength, stat, duration = match.groups()
        item['target-genotype'] = genotype
        item['effect-size'] = strength
        item['affected-stat'] = stat
        item['duration-segments'] = duration

def slurp_item(itemfile):
    f = open(itemfile)
    itemhtml = f.read()
    f.close()
    phtml = BeautifulSoup(itemhtml, 'lxml')
    body = phtml.body
    item_header = body.find('div', attrs = {'class': 'item-detailed-header'})
    item_stats  = body.find('div', attrs = {'class': 'item-detailed-stats'})
    item_desc   = body.find('p', attrs = {'class': 'item-detailed-description'})
    item = {
        'slug'  : itemfile[:-5],
        'name'  : item_header.find('h1').text,
        'desc'  : item_desc.text,
        'rarity': extract_stat(item_stats, 'rarity common')
    }
    for stat in [ 'weight', 'type', 'tier', 'accuracy', 'hand-to-hand', 'range', 'weapon_type', 'piercing-damage', 'impact-damage', 'energy-damage' ]:
        item[stat] = extract_stat(item_stats, stat)
    for boost in [ 'Strength Boost', 'Agility Boost', 'Stamina Boost', 'Intelligence Boost', 'Social Boost', 'Base Toxicity' ]:
        field = boost.lower().replace(' ', '-')
        item[field] = extract_boost(item_stats, boost)
    if item['type']=='Food':
        extract_food_stats(item)
    return item


if __name__ == '__main__':
    items = [slurp_item(f) for f in glob('*.html')]
    types = set([item['type'] for item in items])
    fields1 = ['name', 'tier', 'rarity', 'type']
    fields3 = ['weight', 'slug', 'desc']
    for typ in types:
        if typ=='Weapon':
            fields2 = ['range', 'hand-to-hand', 'weapon_type', 'piercing-damage', 'impact-damage', 'energy-damage', 'accuracy']
        elif typ=='Armor':
            fields2 = ['piercing-damage', 'impact-damage', 'energy-damage']
        elif typ=='Medical':
            fields2 = [ 'strength-boost', 'agility-boost', 'stamina-boost', 'intelligence-boost', 'social-boost', 'base-toxicity' ]
        elif typ=='Food':
            fields2 = [ 'target-genotype', 'affected-stat', 'effect-size', 'duration-segments' ]
        else:
            fields2 = []
        fieldnames = fields1 + fields2 + fields3
        csvfilename = typ + '.csv'
        with open(csvfilename, 'w') as cf:
            cw = csv.DictWriter(cf, fieldnames, extrasaction='ignore')
            cw.writeheader()
            for item in filter(lambda i: i['type']==typ, items):
                cw.writerow(item)

