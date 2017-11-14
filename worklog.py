# -*- mode: python ; coding: utf-8 -*-
# Copyright 2014-2017 Peter Williams <peter@newton.cx>
# Licensed under the GNU General Public License, version 3 or higher.

"""
Shared routines for my worklog tools.
"""

from __future__ import absolute_import, division, print_function
from six import string_types, text_type
from six.moves import map, range, zip

__all__ = str('''
nbsp
months
Holder
die
warn
open_template
slurp_template
process_template
list_data_files
load
unicode_to_latex
html_escape
Markup
MupText
MupItalics
MupBold
MupUnderline
MupLink
MupJoin
MupList
render_latex
render_html
Formatter
ADSCountError
parse_ads_cites
canonicalize_name
surname
best_url
cite_info
compute_cite_stats
partition_pubs
setup_processing
get_ads_cite_count
bootstrap_bibtex''').split()

nbsp = u'\u00a0'
months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()


# Infrastructure

from inifile import Holder

def die(fmt, *args):
    if len(args):
        text = fmt % args
    else:
        text = str(fmt)

    raise SystemExit('error: ' + text)


def warn(fmt, *args):
    if len(args):
        text = fmt % args
    else:
        text = str(fmt)

    import sys
    print('warning:', text, file=sys.stderr)


def open_template(stem):
    from os.path import join, dirname
    from errno import ENOENT

    try:
        return open(join('templates', stem))
    except IOError as e:
        if e.errno != ENOENT:
            raise

    try:
        return open(join(dirname(__file__), 'templates', stem))
    except Exception as e:
        die('cannot open template "%s": %s (%s)', stem, e, e.__class__.__name__)


def slurp_template(stem):
    with open_template(stem) as f:
        return f.read().decode('utf8')


class MultilineHandler(object):
    def handle_line(self, context, line):
        raise NotImplementedError()
    def handle_end_span(self, context):
        raise NotImplementedError()


def process_template(stream, commands, context):
    """Read through a template line-by-line and replace special lines. Each
    regular line is yielded to the caller. `commands` is a dictionary of
    strings to callables; if the first word in a line is in `commands`, the
    callable is invoked, with `context` and the remaining words in the line as
    arguments. Its return value is either a string or an iterable, with each
    iterate being yielded to the caller in the latter case."""

    current_multiline_handler = None

    for line in stream:
        line = line.decode('utf8').rstrip()

        if current_multiline_handler is not None:
            if line != 'END':
                current_multiline_handler.handle_line(context, line)
            else:
                result = current_multiline_handler.handle_end_span(context)
                if isinstance(result, string_types):
                    yield result
                else:
                    for subline in result:
                        yield subline
                current_multiline_handler = None
        else:
            a = line.split()

            if not len(a) or a[0] not in commands:
                yield line
            else:
                result = commands[a[0]](context, *a[1:])
                if isinstance(result, string_types):
                    yield result
                elif isinstance(result, MultilineHandler):
                    current_multiline_handler = result
                else:
                    for subline in result:
                        yield subline


def list_data_files(datadir='.'):
    from os import listdir
    from os.path import join

    any = False

    for item in sorted(listdir(datadir)):
        if item.startswith('.'):
            continue
        if not item.endswith('.txt'):
            continue

        # Note that if there are text files that contain no records (e.g. all
        # commented), we won't complain.
        any = True
        yield join(datadir, item)

    if not any:
        die('no data files found in directory "%s"', datadir)


def load(datadir='.'):
    from inifile import read as iniread

    for path in list_data_files(datadir):
        for item in iniread(path):
            yield item


# Text formatting. We have a tiny DOM-type system for markup so we can
# abstract across LaTeX and HTML. Initially I tried to do everything in HTML,
# and then convert that to LaTeX, but the layers of escaping got a little
# worrisome, and some constructs just don't work well in that model (e.g.
# tables). So we do this silliness instead.

from unicode_to_latex import unicode_to_latex, unicode_to_latex_string

def html_escape(text):
    """Escape special characters for our dumb subset of HTML."""

    return(text_type(text)
           .replace('&', '&amp;')
           .replace('<', '&lt;')
           .replace('>', '&gt;')
           .replace('"', '&quot;')
           .replace("'", '&apos;'))


class Markup(object):
    def _latex(self):
        raise NotImplementedError()

    def _html(self):
        raise NotImplementedError()

    def latex(self):
        return u''.join(self._latex())

    def html(self):
        return u''.join(self._html())



