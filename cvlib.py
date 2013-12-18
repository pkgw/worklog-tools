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


# Text formatting. We have a tiny DOM-type system for markup so we can
# abstract across LaTeX and HTML. Initially I tried to do everything in HTML,
# and then convert that to LaTeX, but the layers of escaping got a little
# worrisome, and some constructs just don't work well in that model (e.g.
# tables). So we do this silliness instead.

from unicode_to_latex import unicode_to_latex

def html_escape (text):
    """Escape special characters for our dumb subset of HTML."""

    return (unicode (text)
            .replace ('&', '&amp;')
            .replace ('<', '&lt;')
            .replace ('>', '&gt;')
            .replace ('"', '&quot;')
            .replace ("'", '&apos;'))


class Markup (object):
    def _latex (self):
        raise NotImplementedError ()

    def _html (self):
        raise NotImplementedError ()

    def latex (self):
        return u''.join (self._latex ())

    def html (self):
        return u''.join (self._html ())



def _maybe_wrap_text (thing):
    if isinstance (thing, Markup):
        return thing
    return MupText (thing)


class MupText (Markup):
    def __init__ (self, text):
        self.text = unicode (text)

    def _latex (self):
        return [unicode_to_latex (self.text)]

    def _html (self):
        return [html_escape (self.text)]


class MupItalics (Markup):
    def __init__ (self, inner):
        self.inner = _maybe_wrap_text (inner)

    def _latex (self):
        return [u'\\textit{'] + self.inner._latex () + [u'}']

    def _html (self):
        return [u'<i>'] + self.inner._html () + [u'</i>']


class MupBold (Markup):
    def __init__ (self, inner):
        self.inner = _maybe_wrap_text (inner)

    def _latex (self):
        return [u'\\textbf{'] + self.inner._latex () + [u'}']

    def _html (self):
        return [u'<b>'] + self.inner._html () + [u'</b>']


class MupLink (Markup):
    def __init__ (self, url, inner):
        self.url = unicode (url)
        self.inner = _maybe_wrap_text (inner)

    def _latex (self):
        return ([u'\\href{', self.url.replace ('%', '\\%'), u'}{'] +
                self.inner._latex () + [u'}'])

    def _html (self):
        return ([u'<a href="', html_escape (self.url), u'">'] +
                self.inner._html () + [u'</a>'])


class MupJoin (Markup):
    def __init__ (self, sep, items):
        self.sep = _maybe_wrap_text (sep)
        self.items = [_maybe_wrap_text (i) for i in items]

    def _latex (self):
        esep = self.sep._latex ()
        result = []
        first = True

        for i in self.items:
            if first:
                first = False
            else:
                result += esep

            result += i._latex ()

        return result

    def _html (self):
        esep = self.sep._html ()
        result = []
        first = True

        for i in self.items:
            if first:
                first = False
            else:
                result += esep

            result += i._html ()

        return result


def render_latex (value):
    if isinstance (value, int):
        return unicode (value)
    if isinstance (value, unicode):
        return unicode_to_latex (value)
    if isinstance (value, str):
        return unicode_to_latex (unicode (value))
    if isinstance (value, Markup):
        return value.latex ()
    raise ValueError ('don\'t know how to render %r into latex' % value)


def render_html (value):
    if isinstance (value, int):
        return unicode (value)
    if isinstance (value, unicode):
        return html_escape (value)
    if isinstance (value, str):
        return html_escape (unicode (value))
    if isinstance (value, Markup):
        return value.html ()
    raise ValueError ('don\'t know how to render %r into HTML' % value)



