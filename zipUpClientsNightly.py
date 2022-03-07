#!/usr/bin/python3

import sqlite3
import sys
import os
import subprocess



# - - - - - - - #
#   JSON map    #
# - - - - - - - #

deviceMap = {
    "E":{
        "group_ids":
            [0, 2, 4, 5, 7, 8, 9, 10, 11],
        "device_ids":
            [34, 62, 73]
    },
    "C":{
        "group_ids":
            [0, 2, 4, 5, 6, 7, 9, 10, 11],
        "device_ids":
            [33, 61, 51]
    },
    "A":{
        "group_ids":
            [0, 2, 4, 5, 6, 7, 9, 10, 11],
        "device_ids":
            [60, 72]
    },
    "I":{
        "group_ids":
            [0, 2, 4, 5, 6, 7, 9, 10, 11],
        "device_ids":
            [52, 59]
    }
}



# - - - - - - #
#    funcs    #
# - - - - - - #

def prowl(msg):
  import subprocess
  import inspect
  caller = inspect.stack()[2].function
  execList = [os.environ['PROWL_LOC'], str("\'ERROR: " + msg + "\'")]
  output = subprocess.run(execList, capture_output = True)
  xmlobj = output.stdout.decode("utf-8")
  return xmlobj

def serviceProb(ss, returncode):
    host = subprocess.check_output("hostname", shell=True).decode("utf-8").strip()
    if ss == "rebuilt":
        message = "Gravity DB on " + host + " could not be rebuilt (return code " + returncode + ")"
    else:
        message = "pihole-FTL service on " + host + " could not be " + ss + " (return code " + stop.returncode + ")"
    prowl(msg = message)
    sys.exit(message)



# - - - - - - - #
#      body     #
# - - - - - - - #

# test for command-line arg
if len(sys.argv) > 1:
    try:
        arg1 = sys.argv[1]
        if arg1.upper() == "REBUILD" then:
            REBUILD = True
        else:
            REBUILD = False
    except exception:
        REBUILD = False



# stop pihole
stop = subprocess.run(["service", "pihole-FTL", "stop"], capture_output = True)
if stop.returncode != 0:
    serviceProb(ss="stopped", returncode = stop.returncode)



# connect to DB and create cursor object
con = sqlite3.connect('/etc/pihole/gravity.db')
cur = con.cursor()

# iterate over the four kids
for key in deviceMap.keys():
    # get device IDs and group IDs for this kid
    thisMap = deviceMap[key]
    piholeDeviceList = thisMap["device_ids"]
    piholeGroupIDs = thisMap["group_ids"]
    # iterate over devices, delete rows that exist, add them all back.
    for deviceID in piholeDeviceList:
        cur.execute("DELETE FROM client_by_group WHERE client_id = (?);", (deviceID,)) # delete current entries for this device
        for groupID in piholeGroupIDs:
            cur.execute("INSERT INTO client_by_group (client_id, group_id) VALUES (?, ?);", (deviceID, groupID)) # add a row for each relevant group for this device

# commit and close DB connection
con.commit()
con.close()



# restart pihole
start = subprocess.run(["service", "pihole-FTL", "start"], capture_output = True)
if start.returncode != 0:
    serviceProb(ss="started", returncode = start.returncode)



# rebuild gravity databse
if REBUILD == True:
    rebuild = subprocess.run(["pihole", "-g"], capture_output = True)
    if rebuild.returncode != 0:
        serviceProb(ss="rebuilt", returncode = rebuild.returncode)