def _maybe_wrap_text(thing):
    if isinstance(thing, Markup):
        return thing
    return MupText(thing)


class MupText(Markup):
    def __init__(self, text):
        self.text = text_type(text)

    def _latex(self):
        return [unicode_to_latex_string(self.text)]

    def _html(self):
        return [html_escape(self.text)]


class MupItalics(Markup):
    def __init__(self, inner):
        self.inner = _maybe_wrap_text(inner)

    def _latex(self):
        return [u'\\textit{'] + self.inner._latex() + [u'}']

    def _html(self):
        return [u'<i>'] + self.inner._html() + [u'</i>']


class MupBold(Markup):
    def __init__(self, inner):
        self.inner = _maybe_wrap_text(inner)

    def _latex(self):
        return [u'\\textbf{'] + self.inner._latex() + [u'}']

    def _html(self):
        return [u'<b>'] + self.inner._html() + [u'</b>']


class MupUnderline(Markup):
    def __init__(self, inner):
        self.inner = _maybe_wrap_text(inner)

    def _latex(self):
        return [u'\\underline{'] + self.inner._latex() + [u'}']

    def _html(self):
        return [u'<u>'] + self.inner._html() + [u'</u>']


class MupLink(Markup):
    def __init__(self, url, inner):
        self.url = str(url)
        self.inner = _maybe_wrap_text(inner)

    def _latex(self):
        return([u'\\href{', self.url.replace(u'%', u'\\%'), u'}{'] +
                self.inner._latex() + [u'}'])

    def _html(self):
        return([u'<a href="', html_escape(self.url), u'">'] +
                self.inner._html() + [u'</a>'])


class MupJoin(Markup):
    def __init__(self, sep, items):
        self.sep = _maybe_wrap_text(sep)
        self.items = [_maybe_wrap_text(i) for i in items]

    def _latex(self):
        esep = self.sep._latex()
        result = []
        first = True

        for i in self.items:
            if first:
                first = False
            else:
                result += esep

            result += i._latex()

        return result

    def _html(self):
        esep = self.sep._html()
        result = []
        first = True

        for i in self.items:
            if first:
                first = False
            else:
                result += esep

            result += i._html()

        return result


class MupList(Markup):
    def __init__(self, ordered, items):
        self.ordered = bool(ordered)
        self.items = [_maybe_wrap_text(i) for i in items]

    def _latex(self):
        if self.ordered:
            res = [u'\\begin{enumerate}']
        else:
            res = [u'\\begin{itemize}']

        for i in self.items:
            res.append(u'\n\\item ')
            res += i._latex()

        if self.ordered:
            res.append(u'\n\\end{enumerate}\n')
        else:
            res.append(u'\n\\end{itemize}\n')

        return res

    def _html(self):
        if self.ordered:
            res = [u'<ol>']
        else:
            res = [u'<ul>']

        for i in self.items:
            res.append(u'\n<li>')
            res += i._html()
            res.append(u'</li>')

        if self.ordered:
            res.append(u'\n</ol>\n')
        else:
            res.append(u'\n</ul>\n')

        return res


def render_latex(value):
    if isinstance(value, int):
        return str(value)
    if isinstance(value, text_type):
        return unicode_to_latex_string(value)
    if isinstance(value, string_types):
        return unicode_to_latex_string(text_type(value))
    if isinstance(value, Markup):
        return value.latex()
    raise ValueError('don\'t know how to render %r into latex' % value)


def render_html(value):
    if isinstance(value, int):
        return str(value)
    if isinstance(value, text_type):
        return html_escape(value)
    if isinstance(value, string_types):
        return html_escape(text_type(value))
    if isinstance(value, Markup):
        return value.html()
    raise ValueError('don\'t know how to render %r into HTML' % value)



