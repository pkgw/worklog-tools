#! /usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# Copyright 2015 Peter Williams <peter@newton.cx>

"""Worklog-related tools for accessing GitHub history, since that seems like
the best available option for capturing my open-source efforts.

"""

from __future__ import absolute_import, division, print_function, unicode_literals

import json, os.path, time

# potential errors we could handle:
#   googleapiclient.errors.HttpError
#   oauth2client.client.AccessTokenRefreshError

BQ_SECRETS_FILE = 'client_secrets.json'
BQ_CREDENTIALS_FILE = 'bigquery_credentials.dat'
BQ_PROJECT_FILE = 'bigquery_projectid.dat'
GH_CREDENTIALS_FILE = 'github_credentials.dat'


def read_secret_line (path):
    """Read a line from a file containing sensitive information. We refuse to
    proceed if the file's permissions are too permissive. This is of course
    only a very primitive form of security.

    """
    import os, stat

    with open (path, 'rt') as f:
        mode = os.fstat (f.fileno ()).st_mode
        if mode & stat.S_IRWXG or mode & stat.S_IRWXO:
            raise Exception ('refusing credentials file %r with group or world access'
                             % path)
        return f.readline ().strip ()


def get_bigquery_jobs_service (authdir, args):
    """`args` should be a list of command-line arguments *not* containing the
    traditional `argv[0]` value.

    """
    import httplib2
    from oauth2client.file import Storage
    from oauth2client.client import flow_from_clientsecrets
    from oauth2client.tools import argparser, run_flow
    from googleapiclient.discovery import build

    storage = Storage (os.path.join (authdir, BQ_CREDENTIALS_FILE))
    credentials = storage.get ()
    projid = read_secret_line (os.path.join (authdir, BQ_PROJECT_FILE))

    if credentials is None or credentials.invalid:
        flow = flow_from_clientsecrets (os.path.join (authdir, BQ_SECRETS_FILE),
                                        scope='https://www.googleapis.com/auth/bigquery')
        parser = argparse.ArgumentParser (description='bigquery auth', parents=[argparser])
        flags = parser.parse_args (args)
        credentials = run_flow (flow, storage, flags)

    http = httplib2.Http ()
    http = credentials.authorize (http)
    bq = build ('bigquery', 'v2', http=http)

    # Hackity hack to not have to drag a projectId around.
    jobs = bq.jobs ()
    jobs.my_project_id = projid
    return jobs


def run_bigquery (jobs, qstring):
    """Execute a BigQuery query using a `jobs` Resource object. Returns a
    generator that yields a dict() of data corresponding to each returned row.
    If your query is going to generate 10 million rows, it should just keep on
    plugging until you've seen them all.

    """
    from itertools import izip
    from sys import maxsize

    body = {'query': qstring}
    req = jobs.query (projectId=jobs.my_project_id, body=body)
    qres = req.execute ()
    rows_seen = 0

    def get_total_rows (result):
        tr = result.get ('totalRows')
        return maxsize if tr is None else int (tr)

    colnames = None
    res = qres
    total_rows = get_total_rows (res)

    while rows_seen < total_rows or not res['jobComplete']:
        req = jobs.getQueryResults (
            projectId=qres['jobReference']['projectId'],
            jobId=qres['jobReference']['jobId'],
            pageToken=res.get ('pageToken'),
            startIndex=rows_seen
        )
        res = req.execute ()

        if 'rows' not in res:
            print ('[no rows, looping ...]')
            continue

        if colnames is None:
            try:
                colnames = [s['name'] for s in res['schema']['fields']]
            except KeyError as e:
                # grrr sometimes this happens still
                from pprint import pprint
                print ('XXX bizzah KeyError:')
                pprint (e)
                print ('XXX result:')
                pprint (res)
                print ('XXX raising:')
                raise

        for rowdata in res['rows']:
            yield dict (izip (colnames, (cell['v'] for cell in rowdata['f'])))

        rows_seen += len (res['rows'])
        total_rows = get_total_rows (res)


