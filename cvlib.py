#! /usr/bin/env python
# -*- mode: python ; coding: utf-8 -*-
# Shared routines for my CV / publication-list tools.

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


# And, conversely, we use a simple HTML parser to deserialize markup trees
# from template text.

from HTMLParser import HTMLParser # note: renamed to html.parser in Py 3.

def _maybe_join (items):
    if not len (items):
        return MupText (u'')
    if len (items) == 1:
        return items[0]
    return MupJoin (u'', items)


class HTMLToMarkupParser (HTMLParser):
    def reset (self):
        # super() doesn't work here for weird reasons
        HTMLParser.reset (self)
        self.stack = [(MupJoin, '', [])]

    def handle_starttag (self, tag, attrs):
        if tag == 'i':
            self.stack.append ((MupItalics, tag, []))
        elif tag == 'b':
            self.stack.append ((MupBold, tag, []))
        elif tag == 'a':
            url = None
            for aname, aval in attrs:
                if aname == 'href':
                    url = aval
            if url is None:
                die ('no "href" attribute in HTML <a> tag')
            self.stack.append ((MupLink, tag, [], url))
        elif tag in ('ol', 'ul'):
            ordered = (tag == 'ol')
            self.stack.append ((MupList, tag, [], ordered))
        elif tag == 'li':
            # We have some basic sanity-checking but are far from
            # comprehensive. I.e., "<ol><b>..." is OK.
            if len (self.stack) < 2:
                die ('disallowed bare <li> in markup HTML')
            if self.stack[-1][0] != MupList:
                die ('disallowed <li> outside of list in markup HTML')
            self.stack.append ((MupJoin, tag, []))
        else:
            die ('disallowed HTML tag "%s" when parsing markup', tag)

    def handle_endtag (self, tag):
        if len (self.stack) < 2:
            die ('endtag "%s" without starttag?', tag)

        info = self.stack.pop ()
        kind, sttag, items = info[:3]

        if tag != sttag:
            die ('mismatching start (%s) and end (%s) tags in HTML',
                 sttag, tag)

        if kind == MupItalics:
            result = MupItalics (_maybe_join (items))
        elif kind == MupBold:
            result = MupBold (_maybe_join (items))
        elif kind == MupLink:
            result = MupLink (info[3], _maybe_join (items))
        elif kind == MupList:
            result = MupList (info[3], items)
        elif kind == MupJoin:
            result = _maybe_join (items)
        else:
            assert False, 'bug in handle_endtag'

        self.stack[-1][2].append (result)

    def handle_data (self, data):
        if not data.strip ():
            return # whitespace between tags
        self.stack[-1][2].append (data)

    def finish (self):
        if len (self.stack) != 1:
            die ('unfinished tags in HTML parse')

        kind, _, items = self.stack[0]
        return _maybe_wrap_text (_maybe_join (items))


def html_to_markup (text):
    p = HTMLToMarkupParser ()
    p.feed (text)
    return p.finish ()


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


def cite_info (item):
    """Create a Holder with citation text from a publication item. This can then
    be fed into a template however one wants. The various computed fields are
    are Unicode or Markups."""

    info = item.copy ()

    # Canonicalized authors with highlighting of self.
    cauths = [canonicalize_name (a) for a in item.authors.split (';')]

    i = int (item.mypos) - 1
    cauths[i] = MupBold (cauths[i])
    info.full_authors = MupJoin (', ', cauths)

    # Short list of authors, with self as 'PKGW'.
    sauths = [surname (a) for a in item.authors.split (';')]
    sauths[i] = 'PKGW'

    if len (sauths) == 1:
        info.short_authors = sauths[0]
    elif len (sauths) == 2:
        info.short_authors = ' & '.join (sauths)
    elif len (sauths) == 3:
        info.short_authors = ', '.join (sauths)
    else:
        info.short_authors = sauths[0] + ' et' + nbsp + 'al.'

    if item.refereed == 'y':
        info.refereed_mark = u'»'
    else:
        info.refereed_mark = u''

    # Title with replaced quotes, for nesting in double-quotes, and
    # optionally-bolded for first authorship.
    info.quotable_title = item.title.replace (u'“', u'‘').replace (u'”', u'’')

    if i == 0:
        info.bold_if_first_title = MupBold (item.title)
    else:
        info.bold_if_first_title = item.title

    # Pub year and nicely-formatted date
    info.year, info.month = map (int, item.pubdate.split ('/'))
    info.pubdate = u'%d%s%s' % (info.year, nbsp, months[info.month - 1])

    # Template-friendly citation count
    citeinfo = parse_ads_cites (item)
    if citeinfo is not None and citeinfo.cites > 0:
        info.citecountnote = u' [%d]' % citeinfo.cites
    else:
        info.citecountnote = u''

    # Citation contents -- a big complicated one. They come in verbose and
    # informal styles.
    if item.has ('yjvi'):
        info.vcite = ', '.join (item.yjvi.split ('/'))
        info.icite = ' '.join (item.yjvi.split ('/')[1:])
    elif item.has ('bookref') and item.has ('posid'):
        # Proceedings of Science
        info.vcite = '%d, in %s, %s' % (info.year, item.bookref, item.posid)
        info.icite = '%s (%s)' % (item.bookref, item.posid)
    elif item.has ('series') and item.has ('itemid'):
        # Various numbered series.
        info.vcite = '%d, %s, #%s' % (info.year, item.series, item.itemid)
        info.icite = '%s #%s' % (item.series, item.itemid)
    elif item.has ('tempstatus'):
        # "in prep"-type items with temporary, manually-set info
        info.vcite = item.tempstatus
        info.icite = item.tempstatus
    else:
        die ('no citation information for %s', item)

    url = best_url (item)
    if url is not None:
        info.vcite = MupLink (url, info.vcite)

    # Other links for the web pub list
    from urllib2 import quote as urlquote

    if item.has ('bibcode'):
        info.abstract_link = MupLink ('http://adsabs.harvard.edu/abs/' + urlquote (item.bibcode),
                                      'abstract')
    else:
        info.abstract_link = u''

    if item.has ('arxiv'):
        info.preprint_link = MupLink ('http://arxiv.org/abs/' + urlquote (item.arxiv),
                                      'preprint')
    else:
        info.preprint_link = u''

    if item.has ('doi'):
        info.official_link = MupLink ('http://dx.doi.org/' + urlquote (item.doi),
                                      'official')
    else:
        info.official_link = u''

    if item.has ('url') and not item.has ('doi'):
        info.other_link = MupLink (item.url, item.kind)
    else:
        info.other_link = u''

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


