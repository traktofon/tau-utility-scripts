#!/usr/bin/env python3

import sys
from bs4 import BeautifulSoup

if __name__ == '__main__':
    changelogfile = sys.argv[1]
    f = open(changelogfile)
    html = f.read()
    f.close()
    phtml = BeautifulSoup(html, "lxml")
    body = phtml.body
    for a in body.findAll("a"):
        try:
            href = a.attrs['href']
        except:
            continue
        if href.find("taustation.space/item/") >= 0:
            slug = href.split('/')[-1]
            print(slug)

