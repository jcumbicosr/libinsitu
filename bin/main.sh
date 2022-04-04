NETWORK=$1
#INPUT_DIR=/mnt/v1/IN_SITU_data/RawData/$NETWORK
INPUT_DIR=./in/$NETWORK
PYTHON=python
OUT_FOLDER=out/$NETWORK
LOGDIR=log
STATUS_FOLDER=status/$NETWORK

if [ -z "$2" ]
then
	LIST=`ls -1d $INPUT_DIR/{??,???,????}`
else
	LIST="$INPUT_DIR/$2"
fi

CMD="$PYTHON transform.py -i -sr -f $STATUS_FOLDER -n $NETWORK -s {2} $OUT_FOLDER/$NETWORK-{2}.nc {1} | tee $LOGDIR/$NETWORK-{2}.log"
echo "$LIST" | awk '{st=$1; sub(".*/", "", st); print $1 ";" toupper(st)}' | parallel --lb -C ';' $CMD