class Formatter(object):
    """Substituted items are delimited by pipes |likethis|. This works well in
    both HTML and Latex. If `israw`, the non-substituted template text is
    returned verbatim; otherwise, it is escaped.

    We have a special hack. If the substituted item is specified as
    |texturl:foo|, the key "foo" will be looked in `item` and output as a link
    whose text value is the same as its URL: i.e.

       <a href="http://...">http://...</a>

    This particular tactic is needed to work with textual URLs in LaTeX, since
    the \\url{} and \\href{} commands redefine character codes such that the
    standard LaTeX escaping mechanism is inappropriate. In particular, URLs
    with tildes were breaking.

    """
    def __init__(self, renderer, israw, text):
        from re import split
        pieces = split(r'(\|[^|]+\|)', text)

        def process(piece):
            if len(piece) and piece[0] == '|':
                return True, piece[1:-1]
            return False, piece

        self.tmplinfo = [process(p) for p in pieces]
        self.renderer = renderer
        self.israw = israw

    def _handle_one(self, tmpldata, item):
        issubst, text = tmpldata

        if not issubst:
            if self.israw:
                return text
            return self.renderer(text)

        try:
            if text.startswith('texturl:'):
                thing = item.get(text[8:])
                thing = MupLink(thing, thing)
            else:
                thing = item.get(text)
            return self.renderer(thing)
        except ValueError as e:
            raise ValueError((u'while rendering field "%s" of item %s: %s' \
                              % (text, item, e)).encode('utf-8'))

    def __call__(self, item):
        return ''.join(self._handle_one(d, item) for d in self.tmplinfo)


# Utilities for dealing with publications.

def parse_ads_cites(pub):
    from time import mktime

    if not pub.has('adscites'):
        return None

    try:
        a = pub.adscites.split()[:2]
        y, m, d = [int(x) for x in a[0].split('/')]
        lastupdate = int(mktime((y, m, d, 0, 0, 0, 0, 0, 0)))
        cites = int(a[1])
    except Exception:
        warn('cannot parse adscites entry "%s"', pub.adscites)
        return None

    return Holder(lastupdate=lastupdate, cites=cites)


def canonicalize_name(name):
    """Convert a name into "canonical" form, by which I mean something like "PKG
    Williams". The returned string uses a nonbreaking space between the two
    pieces.

    I handle spaces in surnames by replacing them with underscores. Hopefully
    none of my coauthors will ever have an underscore in their names.

    TODO: handle "Surname, First Middle" etc.
    TODO: also Russian initials: Yu. G. Levin
    """

    bits = name.strip().split()
    surname = bits[-1].replace('_', ' ')
    rest = bits[:-1]
    abbrev = []

    for item in rest:
        for char in item:
            if char.isupper() or char == '-':
                abbrev.append(char)

    return ''.join(abbrev) + nbsp + surname


def surname(name):
    return name.strip().split()[-1].replace('_', ' ')


def best_url(item):
    try:
        from urllib.parse import quote
    except ImportError:
        from urllib2 import quote

    if item.has('bibcode'):
        return 'http://adsabs.harvard.edu/abs/' + quote(item.bibcode)
    if item.has('doi'):
        return 'http://dx.doi.org/' + quote(item.doi)
    if item.has('url'):
        return item.url
    if item.has('arxiv'):
        return 'http://arxiv.org/abs/' + quote(item.arxiv)

    return None


