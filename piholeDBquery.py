#!/usr/bin/python3


import sqlite3
import time
import json
import sys

# use epoch time as file suffix
ep = str(time.mktime(time.localtime()))
outloc = "/tmp/piholeDBquery_" + ep + ".json"


# get command-line arg (client ID or IP address)
try:
	arg1 = sys.argv[1]
except IndexError:
	sys.exit("You must supply a LAN IP address or a machine name.")

# connect to DB
con = sqlite3.connect('/etc/pihole/pihole-FTL.db')


# create cursor object
cur = con.cursor()


# time calculations
now = time.localtime()
nowDay = time.strftime("%Y-%m-%d", now)
midnight = str(int(time.mktime(time.strptime(nowDay + " 00:00:00", "%Y-%m-%d %H:%M:%S"))))


# query FTL database, do some basic filtering:
# (ignore rasp-pi localhost queries, uncommon query types, only valid replies, exclude lan queries and PTRs)
cur.execute('SELECT client, domain, timestamp \
	         FROM queries \
	         WHERE timestamp > (?) and \
                   client != "127.0.0.1" and \
	               type in (1, 2, 16) and \
	               reply_type in (3, 4, 5) and \
	               domain not like "%.lan" and \
	               client == (?) and \
	               domain not like "%in-addr.arpa"\
	         ORDER BY client, timestamp;', (midnight, arg1))


queries = cur.fetchall()


# copy query table, adding formatted timestamps
# con.execute("DROP TABLE myqueries;")
con.execute("CREATE TEMPORARY TABLE myqueries (client TEXT, domain TEXT, timestamp INT, time_fmt TEXT, time15_fmt TEXT)")


new = []
for item in queries:
	timestamp = item[2]
	timestamp15 = timestamp - (timestamp % (15 * 60))
	time_fmt = time.strftime("%H:%M", time.localtime(timestamp))
	time15_fmt = time.strftime("%H:%M", time.localtime(timestamp15))
	new.append(item + (time_fmt, time15_fmt))


con.executemany("insert into myqueries(client, domain, timestamp, time_fmt, time15_fmt) values (?, ?, ?, ?, ?)", new)


# summary data
cur.execute('SELECT client, time15_fmt AS time, count(*) AS count \
	         FROM myqueries \
	         GROUP BY client, time \
	         ORDER BY client, time;')
qtr_hr_list = cur.fetchall()


cur.execute('SELECT client, domain, count(*) AS count \
	         FROM myqueries \
	         GROUP BY client, domain \
	         ORDER BY client, count DESC;')
top_domains_list = cur.fetchall()


# close DB connection
con.close()

# DNS queries per quarter-hour increment for this client
qtr_hr_dict = {}
for mytuple in qtr_hr_list:
	qtr_hr = mytuple[1]
	count = mytuple[2]
	qtr_hr_dict[qtr_hr] = count
output = json.dumps(qtr_hr_dict)


# top domains today for this client
top_domains_dict = {}
for mytuple in top_domains_list:
	domain = mytuple[1]
	count = mytuple[2]
	top_domains_dict[domain] = count
output2 = json.dumps(top_domains_dict)

# write to file
outfile = open(outloc, "a")
outfile.write(output)
outfile.write("\n\n")
outfile.write(output2)
outfile.write("\n")
outfile.close()
