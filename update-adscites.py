#! /usr/bin/env python
# -*- python -*-

"""
Fetch citation counts from ADS and insert/update the information in
the data files.
"""

import sys, time, inifile

 # minimum number of seconds to wait before downloading new info:
MINWAIT = 7 * 24 * 3600 # 1 week

# template URL to load: uses a custom format that returns exactly
# the ADS citation count
URLTMPL = (r'http://adsabs.harvard.edu/cgi-bin/nph-abs_connect?'
           r'bibcode=%(bibcode)s&data_type=Custom&format=%%25c&nocookieset=1')


def get_cite_count (bibcode):
    from urllib2 import urlopen
    url = URLTMPL % {'bibcode': bibcode}
    lastnonempty = None

    for line in urlopen (url):
        line = line.strip ()
        if len (line):
            lastnonempty = line

    if lastnonempty is None:
        print >>sys.stderr, 'error: got only empty lines'
        raise Exception ()

    if lastnonempty.startswith ('Retrieved 0 abstracts'):
        print >>sys.stderr, 'warning: no ADS entry for following entry:'
        return 0

    try:
        count = int (lastnonempty)
    except Exception:
        print >>sys.stderr, 'error: got unexpected final line:', lastnonempty
        raise

    return count


def update (inipath, minwait=MINWAIT):
    now = int (time.time ())
    nowstr = time.strftime ('%Y/%m/%d ', time.gmtime (now))

    for item in inifile.mutateInPlace (inipath):
        if not item.data.has ('bibcode'):
            continue

        bibcode = item.data.bibcode
        firstauth = item.data.has ('mypos') and int (item.data.mypos) == 1
        reffed = item.data.has ('refereed') and item.data.refereed == 'y'

        if not item.data.has ('adscites'):
            lastupdate = curcites = 0
        else:
            try:
                a = item.data.adscites.split ()[:2]
                y, m, d = [int (x) for x in a[0].split ('/')]
                lastupdate = time.mktime ((y, m, d, 0, 0, 0, 0, 0, 0))
                curcites = int (a[1])
            except Exception:
                print >>sys.stderr, 'warning: cannot parse adscites entry:', \
                    item.data.adscites
                continue

        if lastupdate + MINWAIT > now:
            continue

        print bibcode, ' *'[firstauth] + ' R'[reffed], '...',
        newcites = get_cite_count (bibcode)
        item.set ('adscites', nowstr + str (newcites))
        print '%d (%+d)' % (newcites, newcites - curcites)


if __name__ == '__main__':
    if len (sys.argv) != 2:
        print >>sys.stderr, 'usage: update-adscites.py <datafile>'
        sys.exit (1)
    update (sys.argv[1])
