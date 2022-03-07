#!/bin/bash

dt1=`date +"%D %H:%M:%S"`

desc=${1}
apiurl="https://api.prowlapp.com/publicapi/add"
apikey=${PROWL_API_KEY}
prty=0
app=${2}
event="${2} returned an error at ${dt1}"

curl $apiurl -F apikey=$apikey -F priority=$prty -F application="$app" -F event="$event" -F description="$desc"
