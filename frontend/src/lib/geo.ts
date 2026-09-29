const MEAN_EARTH_RADIUS_METERS = 6_371_008.8;

function ringAreaSquareMeters(ring: number[][]): number {
  if (ring.length < 3) return 0;

  let sum = 0;
  for (let index = 0; index < ring.length; index += 1) {
    const current = ring[index];
    const next = ring[(index + 1) % ring.length];
    const longitudeDelta = ((next[0] - current[0]) * Math.PI) / 180;
    const currentLatitude = (current[1] * Math.PI) / 180;
    const nextLatitude = (next[1] * Math.PI) / 180;
    sum += longitudeDelta * (2 + Math.sin(currentLatitude) + Math.sin(nextLatitude));
  }

  return Math.abs((sum * MEAN_EARTH_RADIUS_METERS ** 2) / 2);
}

/** Calculates the geodesic surface area of a GeoJSON Polygon in hectares. */
export function calculatePolygonAreaHectares(rings: number[][][]): number {
  if (!rings.length) return 0;

  const outerRingArea = ringAreaSquareMeters(rings[0]);
  const holeArea = rings.slice(1).reduce((total, ring) => total + ringAreaSquareMeters(ring), 0);
  return Math.max(0, (outerRingArea - holeArea) / 10_000);
}
