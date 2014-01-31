worklog-tools
=============

This software is part of a system for recording academic output and reporting
it in documents like CVs or publication lists. 

### “Why do you need software for that?”

Two reasons:

* I want to have my CV and publications list available in both nicely printable
  *and* slick web-native formats … without having to update two very different
  documents all the time.
* I want my CV to include things like my *h*-index, citation counts, total
  observing time allocated, and so on. And I want the computer to be
  responsible for figuring those out. Because that kind of stuff is why we
  invented computers.

To accomplish these things, the worklog tools process simple structured text
files and use the results to fill in LaTeX and HTML templates.

### “OK, sounds interesting. Should I care?”

Yes! You can copy the tools and example files to quickly get started
automating the generation of your own CV. The data format is flexible and
the scripts are simple, so the sky’s the limit in terms of what kinds of
numbers you can compute or effects you can achieve.

Also, I like think that my LaTeX CV template is pretty nice.


Diving in
---------

The worklog system has three pieces:

* Simple text files logging academic output
* LaTeX/HTML templates used to generate output documents
* Scripts that fill the latter using data gathered from the former.

The scripts are found in the same directory as this file. The `example`
subdirectory contains sample copies of templates (in `templates/`) and log
files (in `2012.txt`, `2013.txt`).

To get started, try going into the `example` directory and typing `make`. This
will create the outputs: a CV and publication list in PDF and HTML formats.
(Assuming nothing breaks … the scripts are in Python and have few dependencies,
so they should be widely portable.) The HTML results have not been particularly
beautified, but I've tried to make the PDFs come out nicely.

Now check out `examples/2013.txt`. Log files are in a basic [“ini
file”][inifile] format, with entries coming in paragraphs headed by a word
encased in square brackets. A typical record is:

[inifile]: http://en.wikipedia.org/wiki/INI_file

    [talk]
    date = 2013 Apr
    where = OIR seminar, Harvard/Smithsonian Center for Astrophysics
    what = Magnetic Activity Past the Bottom of the Main Sequence
    invited = n

(The precise file format is defined among the “Technical details” below.) A
major point of emphasis is that this format is very simple and readable for
humans and computers alike.

The template files, on the other hand, are complicated since they go to some
effort to create attractive output. (Well, currently, this is much more true
of the LaTeX templates than the HTML templates.) Most of this effort is in
initialization, so the ends of the files are where the actual content shows
up. For instance, toward the bottom of `example/templates/cv.tmpl.tex` you’ll
find:

    FORMAT \item[|date|] \emph{|where|} \\ ``|what|''

    \section*{Professional Talks --- Invited}
    \begin{datelist} % this is a custom environment for nice spacing
    RMISCLIST_IF talk invited
    \end{datelist}

    \section*{Professional Talks --- Other}
    \begin{datelist}
    RMISCLIST_IF_NOT talk invited
    \end{datelist}

The lines beginning with ALL_CAPS trigger actions in the templating scripts.
The `RMISCLIST_IF` directive writes a sequence of `talk` data items in
reversed order, filtering for an `invited` field equal to `y`, filling in a
template specified by the most recent `FORMAT` directive. Strings between
pipes (`|what|`) in the `FORMAT` are replaced by the corresponding values from
the data files. (The precise functionalities of the various directives are
also defined among the “Technical details” below.)

Finally, the `Makefile` in the `example` directory wires up commands to
automatically create or update the output files using the standard `make`
command.


Getting started
---------------

To get started using this system for yourself, you should copy the scripts and
example files. Then there are two things to work on: customizing the
templates, and entering your previous accomplishments into log files.

There are only very loose constraints on how you want to name or arrange the
various files. The relative locations of the data files (templates and
`<year>.txt`) and the scripts (`cvlib.py` and friends) don’t particularly
matter — they only come up in the `Makefile` in the example setup.

The main processing script reads in data from every file in the current
directory whose name ends in `.txt`. The files are processed in alphabetical
order.

A few of the templating directives read in small, standalone sub-template
files. These are searched for first in a directory named `templates` below the
current directory, and then in one named `templates` below the directory
containing the scripts.


