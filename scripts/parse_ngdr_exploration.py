# -*- coding: utf-8 -*-
"""
Parse the two downloaded NGDR exploration packages into clean, analysis-ready files.

Inputs (already on disk):
  data/external/exploration/ngdr_registered_downloads/Gudma_CRO-23394-2017/*.xlsx
  data/external/exploration/ngdr_registered_downloads/Western_Ukwa_CRO-23290-2016/*.xlsx
  data/external/geology/ngdr/downloads/<NUID>/extracted/*_gdb/*.gdb   (ESRI File GDBs)

Outputs -> data/external/exploration/ngdr_parsed/
  boreholes_collars.csv        all collars (GDB + workbook RLs merged)
  borehole_assays.csv          real core-sample assays (Mn/Fe/SiO2/P, intervals)
  borehole_lithologs.csv       summarized lithology intervals per borehole
  resource_estimates.csv       GSI resource blocks (thickness, Mn%, SG, volume, tonnage, category)
  structure_measurements.csv   strike/dip (planes) + strike/plunge (lines)
  lithology_polygons.geojson   mapped lithology polygons from both GDBs
  exploration_boreholes.geojson  collar points (for dashboard map layer)
  parse_summary.txt            human-readable summary
"""
import os, re, glob, json
import pandas as pd
import openpyxl
import pyogrio

ROOT = "."
DL = os.path.join(ROOT, "data", "external", "exploration", "ngdr_registered_downloads")
GDB_BASE = os.path.join(ROOT, "data", "external", "geology", "ngdr", "downloads")
OUT = os.path.join(ROOT, "data", "external", "exploration", "ngdr_parsed")
os.makedirs(OUT, exist_ok=True)

