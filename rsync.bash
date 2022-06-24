#!/usr/bin/bash
NETWORKS=("BSRN" "SAURAN"  "enerMENA"  "ABOM" "NREL_MIDC" "SOLRAD" "SURFRAD")
FOLDERS=("bsrn" "sauran" "enermena" "bom" "nrelmidc" "solrad" "surfrad")
for i in ${!NETWORKS[@]}
do
	network=${NETWORKS[i]}
	folder=${FOLDERS[i]}
	rsync -rtL --delete --chmod=644 --chown=tds-insitu:tomcat "out/${network}/" "tds-insitu@brume:/home/thredds_content/thredds/public/${folder}stations/"
done
