# -*- mode: python ; coding: utf-8 -*-
# Shared routines for my CV / publication-list tools.

import sys, inifile
from unicode_to_latex import unicode_to_latex as latex

nbsp = u'\u00a0'

months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split ()

titles = {
    'ed': 'Education',
    'fawards': 'Fellowships and Awards',
    'train': 'Other Training',
    'jobs': 'Employment',
    'talks': 'Professional Talks',
    'teach': 'Teaching',
    'outreach': 'Outreach',
    'refd': 'Refereed',
    'unrefd': 'Non-Refereed',
    'abs': 'Abstracts',
}


def d (**kwargs):
    return kwargs


def parseADSCites (pub):
    from time import mktime

    if not pub.has ('adscites'):
        return None

    try:
        a = pub.adscites.split ()[:2]
        y, m, d = [int (x) for x in a[0].split ('/')]
        lastupdate = int (mktime ((y, m, d, 0, 0, 0, 0, 0, 0)))
        cites = int (a[1])
    except Exception:
        print >>sys.stderr, 'warning: cannot parse adscites entry:', \
            pub.adscites
        return None

    return inifile.Holder (lastupdate=lastupdate, cites=cites)


def canonicalizename (name):
    """Convert a name into "canonical" form, by which I mean
    something like "PKG Williams". The returned string uses
    a nonbreaking space between the two pieces.

    TODO: handle "Surname, First Middle" etc.
    """

    bits = name.strip ().split ()
    surname = bits[-1].replace ('_', ' ')
    rest = bits[:-1]
    abbrev = []

    for item in rest:
        for char in item:
            if char.isupper () or char == '-':
                abbrev.append (char)

    return ''.join (abbrev) + nbsp + surname


def bestURL (item):
    if item.has ('bibcode'):
        return 'http://adsabs.harvard.edu/abs/' + item.bibcode
    if item.has ('doi'):
        return 'http://dx.doi.org/' + item.doi
    if item.has ('url'):
        return item.url
    if item.has ('arxiv'):
        return 'http://arxiv.org/abs/' + item.arxiv

    return None


def computeCiteStats (pubs):
    cites = []
    dates = []
    refcites = 0

    for pub in inifile.read (pubs):
        citeinfo = parseADSCites (pub)
        if citeinfo is None:
            continue
        if citeinfo.cites < 1:
            continue

        cites.append (citeinfo.cites)
        dates.append (citeinfo.lastupdate)

        if pub.refereed == 'y':
            refcites += citeinfo.cites

    if not len (cites):
        return 0, 0, 0

    ranked = sorted (cites, reverse=True)
    index = 0

    while index < len (ranked) and ranked[index] >= index + 1:
        index += 1

    dates = sorted (dates)
    meddate = dates[len (dates) // 2]

    return refcites, index, meddate
