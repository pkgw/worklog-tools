# -*- mode: python ; coding: utf-8 -*-

"""
Shared routines for my worklog tools.
"""

__all__ = ('nbsp months '
           'Holder die warn open_template slurp_template process_template '
           'unicode_to_latex html_escape '
           'Markup MupText MupItalics MupBold MupLink MupJoin MupList '
           'render_latex render_html Formatter load '
           'parse_ads_cites canonicalize_name surname best_url cite_info '
           'compute_cite_stats partition_pubs '
           'setup_processing').split ()

nbsp = u'\u00a0'
months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split ()


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


def process_template (stream, commands, context):
    """Read through a template line-by-line and replace special lines. Each
    regular line is yielded to the caller. `commands` is a dictionary of
    strings to callables; if the first word in a line is in `commands`, the
    callable is invoked, with `context` and the remaining words in the line as
    arguments. Its return value is either a string or an iterable, with each
    iterate being yielded to the caller in the latter case."""

    for line in stream:
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


class MupList (Markup):
    def __init__ (self, ordered, items):
        self.ordered = bool (ordered)
        self.items = [_maybe_wrap_text (i) for i in items]

    def _latex (self):
        if self.ordered:
            res = [u'\\begin{enumerate}']
        else:
            res = [u'\\begin{itemize}']

        for i in self.items:
            res.append (u'\n\\item ')
            res += i._latex ()

        if self.ordered:
            res.append (u'\n\\end{enumerate}\n')
        else:
            res.append (u'\n\\end{itemize}\n')

        return res

    def _html (self):
        if self.ordered:
            res = [u'<ol>']
        else:
            res = [u'<ul>']

        for i in self.items:
            res.append (u'\n<li>')
            res += i._html ()
            res.append (u'</li>')

        if self.ordered:
            res.append (u'\n</ol>\n')
        else:
            res.append (u'\n</ul>\n')

        return res


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

        try:
            return self.renderer (item.get (text))
        except ValueError as e:
            raise ValueError ((u'while rendering field "%s" of item %s: %s' \
                               % (text, item, e)).encode ('utf-8'))

    def __call__ (self, item):
        return ''.join (self._handle_one (d, item) for d in self.tmplinfo)


# Loading up the data

def load (datadir='.'):
    from os import listdir
    from os.path import join
    from inifile import read as iniread

    any = False

    for item in sorted (listdir (datadir)):
        if not item.endswith ('.txt'):
            continue

        # Note that if there are text files that contain no record (e.g. all
        # commented), we won't complain.
        any = True

        path = join (datadir, item)
        for item in iniread (path):
            yield item

    if not any:
        die ('no data files found in directory "%s"', datadir)


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

    I handle spaces in surnames by replacing them with underscores. Hopefully
    none of my coauthors will ever have an underscore in their names.

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


def surname (name):
    return name.strip ().split ()[-1].replace ('_', ' ')


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


def cite_info (oitem, context):
    """Create a Holder with citation text from a publication item. This can then
    be fed into a template however one wants. The various computed fields are
    are Unicode or Markups.

    `oitem` = original item; not to be modified
    `aitem` = augmented item; = oitem + new fields
    """

    aitem = oitem.copy ()

    # Canonicalized authors with highlighting of self.
    cauths = [canonicalize_name (a) for a in oitem.authors.split (';')]

    i = int (oitem.mypos) - 1
    cauths[i] = MupBold (cauths[i])
    aitem.full_authors = MupJoin (', ', cauths)

    # Short list of authors, possibly abbreviating my name.
    sauths = [surname (a) for a in oitem.authors.split (';')]
    if context.my_abbrev_name is not None:
        sauths[i] = context.my_abbrev_name

    if len (sauths) == 1:
        aitem.short_authors = sauths[0]
    elif len (sauths) == 2:
        aitem.short_authors = ' & '.join (sauths)
    elif len (sauths) == 3:
        aitem.short_authors = ', '.join (sauths)
    else:
        aitem.short_authors = sauths[0] + ' et' + nbsp + 'al.'

    if oitem.refereed == 'y':
        aitem.refereed_mark = u'»'
    else:
        aitem.refereed_mark = u''

    # Title with replaced quotes, for nesting in double-quotes, and
    # optionally-bolded for first authorship.
    aitem.quotable_title = oitem.title.replace (u'“', u'‘').replace (u'”', u'’')

    if i == 0:
        aitem.bold_if_first_title = MupBold (oitem.title)
    else:
        aitem.bold_if_first_title = oitem.title

    # Pub year and nicely-formatted date
    aitem.year, aitem.month = map (int, oitem.pubdate.split ('/'))
    aitem.pubdate = u'%d%s%s' % (aitem.year, nbsp, months[aitem.month - 1])

    # Template-friendly citation count
    citeinfo = parse_ads_cites (oitem)
    if citeinfo is not None and citeinfo.cites > 0:
        aitem.citecountnote = u' [%d]' % citeinfo.cites
    else:
        aitem.citecountnote = u''

    # Citation text with link
    url = best_url (oitem)
    if url is None:
        aitem.lcite = aitem.cite
    else:
        aitem.lcite = MupLink (url, aitem.cite)

    # Other links for the web pub list
    from urllib2 import quote as urlquote

    aitem.abstract_link = u''
    aitem.preprint_link = u''
    aitem.official_link = u''
    aitem.other_link = u''

    if oitem.has ('bibcode'):
        aitem.abstract_link = MupLink ('http://adsabs.harvard.edu/abs/' + urlquote (oitem.bibcode),
                                      'abstract')

    if oitem.has ('arxiv'):
        aitem.preprint_link = MupLink ('http://arxiv.org/abs/' + urlquote (oitem.arxiv),
                                      'preprint')

    if oitem.has ('doi'):
        aitem.official_link = MupLink ('http://dx.doi.org/' + urlquote (oitem.doi),
                                      'official')

    if oitem.has ('url') and not oitem.has ('doi'):
        aitem.other_link = MupLink (oitem.url, oitem.kind)

    return aitem


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
    groups.all_formal = []
    groups.all_non_refereed = []
    groups.informal = []

    for pub in pubs:
        refereed = (pub.refereed == 'y')
        formal = (pub.get ('informal', 'n') == 'n')
        # we assume refereed implies formal.

        groups.all.append (pub)
        if formal:
            groups.all_formal.append (pub)

        if refereed:
            groups.refereed.append (pub)
        else:
            groups.all_non_refereed.append (pub)

            if formal:
                groups.non_refereed.append (pub)
            else:
                groups.informal.append (pub)

    groups.all_rev = groups.all[::-1]
    groups.refereed_rev = groups.refereed[::-1]
    groups.non_refereed_rev = groups.non_refereed[::-1]
    groups.informal_rev = groups.informal[::-1]
    return groups


