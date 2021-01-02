#!/bin/bash

mkdir -p 'items'

while read slug; do
   [ -f "items/$slug.html" ] && continue
   if wget --quiet "https://taustation.space/item/$slug" -O "items/$slug.html"; then
      sleep 0.5
      echo $slug
   else
      rm -f "items/$slug.html"
      echo "FAILED: $slug" >&2
   fi
done
