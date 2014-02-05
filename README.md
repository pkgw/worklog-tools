worklog-tools
=============

This software is part of a system for recording academic output and reporting
it in documents like CVs or publication lists.

### “Why do you need software for that?”

Two reasons:

* I want to have my CV and publications list available in both nicely
  *printable and* slick web-native formats … without having to keep two very
  different documents in sync.
* I want my CV to include things like my *h*-index, citation counts, total
  telescope time allocated, and so on. (Oh, by the way: I’m an astronomer.)
  And I want the computer to be responsible for figuring those out. Because
  that kind of stuff is why we invented computers.

To accomplish these things, the worklog tools process simple structured text
files and use the results to fill in LaTeX and HTML templates. There’s
built-in functionality to fetch citation counts and fill in statistics like
your *h*-index.

### “Sounds like a thing. Should I care?”

Yes! You can copy the tools and example files to quickly get started
automating the generation of your own CV. The log format is flexible and the
scripts are simple, so the sky’s the limit in terms of what effects you can
achieve.

Also, I like to think that my LaTeX templates are pretty nice. Here are [my
printable CV](http://newton.cx/~peter/files/cv.pdf) and [my publications
list](http://newton.cx/~peter/files/pubs.pdf). Here’s my [online publications
list](http://newton.cx/~peter/pubs/).


Diving in
---------

The worklog system has three pieces:

* Simple text files logging academic output
* LaTeX/HTML templates used to generate output documents
* Software to fill the latter using data gathered from the former

The software is in the same directory as this file — the [wltool](wltool)
script drives everything from the command line. The [example](example)
subdirectory contains sample copies of templates (in `*.tmpl.*`) and log files
(in [2012.txt](example/2012.txt), [2013.txt](example/2013.txt)).

To get started, first check out this repository if you haven’t done so
already. Go into the [example](example) directory and type `make`. This will
create the outputs: a CV and publication list in PDF and HTML formats.
(Assuming nothing breaks … the scripts are in Python and have few
dependencies, so they should be widely portable.) The HTML results have not
been particularly beautified, but I've tried to make the PDFs come out nicely.

Now check out [example/2013.txt](example/2013.txt). Log files are in a basic
[“ini file”][inifile] format, with records coming in paragraphs headed by a
word encased in square brackets. A typical record is:

[inifile]: http://en.wikipedia.org/wiki/INI_file

```INI
[talk]
date = 2013 Apr
where = OIR seminar, Harvard/Smithsonian Center for Astrophysics
what = Magnetic Activity Past the Bottom of the Main Sequence
invited = n
```

(The precise file format is [defined among the “Technical
details”](#technical-details-the-ini-file-format) below.) A major point of
emphasis is that this format is very simple and readable for humans and
computers alike.

The template files, on the other hand, are complicated since they go to some
effort to create attractive output. (Well, currently, this is much more true
of the LaTeX templates than the HTML templates.) Most of this effort is in
initialization, so the ends of the files are where the actual content shows
up. For instance, toward the bottom of
[example/cv.tmpl.tex](example/cv.tmpl.tex) you’ll find:

```TeX
FORMAT \item[|date|] \emph{|where|} \\ ``|what|''

\section*{Professional Talks --- Invited}
\begin{datelist} % this is a custom environment for nice spacing
RMISCLIST_IF talk invited
\end{datelist}

\section*{Professional Talks --- Other}
\begin{datelist}
RMISCLIST_IF_NOT talk invited
\end{datelist}
```

The lines beginning with ALL_CAPS trigger actions in the templating scripts.
The `RMISCLIST_IF` directive writes a sequence of `[talk]` records in reversed
order, filtering for an `invited` field equal to `y`. Each record is
LaTeXified using the template specified in the most recent `FORMAT` directive.
Strings between pipes (`|what|`) in the `FORMAT` are replaced by the
corresponding values from each record. (The precise functionalities of the
various directives are also [defined among the “Technical
details”](#technical-details-template-directives) below.)

Finally, the [Makefile](example/Makefile) in the [example](example) directory
wires up commands to automatically create or update the output files using the
standard `make` command.


Using the tools for your own documents
--------------------------------------

To get started using this system for yourself, you should copy the script code
and example files. You can put them all in the same directory and just edit
the [Makefile](example/Makefile) to change `toolsdir` to `.` rather than `..`.
Then there are two things to work on: customizing the templates, and entering
your previous accomplishments into log files. You’ll probably edit these
hand-in-hand as you decide what things to include in your CV and how you want
to express them in your log files. Obviously, for some things it makes more
sense just to put them directly in the templates, rather than filling in
fields from the log files.

Unsurprisingly, the templates get filled by running the [wltool](wltool)
program. It has several subcommands that [are documented
below](#technical-details-wltool-invocation). The `latex` and `html`
subcommands are the main ones to use. Of special note, however, is the
`update-cites` subcommand, which automatically fetches citation information
from [NASA ADS].

[NASA ADS]: http://adsabs.harvard.edu/

I organize my log files by year (e.g. [2012.txt](example/2012.txt)) but you
can arrange them any way you want. The [wltool](wltool) reads in data from
every file in the current directory whose name ends in `.txt`, processing the
files in alphabetical order.

I recommend that you use `make` to drive the template filling and
[git](http://git-scm.com/) to version-control your files, but those things are
up to you.


### Generic lists

The main method for filling the templates with data is a combination of
`RMISCLIST` and `FORMAT` directives. These provide almost complete flexibility
because you can define whatever fields you want in your log files and get them
inserted by writing a `FORMAT` directive.

*Important!* When fields from the logs are inserted into the templates, they
are escaped for LaTeX and HTML as appropriate. So if you write

```INI
[foo]
bar = $x^2$
```

and insert `|bar|` in a template somewhere, you’ll get dollar signs and
carets, not *x²*. We can’t sanely output to both HTML and LaTeX without doing
this escaping. To get non-keyboard characters, use [Unicode] — get friendly
with http://unicodeit.net/ and [Compose Key] keyboard features. The log files
are fully Unicode-enabled and Unicode characters will be correctly converted
to their LaTeX expressions in the output (see the module
[unicode_to_latex.py](unicode_to_latex.py)).

[Unicode]: http://en.wikipedia.org/wiki/Unicode
[Compose Key]: http://en.wikipedia.org/wiki/Compose_key

The main constraint in the list system is in the ability to *filter* and
*reorder* records. The built-in facilities for doing so are limited, though so
far they’ve been sufficient for my needs. The only supported ordering is
“reversed”, where that’s relative to the order that the data files are read
in: alphabetically by file name, beginning to end. Since I name my files
chronologically and append records to them as I do things, this works out to
reverse chronological order, which is generally what you want.

As for filtering, the `RMISCLIST` directives select log records of only a
certain type, where the “type” is defined by the word inside square brackets
beginning each record (e.g., `[talk]`). The `RMISCLIST_IF` and
`RMISCLIST_IF_NOT` directives further filter checking whether a field in each
record is equal to `y`, with a missing field being treated as `n`.

To extend this behavior, you’re going to need to edit
[worklog.py](worklog.py). See the `cmd_rev_misc_list*` functions and
`setup_processing`, which activates different directives.

### Publication lists

Publications are listed in `[pub]` records. These follow a more detailed
format to allow automatic fetching of citation counts, generation of reference
lists with links, and computation of statistics such as the *h*-index.

Publication records are read in and then “partitioned” into various groups
(i.e., “refereed”, “non-refereed”) by the `partition_pubs` function in
[worklog.py](worklog.py). The `PUBLIST` directive causes one of these groups
to be output, with the crucial wrinkle that each record is augmented with a
variety of extra fields to allow various special effects. This augmentation is
done in the `cite_info` function in [worklog.py](worklog.py).

If you want to group your publications differently (i.e. “refereed
first-author”), then, you’ll need to edit `partition_pubs`. To change citation
text generation or do more processing, you’ll need to dive into `cite_info`.

The details of publication processing are [documented in the next
section](#technical-details-publication-processing).

### Miscellaneous template directives

There are also some more specialized templating directives that are [fully
documented below](#technical-details-template-directives). Of particular
interest are `TODAY.`, which inserts the current date, and `CITESTATS`, which
inserts some citation statistics based on the information gathered from [NASA
ADS].


Technical details: publication processing
-----------------------------------------

As mentioned above, there are two basic wrinkles to the processing of
publications. First, extra fields are added to the records on the fly.
Second, the publications are “partitioned” into various subgroups.

The automatic processing assumes that all publication records will define
certain fields. Some of the key ones are:

* `title` — the title of the publication
* `authors` — the list of authors, in a special format. Separate authors’
  names are separated by *semicolons*. Each author’s name should be in
  first-middle-last order — no commas. Surnames containing multiple words
  should have the words separated by *underscores* — this is the easiest
  way to have the software pull out surnames automatically. Initials are OK.
* `mypos` — your numerical position in the author list, with 1 (sensibly)
  being first.
* `pubdate` — the year and month of the publication, in numerical `YYYY/MM`
  format. The worklog system generally tries not to enforce a particular
  date format, but here it does.
* `refereed` — `y` if the publication is refereed, `n` if not.
* `informal` — `y` if the publication is informal (e.g., a poster); this
  affects the partitioning process as described below.
* `cite` — citation text for the publication. This is free-form. My personal
  preference is to keep it terse and undecorated. Examples include:
  * `ApJ 746 L20`
  * `proceedings of “RFI Mitigation Workshop” (Groningen)`
  * `The Astronomer’s Telegram #3135`
  * `MNRAS submitted`

There are also a set of fields used to create various hyperlinks. As many of
these should be defined as exist:

* `arxiv` — the item’s unadorned Arxiv identifier, i.e. `1310.6757`.
* `bibcode` — the item’s unadorned [NASA ADS] bibcode, i.e. `2006ApJ...649.1020W`.
* `doi` — the item’s unadorned DOI, i.e. `10.1088/2041-8205/733/2/L20`.
* `url` — some other relevant URL.

Some fields are optional:

* `adscites` — records [NASA ADS] citation counts. Automatically set by the `wltool
  update-cites` command.
* `kind` — a one-word description of the item kind if it is nonstandard (e.g.,
  `poster`). This is only used for the `other_link` field described below.

The `cite_info` function uses the above information to create the following fields:

* `abstract_link` — a hyperlink reading “abstract” that leads to the ADS
  page for the publication, if its `bibcode` is defined.
* `bold_if_first_title` — a copy of `title`, but with markup to render it in bold
  if `mypos` is `1`, that is, you are the first author of the item.
* `citecountnote` — text such as “ [4]” (including a leading space) if the item
  has 4 ADS citations; otherwise, it is empty.
* `full_authors` — the full author list, with names separated by commas and
  non-surnames reduced to initials without punctuation; e.g. “PKG Williams,
  GC Bower”.
* `lcite` — a copy of `cite`, but with markup to make it a hyperlink to an
  appropriate URL for the publication, based on `arxiv`, `bibcode`, `doi`, or
  `url`.
* `month` — the numerical month of publication
* `official_link` — a hyperlink reading “official” that leads to the DOI
  page for the publication, if `doi` is defined.
* `other_link` — a hyperlink leading to the publication’s `url` field. The link
  text is the value of the `kind` field.
* `preprint_link` — a hyperlink reading “preprint” that leads to the Arxiv
  page for the publication, if its `arxiv` is defined.
* `quotable_title` — a copy of `title` with double quotes replaced with single
  quotes. This makes it suitable for encasing in double quotes itself. (We don‘t
  worry about subquotes in the title itself.) Note that the replacement operates
  on proper typographic left and right quotes; that is, >“< and >”<, but not >"<.
* `pubdate` — this is modified to read “{year} {Mon}”, where “{Mon}” is the standard
  three-letter abbreviation of the month name. The space between the year and the
  month is nonbreaking.
* `refereed_mark` — a guillemet (») if the publication has `refereed` equal to `y`;
  nothing otherwise.
* `short_authors` — a shortened author list; either “Foo”, “Foo & Bar”, “Foo, Bar,
  Baz”, or “Foo et al.”. Only surnames are included. If the `MYABBREVNAME`
  directive has been used, your name (as determined from `mypos`) is replaced with
  an abbreviated value, so that the author list might read “PKGW & Bower”.
* `year` — the numerical year of publication.

The groups that publications can be sorted into are:

* `all` — absolutely all publications in chronological order
* `all_rev` — all publications in reverse chronological order
* `all_formal` — publications without `informal = y`
* `refereed` — publications with `refereed = y`
* `refereed_rev` — as above but in reverse chronological order
* `all_non_refereed` — publications without `refereed = y`
* `non_refereed` — publications without `refereed = y` *or* `informal = y`
* `non_refereed_rev` — as above but in reverse chronological order
* `informal` — publications without `refereed = y` but with `informal = y`
* `informal_rev` — as above but in reverse chronological order

It’s assumed that `refereed = y` and `informal = y` never go together. The
combination of `refereed`, `non_refereed`, and `informal` captures all
publications.


Technical details: wltool invocation
------------------------------------

Here are the subcommands supported by the [wltool](wltool) program:

### extract {record-type} [datadir=.]

This is a sort of `grep` for your log files. It merely reads them all in and
prints out all of the records whose type matches `record-type`. This can be
useful for scripting or reminding yourself what fields you used for a certain
kind of entry.

The optional argument `datadir` specifies where the log files are; the default
is the current directory.

Example:

```Shell
$ ./wltool extract pub
[pub]
title = An amazing paper
… lots more output …
$
```

### html {template-file} [datadir=.]

Fill in the specified `template-file` by processing the directives [described
below](#technical-details-template-directives). The filled-in template is
printed to standard output. The output is assumed to be in HTML format; in
particular, this means that special characters are encoded in Unicode with
UTF-8, and certain fancy text effects (making text bold, for instance) are
done with HTML tags.

The optional argument `datadir` specifies where the log files are; the default
is the current directory.

Example:

```Shell
$ ./wltool html pubslist.tmpl.html >pubslist.html
$
```

### latex {template-file} [datadir=.]

Operates exactly as the `html` subcommand, except that the output is assumed
to be in LaTeX format. Special characters are converted to LaTeX escapes
(e.g., “α” → “\alpha”) and text effects are done with LaTeX constructs (e.g.,
“\textbf{…}”).

Example:

```Shell
$ ./wltool html cv.tmpl.tex >cv.tex
$
```

### summarize [datadir=.]

Print out the number of records of each type in your log files.

The optional argument `datadir` specifies where the log files are; the default
is the current directory.

Example:

```Shell
$ ./wltool summarize
   award: 1
     job: 2
outreach: 2
    prop: 1
     pub: 10
    talk: 13
teaching: 1
$
```

### update-cites [datadir=.]

Updates citation counts for publications from [NASA ADS].

For each record in the log files with a `bibcode` field, the script connects
to the ADS website and fetches the number of citations. The log files are
modified in-place to have the citation counts inserted into each record in a
field called `adscites`. The `adscites` field records the date that citation
counts were last checked, and the script won’t update check counts more
frequently than once a week.

As the updates are conducted, the script will print out each bibcode and the
change in the number of citations it has received. Records will be annotated
with an asterisk if they’re first-author publications and an “R” if they’re
refereed.

The optional argument `datadir` specifies where the log files are; the default
is the current directory.

Example:

```Shell
$ ./wltool update-cites
2012arXiv1201.5413W *  ... 0 (+0)
2012PASP..124..624W *R ... 4 (+0)
2013ApJ...762...85W *R ... 1 (+0)
2013PASA...30....6M  R ... 12 (+1)
…
$
```


Technical details: template directives
--------------------------------------

Here are the directives supported by the template processor. Each directive is
recognized when it appears at the very beginning of a line in a template.

* CITESTATS
* FORMAT
* MYABBREVNAME
* PUBLIST
* RMISCLIST
* RMISCLIST_IF
* RMISCLIST_IF_NOT
* TODAY.


Technical details: the ini file format
--------------------------------------

To be written.


Copyright and license status of this document
---------------------------------------------

This work is dedicated to the public domain.
