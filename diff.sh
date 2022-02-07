#!/usr/bin/bash
NETWORK=$1
FOLDER1=out/$NETWORK
FOLDER2=/mnt/v1/IN_SITU_data/NetCDF_data/netCDF_$NETWORK/
TMP_FILE=/tmp/args

: > $TMP_FILE

STATIONS=`cut -d, -f 1 res/station-info/$NETWORK.csv | sed 1d`
for station in $STATIONS
do
	echo $FOLDER1/*$station* $FOLDER2/*$station* >> $TMP_FILE
done	

cat $TMP_FILE | parallel --col-sep ' ' ./tools/diff.py | tee diff-$NETWORK.log
