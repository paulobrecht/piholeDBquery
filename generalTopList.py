#!/usr/bin/python3

import sqlite3
import time
import json
import sys
import json
import os
import pandas as pd


pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 200)
pd.set_option('display.width', 1000)


def readJSON(maploc = os.environ['HOME'] + "/Scripts/piholeDBquery/mapfile.json"):
    """readJSON(): Read JSON file

    Simple function: opens, reads, closes, returns dict
    """
    file = open(maploc)
    try:
        data = json.load(file)
    except ValueError as err:
        file.close()
        return False
    else:
        file.close()
        return data


def validateInputs(arg1):
    """validateInputs(): Validate inputs and return a list of IP addresses

    Validates inputs and returns a list of IP addresses appropriate to the type of input provided in arg1   
    """

    arg1u = arg1.upper()
    map = readJSON()
    if map == False:
        sys.exit("Malformed JSON mapping file. Quitting.")

    # Argument 1
    if arg1u in ["ELH", "CLH", "AMLO", "IELO", "KIDS", "PERSONAL"]:
        thisMap = map[arg1u]
        iplist = thisMap["ip_list"]
    elif "192.168.1." in arg1u:
        iplist = [arg1u,]
    elif ".LAN" in arg1u:
        try:
            iplist = [map[arg1.lower()],]
        except KeyError as err:
            sys.exit(arg1 + " is not a known device on this network. Make sure you have the name correct and that it ends in .lan.")
    else:
        sys.exit("Valid values for arg1: 'ELO', 'CLH', 'AMLO', 'IELO', 'KIDS', 'PERSONAL', a 192.168.x.x IP address, or '<device name>.lan'.")

    if iplist == "" or iplist == [] or len(iplist) == 0:
        sys.exit("Something went wrong. validateInputs() returned a zero-length object.")

    return iplist


arg1 = "PERSONAL"
ipList = validateInputs(arg1)


# connect to DB
con = sqlite3.connect('/etc/pihole/pihole-FTL.db')


# create cursor object
cur = con.cursor()


# time calculations
now = time.localtime(1625122800) # July 1, 2021
nowDay = time.strftime("%Y-%m-%d", now)
midnight = str(int(time.mktime(time.strptime(nowDay + " 00:00:00", "%Y-%m-%d %H:%M:%S"))))


# query FTL database, do some basic filtering:
# (ignore rasp-pi localhost queries, uncommon query types, only valid replies, exclude lan queries and PTRs)
queries = []
for ip in ipList:
    cur.execute('SELECT a.client, b.name, a.domain, a.timestamp \
                 FROM queries a inner join client_by_id b on a.client = b.ip \
                 WHERE a.timestamp > (?) and \
                       a.type in (1, 2, 16) and \
                       a.reply_type in (3, 4, 5) and \
                       a.status in (2, 3) and \
                       a.domain not like "%akamaiedge.net" and \
                       a.domain not like "%akadns.net" and \
                       a.domain not like "%me.com" and \
                       a.domain not like "%akamai.net" and \
                       a.domain not like "%me.com" and \
                       a.domain not like "%.apple%" and \
                       a.domain not like "%icloud%" and \
                       a.client == (?) and \
                       a.domain not like "%in-addr.arpa"\
                 ORDER BY a.client, a.timestamp;', (midnight, ip))
    tmp = cur.fetchall()
    queries = queries + tmp

# if nothing was returned, exit.
if len(queries) == 0:
    sys.exit("No results returned for " + arg1)


# copy query table, adding formatted timestamps
# con.execute("DROP TABLE myqueries;")
con.execute("CREATE TEMPORARY TABLE myqueries (ip TEXT, name TEXT, domain TEXT, timestamp INT, time_fmt TEXT, time15_fmt TEXT)")


new = []
for item in queries:
    timestamp = item[3]
    timestamp15 = timestamp - (timestamp % (15 * 60))
    time_fmt = time.strftime("%H:%M", time.localtime(timestamp))
    time15_fmt = time.strftime("%H:%M", time.localtime(timestamp15))
    new.append(item + (time_fmt, time15_fmt))


con.executemany("insert into myqueries(ip, name, domain, timestamp, time_fmt, time15_fmt) values (?, ?, ?, ?, ?, ?)", new)


cur.execute('SELECT ip, name, domain, count(*) AS count \
             FROM myqueries \
             GROUP BY ip, name, domain \
             HAVING count > 2 \
             ORDER BY ip, name, count DESC;')
mylist = cur.fetchall()
xdf = pd.DataFrame(mylist, columns = ["IP Address", "Device Name", "Site", "# Queries"])
xdf['# Queries'] = xdf['# Queries'].astype(int)
xdf['Device Name'] = xdf['Device Name'].replace(".lan", "")

print(xdf)

# close DB connection
con.close()
