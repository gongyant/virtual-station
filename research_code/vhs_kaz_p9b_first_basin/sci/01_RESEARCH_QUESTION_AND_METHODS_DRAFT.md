# Manuscript working draft — Methods

**Research question:** Can meteorological memory gains at calibrated gauges survive target-label exclusion and geographically structured validation, and what data evidence is required before admitting a virtual gauge in a transboundary endorheic basin?

## Draft: completed data preparation

We separated temporal reconstruction at previously calibrated gauges from prediction at locations whose discharge labels are excluded. The Kazakhstan pilot covers the Balkhash–Alakol water-management basin. Public river and sub-basin geometry was processed independently of the frozen European model experiments. We did not fit or select a hydrological model during this data-admission stage.

The P9A HydroRIVERS network and station crosswalk were verified against their SHA256 manifests. The 49 selected coordinates remained provisional matches rather than certified station identities. Original station codes, names, coordinate sources, nearest source reach identifiers and match distances were retained. Cross-source corroboration used manually reviewed river and locality names and, where available, independently published catchment areas. A documentary statistics period was not treated as an acquired discharge series, a commissioning date or a migration history. Conflicting areas remained explicit source conflicts.

Directed river relationships were derived from unique HydroRIVERS reach identifiers and their downstream links, following the hydrographic framework described by Lehner and Grill (2013). Distances included the within-reach distance between the upstream endpoint and each snapped site. A path from a headwater to a site was distinguished from the summed lengths of all connected upstream branches. Transboundary upstream geometry was retained. Scalar downstream routing was not assumed to establish actual bifurcations, diversions, reservoirs or changing lake connections.

Because a complete, compatible hydrologically conditioned DEM and flow-direction raster was unavailable, we did not label the candidate catchments exact. We assembled the HydroBASINS L12 upstream union terminating at each reach-assigned source sub-basin outlet. An interior river point can have a different watershed from that outlet. We therefore reported the unresolved host-unit area, whether the source host polygon contains the point, source-area discrepancies, duplicated proxies and cross-border area. Removing the host polygon does not generally establish a strict lower bound on the point catchment, because tributaries can join within that unit.

Thirty candidate records comprise the 20 original main-chain points and ten alternatives selected from different directed tributary paths using fixed geometry rules. Neither a candidate count nor a valid polygon constituted hydrological admission. Nominal ERA5-Land grid-cell intersections were calculated for outlet proxies only. The resulting normalized area weights are preparatory objects and were not used as certified point-catchment forcings or to train a model. ERA5-Land is a reanalysis product rather than a local gauge observation (Muñoz-Sabater et al., 2021).

## Draft: prospective P10 analysis, not yet executed

P10 will compare donor climatology, geographic donor transfer, area-normalized donor transfer, static-and-climate similarity transfer and, conditional on data support, a low-dimensional shared model. All target discharge, target-derived statistics and target seasonal templates will be removed before training and tuning. European station-specific coefficients will not be transferred as if calibrated for Kazakhstan. Training-fold transformations and donor selection will use eligible donor data only.

The design distinguishes leave-one-gauge-out, nested-donor exclusion, tributary-group masking and forward year blocks. A future independent label set must be held by a separate custodian, with predictions sealed before scoring. Reported 2021–2024 values and aggregates inspected in this stage cannot be relabeled unseen confirmation data. NSE, KGE and their components will be reported with explicit baselines; they do not share an interchangeable zero-skill interpretation (Knoben et al., 2019). Related gauges and seasons will not be treated as independent basin replicates.

## 中文核对

以上前半段描述本轮实际处理，P10部分明确使用将来时。没有宣称模型已完成哈萨克斯坦验证，没有将出口代理称点位精确边界，没有把年度月Q求和当年平均。发表前须补齐真实Q许可/QC、精确或经验证误差可接受的汇水区及同源P/T；作者需核对论证和数据披露范围。