def format_string_literal (text):
    """The Google Python libraries do not seem to provide a function for this, and
    Googling does not yield anything helpful. Hopefully my attempt is not
    broken!

    """
    return '"' + text.encode ('unicode_escape').replace ('"', '\\"').replace ('\'', '\\\'') + '"'


def get_repos_with_pushes_from_user (jobs, login):
    """Returns a set of names of repository (of the format "owner/reponame") that
    a user has pushed to since 2011.

    I'd kind of like to access aggregated monthly tables rather than a
    separate table for every single day, but presumably the by-day storage is
    decently efficient, and I don't see an easy way to query all by-month
    tables starting with 201501 (unless there's a way that I can turn that
    into a numerical test?). But we have to break the queries up into chunks
    to not look at too many tables at once (current maximum: 1000).

    """
    from itertools import chain
    first_year = 2011 # start of githubarchive data set.
    cur_year = time.localtime ()[0]

    year_ts_template = "TIMESTAMP('{0}-01-01')"
    query_template = '''
SELECT
  UNIQUE(repo.name) AS reponame
FROM
  TABLE_DATE_RANGE([githubarchive:day.], {0}, {1})
WHERE
  actor.login == {2} AND
  type == "PushEvent"
'''

    queries = []
    for year in xrange (first_year, cur_year):
        y1 = year_ts_template.format (year)
        y2 = year_ts_template.format (year+1)
        queries.append (query_template.format (y1, y2, format_string_literal (login)))

    y = year_ts_template.format (cur_year)
    queries.append (query_template.format (y, 'CURRENT_TIMESTAMP()', format_string_literal (login)))

    seen = set ()
    results = chain (*[run_bigquery (jobs, q) for q in queries])

    for r in results:
        name = r['reponame']
        if name in seen:
            continue
        seen.add (name)
        yield name


def get_github_service (authdir):
    """Create and return a PyGithub (v3) `Github` object. Much simpler to set up
    than BigQuery since we just assume a personal access token has been set
    up.

    """
    from github import Github
    token = read_secret_line (os.path.join (authdir, GH_CREDENTIALS_FILE))
    gh = Github (token, per_page=99) # only up to 100/page is allowed
    return gh


def get_repo_commit_stats (gh, reponame):
    """Get statistics for the logged-in user's commits in the named repository.
    The `reponame` should look something like "pkgw/bibtools". Returns a Holder.

    """
    from inifile import Holder

    repo = gh.get_repo (reponame)
    res = Holder (commits=0, lines=0)
    latest = None

    for c in repo.get_commits (author=gh.get_user ()):
        res.commits += 1

        # I want to count the total lines committed, but this requires
        # fetching the full commit information for each commit, which is slow
        # and blows up my GitHup API rate limit. TODO: figure out alternative
        # metric?
        ### XXX res.lines += c.stats.total

        if latest is None:
            latest = c.commit.committer.date
        else:
            latest = max (latest, c.commit.committer.date)

    res.latest_date = latest
    return res


def github_list_size (paginated_list):
    # TODO: better way to do this, without fetching all of the data?
    n = 0
    for item in paginated_list:
        n += 1
    return n


def get_repo_impact_stats (gh, reponame):
    """Get statistics that try to get at the impact/popularity of a particular
    repository. The `reponame` should look something like "pkgw/bibtools".
    Returns a Holder.

    """
    from inifile import Holder
    from time import sleep

    repo = gh.get_repo (reponame)
    res = Holder ()
    res.description = repo.description # OK this isn't impact but it's handy

    # It can take GitHub a little while to compute the 'stats' items, in which
    # case the relevant binding functions will return None. We make these
    # requests first, then make other ones; the hope is that by the time we
    # come back and retry, the stats will have been computed.

    def retry (func, first_try):
        if first_try is not None:
            return first_try

        for i in xrange (10):
            result = func ()
            if result is not None:
                return result
            sleep (3)
        raise Exception ('function %r took too long' % func)

    contrib = repo.get_stats_contributors ()

    res.commits = github_list_size (repo.get_commits ()) # this counts commits on main branch
    res.forks = github_list_size (repo.get_forks ())
    res.stars = github_list_size (repo.get_stargazers ())
    res.contributors = github_list_size (retry (repo.get_stats_contributors, contrib))
    return res