class Formatter (object):
    """Substituted items are delimited by pipes |likethis|. This works well in
    both HTML and Latex. If `israw`, the non-substituted template text is
    returned verbatim; otherwise, it is escaped."""

    def __init__ (self, renderer, israw, text):
        from re import split
        pieces = split (r'(\|[^|]+\|)', text)

        def process (piece):
            if len (piece) and piece[0] == '|':
                return True, piece[1:-1]
            return False, piece

        self.tmplinfo = [process (p) for p in pieces]
        self.renderer = renderer
        self.israw = israw

    def _handle_one (self, tmpldata, item):
        issubst, text = tmpldata

        if not issubst:
            if self.israw:
                return text
            return self.renderer (text)

        return self.renderer (item.get (text))

    def __call__ (self, item):
        return ''.join (self._handle_one (d, item) for d in self.tmplinfo)


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
    are Unicode or Markups."""

    info = item.copy ()

    # Canonicalized authors with highlighting of self.
    cauths = [canonicalize_name (a) for a in item.authors.split (';')]

    i = int (item.mypos) - 1
    cauths[i] = MupBold (cauths[i])
    info.authors = MupJoin (', ', cauths)

    # Title with replaced quotes, for nesting in double-quotes.
    info.quotable_title = item.title.replace (u'“', u'‘').replace (u'”', u'’')

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

    url = best_url (item)
    if url is not None:
        info.vcite = MupLink (url, info.vcite)

    return info


def compute_cite_stats (pubs):
    """Compute an h-index and other stats from the known publications."""
    from time import gmtime

    stats = Holder ()
    stats.refpubs = 0
    stats.refcites = 0
    stats.reffirstauth = 0
    cites = []
    dates = []

    for pub in pubs:
        if pub.refereed == 'y':
            stats.refpubs += 1
            if int (pub.mypos) == 1:
                stats.reffirstauth += 1

        citeinfo = parse_ads_cites (pub)
        if citeinfo is None:
            continue
        if citeinfo.cites < 1:
            continue

        cites.append (citeinfo.cites)
        dates.append (citeinfo.lastupdate)

        if pub.refereed == 'y':
            stats.refcites += citeinfo.cites

    if not len (cites):
        stats.meddate = 0
        stats.hindex = 0
    else:
        ranked = sorted (cites, reverse=True)
        index = 0

        while index < len (ranked) and ranked[index] >= index + 1:
            index += 1

        dates = sorted (dates)
        stats.meddate = dates[len (dates) // 2]
        stats.hindex = index

    stats.year, stats.month, stats.day = gmtime (stats.meddate)[:3]
    stats.monthstr = months[stats.month - 1]
    stats.italich = MupItalics ('h')
    return stats


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

    groups.refereed_rev = groups.refereed[::-1]
    groups.non_refereed_rev = groups.non_refereed[::-1]
    return groups


# Commands for templates

def cmd_today (context):
    """Note the trailing period in the output."""
    from time import time, localtime

    # This is a little bit gross.
    yr, mo, dy = localtime (time ())[:3]
    text = '%s%s%d,%s%d.' % (months[mo - 1], nbsp, dy, nbsp, yr)
    return context.render (text)


def cmd_cite_stats (context, template):
    info = compute_cite_stats (context.pubgroups.all)
    return Formatter (context.render, False, slurp_template (template)) (info)


def cmd_pub_list (context, group, template):
    fmt = Formatter (context.render, True, slurp_template (template))
    pubs = context.pubgroups.get (group)
    npubs = len (pubs)

    for num, pub in enumerate (pubs):
        info = cite_info (pub)
        info.number = num + 1
        info.rev_number = npubs - num
        yield fmt (info)


# Driver

def driver (template, render, datadir):
    context = Holder ()
    context.render = render
    context.items = list (load (datadir))
    context.pubs = [i for i in context.items if i.section == 'pub']
    context.pubgroups = partition_pubs (context.pubs)

    commands = {}
    commands['TODAY.'] = cmd_today
    commands['CITESTATS'] = cmd_cite_stats
    commands['PUBLIST'] = cmd_pub_list

    for outline in process_template (template, commands, context):
        print outline.encode ('utf8')


if __name__ == '__main__':
    import sys

    if len (sys.argv) not in (3, 4):
        die ('usage: {driver} <latex|html> <template> [datadir]')

    fmtname = sys.argv[1]
    tmpl = sys.argv[2]

    if len (sys.argv) < 4:
        datadir = '.'
    else:
        datadir = sys.argv[3]

    if fmtname == 'latex':
        render = render_latex
    elif fmtname == 'html':
        render = render_html
    else:
        die ('unknown output format "%s"', fmtname)

    driver (tmpl, render, datadir)