def cite_info(oitem, context):
    """Create a Holder with citation text from a publication item. This can then
    be fed into a template however one wants. The various computed fields are
    are Unicode or Markups.

    `oitem` = original item; not to be modified
    `aitem` = augmented item; = oitem + new fields
    """

    aitem = oitem.copy()

    # Canonicalized authors with bolding of self and underlining of advisees.
    cauths = [canonicalize_name(a) for a in oitem.authors.split(';')]

    myidx = int(oitem.mypos) - 1
    cauths[myidx] = MupBold(cauths[myidx])

    advposlist = oitem.get('advpos', '')
    if len(advposlist):
        for i in [int(x) - 1 for x in advposlist.split(',')]:
            cauths[i] = MupUnderline(cauths[i])

    aitem.full_authors = MupJoin(', ', cauths)

    # Short list of authors, possibly abbreviating my name.
    sauths = [surname(a) for a in oitem.authors.split(';')]
    if context.my_abbrev_name is not None:
        sauths[myidx] = context.my_abbrev_name

    if len(advposlist):
        for i in [int(x) - 1 for x in advposlist.split(',')]:
            sauths[i] = MupUnderline(sauths[i])

    if len(sauths) == 1:
        aitem.short_authors = sauths[0]
    elif len(sauths) == 2:
        aitem.short_authors = MupJoin(' & ', sauths)
    elif len(sauths) == 3:
        aitem.short_authors = MupJoin(', ', sauths)
    else:
        aitem.short_authors = MupJoin(' ', [sauths[0], 'et' + nbsp + 'al.'])

    if oitem.refereed == 'y':
        aitem.refereed_mark = u'»'
    else:
        aitem.refereed_mark = u''

    # Title with replaced quotes, for nesting in double-quotes, and
    # optionally-bolded for first authorship.
    aitem.quotable_title = oitem.title.replace(u'“', u'‘').replace(u'”', u'’')

    if myidx == 0:
        aitem.bold_if_first_title = MupBold(oitem.title)
    else:
        aitem.bold_if_first_title = oitem.title

    # Pub year and nicely-formatted date
    aitem.year, aitem.month = list(map(int, oitem.pubdate.split('/')))
    aitem.pubdate = u'%d%s%s' % (aitem.year, nbsp, months[aitem.month - 1])

    # Template-friendly citation count
    citeinfo = parse_ads_cites(oitem)
    if citeinfo is not None and citeinfo.cites > 0:
        aitem.citecountnote = u' [%d]' % citeinfo.cites
    else:
        aitem.citecountnote = u''

    # Citation text with link
    url = best_url(oitem)
    if url is None:
        aitem.lcite = aitem.cite
    else:
        aitem.lcite = MupLink(url, aitem.cite)

    # Other links for the web pub list
    try:
        from urllib.parse import quote as urlquote
    except ImportError:
        from urllib2 import quote as urlquote

    aitem.abstract_link = u''
    aitem.preprint_link = u''
    aitem.official_link = u''
    aitem.other_link = u''

    if oitem.has('bibcode'):
        aitem.abstract_link = MupLink('http://adsabs.harvard.edu/abs/' + urlquote(oitem.bibcode),
                                      'abstract')

    if oitem.has('arxiv'):
        aitem.preprint_link = MupLink('http://arxiv.org/abs/' + urlquote(oitem.arxiv),
                                      'preprint')

    if oitem.has('doi'):
        aitem.official_link = MupLink('http://dx.doi.org/' + urlquote(oitem.doi),
                                      'official')

    if oitem.has('url') and not oitem.has('doi'):
        aitem.other_link = MupLink(oitem.url, oitem.kind)

    return aitem


