#!/usr/bin/python3

import sqlite3
import time
import json
import sys
import json
import os
import subprocess
import pandas as pd
import matplotlib

matplotlib.use('Agg')

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 200)
pd.set_option('display.width', 1000)
pd.set_option('colheader_justify', 'center')

# - - - - - - - #
#   functions   #
# - - - - - - - #


def readJSON(maploc = os.environ['HOME'] + "/Scripts/piholeDBquery/mapfile.json"):
    with open(maploc) as file:
        try:
            data = json.load(file)
        except ValueError as err:
            return False
        else:
            return data
    

def validateInputs(arg1):
    arg1u = arg1.upper()
    map = readJSON()
    if map == False:
        sys.exit("Malformed JSON mapping file. Quitting.")

    # Argument 1
    if arg1u in ["ELH", "CLH", "AMLO", "IELO", "KIDS"]:
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
        sys.exit("Valid values for arg1: 'ELO', 'CLH', 'AMLO', 'IELO', 'KIDS', a 192.168.x.x IP address, or '<device name>.lan'.")

    if iplist == "" or iplist == [] or len(iplist) == 0:
        sys.exit("Something went wrong. validateInputs() returned a zero-length object.")

    return iplist


def myStyler(styler):
    styler.set_caption(caption)
    styler.set_uuid(uuid)
    return styler




# - - - - - - - #
#      body     #
# - - - - - - - #

# test for command-line arg
try:
    arg1 = sys.argv[1]
except IndexError:
    sys.exit("You must supply a device or individual identifier as arg1 to this function.")

ipList = validateInputs(arg1)


# connect to DB
con = sqlite3.connect('/etc/pihole/pihole-FTL.db')


# create cursor object
cur = con.cursor()


# time calculations
now = time.localtime()
nowDay = time.strftime("%Y-%m-%d", now)
nowHMS = time.strftime("%H:%M:%S", now)
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
                       a.domain not like "%akamai.net" and \
                       a.domain not like "%ubuntu.com" and \
                       a.domain not like "%google.com" and \
                       a.domain not like "%gstatic%" and \
                       a.domain not like "%.firefox%" and \
                       a.domain not like "%googleapis%" and \
                       a.domain not like "%mozilla%" and \
                       a.domain not like "%example.org" and \
                       a.domain not like "%googleusercontent.com" and \
                       a.domain not like "%aaplimg.com" and \
                       a.domain not like "%apple%" and \
                       a.domain not like "%me.com" and \
                       a.domain not like "%icloud%" and \
                       a.client == (?) \
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


# - - - - - - - - - - - #
# Time increment table  #
# - - - - - - - - - - - #
cur.execute('SELECT ip, name, time15_fmt AS time, count(*) AS count \
             FROM myqueries \
             GROUP BY time, ip, name \
             ORDER BY time, ip, name;')
mylist = cur.fetchall()
df = pd.DataFrame(mylist, columns = ["IP Address", "Device Name", "Time", "# Queries"])
df = df.replace(to_replace={"Device Name":r'^(.*)\.lan$'}, value={"Device Name":r'\1'}, regex=True)
df = df.replace(to_replace={"Device Name":r'^(.+)-(.+)$'}, value={"Device Name":r'\1.\2'}, regex=True)
df = df.replace(to_replace={"Device Name":r'^thinkpad(.+)$'}, value={"Device Name":r'tpad\1'}, regex=True)
df = df.replace(to_replace={"Device Name":r'^iphone10(.+)$'}, value={"Device Name":r'fon\1'}, regex=True)
df2 = df.pivot_table(index = "Time", columns = "Device Name", values = "# Queries", fill_value = 0)
df2.columns.name = ""
df2.index.name=None
caption = "Today's query count by device" # used in styler
uuid = "by15" # used in styler
groomed = df2.style.pipe(myStyler)
out15 = groomed.render(render_links = False)

# - - - - - - - - - - - - - #
# Site hierarchy by device  #
# - - - - - - - - - - - - - #
cur.execute('SELECT ip, name, domain, count(*) AS count \
             FROM myqueries \
             GROUP BY ip, name, domain \
             HAVING count > 1 \
             ORDER BY ip, name, count DESC;')
mylist = cur.fetchall()
xdf = pd.DataFrame(mylist, columns = ["IP Address", "Device Name", "Site", "# Queries"])
xdf = xdf.replace(to_replace={"Device Name":r'^(.*)\.lan$'}, value={"Device Name":r'\1'}, regex=True)
xdf['# Queries'] = xdf['# Queries'].astype(int)

# close DB connection
con.close()


# - - - - - - - - - - - - - #
# write output to html file #
# - - - - - - - - - - - - - #

# first read HTML templates
with open(os.environ["HOME"] + "/Scripts/piholeDBquery/top.html") as top:
    top_html = top.read()

with open(os.environ["HOME"] + "/Scripts/piholeDBquery/bottom.html") as bottom:
    bottom_html = bottom.read()

# unique temp filename has arg1 and unix timestamp in it for uniqueness
ep = str(time.mktime(time.localtime()))
outloc = "/tmp/piholeDBquery_" + arg1 + "_" + ep + ".html"

with open(outloc, "a") as outfile:
    outfile.write(top_html) # write HTML head, etc
    outfile.write(out15) ## first table (15-min increments for all devices)

    # now one table of ranked activity per device
    thelist = xdf["Device Name"].unique()
    for dn in thelist:        
        xdf2 = xdf[xdf["Device Name"] == dn].copy(deep = True)
        caption = xdf2["Device Name"][xdf2.index[0]] + " (" + xdf2["IP Address"][xdf2.index[0]] + ")" # used in styler
        uuid = "freq" # used in styler
        xdf2.drop(["IP Address", "Device Name"], axis = 1, inplace = True)
        groomed = xdf2.style.pipe(myStyler)
        thisout = groomed.hide_index().render(render_links = False)
        outfile.write(thisout)
        if dn == thelist[-1]:
            outfile.write(bottom_html) # write HTML bottom


# - - - - - - - - - - - - - #
#        send email         #
# - - - - - - - - - - - - - #

header1 = 'Content-Type: text/html; charset="UTF-8"'
header2 = '"MIME-Version: 1.0"'
emailSubj = "Today's DNS activity for " + arg1.upper() + " as of " + nowHMS
recipient = os.environ['PIHOLE_DB_QUERY_EMAIL_RECIPIENT']

body = subprocess.Popen(('cat', outloc), stdout=subprocess.PIPE)
output = subprocess.run(['mail', '-a', header1, '-a', header2, '-s', emailSubj, recipient], stdin=body.stdout, capture_output = True)


# return subprocess.run() output to Shortcut if it's not a clean exit
shortcutsReturn = output.stdout.decode("utf-8")
if shortcutsReturn != "":
    print(shortcutsReturn)

# cleanup
os.remove(outloc)
