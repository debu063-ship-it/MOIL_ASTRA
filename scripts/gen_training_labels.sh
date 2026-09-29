#!/bin/bash
# Generate training_labels.geojson: 20 positives per mine (jitter <1km), 2x negatives
MINES="21.8333,80.2333,Balaghat 21.84,80.2311,Bharweli 21.97,80.47,Ukwa 21.684,79.727,Tirodi 21.4,79.25,Mansar 21.55,79.6941,DongriBuzurg"
OUT=data/raw/training_labels.geojson
echo '{"type":"FeatureCollection","name":"training_labels","crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}},"note":"Regenerated 2026-09-24 on corrected mine points from known_occurrences.csv. 20 positives per mine (Gaussian jitter ~1km), negatives sampled away from all mines.","features":[' > "$OUT"
first=1
# positives: 20 per mine, jitter up to ~0.01 deg
for m in $MINES; do
  IFS=',' read lat lon name <<< "$m"
  for i in $(seq 1 20); do
    # deterministic pseudo-random jitter in [-0.005, 0.005] (~550m)
    j1=$(awk -v s=$((RANDOM)) 'BEGIN{srand(s+1000*'"$i"');printf "%.6f",(rand()-0.5)*0.01}')
    j2=$(awk -v s=$((RANDOM)) 'BEGIN{srand(s+2000*'"$i"');printf "%.6f",(rand()-0.5)*0.01}')
    nlat=$(awk -v a=$lat -v b=$j1 'BEGIN{printf "%.6f",a+b}')
    nlon=$(awk -v a=$lon -v b=$j2 'BEGIN{printf "%.6f",a+b}')
    [ $first -eq 0 ] && echo "," >> "$OUT"
    first=0
    printf '{ "type": "Feature", "properties": { "lat": %s, "lon": %s, "label": 1, "type": "positive", "near_mine": "%s Mine" }, "geometry": { "type": "Point", "coordinates": [ %s, %s ] } }' "$nlat" "$nlon" "$name" "$nlon" "$nlat" >> "$OUT"
  done
done
# negatives: 240, sampled in study bbox away (>5km/0.05deg) from all mine points
n=0
while [ $n -lt 240 ]; do
  nlat=$(awk 'BEGIN{srand('"$RANDOM$n"');printf "%.6f",21.1+rand()*0.9}')
  nlon=$(awk 'BEGIN{srand('"$RANDOM$n"'7);printf "%.6f",79.2+rand()*1.3}')
  ok=1
  for m in $MINES; do
    IFS=',' read mlat mlon mname <<< "$m"
    d=$(awk -v a=$nlat -v b=$mlat -v c=$nlon -v e=$mlon 'BEGIN{dx=(c-e)*cos(21.6*3.14159/180)*111; dy=(a-b)*111; printf "%.2f", sqrt(dx*dx+dy*dy)}')
    if awk -v d=$d 'BEGIN{exit !(d<5)}'; then ok=0; break; fi
  done
  if [ $ok -eq 1 ]; then
    echo "," >> "$OUT"
    printf '{ "type": "Feature", "properties": { "lat": %s, "lon": %s, "label": 0, "type": "negative", "near_mine": null }, "geometry": { "type": "Point", "coordinates": [ %s, %s ] } }' "$nlat" "$nlon" "$nlon" "$nlat" >> "$OUT"
    n=$((n+1))
  fi
done
echo ']}' >> "$OUT"
echo "positives=$((6*20)) negatives=$n"