# Commands for templates

def cmd_cite_stats (context, template):
    info = compute_cite_stats (context.pubgroups.all_formal)
    return Formatter (context.render, False, slurp_template (template)) (info)


def cmd_format (context, *inline_template):
    inline_template = ' '.join (inline_template)
    context.cur_formatter = Formatter (context.render, True, inline_template)
    return ''


def cmd_my_abbrev_name (context, *text):
    context.my_abbrev_name = ' '.join (text)
    return ''


def cmd_pub_list (context, group):
    if context.cur_formatter is None:
        die ('cannot use PUBLIST command before using FORMAT')

    pubs = context.pubgroups.get (group)
    npubs = len (pubs)

    for num, pub in enumerate (pubs):
        info = cite_info (pub, context)
        info.number = num + 1
        info.rev_number = npubs - num
        yield context.cur_formatter (info)


def _rev_misc_list (context, sections, gate):
    if context.cur_formatter is None:
        die ('cannot use RMISCLIST* command before using FORMAT')

    sections = frozenset (sections.split (','))

    for item in context.items[::-1]:
        if item.section not in sections:
            continue
        if not gate (item):
            continue
        yield context.cur_formatter (item)


def cmd_rev_misc_list (context, sections):
    return _rev_misc_list (context, sections, lambda i: True)

def cmd_rev_misc_list_if (context, sections, gatefield):
    """Same a RMISCLIST, but only shows items where a certain item
    is True. XXX: this kind of approach could get out of hand
    quickly."""
    return _rev_misc_list (context, sections,
                           lambda i: i.get (gatefield, 'n') == 'y')

def cmd_rev_misc_list_if_not (context, sections, gatefield):
    return _rev_misc_list (context, sections,
                           lambda i: i.get (gatefield, 'n') != 'y')


def cmd_today (context):
    """Note the trailing period in the output."""
    from time import time, localtime

    # This is a little bit gross.
    yr, mo, dy = localtime (time ())[:3]
    text = '%s%s%d,%s%d.' % (months[mo - 1], nbsp, dy, nbsp, yr)
    return context.render (text)


def setup_processing (render, datadir):
    context = Holder ()
    context.render = render
    context.items = list (load (datadir))
    context.pubs = [i for i in context.items if i.section == 'pub']
    context.pubgroups = partition_pubs (context.pubs)
    context.cur_formatter = None
    context.my_abbrev_name = None

    commands = {}
    commands['CITESTATS'] = cmd_cite_stats
    commands['FORMAT'] = cmd_format
    commands['MYABBREVNAME'] = cmd_my_abbrev_name
    commands['PUBLIST'] = cmd_pub_list
    commands['RMISCLIST'] = cmd_rev_misc_list
    commands['RMISCLIST_IF'] = cmd_rev_misc_list_if
    commands['RMISCLIST_IF_NOT'] = cmd_rev_misc_list_if_not
    commands['TODAY.'] = cmd_today

    return context, commands
