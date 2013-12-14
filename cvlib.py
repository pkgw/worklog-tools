# -*- mode: python ; coding: utf-8 -*-
# Shared routines for my CV / publication-list tools.


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


# Infrastructure

from inifile import Holder

def die (fmt, *args):
    if len (args):
        text = fmt % args
    else:
        text = str (fmt)

    raise SystemExit ('error: ' + text)


def warn (fmt, *args):
    if len (args):
        text = fmt % args
    else:
        text = str (fmt)

    import sys
    print >>sys.stderr, 'warning:', text


def open_template (stem):
    from os.path import join, dirname
    from errno import ENOENT

    try:
        return open (join ('templates', stem))
    except IOError as e:
        if e.errno != ENOENT:
            raise

    try:
        return open (join (dirname (__file__), 'templates', stem))
    except Exception as e:
        die ('cannot open template "%s": %s (%s)', stem, e, e.__class__.__name__)


def slurp_template (stem):
    with open_template (stem) as f:
        return unicode (f.read ())


# Text formatting. The internal format is basic HTML in Unicode. This is
# exported to LaTeX for those cases that need it -- it seems easier to go this
# direction than the other.

_html_latex_tags = {
    '<i>': r'\textit{',
    '</i>': r'}',
    '<em>': r'\emph{',
    '</em>': r'}',
}

def html_to_latex (html):
    """Convert very simple Unicode/HTML to LaTeX. We have to do this carefully so
    that unicode_to_latex doesn't try to double-escape control sequences. We only
    support basic entities (e.g. &lt;) to make life easier -- anything that can
    sensibly be done in Unicode should be.
    """

    from re import split
    from unicode_to_latex import unicode_to_latex as latex

    a = split ('(<[^>]+>)', unicode (html))

    def tolatex_piece (piece):
        c = _html_latex_tags.get (piece)
        if c is not None:
            return c

        if '<' in piece or '>' in piece:
            die ('missing HTML-to-LaTeX translation of "%s"', piece)

        piece = (piece.replace ('&lt;', '<').replace ('&gt;', '>')
                 .replace ('&nbsp;', nbsp).replace ('&amp;', '&'))
        return latex (piece)

    return ''.join (tolatex_piece (piece) for piece in a)


# Utilities for dealing with publications.

def parse_ads_cites (pub):
    from time import mktime

    if not pub.has ('adscites'):
        return None

    try:
        a = pub.adscites.split ()[:2]
        y, m, d = [int (x) for x in a[0].split ('/')]
        lastupdate = int (mktime ((y, m, d, 0, 0, 0, 0, 0, 0)))
        cites = int (a[1])
    except Exception:
        warn ('cannot parse adscites entry "%s"', pub.adscites)
        return None

    return inifile.Holder (lastupdate=lastupdate, cites=cites)


def canonicalize_name (name):
    """Convert a name into "canonical" form, by which I mean something like "PKG
    Williams". The returned string uses a nonbreaking space between the two
    pieces.

    TODO: handle "Surname, First Middle" etc.
    TODO: also Russian initials: Yu. G. Levin
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


def best_url (item):
    if item.has ('bibcode'):
        return 'http://adsabs.harvard.edu/abs/' + item.bibcode
    if item.has ('doi'):
        return 'http://dx.doi.org/' + item.doi
    if item.has ('url'):
        return item.url
    if item.has ('arxiv'):
        return 'http://arxiv.org/abs/' + item.arxiv

    return None


def compute_cite_stats (pubs):
    """Compute an h-index and other stats from the known publications."""

    cites = []
    dates = []
    refcites = 0

    for pub in pubs:
        citeinfo = parse_ads_cites (pub)
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


def cite_stats_to_html (pubs):
    """Returns HTML text describing citation statistics (most important,
    h-index)."""
    from time import gmtime

    info = Holder ()
    info.refcites, info.hindex, meddate = compute_cite_stats (pubs)
    info.year, info.month, info.day = gmtime (meddate)[:3]
    info.monthstr = months[info.month - 1]
    return info.format (slurp_template ('citestats.frag.html'))
