## EStreams: An Integrated Dataset and Catalogue of Streamflow, Hydro-Climatic Variables and Landscape Descriptors for Europe
> November 2025

Authors: Thiago Nascimento, Julia Rudlang, Marvin Hoege, Ruud van der Ent, Máté Chappon, Jan Seibert, Markus Hrachowitz and Fabrizio Fenicia 

Contact: thiago.nascimento@eawag.ch

### Folders and content
- **hydroclimatic_signatures/**: This folder contains `one` csv-file with all derived signatures.
	- estreams_hydrometeo_signatures.csv

- **meteorology:** This folder contains one csv-file per catchment (`17,130` files). Each file contains all derived meteorological daily time-series.
	- estreams_meteorology_{basin_id}.csv

- **shapefiles/**: This folder contains `two` shape-files. One with all basin delineations and another with all gauging stations.
	- estreams_catchments.{cpg,dbf,prj,shp,shx}
	- estreams_gauging_stations.{cpg,dbf,prj,shp,shx}

- **attributes/**:
	- **static_attributes/**: This sub-folder contains all catchment static attributes, divided into `eight` csv-files according to their respective landscape group. 
		- estreams_geology_attributes.csv
		- estreams_hydrology_attributes.csv
		- estreams_meteorology_density.csv
		- estreams_snowcover_attributes.csv
		- estreams_soil_attributes.csv
		- estreams_topography_attributes.csv
		- estreams_vegetation_attributes.csv
		- estreams_geologycontinental_attributes.csv
	- **temporal_attributes/**: This sub-folder contains all derived temporal landscape attributes divided into `eight` csv-files according to their respective landscape group. 
		- estreams_irrigation_yearly.csv
		- estreams_LAI_monthly.csv
		- estreams_LAI_yearly.csv
		- estreams_landcover_attributes.csv
		- estreams_NDVI_monthly.csv
		- estreams_NDVI_yearly.csv
		- estreams_snowcover_monthly.csv
		- estreams_snowcover_yearly.csv
- **streamflow_gauges/**: This folder contains `three` csv-files. One with all gauging stations metadata, and another with the streamflow data-source catalogue. 
	- estreams_gauging_stations.csv
	- estreams_stations_catalogue.csv
	- estreams_catchments_hierarchy.csv

- **streamflow_indices/**: This folder is divided into `four` sub-folders which contain all the derived streamflow indices according to their respective time-resolution. 
	- **monthly/**:
		- monthly_streamflow_cv.csv
		- monthly_streamflow_iqr.csv
		- monthly_streamflow_max.csv
		- monthly_streamflow_max7days.csv
		- monthly_streamflow_mean.csv
		- monthly_streamflow_min.csv
		- monthly_streamflow_min7days.csv
		- monthly_streamflow_std.csv
	- **seasonal/**:
		- seasonal_streamflow_max7days.csv
		- seasonal_streamflow_min7days.csv
		- seasonal_streamflow_p90.csv
		- seasonal_streamflow_p80.csv
		- seasonal_streamflow_p70.csv
		- seasonal_streamflow_p60.csv
		- seasonal_streamflow_p50.csv
		- seasonal_streamflow_p40.csv
		- seasonal_streamflow_p30.csv
		- seasonal_streamflow_p20.csv
		- seasonal_streamflow_p10.csv
		- seasonal_streamflow_iqr.csv
		- seasonal_streamflow_max.csv
		- seasonal_streamflow_min.csv
		- seasonal_streamflow_cv.csv
		- seasonal_streamflow_std.csv
		- seasonal_streamflow_mean.csv
	- **weekly/**:
		- weekly_streamflow_cv.csv
		- weekly_streamflow_iqr.csv
		- weekly_streamflow_max.csv
		- weekly_streamflow_mean.csv
		- weekly_streamflow_min.csv
		- weekly_streamflow_std.csv
	- **yearly/**:
		- yearly_streamflow_gini.csv
		- yearly_streamflow_doy7min.csv
		- yearly_streamflow_doymax.csv
		- yearly_streamflow_doymin.csv
		- yearly_streamflow_ct.csv
		- yearly_streamflow_max7days.csv
		- yearly_streamflow_min7days.csv
		- yearly_streamflow_p90.csv
		- yearly_streamflow_p80.csv
		- yearly_streamflow_p70.csv
		- yearly_streamflow_p60.csv
		- yearly_streamflow_p50.csv
		- yearly_streamflow_p40.csv
		- yearly_streamflow_p30.csv
		- yearly_streamflow_p20.csv
		- yearly_streamflow_p10.csv
		- yearly_streamflow_iqr.csv
		- yearly_streamflow_max.csv
		- yearly_streamflow_min.csv
		- yearly_streamflow_cv.csv
		- yearly_streamflow_std.csv
		- yearly_streamflow_mean.csv
		- yearly_streamflow_doym7in.csv

- **appendix/**: This folder contains `four` txt-files with. One with the lithological classes description labels, another with the landcover classes description labels, and another with licenses and sources information for the data used to derive the current dataset.
	- CORINE_landcover_classes.txt
	- GLiM_lithological_classes.txt
	- licenses.txt
	- IHME_lithological_classes.txt

## References
Currently EStreams covers `17,130` rivers catchments within pan-European territory. Please refer to the [EStreams publication](https://doi.org/10.1038/s41597-024-03706-1), for a detailed description of the current dataset, including their respective variables units. For the codes used to derive the current dataset, users can refer to the [EStreams GitHub](https://doi.org/10.5281/zenodo.13255133). 

## How to cite
do Nascimento, T. V. M., Rudlang, J., Höge, M., van der Ent, R., Chappon, M., Seibert, J., Hrachowitz, M., & Fenicia, F. (2024). EStreams: An Integrated Dataset and Catalogue of Streamflow, Hydro-Climatic Variables and Landscape Descriptors for Europe (1.4) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.17598150
