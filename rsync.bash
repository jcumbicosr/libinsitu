#!/usr/bin/bash
NETWORKS=("BSRN" "SAURAN"  "enerMENA"  "ABOM" "NREL_MIDC" "SOLRAD" "SURFRAD")

if [ -z "$1" ]
then
	NETWORKS=("BSRN" "SAURAN"  "enerMENA"  "ABOM" "NREL_MIDC" "SOLRAD" "SURFRAD")
else
	NETWORKS=("$1")
fi
	
for i in ${!NETWORKS[@]}
do
	network=${NETWORKS[i]}
	folder=${network,,}
	folder=${folder//_}
	
	rsync -rtLv --delete --chmod=644 --chown=tds-insitu:tomcat "out/${network}/" "tds-insitu@brume:/home/thredds_content/thredds/public/${folder}stations/"
done