More details and customization
------------------------------

The set of sections that I use in my CV and publication list probably don’t
match exactly with the ones that you’d like to use. The aim of this system
is to make it easy to take slightly different approaches.

(The visual appearance of my documents may not match your preferences either.
That’s entirely up to the LaTeX and HTML templates and your level of interest
in futzing with them.)

### Generic lists

The main method for filling the templates with data is a combination of
`RMISCLIST` and `FORMAT` directives. These provide almost complete flexibility
because you can define whatever fields you want in your `<year>.txt` files
and get them inserted by writing a `FORMAT` directive.

The main constraint is in the ability to *filter* and *reorder* records: the
built-in facilities for doing so are limited, though so far they’ve been
sufficient for my needs. The only supported ordering is “reversed”, where
that’s relative to the order that the data files are read in: alphabetically
by file name, beginning to end. Since I name my files chronologically and
append records to them as I do things, this works out to reverse chronological
order, which is generally what you want.

As for filtering, the `RMISCLIST` directives select log records of only a
certain type, where the “type” is defined by the word inside square brackets
beginning each record (e.g., `[talk]`). The `RMISCLIST_IF` and
`RMISCLIST_IF_NOT` directives further filter checking whether an item in each
record is equal to `y`, with a missing item being treated as `n`.

To extend this behavior, you’re going to need to edit `cvlib.py`. See the
`cmd_rev_misc_list*` functions and `setup_processing`, which activates
different directives.

### Publication lists

Publications (`[pub]` records) follow a more detailed format to allow
automatic fetching of citation counts, generation of reference lists with
links, and computation of statistics such as the *h*-index.

Publication records are read in and then “partitioned” into various groups
(i.e., “refereed”, “non-refereed”) by the `partition_pubs` function in
`cvlib.py`. The `PUBLIST` directive causes one of these groups to be output,
with the crucial wrinkle that each record is augmented with a variety of extra
records to allow various special effects. This augmentation is done in the
`cite_info` function in `cvlib.py`.

If you want to group your publications differently (i.e. “refereed
first-author”), then, you’ll need to edit `partition_pubs`. To change citation
text generation or do more processing, you’ll need to dive into `cite_info`.

The details of publication processing are documented farther below.


Best practices
--------------

* The `<year>.txt` files are processed as Unicode text, with full support for
  non-ASCII characters such as ² or α. Do *not* use TeX escaping. Instead, get
  friendly with [http://unicodeit.net/] and [Compose Key] keyboard features.
  This is the only sane way to include special characters in both LaTeX and
  HTML output.
* I *strongly* suggest that you maintain your data files in a version control
  system such as [git]. In my personal CV repository, I link my data to these
  scripts using the git “submodule” functionality, which works well but is
  unfortunately not at all intuitive to learn.

[Compose Key]: http://en.wikipedia.org/wiki/Compose_key
[git]: http://git-scm.com/


Technical details: publication records
--------------------------------------

The processing of publication records is a somewhat complicated part of the
worklog system.

As mentioned above, there are two basic wrinkles to the processing of
publications. First, extra fields are added to the records on the fly.
Second, the publications are “partitioned” into various subgroups.

The automatic processing assumes that all publication records will define
certain items. Some of the key ones are:

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
* `cite` — citation text for the publication. This is free-form. My personal
  preference is to keep it terse and undecorated. Examples include:
  * `ApJ 746 L20`
  * `proceedings of “RFI Mitigation Workshop” (Groningen)`
  * `The Astronomer’s Telegram #3135`
  * `MNRAS submitted`

There are also a set of items used to create various hyperlinks. As many of
these should be defined as exist:

* `arxiv` — the item’s unadorned Arxiv identifier, i.e. `1310.6757`.
* `bibcode` — the item’s unadorned ADS bibcode, i.e. `2006ApJ...649.1020W`.
* `doi` — the item’s unadorned DOI, i.e. `10.1088/2041-8205/733/2/L20`.
* `url` — some other relevant URL.


Technical details: script invocation
------------------------------------



Technical details: template commands
------------------------------------

To be filled in.

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
