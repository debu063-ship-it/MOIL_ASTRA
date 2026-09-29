# MOIL mine and lease reserves dataset

Source: IBM, *Indian Minerals Yearbook 2024*, Manganese Ore chapter, Table 2,
printed pages 66–67. Official PDF:
https://ibm.gov.in/writereaddata/files/177426215469c1178a48453IMYB_2024_EBookFinal.pdf

Extracted rows are in `data/external/exploration/ibm_moil_reserves_2024.csv`.
They contain reported MOIL mine/lease areas, UNFC resource tonnages, and where
provided, 2023–24 drilling counts and metres. The `unfc_tonnes` field stores
semicolon-separated `UNFC code:tonnes` pairs. Empty fields indicate the source
table did not report that value.

This is a public mine/lease summary, **not a 3D geological or block model**. It
does not provide collar coordinates, downhole intervals, grades, or block
geometry. The target 3D model remains unavailable in this public source.
