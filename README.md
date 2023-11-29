Archiving as Tau Station has closed.


# Tau Station utility scripts

Subdirectories contain manually collected information.
Each subdirectory is one system, and has further subdirectories for each station.
In each station directory, there are the files

* `fuel-price` contains a single line with the station's fuel price (at the collection point of time)
* `*.html` is the saved html for the different vendors at the station (not included in repo due to copyright worries)


## Scripts

### Vendors

`vendors-to-csv.py`

Arguments: a list of directories

Produces the file `tau-vendors.csv`, a spreadsheet with all the vendor item data from the given directories.


`get-fuel-price-strategy.py`

A horrible script that produces a strategy (in file `fuel-price-strategy.csv`) for estimating current
station fuel price (for stations that have vendors) based on items that are either available at a
single or at just two vendors.  Requires `tau-vendors.csv`.


`get-fuel-price-strategy-from-tracker.py`

Similar, but doesn't require `tau-vendors.csv`. Instead pricing information is pulled from
the Tau Tracker service. Requires internet access.


`run-fuel-price-strategy.py`

Runs the strategy (read from `fuel-price-strategy.csv`) to estimate the current fuel price for each
station.  Pass `-v` to show verbose output about the reasoning.
**Note**: needs internet access, as it queries `https://taustation.space/item/...`, one
query per station.


### Items

`vendor-items.py`

Extracts item slugs from `tau-vendors.csv` and prints them to stdout, one slug per line.


`tauhead-items.py`

Extracts item slugs from the JSON file `tauhead-items.json` (not included in this repo),
which can be obtained from [Tauhead](https://tauhead.com).  Optional argument is the
path to the JSON file. Prints to stdout, one slug per line.


`changelog-items.py`

Extracts item slugs from links found in the changelogs from the
[Taustation Blog](https://taustation.space/blog/). Argument is the path to the
HTML file with the changelog. Prints to stdout, one slug per line.


`get-items.sh`

Reads item slugs from stdin, and downloads the item page for each slug into
the subdirectory `items` (a rate limit is applied). Already existing items won't
be downloaded again, so to force updates you should remove the `.html` files from
the `items` directory.


`items-to-csv.py`

Must be run inside the `items` subdirectory. Produces one CSV file for each
item category, e.g. `Weapon.csv`, `Armor.csv`, etc.  The fields included in the
CSV depend on the category.  Note: for the Armor category, the fields named
"damage" actually refer to the defense stats.

