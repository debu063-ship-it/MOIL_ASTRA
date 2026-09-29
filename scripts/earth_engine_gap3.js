// Fallback for Gap 3 only if the public Planetary Computer workflow cannot run.
// In the Earth Engine Code Editor, replace bbox with the project grid bbox plus 2 km.
// Export outputs use EPSG:4326 to match the project's lat/lon grid.
var bbox = [79.181, 21.082, 80.510, 22.063]; // approximate 2 km buffer
var region = ee.Geometry.Rectangle(bbox, 'EPSG:4326', false);
var start = '2024-01-01';
var end = '2024-04-01';

function maskS2(image) {
  var scl = image.select('SCL');
  var mask = scl.neq(3).and(scl.neq(8)).and(scl.neq(9))
      .and(scl.neq(10)).and(scl.neq(11));
  return image.updateMask(mask).divide(10000);
}

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterDate(start, end).filterBounds(region)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
  .map(maskS2).median().clip(region);
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1')
  .select('DEM').mosaic().clip(region);
var terrain = ee.Terrain.products(dem);
var ndvi = s2.normalizedDifference(['B8', 'B4']).rename('ndvi');
var hillshade = terrain.select('hillshade');

function exportCog(image, name) {
  Export.image.toDrive({
    image: image, description: 'MOIL_' + name, fileNamePrefix: name,
    region: region, scale: 30, crs: 'EPSG:4326', maxPixels: 1e13,
    fileFormat: 'GeoTIFF', formatOptions: {cloudOptimized: true}
  });
}
exportCog(dem.rename('elevation'), 'dem');
exportCog(terrain.select('slope'), 'slope');
exportCog(terrain.select('aspect'), 'aspect');
exportCog(hillshade, 'hillshade');
exportCog(s2.select(['B4','B3','B2']).rename(['B04','B03','B02']), 's2_truecolor');
exportCog(s2.select(['B8','B4','B3']).rename(['B08','B04','B03']), 's2_falsecolor');
exportCog(s2.select(['B2','B3','B4','B8','B11','B12'])
  .rename(['B02','B03','B04','B08','B11','B12']), 's2_reflectance');
exportCog(ndvi, 'ndvi');