def num(v):
    """Robust numeric parse from messy workbook cells."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s in {"-", "---", "None"}:
        return None
    s = s.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None

def clean(v):
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None

def col(r, i):
    """Index into a possibly-short row, returning None past the end."""
    return r[i] if i < len(r) else None

wb_paths = {
    "Gudma": glob.glob(os.path.join(DL, "Gudma_CRO-23394-2017", "*.xlsx"))[0],
    "Western Ukwa": glob.glob(os.path.join(DL, "Western_Ukwa_CRO-23290-2016", "*.xlsx"))[0],
}

gdb_paths = {
    "Western Ukwa": os.path.join(GDB_BASE, "CRO-23290-2016", "extracted", "plate3_dm_gdb",
                                 "CRO-23290-2016-PLATE-3-DM.gdb"),
    "Western Ukwa LSM": os.path.join(GDB_BASE, "CRO-23290-2016", "extracted", "plate4_lsm_gdb",
                                     "CRO-23290-2016-PLATE-4-LSM.gdb"),
    "Gudma": os.path.join(GDB_BASE, "CRO-23394-2017", "extracted", "plate7_dm_gdb",
                          "CRO-23394-2017-PLATE-7-DM.gdb"),
}

def sheet_rows(path, name):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[name]
    rows = [[c for c in r] for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows

# ---------------------------------------------------------------- 1. ASSAYS
assay_frames = []

# --- Gudma Table-V: SrNo | Borehole No | From | To | Sample No | Lithology | Mn%
rows = sheet_rows(wb_paths["Gudma"], "Table-V")
for r in rows[2:]:
    if r[1] is None or clean(r[1]) in ("Check Samples",):
        continue
    assay_frames.append({
        "block": "Gudma", "nuid": "CRO-23394-2017", "source_sheet": "Table-V",
        "borehole": clean(r[1]), "from_m": num(r[2]), "to_m": num(r[3]),
        "sample_no": clean(r[4]), "lithology": clean(r[5]), "mn_pct": num(r[6]),
        "fe_pct": None, "sio2_pct": None, "p_pct": None, "sg": None,
    })

# --- Gudma Annexure-V: SrNo | Sample No | Lat | Long | SiO2 | Fe2O3 | P2O5 | MnO | TiO2 | Mn% | Si% | Fe% | P% | Ti%
rows = sheet_rows(wb_paths["Gudma"], "Annexure-V")
for r in rows[2:]:
    sn = clean(r[1])
    if not sn:
        continue
    m = re.search(r"GDBH-\s*(\d+)", sn, re.I)
    bh = f"GDBH-{m.group(1)}" if m else None
    assay_frames.append({
        "block": "Gudma", "nuid": "CRO-23394-2017", "source_sheet": "Annexure-V",
        "borehole": bh, "from_m": None, "to_m": None,
        "sample_no": sn, "lithology": None,
        "mn_pct": num(r[9]), "fe_pct": num(r[11]), "sio2_pct": num(r[10]),
        "p_pct": num(r[12]), "sg": None,
        "lat": num(r[2]), "lon": num(r[3]),
    })

# --- Ukwa ANNEXURE-VIII(B): SrNo | Borehole No | S No | From | To | True Width | Description | SG | Mn% | Fe% | SiO2% | P%
rows = sheet_rows(wb_paths["Ukwa"] if "Ukwa" in wb_paths else wb_paths["Western Ukwa"], "ANNEXURE-VIII(B)")
cur_bh = None
for r in rows[2:]:
    b = clean(r[1])
    if b and re.match(r"UKH|UKBH|GSU|GUG", b):
        cur_bh = re.sub(r"\s+", "", b)
    if cur_bh is None or r[3] is None:
        continue
    desc = clean(r[6]) or ""
    if desc.lower().startswith("total"):
        continue
    assay_frames.append({
        "block": "Western Ukwa", "nuid": "CRO-23290-2016", "source_sheet": "ANNEXURE-VIII(B)",
        "borehole": cur_bh, "from_m": num(r[3]), "to_m": num(r[4]),
        "sample_no": clean(r[2]), "lithology": desc,
        "mn_pct": num(r[8]), "fe_pct": num(r[9]), "sio2_pct": num(r[10]),
        "p_pct": num(r[11]), "sg": num(r[7]),
        "true_width_m": num(r[5]),
    })

assays = pd.DataFrame(assay_frames)
for c in ("lat", "lon", "true_width_m"):
    if c not in assays.columns:
        assays[c] = None
assays = assays[["block", "nuid", "borehole", "from_m", "to_m", "true_width_m", "sample_no",
                 "lithology", "mn_pct", "fe_pct", "sio2_pct", "p_pct", "sg", "lat", "lon", "source_sheet"]]
assays.to_csv(os.path.join(OUT, "borehole_assays.csv"), index=False)
print(f"assays: {len(assays)} rows")

# ------------------------------------------------------- 2. RESOURCE BLOCKS
res_frames = []

# --- Ukwa Table-18 (cross-section method)
rows = sheet_rows(wb_paths["Western Ukwa"], "Table-18")
last_bh, last_sec = None, None
for r in rows[2:]:
    sec = clean(col(r, 1))
    bh = clean(col(r, 2))
    if sec:
        last_sec = sec
    if bh:
        last_bh = re.sub(r"\s+", "", bh)
    if last_bh is None:
        continue
    # inferred continuation rows have no angle; keep any row with thickness+volume
    if num(col(r, 4)) is None and num(col(r, 14)) is None:
        continue
    res_frames.append({
        "block": "Western Ukwa", "nuid": "CRO-23290-2016", "method": "cross-section",
        "section": last_sec, "borehole": last_bh,
        "angle_lode_deg": clean(col(r, 3)), "app_thickness_m": num(col(r, 4)), "true_thickness_m": num(col(r, 5)),
        "dip_length_m": num(col(r, 8)), "strike_length_m": num(col(r, 11)), "mn_pct": num(col(r, 12)),
        "sg": num(col(r, 13)), "volume_m3": num(col(r, 14)), "tonnage_t": num(col(r, 15)),
        "category": clean(col(r, 16)),
    })

# --- Ukwa Table 2 (probable partial western block)
rows = sheet_rows(wb_paths["Western Ukwa"], "Table 2")
for r in rows[2:]:
    if r[2] is None:
        continue
    res_frames.append({
        "block": "Western Ukwa", "nuid": "CRO-23290-2016", "method": "probable-partial",
        "section": clean(r[1]), "borehole": re.sub(r"\s+", "", str(r[2])),
        "angle_lode_deg": clean(r[8]), "app_thickness_m": num(r[11]), "true_thickness_m": num(r[11]),
        "dip_length_m": num(r[10]), "strike_length_m": num(r[3]), "mn_pct": None,
        "sg": 3.92, "volume_m3": num(r[12]), "tonnage_t": (num(r[12]) or 0) * 3.92,
        "category": "Probable",
    })

# --- Gudma Table-X (gross resource, dip-length method)
rows = sheet_rows(wb_paths["Gudma"], "Table-X")
for r in rows[2:]:
    if r[2] is None:
        continue
    res_frames.append({
        "block": "Gudma", "nuid": "CRO-23394-2017", "method": "cross-section",
        "section": clean(r[1]), "borehole": re.sub(r"\s+", "", str(r[2])),
        "angle_lode_deg": clean(r[3]), "app_thickness_m": num(r[4]), "true_thickness_m": num(r[5]),
        "dip_length_m": num(r[6]), "strike_length_m": num(r[9]), "mn_pct": num(r[10]),
        "sg": num(r[11]), "volume_m3": num(r[12]), "tonnage_t": num(r[13]),
        "category": "Inferred (UNFC 333)",
    })

res = pd.DataFrame(res_frames)
res.to_csv(os.path.join(OUT, "resource_estimates.csv"), index=False)
print(f"resource blocks: {len(res)} rows")

# --------------------------------------------------------------- 3. LITHOLOGS
# Ukwa Table-10 / ANNEXURE-IV: borehole header row + interval rows (forward-fill borehole)
litho_frames = []
for sheet in ("Table-10", "ANNEXURE-IV"):
    rows = sheet_rows(wb_paths["Western Ukwa"], sheet)
    cur_bh, cur_rl = None, None
    for r in rows[2:]:
        b = clean(col(r, 1))
        if b and re.match(r"UKBH|UKH|GSU|GUG", b, re.I):
            cur_bh = re.sub(r"\s+", "", b)
            cur_rl = num(col(r, 3))
        if cur_bh is None:
            continue
        fm, to = num(col(r, 8)), num(col(r, 9))
        if fm is None or to is None:
            continue
        litho_frames.append({
            "block": "Western Ukwa", "nuid": "CRO-23290-2016", "borehole": cur_bh,
            "collar_rl_m": cur_rl, "from_m": fm, "to_m": to,
            "lithology": clean(col(r, 10)), "ore_notes": clean(col(r, 11)),
            "source_sheet": sheet,
        })

# Gudma: no litholog sheet in workbook; host-rock context from Table-V lithology
# (kept in assays). Add note in summary.

lithos = pd.DataFrame(litho_frames)
lithos.to_csv(os.path.join(OUT, "borehole_lithologs.csv"), index=False)
print(f"litholog intervals: {len(lithos)} rows")

# ------------------------------------------------------------------ 4. GDBs
# 4a. Borehole collars
collar_frames = []
gdb_collar_layer = {
    "Western Ukwa": ("Borehole_Points_DM", "RL_COLLAR_in_meter"),
    "Gudma": ("Borehole_Points_DM", "RL_COLLAR_in_meter_1"),
}
for blk, (layer, rlcol) in gdb_collar_layer.items():
    gdf = pyogrio.read_dataframe(gdb_paths[blk], layer=layer)
    for _, row in gdf.iterrows():
        rl_raw = clean(row.get(rlcol))
        rl = num(rl_raw)
        if rl is not None and rl > 0:
            rl_clean = rl if rl < 5000 else None  # '597m' parsed by num() fine; guard absurd
        else:
            rl_clean = None
        collar_frames.append({
            "block": blk,
            "nuid": "CRO-23290-2016" if "Ukwa" in blk else "CRO-23394-2017",
            "source": "gdb",
            "borehole": clean(row.get("BOREHOLE_NAME")),
            "lat": float(row.geometry.y), "lon": float(row.geometry.x),
            "collar_rl_m": rl_clean,
            "total_depth_m": num(row.get("LENGTH_in_meter")) or None,
            "toposheet": clean(row.get("TOPOSHEET_")) or clean(row.get("TOPOSHEET_NO")),
        })

# Enrich Ukwa collars with workbook R.L. + total depth from Table-10 headers
rl_map, td_map = {}, {}
rows = sheet_rows(wb_paths["Western Ukwa"], "Table-10")
for r in rows[2:]:
    b = clean(col(r, 1))
    if b and re.match(r"UKBH|UKH", b):
        bh = re.sub(r"\s+", "", b)
        rl_map[bh] = num(col(r, 3))
        td_map[bh] = num(col(r, 6))
# Historical holes (UKH/GSU/GUG) from ANNEXURE-IV headers
rows = sheet_rows(wb_paths["Western Ukwa"], "ANNEXURE-IV")
for r in rows[2:]:
    b = clean(col(r, 1))
    if b and re.match(r"UKH|GSU|GUG", b, re.I) and re.sub(r"\s+", "", b) not in rl_map:
        bh = re.sub(r"\s+", "", b)
        rl_map[bh] = num(col(r, 3))
        td_map[bh] = num(col(r, 6))

for c in collar_frames:
    if c["block"] == "Western Ukwa":
        bh = c["borehole"]
        if c["collar_rl_m"] is None and bh in rl_map and rl_map[bh]:
            c["collar_rl_m"], c["source_rl"] = rl_map[bh], "workbook"
        if not c["total_depth_m"] and bh in td_map:
            c["total_depth_m"] = td_map[bh]

# Gudma: RL from Table-10-style info is absent in workbook (only GDBH RLs in GDB already)
collars = pd.DataFrame(collar_frames)
collars.to_csv(os.path.join(OUT, "boreholes_collars.csv"), index=False)
print(f"collars: {len(collars)} rows")

# 4b. Structure measurements
struct_frames = []
struct_layers = {
    "Western Ukwa": [("Oriented_Structure_Plane_DM", "plane"),
                     ("Oriented_Structure_Line_DM", "line")],
}
for blk, layers in struct_layers.items():
    for layer, kind in layers:
        gdf = pyogrio.read_dataframe(gdb_paths[blk], layer=layer)
        for _, row in gdf.iterrows():
            struct_frames.append({
                "block": blk, "kind": kind, "point_type": clean(row.get("POINT_TYPE")),
                "strike_deg": num(row.get("STRIKE")),
                "dip_deg": num(row.get("DIP_AMOUNT")),
                "dip_direction_deg": num(row.get("DIP_DIRECTION")),
                "plunge_direction_deg": num(row.get("PLUNGE_DIRECTION")),
                "plunge_deg": num(row.get("PLUNGE_AMOUNT")),
                "remarks": clean(row.get("REMARKS")),
                "lat": float(row.geometry.y), "lon": float(row.geometry.x),
            })
struct = pd.DataFrame(struct_frames)
struct.to_csv(os.path.join(OUT, "structure_measurements.csv"), index=False)
print(f"structure measurements: {len(struct)} rows")

# 4c. Lithology polygons -> GeoJSON
import shapely.geometry as sg

def geom_to_geojson(geom):
    def feat(g):
        mapping = sg.mapping(g)
        return mapping
    return feat

feats = []
for blk, path in gdb_paths.items():
    for layer in pyogrio.list_layers(path)[:, 0]:
        if not layer.startswith("Lithology"):
            continue
        gdf = pyogrio.read_dataframe(path, layer=layer)
        for _, row in gdf.iterrows():
            props = {
                "block": blk,
                "nuid": "CRO-23290-2016" if "Ukwa" in blk else "CRO-23394-2017",
                "layer": layer,
                "age": clean(row.get("STRATIGRAPHIC_AGE")),
                "supergroup": clean(row.get("SUPERGROUP")),
                "group": clean(row.get("GROUP_NAME")),
                "unit": clean(row.get("LITHOLOGICAL_UNIT")),
                "major_mineral": clean(row.get("MAJOR_MINERAL")),
                "remarks": clean(row.get("REMARKS")),
            }
            g = row.geometry
            if g is None:
                continue
            feats.append({
                "type": "Feature",
                "properties": props,
                "geometry": g.__geo_interface__,
            })
fc = {"type": "FeatureCollection", "features": feats}
with open(os.path.join(OUT, "lithology_polygons.geojson"), "w", encoding="utf-8") as fh:
    json.dump(fc, fh)
print(f"lithology polygons: {len(feats)} features")

# 4d. Collar points GeoJSON (for dashboard)
feats = [{
    "type": "Feature",
    "properties": {k: v for k, v in r.items() if k not in ("lat", "lon") and v is not None},
    "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
} for r in collars.to_dict(orient="records")]
with open(os.path.join(OUT, "exploration_boreholes.geojson"), "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "features": feats}, fh)
print(f"collar geojson: {len(feats)} features")

# ------------------------------------------------------------------ 5. SUMMARY
lines = []
lines.append("NGDR exploration parse summary (generated %s)" % pd.Timestamp.now().isoformat(timespec="seconds"))
lines.append("")
lines.append("== Assays ==")
ok = assays[assays.mn_pct.notna()]
lines.append(f"rows with Mn%%: {len(ok)}  (Gudma: {(ok.block=='Gudma').sum()}, W. Ukwa: {(ok.block=='Western Ukwa').sum()})")
lines.append(f"Mn%% range: {ok.mn_pct.min():.2f} - {ok.mn_pct.max():.2f}, mean {ok.mn_pct.mean():.2f}")
ore = ok[ok.mn_pct >= 15]
lines.append(f"ore-grade samples (Mn>=15%%): {len(ore)}, mean {ore.mn_pct.mean():.2f}%%" if len(ore) else "no ore-grade samples")
lines.append("")
lines.append("== Resource blocks (GSI estimates) ==")
lines.append(f"total rows: {len(res)}; total tonnage: {res.tonnage_t.sum():,.0f} t")
for (blk, meth), g in res.groupby(["block", "method"]):
    lines.append(f"  {blk} / {meth}: {len(g)} blocks, {g.tonnage_t.sum():,.0f} t")
lines.append("")
lines.append("== Collars ==")
lines.append(collars.groupby("block").borehole.count().to_string())
lines.append("")
lines.append("== Litholog intervals ==")
lines.append(f"{len(lithos)} intervals across {lithos.borehole.nunique()} boreholes")
lines.append("")
lines.append("== Structure ==")
lines.append(struct.groupby(["block", "kind"]).size().to_string())
with open(os.path.join(OUT, "parse_summary.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("\n".join(lines))
