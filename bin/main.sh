NETWORK=$1
#INPUT_DIR=/mnt/v1/IN_SITU_data/RawData/$NETWORK
INPUT_DIR=/mnt/v1/in-situ/in/$NETWORK
PYTHON=python 
OUT_FOLDER=out/$NETWORK
LOGDIR=log
STATUS_FOLDER=status/$NETWORK
STATION_INFO_DIR=libinsitu/res/station-info/

if [ -z "$2" ]
then
	LIST=`cat $STATION_INFO_DIR/${NETWORK}.csv | tail -n +2 | cut -d, -f 1`
else
	LIST="$2"
fi

CMD="echo $PYTHON bin/transform.py -i -sr -f $STATUS_FOLDER -n $NETWORK -s {1} $OUT_FOLDER/$NETWORK-{1}.nc $INPUT_DIR | tee $LOGDIR/$NETWORK-{1}.log"
echo "$LIST" | parallel --lb -C ';' $CMD
