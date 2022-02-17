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
cur.execute('SELECT a.client, b.name, a.domain, a.timestamp \
             FROM queries a inner join client_by_id b on \
             a.client = b.ip\
             WHERE a.timestamp > (?) and \
                   a.type in (1, 2, 16) and \
                   a.reply_type in (3, 4, 5) and \
                   a.domain not like "%.lan" and \
                   a.client == (?) and \
                   a.domain not like "%in-addr.arpa"\
             ORDER BY client, timestamp;', (midnight, arg1))


queries = cur.fetchall()


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


# summary data
cur.execute('SELECT ip, name, time15_fmt AS time, count(*) AS count \
             FROM myqueries \
             GROUP BY ip, name, time \
             ORDER BY ip, name, time;')
qtr_hr_list = cur.fetchall()


cur.execute('SELECT ip, name, domain, count(*) AS count \
             FROM myqueries \
             GROUP BY ip, name, domain \
             ORDER BY ip, name, count DESC;')
top_domains_list = cur.fetchall()


# close DB connection
con.close()

# DNS queries per quarter-hour increment for this client
qtr_hr_dict = {}
for mytuple in qtr_hr_list:
	qtr_hr = mytuple[2]
	count = mytuple[3]
	qtr_hr_dict[qtr_hr] = count
output = json.dumps(qtr_hr_dict)


# top domains today for this client
top_domains_dict = {}
for mytuple in top_domains_list:
	domain = mytuple[2]
	count = mytuple[3]
	top_domains_dict[domain] = count
output2 = json.dumps(top_domains_dict)

# write to file
outfile = open(outloc, "a")
outfile.write(output)
outfile.write("\n\n")
outfile.write(output2)
outfile.write("\n")
outfile.close()

