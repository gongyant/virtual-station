# Draft: Data and experimental protocol

The CA-discharge v1.0 GeoPackage was retrieved from Zenodo record8147591 and verified against its published MD5. It is distributed under CC-BY4.0. Its station, basin, discharge and quality-flag layers were inspected separately; long-term norm discharge was not treated as a historical time series. Marti et al. (2023) describe the yearbook provenance and preprocessing. All six records labeled KAZ lie outside the selected basin. The acquired Sayram–Tasarik monthly series therefore supplies no target-basin training labels. Source quality flags and possible preprocessing were retained, rather than describing every numeric entry as an untouched daily observation.

The official Kazakhstan bulletin supplied reported monthly figures for March2021–February2024. We transcribed the printed table without correction, verified numeric entries against independently extracted PDF word positions, mapped water-year labels to calendar months and checked printed seasonal and annual sums using tolerances derived solely from displayed precision. The Lepsy records with internal inconsistencies were retained as rejected evidence. Public document availability did not establish unrestricted model-training or redistribution rights. Matching five named sites provisionally to the coordinate catalogue did not certify station codes, positions or relocation histories.

Data admission precedes model evaluation. For the prospective primary study, the design proposes at least eight admitted gauges in three predefined tributary groups, each with at least eight complete calendar years. These are design choices, not empirically established thresholds. Short, unresolved or imputed records cannot be silently promoted to the primary set. All models must use identical legal station-month support. Negative scores, source conflicts and failed folds must remain visible.

This project has already inspected European temporal and spatial development results. Its known-gauge memory-model improvement is not evidence of Kazakhstan ungauged accuracy. The unsuccessful P7-SL variant, the negative final time block of P7-MEM, and weak macro-region donor transfer must accompany positive results. The Kazakhstan P10 design has not been executed, and no truly independent future target set has yet been obtained.

## Data Availability — draft

CA-dischargev1.0 is available from https://doi.org/10.5281/zenodo.8147591 under its deposited CC-BY4.0 terms. HydroRIVERS and HydroBASINS are reused under the HydroSHEDS terms and required attribution, accessible through https://www.hydrosheds.org/. Official bulletin material was accessed through https://www.kazhydromet.kz/en/water-resources/. Its data-use and redistribution scope remains to be clarified with the provider; local extraction is not a grant to republish an entire third-party archive. The generated GIS proxies, source audit and protocol are preserved locally with source hashes; no public repository deposition or new DOI is claimed. Restricted teacher data are not included.

## Code availability — draft

P9B acquisition, geometry, transcription and verification scripts are preserved in the local delivery code directory with SHA256 manifests. No public repository URL has been assigned. Candidate driver values and P10 model outputs do not yet exist and are not described as available.
