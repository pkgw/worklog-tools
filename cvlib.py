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
        return f.read ().decode ('utf8')


def process_template (stem, commands, context):
    """Read through a template line-by-line and replace special lines. Each
    regular line is yielded to the caller. `commands` is a dictionary of
    strings to callables; if the first word in a line is in `commands`, the
    callable is invoked, with `context` and the remaining words in the line as
    arguments. Its return value is either a string or an iterable, with each
    iterate being yielded to the caller in the latter case."""

    with open_template (stem) as f:
        for line in f:
            line = line.decode ('utf8').rstrip ()
            a = line.split ()

            if not len (a) or a[0] not in commands:
                yield line
            else:
                result = commands[a[0]] (context, *a[1:])
                if isinstance (result, basestring):
                    yield result
                else:
                    for subline in result:
                        yield subline


# Text formatting. The internal format is basic HTML in Unicode. This is
# exported to LaTeX for those cases that need it -- it seems easier to go this
# direction than the other.

def html_escape (text):
    """Escape special characters for our dumb subset of HTML."""

    return (unicode (text)
            .replace ('<', '&lt;')
            .replace ('>', '&gt;')
            .replace ('&', '&amp;'))


_html_latex_tags = {
    '<i>': r'\textit{',
    '</i>': r'}',
    '<em>': r'\emph{',
    '</em>': r'}',
    '</a>': r'}',
}

def html_to_latex (html):
    """Convert very simple Unicode/HTML to LaTeX. We have to do this carefully so
    that unicode_to_latex doesn't try to double-escape control sequences. We only
    support basic entities (e.g. &lt;) to make life easier -- anything that can
    sensibly be done in Unicode should be.
    """

    from re import split, match
    from unicode_to_latex import unicode_to_latex as latex

    a = split ('(<[^>]+>)', unicode (html))

    def tolatex_piece (piece):
        c = _html_latex_tags.get (piece)
        if c is not None:
            return c

        if piece.startswith ('<a '):
            m = match ('<a href="(.*)">', piece)
            if not m:
                die ('malformed dumb-HTML <a> tag: "%s"', piece)
            url = m.groups ()[0]
            url = (url.replace ('&lt;', '<').replace ('&gt;', '>')
                   .replace ('&amp;', '&'))
            return r'\href{' + url + '}{'

        if '<' in piece or '>' in piece:
            die ('missing HTML-to-LaTeX translation of "%s"', piece)

        piece = (piece.replace ('&lt;', '<').replace ('&gt;', '>')
                 .replace ('&nbsp;', nbsp).replace ('&amp;', '&'))
        return latex (piece)

    return ''.join (tolatex_piece (piece) for piece in a)


# Loading up the data

def load (datadir='.'):
    from os import listdir
    from os.path import join
    from inifile import read as iniread

    for item in sorted (listdir (datadir)):
        if not item.endswith ('.txt'):
            continue

        path = join (datadir, item)
        for item in iniread (path):
            yield item


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

    return Holder (lastupdate=lastupdate, cites=cites)


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
    from urllib2 import quote

    if item.has ('bibcode'):
        return 'http://adsabs.harvard.edu/abs/' + quote (item.bibcode)
    if item.has ('doi'):
        return 'http://dx.doi.org/' + quote (item.doi)
    if item.has ('url'):
        return item.url
    if item.has ('arxiv'):
        return 'http://arxiv.org/abs/' + quote (item.arxiv)

    return None


def cite_info (item):
    """Create a Holder with citation text from a publication item. This can then
    be fed into a template however one wants. The various computed fields are
    are HTML Unicode."""

    # FIXME: this function requires too much care in making sure I've rememebered
    # to HTML escape things.

    info = item.copy ()

    # Canonicalized authors with highlighting of self.
    cauths = [html_escape (canonicalize_name (a)) for a in item.authors.split (';')]

    i = int (item.mypos) - 1
    if cauths[i] == 'PH' + nbsp + 'Williams':
        cauths[i] += ' (sic)' # ahhh ...
    cauths[i] = '<em>' + cauths[i] + '</em>'
    info.authors = ', '.join (cauths)

    # Title -- one with replaced quotes, for nesting in double-quotes.
    info.title = html_escape (item.title)
    info.quotable_title = html_escape (item.title.replace (u'“', u'‘').replace (u'”', u'’'))

    # Pub year.
    info.year = int (item.pubdate.split ('/')[0])

    # Template-friendly citation count
    citeinfo = parse_ads_cites (item)
    if citeinfo is not None and citeinfo.cites > 0:
        info.citecountnote = u' [%d]' % citeinfo.cites
    else:
        info.citecountnote = u''

    # Verbose citation contents -- the big complicated one.
    if item.has ('yjvi'):
        info.vcite = ', '.join (item.yjvi.split ('/'))
    elif item.has ('yjvp'):
        info.vcite = ', '.join (item.yjvp.split ('/'))
    elif item.has ('bookref') and item.has ('posid'):
        # Proceedings of Science
        info.vcite = '%d, in %s, %s' % (info.year, item.bookref, item.posid)
    elif item.has ('series') and item.has ('itemid'):
        # Various numbered series.
        info.vcite = '%d, %s, #%s' % (info.year, item.series, item.itemid)
    elif item.has ('tempstatus'):
        # "in prep"-type items with temporary, manually-set info
        info.vcite = item.tempstatus
    else:
        die ('no citation information for %s', item)

    info.vcite = html_escape (info.vcite)

    url = best_url (item)
    if url is not None:
        info.vcite = u'<a href="%s">%s</a>' % (url, info.vcite)

    return info


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


def partition_pubs (pubs):
    groups = Holder ()
    groups.all = []
    groups.refereed = []
    groups.non_refereed = []

    for pub in pubs:
        groups.all.append (pub)

        if pub.refereed == 'y':
            groups.refereed.append (pub)
        else:
            groups.non_refereed.append (pub)

    return groups


# Commands for templates

def cmd_latex_cite_stats (context):
    yield html_to_latex (cite_stats_to_html (context.pubgroups.all))


def cmd_latex_pub_list (context, group, template):
    tmpltext = slurp_template (template)
    pubs = context.pubgroups.get (group)

    for pub in pubs:
        html = cite_info (pub).format (tmpltext)
        yield html_to_latex (html)


# Driver

def driver (template, datadir='.', outenc='utf8'):
    context = Holder ()
    context.items = list (load (datadir))
    context.pubs = [i for i in context.items if i.section == 'pub']
    context.pubgroups = partition_pubs (context.pubs)

    commands = {}
    commands['LATEXCITESTATS'] = cmd_latex_cite_stats
    commands['LATEXPUBLIST'] = cmd_latex_pub_list

    for outline in process_template (template, commands, context):
        print outline.encode (outenc)


if __name__ == '__main__':
    import sys

    if '-a' in sys.argv:
        outenc = 'ascii'
        sys.argv.remove ('-a')
    else:
        outenc = 'utf8'

    if len (sys.argv) == 2:
        driver (sys.argv[1], '.', outenc=outenc)
    elif len (sys.argv) == 3:
        driver (sys.argv[1], sys.argv[2], outenc=outenc)
    else:
        die ('unexpected command-line arguments')
