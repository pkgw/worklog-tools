worklog-tools
=============

This software is part of a system for logging academic output. The idea is
that you keep track of what you by making entries in simple text files. These
tools process the files to automatically fill in templates for things like CVs
and publication lists.

In particular, in this system you log activities in a simple, flexible [“ini
file”][inifile] format. The tools extract information to fill HTML and LaTeX
templates to create attractive web or printable documents.

[inifile]: http://en.wikipedia.org/wiki/INI_file


The basic approach
------------------

I log my output in a set of text files, one for each year (e.g. `2014.txt`).
A typical entry might look like this:

    [talk]
    date = 2014 Jan
    where = At ‘Third BCool Workshop’ (St Andrews, Scotland)
    what = Radio emission and magnetic activity in the ultracool regime
    invited = n

Meanwhile, I also maintain CV templates in LaTeX and HTML formats. A relevant
part of the LaTeX template looks like:

    FORMAT \item[|date|] \emph{|where|} \\ ``|what|''

    \section*{Professional Talks --- Invited}
    \begin{datelist} % this is a custom environment for nice spacing
    RMISCLIST_IF talk invited
    \end{datelist}

    \section*{Professional Talks --- Other}
    \begin{datelist}
    RMISCLIST_IF_NOT talk invited
    \end{datelist}

As you might guess, the `RMISCLIST` commands fill the template with lists
generated from the `[talk]` items in my log files, using the style specified
by the preceding `FORMAT` command.

The nice thing about this system is that it’s quite lightweight and flexible.
It works best if you log just enough information to generate the relevant CV
line and remind yourself of whatever it was you did.

There are a few other commands that process worklog items more pickily to do
certain kinds of deeper processing. In particular `[pub]` items follow a more
detailed format to allow automatic checking of citation counts, generation of
reference lists with links, and computation of statistics such as the
*h*-index.


Technical details: template commands
------------------------------------

To be filled in.

* CITESTATS
* MARKUP (if kept)
* FORMAT
* PUBLIST
* RMISCLIST
* RMISCLIST_IF
* RMISCLIST_IF_NOT
* TODAY.


Technical details: the ini file format
--------------------------------------

To be written.

Technical details:


Best practices
--------------

To be written.
