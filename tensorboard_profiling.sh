#!/bin/bash

HW_TYPE=$1
MODEL_NAME=$2

tensorboard --bind_all --logdir=./${MODEL_NAME}_logdir &
sleep 10


NAME_LIST=$(find ./${MODEL_NAME}_logdir -name *.trace.json.gz)

TB_URL1="http://localhost:6006/data/plugin/profile/data?run="
TB_URL3="&tag=tensorflow_stats&host="
TB_URL5="&tqx=out:csv;"

for NAME in $NAME_LIST
do  
    echo $NAME
    TB_URL2=$(echo $NAME | cut -d "/" -f 5)
    echo $TB_URL2
    TB_URL4=$(echo $NAME | cut -d "/" -f 6 | cut -d "." -f 1)
    echo $TB_URL4


    TB_URL="$TB_URL1$TB_URL2$TB_URL3$TB_URL4$TB_URL5"
    echo $TB_URL
    FILENAME="./$HW_TYPE$MODEL_NAME-$TB_URL2-$TB_URL4.csv"
    curl -o $FILENAME $TB_URL
    sleep 1
done

ps -ef | grep tensorboard | grep -v grep | awk '{print $2}' | xargs kill