def cmd_markup (context, template):
    return context.render (html_to_markup (slurp_template (template)))


def cmd_format (context, *inline_template):
    inline_template = ' '.join (inline_template)
    context.cur_formatter = Formatter (context.render, True, inline_template)
    return ''


def cmd_pub_list (context, group):
    if context.cur_formatter is None:
        die ('cannot use PUBLIST command before using FORMAT')

    pubs = context.pubgroups.get (group)
    npubs = len (pubs)

    for num, pub in enumerate (pubs):
        info = cite_info (pub)
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


# Command-line driver

def setup_processing (render, datadir):
    context = Holder ()
    context.render = render
    context.items = list (load (datadir))
    context.pubs = [i for i in context.items if i.section == 'pub']
    context.pubgroups = partition_pubs (context.pubs)
    context.cur_formatter = None

    commands = {}
    commands['CITESTATS'] = cmd_cite_stats
    commands['MARKUP'] = cmd_markup
    commands['FORMAT'] = cmd_format
    commands['PUBLIST'] = cmd_pub_list
    commands['RMISCLIST'] = cmd_rev_misc_list
    commands['RMISCLIST_IF'] = cmd_rev_misc_list_if
    commands['RMISCLIST_IF_NOT'] = cmd_rev_misc_list_if_not
    commands['TODAY.'] = cmd_today

    return context, commands


def _cli_render (argv):
    fmtname = argv[0]

    if len (argv) not in (2, 3):
        die ('usage: {driver} %s <template> [datadir]', fmtname)

    tmpl = argv[1]

    if len (argv) < 3:
        datadir = '.'
    else:
        datadir = argv[2]

    if fmtname == 'latex':
        render = render_latex
    elif fmtname == 'html':
        render = render_html
    else:
        die ('unknown output format "%s"', fmtname)

    context, commands = setup_processing (render, datadir)

    with open (tmpl) as f:
        for outline in process_template (f, commands, context):
            print outline.encode ('utf8')


cli_latex = _cli_render
cli_html = _cli_render


def cli_extract (argv):
    from inifile import write
    import sys

    if len (argv) not in (2, 3):
        die ('usage: {driver} extract <section-name> [datadir]')

    sectname = argv[1]

    if len (argv) < 3:
        datadir = '.'
    else:
        datadir = argv[2]

    write (sys.stdout, (i for i in load (datadir) if i.section == sectname))


def cli_summarize (argv):
    if len (argv) not in (1, 2):
        die ('usage: {driver} summarize [datadir]')

    if len (argv) < 2:
        datadir = '.'
    else:
        datadir = argv[1]

    counts = {}
    maxsectlen = 0

    for i in load (datadir):
        counts[i.section] = counts.get (i.section, 0) + 1
        maxsectlen = max (maxsectlen, len (i.section))

    for section, count in sorted (counts.iteritems ()):
        print '% *s: %d' % (maxsectlen, section, count)


if __name__ == '__main__':
    import sys

    if len (sys.argv) < 2:
        die ('usage: {driver} <command> [args...]')

    cmdname = sys.argv[1]
    clicmd = globals ().get ('cli_' + cmdname)

    if not callable (clicmd):
        die ('unknown subcommand "%s"', cmdname)

    clicmd (sys.argv[1:])