def compute_cite_stats(pubs):
    """Compute an h-index and other stats from the known publications."""
    from time import gmtime

    stats = Holder()
    stats.refpubs = 0
    stats.refcites = 0
    stats.reffirstauth = 0
    cites = []
    dates = []

    for pub in pubs:
        if pub.refereed == 'y':
            stats.refpubs += 1
            if int(pub.mypos) == 1:
                stats.reffirstauth += 1

        citeinfo = parse_ads_cites(pub)
        if citeinfo is None:
            continue
        if citeinfo.cites < 1:
            continue

        cites.append(citeinfo.cites)
        dates.append(citeinfo.lastupdate)

        if pub.refereed == 'y':
            stats.refcites += citeinfo.cites

    if not len(cites):
        stats.meddate = 0
        stats.hindex = 0
    else:
        ranked = sorted(cites, reverse=True)
        index = 0

        while index < len(ranked) and ranked[index] >= index + 1:
            index += 1

        dates = sorted(dates)
        stats.meddate = dates[len(dates) // 2]
        stats.hindex = index

    stats.year, stats.month, stats.day = gmtime(stats.meddate)[:3]
    stats.monthstr = months[stats.month - 1]
    stats.italich = MupItalics('h')
    stats.adslink = MupLink('http://labs.adsabs.harvard.edu/adsabs', 'ADS')
    return stats


def partition_pubs(pubs):
    groups = Holder()
    groups.all = []
    groups.refereed = []
    groups.refpreprint = []
    groups.non_refereed = []
    groups.all_formal = []
    groups.all_non_refereed = []
    groups.informal = []
    groups.chapters = []

    for pub in pubs:
        refereed = (pub.refereed == 'y')
        refpreprint = (pub.get('refpreprint', 'n') == 'y')
        chapter = (pub.get('kind', 'default') == 'book chapter')
        formal = (pub.get('informal', 'n') == 'n')
        # we assume refereed implies formal.

        groups.all.append(pub)
        if formal:
            groups.all_formal.append(pub)

        if refereed:
            groups.refereed.append(pub)
        elif refpreprint:
            groups.refpreprint.append(pub)
        elif chapter:
            groups.chapters.append(pub)
        else:
            groups.all_non_refereed.append(pub)

            if formal:
                groups.non_refereed.append(pub)
            else:
                groups.informal.append(pub)

    groups.all_rev = groups.all[::-1]
    groups.chapters_rev = groups.chapters[::-1]
    groups.refereed_rev = groups.refereed[::-1]
    groups.refpreprint_rev = groups.refpreprint[::-1]
    groups.non_refereed_rev = groups.non_refereed[::-1]
    groups.informal_rev = groups.informal[::-1]
    return groups


# Utilities for dealing with allocated observing time. Namely, we total up the
# time allocated for each telescope as PI.

def compute_time_allocations(props):
    allocs = {}

    def get_contributions(prop):
        amount = prop.get('award')
        if amount is None:
            amount = prop.get('request')
        if amount is None:
            die('no "award" or "request" for proposal %s', prop)

        try:
            facil1 = prop.facil
            quantity1, units1 = amount.split()
            quantity1 = float(quantity1)
        except Exception as e:
            die('error processing primary outcome of proposal <%s>: %s', prop, e)

        yield facil1, quantity1, units1

        i = 2

        while True:
            amount = prop.get('award%d' % i)
            if amount is None:
                amount = prop.get('request%d' % i)
            if amount is None:
                break

            try:
                quantity, units, facil = amount.split(None, 2)
                quantity = float(quantity)
            except Exception as e:
                die('error processing outcome #%d of proposal <%s>: %s', i, prop, e)

            yield facil, quantity, units
            i += 1

    for prop in props:
        if prop.get('mepi', 'n') != 'y':
            continue # self as PI only

        if prop.get('accepted', 'n') != 'y':
            continue # only accepted ones!

        for facil, quantity, units in get_contributions(prop):
            if facil not in allocs:
                allocs[facil] = (quantity, units)
            else:
                q0, u0 = allocs[facil]
                if u0 != units:
                    die('disagreeing time units for %s: both "%s" and "%s"',
                         facil, u0, units)
                allocs[facil] = (q0 + quantity, u0)

    # Implement the hack for putting support funding last and in italics. For
    # some allocations we have fractional precision (e.g., right now I've been
    # awarded 244.64 ks on Chandra), but the float formatting is annoying to
    # get to work universally, so just round everything off.

    def process(facil_text, info):
        quantity, unit = info
        is_summary = facil_text.startswith('SUMMARY:')

        if is_summary:
            facil = MupItalics(facil_text[8:])
        else:
            facil = facil_text

        return Holder(
            is_summary = is_summary,
            facil = facil,
            total = '%.0f' % quantity,
            unit = unit,
        )

    return sorted((process(k, v) for (k, v) in allocs.items()),
                  key=lambda h: (h.is_summary, h.facil))


# Utilities for dealing with public code repositories

def process_repositories(items):
    try:
        from urllib.parse import quote as urlquote
    except ImportError:
        from urllib2 import quote as urlquote
    repos = []

    for i in items:
        if i.section != 'repo':
            continue
        if i.get('skip', 'n') == 'y':
            continue
        if i.usercommits == '0':
            continue

        repo = i.copy()
        repos.append(repo)

        if i.service == 'github':
            repo.linkname = MupLink('https://github.com/' + urlquote(i.name), i.name)
        else:
            repo.linkname = i.name

        repo.commit_frac = '%.0f%%' % (100. * int(i.usercommits) / int(i.allcommits))
        if repo.commit_frac == '0%':
            repo.commit_frac = '<1%'

        repo.luc_year, repo.luc_month, repo.luc_day = [int(x) for x in i.lastusercommit.split('/')]
        repo.date = '%04d %s' % (repo.luc_year, months[repo.luc_month - 1])
        repo._datekey = repo.luc_year * 10000 + repo.luc_month * 100 + repo.luc_day

    return sorted(repos, key=lambda r: r._datekey)


def compute_repo_stats(repos):
    info = {}
    info['total_repos'] = len(repos)

    tc = 0
    pa_stars = 0
    pa_forks = 0

    for repo in repos:
        tc += int(repo.usercommits)

        if 2 * int(repo.usercommits) > int(repo.allcommits): # >=50% of commits ("primary author")?
            pa_stars += int(repo.get('stars', '0'))
            pa_forks += int(repo.get('forks', '0'))

    info['total_commits'] = tc
    info['primary_author_stars'] = pa_stars
    info['primary_author_forks'] = pa_forks
    return info


# (Professional) Talks

def summarize_talks(talks):
    info = {}
    info['n_total'] = len(talks)
    info['n_invited'] = len([t for t in talks if t.get('invited', 'n') == 'y'])
    info['n_conference'] = len([t for t in talks if t.get('conference', 'n') == 'y'])
    return info


# Public engagement

def summarize_engagement(items):
    info = {}
    count = lambda c: len([i for i in items if i.get('class', '?') == c])

    info['n_interviews'] = count('interview')
    info['n_outreach_events'] = count('outreach_event')
    info['n_press_releases'] = count('press_release')
    info['n_public_talks'] = count('public_talk')
    return info


# Commands for templates

class MultilineSubstHandler(MultilineHandler):
    def __init__(self, info):
        self.info = info
        self.lines = []

    def handle_line(self, context, line):
        self.lines.append(line)

    def handle_end_span(self, context):
        tmpl = '\n'.join(self.lines)
        return Formatter(context.render, True, tmpl)(self.info)


def cmd_begin_subst(context, group):
    try:
        info = getattr(context, group)
    except AttributeError:
        die('no such substitution group \"%s\" for BEGIN_SUBST command', group)
    return MultilineSubstHandler(info)


def cmd_format(context, *inline_template):
    inline_template = ' '.join(inline_template)
    context.cur_formatter = Formatter(context.render, True, inline_template)
    return ''


def cmd_my_abbrev_name(context, *text):
    context.my_abbrev_name = ' '.join(text)
    return ''


def cmd_pub_list(context, group):
    if context.cur_formatter is None:
        die('cannot use PUBLIST command before using FORMAT')

    pubs = context.pubgroups.get(group)
    npubs = len(pubs)

    for num, pub in enumerate(pubs):
        info = cite_info(pub, context)
        info.number = num + 1
        info.rev_number = npubs - num
        yield context.cur_formatter(info)


def cmd_talloc_list(context):
    if context.cur_formatter is None:
        die('cannot use TALLOCLIST command before using FORMAT')

    for info in context.time_allocs:
        yield context.cur_formatter(info)


def cmd_split_talloc_list(context, *split_template):
    if context.cur_formatter is None:
        die('cannot use SPLIT_TALLOCLIST command before using FORMAT')

    split_template = ' '.join(split_template)
    alloc_info = list(context.time_allocs)
    n = len(alloc_info)

    for info in alloc_info[:(n+1)//2]:
        yield context.cur_formatter(info)

    yield split_template

    for info in alloc_info[(n+1)//2:]:
        yield context.cur_formatter(info)


def _rev_misc_list(context, sections, gate):
    if context.cur_formatter is None:
        die('cannot use RMISCLIST* command before using FORMAT')

    sections = frozenset(sections.split(','))

    for item in context.items[::-1]:
        if item.section not in sections:
            continue
        if not gate(item):
            continue
        yield context.cur_formatter(item)


def cmd_rev_misc_list(context, sections):
    return _rev_misc_list(context, sections, lambda i: True)

def cmd_rev_misc_list_if(context, sections, gatefield):
    """Same a RMISCLIST, but only shows items where a certain item
    is True. XXX: this kind of approach could get out of hand
    quickly."""
    return _rev_misc_list(context, sections,
                          lambda i: i.get(gatefield, 'n') == 'y')

def cmd_rev_misc_list_if_not(context, sections, gatefield):
    return _rev_misc_list(context, sections,
                          lambda i: i.get(gatefield, 'n') != 'y')

def cmd_rev_repo_list(context, sections):
    if context.cur_formatter is None:
        die('cannot use RREPOLIST command before using FORMAT')

    sections = frozenset(sections.split(','))

    for item in context.repos[::-1]:
        if item.section not in sections:
            continue
        yield context.cur_formatter(item)


def cmd_today(context):
    """Note the trailing period in the output."""
    from time import time, localtime

    # This is a little bit gross.
    yr, mo, dy = localtime(time())[:3]
    text = '%s%s%d,%s%d.' % (months[mo - 1], nbsp, dy, nbsp, yr)
    return context.render(text)


def setup_processing(render, datadir):
    context = Holder()
    context.render = render
    context.items = list(load(datadir))
    context.pubs = [i for i in context.items if i.section == 'pub']
    context.pubgroups = partition_pubs(context.pubs)
    context.props = [i for i in context.items if i.section == 'prop']
    context.time_allocs = compute_time_allocations(context.props)
    context.repos = process_repositories(context.items)
    context.cite_stats = compute_cite_stats(context.pubgroups.all_formal)
    context.repo_stats = compute_repo_stats(context.repos)
    context.talk_stats = summarize_talks([i for i in context.items if i.section == 'talk'])
    context.engagement_stats = summarize_engagement([i for i in context.items if i.section == 'engagement'])
    context.cur_formatter = None
    context.my_abbrev_name = None

    commands = {}
    commands['BEGIN_SUBST'] = cmd_begin_subst
    commands['FORMAT'] = cmd_format
    commands['MYABBREVNAME'] = cmd_my_abbrev_name
    commands['PUBLIST'] = cmd_pub_list
    commands['TALLOCLIST'] = cmd_talloc_list
    commands['SPLIT_TALLOCLIST'] = cmd_split_talloc_list
    commands['RMISCLIST'] = cmd_rev_misc_list
    commands['RMISCLIST_IF'] = cmd_rev_misc_list_if
    commands['RMISCLIST_IF_NOT'] = cmd_rev_misc_list_if_not
    commands['RREPOLIST'] = cmd_rev_repo_list
    commands['TODAY.'] = cmd_today

    return context, commands


# ADS citation counts

# this custom format returns exactly the ADS citation count
_ads_url_tmpl =(r'http://adsabs.harvard.edu/cgi-bin/nph-abs_connect?'
                r'bibcode=%(bibcode)s&data_type=Custom&format=%%25c&nocookieset=1')


class ADSCountError(Exception):
    def __init__(self, fmt, *args):
        super(ADSCountError, self).__init__(fmt % args)


def get_ads_cite_count(bibcode):
    try:
        from http import client
        from urllib.request import urlopen
        from urllib.parse import quote
        from urllib.error import URLError
    except ImportError:
        import httplib as client
        from urllib2 import urlopen, quote, URLError

    url = _ads_url_tmpl % {'bibcode': quote(bibcode)}
    lastnonempty = None

    try:
        for line in urlopen(url):
            line = line.strip()
            if len(line):
                lastnonempty = line
    except client.BadStatusLine as e:
        raise ADSCountError('received bad HTTP status: %r', e)
    except URLError as e:
        raise ADSCountError('%s', e)

    if lastnonempty is None:
        raise ADSCountError('got only empty lines')

    if lastnonempty.startswith(b'Retrieved 0 abstracts'):
        raise ADSCountError('no such bibcode')

    try:
        count = int(lastnonempty)
    except Exception:
        raise ADSCountError('got unexpected final line %r', lastnonempty)

    return count


# Bootstrapping from a BibTeX file. This is currently aimed 100% at
# ADS-generated BibTeX; it'd be nice to make it more general.

def _write_with_wrapping(outfile, key, value):
    # we assume whitespace is fungible.

    if '#' in value:
        print(('%s = "%s"' % (key, value)).encode('utf-8'), file=outfile)
        return

    bits = value.split()
    ofs = len(key) + 2
    head = 0
    tail = 0

    while tail < len(bits):
        ofs += len(bits[tail]) + 1
        tail += 1

        if ofs > 78:
            if head == 0:
                s = '%s = %s' % (key, ' '.join(bits[head:tail]))
            else:
                s = '  %s' % (' '.join(bits[head:tail]))
            print(s.encode('utf-8'), file=outfile)
            head = tail
            ofs = 1

    if head == 0:
        s = '%s = %s' % (key, ' '.join(bits[head:tail]))
    elif head < len(bits):
        s = '  %s' % (' '.join(bits[head:tail]))
    else:
        return

    print(s.encode('utf-8'), file=outfile)


def _bib_fixup_author(text):
    text = text.replace('{', '').replace('}', '').replace('~', ' ')
    surname, rest = text.split(',', 1)
    return rest + ' ' + surname.replace(' ', '_')


_bib_months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
               'may': '05',  'jun': '06',  'jul': '07',  'aug': '08',
               'sep': '09',  'oct': '10',  'nov': '11',  'dec': '12'}

_bib_journals = {'\\aap': 'A&Ap', '\\aj': 'AJ', '\\apj': 'ApJ',
                 '\\apjl': 'ApJL', '\\apjs': 'ApJS', '\\araa': 'ARA&A',
                 '\\mnras': 'MNRAS', '\\pasa': 'PASA'}


def _bib_cite(rec):
    if 'journal' in rec and 'volume' in rec and 'pages' in rec:
        return ' '.join((rec['journal'], rec['volume'], rec['pages']))

    if 'series' in rec and 'volume' in rec and 'pages' in rec:
        return ' '.join((rec['series'], rec['volume'], rec['pages']))

    if rec.get('type') == 'inproceedings' and 'booktitle' in rec and 'pages' in rec:
        return u'proceedings of “%s”, %s' % (rec['booktitle'], rec['pages'])

    if rec.get('journal') == u'ArXiv e-prints' and 'eprint' in rec:
        return u'arxiv:' + rec['eprint']

    return None


class BibCustomizer(object):
    # By "customize" the bibtexparser module just means post-processing. These
    # are a bunch of ad-hoc hacks based on what ADS gives us.

    def __init__(self, mysurname):
        self.mylsurname = mysurname.lower()

    def __call__(self, rec):
        from bibtexparser.customization import author, type, convert_to_unicode
        rec = type(convert_to_unicode(rec))

        for key in list(rec.keys()):
            val = rec.get(key)
            val = (val
                   .replace('{\\nbsp}', nbsp)
                   .replace('``', u'“')
                   .replace("''", u'”'))
            rec[key] = val

        if 'journal' in rec:
            rec['journal'] = _bib_journals.get(rec['journal'].lower(),
                                               rec['journal'])

        rec = author(rec)

        if 'author' in rec:
            newauths = []

            for idx, text in enumerate(rec['author']):
                text = text.replace('{', '').replace('}', '').replace('~', ' ')
                surname, rest = text.split(',', 1)
                if surname.lower() == self.mylsurname:
                    rec['wl_mypos'] = text_type(idx + 1)
                newauths.append(rest + ' ' + surname.replace(' ', '_'))

            rec['author'] = '; '.join(newauths)

        rec['wl_cite'] = _bib_cite(rec)
        return rec


def bootstrap_bibtex(bibfile, outdir, mysurname):
    import os.path

    # XXX we assume heavily that we're dealing with ADS bibtex.

    from bibtexparser.bparser import BibTexParser
    bp = BibTexParser(bibfile, customization=BibCustomizer(mysurname))
    byyear = {}

    for rec in bp.get_entry_list():
        year = rec.get('year', 'noyear')

        if year in byyear:
            outfile = byyear[year]
        else:
            outfile = open(os.path.join(outdir, year + '.txt'), 'w')
            byyear[year] = outfile
            print('# -*- conf -*-', file=outfile)
            print('# XXX for all records, refereed status is guessed crudely', file=outfile)

        print('\n[pub]', file=outfile)

        if 'title' in rec:
            _write_with_wrapping(outfile, 'title', rec['title'])
        else:
            print('title = ? # XXX no title for this record', file=outfile)

        if 'author' in rec:
            _write_with_wrapping(outfile, 'authors', rec['author'])
        else:
            print('authors = ? # XXX no authors for this record', file=outfile)

        if 'wl_mypos' in rec:
            _write_with_wrapping(outfile, 'mypos', rec['wl_mypos'])
        else:
            print('mypos = 0 # XXX cannot determine "mypos" for this record', file=outfile)

        if 'year' in rec and 'month' in rec:
            _write_with_wrapping(outfile, 'pubdate',
                                 rec['year'] + '/' +
                                 _bib_months.get(rec['month'].lower(),
                                                 rec['month']))
        elif 'year' in rec:
            print('pubdate = %s/01 # XXX actual month unknown' % rec['year'], file=outfile)
        else:
            print('pubdate = ? # XXX no year and month for this record', file=outfile)

        if 'id' in rec:
            _write_with_wrapping(outfile, 'bibcode', rec['id'])

        if 'eprint' in rec:
            _write_with_wrapping(outfile, 'arxiv', rec['eprint'])

        if 'doi' in rec:
            _write_with_wrapping(outfile, 'doi', rec['doi'])

        refereed = 'journal' in rec
        print('refereed = %s' % 'ny'[refereed], file=outfile)

        cite = _bib_cite(rec)
        if cite is not None:
            _write_with_wrapping(outfile, 'cite', cite)
        else:
            print('cite = ? # XXX cannot infer citation text', file=outfile)

    for f in byyear.values():
        f.close()
