INPUT_DIR=/mnt/v1/IN_SITU_data/RawData/BSRN
NETWORK=BSRN
PYTHON=python
OUT_FOLDER=out/$NETWORK
LOGDIR=log
STATUS_FOLDER=status

if [ -z "$1" ]
then
	LIST=`ls -1D $INPUT_DIR/???`
else
	LIST="$INPUT_DIR/$1"
fi

CMD="$PYTHON insitu-etl.py -i -f $STATUS_FOLDER -n $NETWORK -s {2} $OUT_FOLDER/$NETWORK-{2}.nc {1} | tee $LOGDIR/$NETWORK-{2}.log"
echo "$LIST" | awk '{st=$1; sub(".*/", "", st); print $1 ";" toupper(st)}' | parallel -C ';' $CMD
