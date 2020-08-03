# Tau Station utility scripts

Subdirectories contain manually collected information.
Each subdirectory is one system, and has further subdirectories for each station.
In each station directory, there are the files

* `fuel-price` contains a single line with the station's fuel price (at the collection point of time)
* `*.html` is the saved html for the different vendors at the station (not included in repo due to copyright worries)


## Scripts

`vendors-to-csv.py`

Arguments: a list of directories

Produces the file `tau-vendors.csv`, a spreadsheet with all the vendor item data from the given directories.


`get-fuel-price-strategy.py`

A horrible script that produces a strategy (in file `fuel-price-strategy.csv`) for estimating current
station fuel price (for stations that have vendors) based on items that are either available at a
single or at just two vendors.  Requires `tau-vendors.csv`.


`run-fuel-price-strategy.py`

Runs the strategy (read from `fuel-price-strategy.csv`) to estimate the current fuel price for each
station.  Pass `-v` to show verbose output about the reasoning.
**Note**: needs internet access, as it queries `https://taustation.space/item/...`, one
query per station.

