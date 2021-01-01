#!/bin/bash

mkdir -p 'items'

while read slug; do
   [ -f "items/$slug.html" ] && continue
   wget --quiet "https://taustation.space/item/$slug" -O "items/$slug.html" && sleep 0.5
   echo $slug
done
