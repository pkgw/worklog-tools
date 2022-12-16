#! /usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# Copyright 2015-2022 Peter Williams <peter@newton.cx>

"""Worklog-related tools for accessing GitHub history, since that seems like
the best available option for capturing my open-source efforts.

"""

import argparse
from itertools import chain
import os.path
import sys
import time

__all__ = [
    "get_bigquery_jobs_service",
    "get_github_service",
    "get_repo_commit_stats",
    "get_repo_impact_stats",
    "get_repos_with_merged_prs_from_user",
    "get_root_repos_with_pushes_from_user",
]

# potential errors we could handle:
#   googleapiclient.errors.HttpError
#   oauth2client.client.AccessTokenRefreshError

BQ_SECRETS_FILE = "client_secrets.json"
BQ_CREDENTIALS_FILE = "bigquery_credentials.dat"
BQ_PROJECT_FILE = "bigquery_projectid.dat"
GH_CREDENTIALS_FILE = "github_credentials.dat"


def read_secret_line(path):
    """Read a line from a file containing sensitive information. We refuse to
    proceed if the file's permissions are too permissive. This is of course
    only a very primitive form of security.

    """
    import os, stat

    with open(path, "rt") as f:
        mode = os.fstat(f.fileno()).st_mode
        if mode & stat.S_IRWXG or mode & stat.S_IRWXO:
            raise Exception(
                "refusing credentials file %r with group or world access" % path
            )
        return f.readline().strip()


def get_bigquery_jobs_service(authdir, args):
    """`args` should be a list of command-line arguments *not* containing the
    traditional `argv[0]` value.

    """
    import httplib2
    from oauth2client.file import Storage
    from oauth2client.client import flow_from_clientsecrets
    from oauth2client.tools import argparser, run_flow
    from googleapiclient.discovery import build

    storage = Storage(os.path.join(authdir, BQ_CREDENTIALS_FILE))
    credentials = storage.get()
    projid = read_secret_line(os.path.join(authdir, BQ_PROJECT_FILE))

    if credentials is None or credentials.invalid:
        flow = flow_from_clientsecrets(
            os.path.join(authdir, BQ_SECRETS_FILE),
            scope="https://www.googleapis.com/auth/bigquery",
        )
        parser = argparse.ArgumentParser(
            description="bigquery auth", parents=[argparser]
        )
        flags = parser.parse_args(args)
        credentials = run_flow(flow, storage, flags)

    http = httplib2.Http()
    http = credentials.authorize(http)
    bq = build("bigquery", "v2", http=http)

    # Hackity hack to not have to drag a projectId around.
    jobs = bq.jobs()
    jobs.my_project_id = projid
    return jobs


def _run_bigquery(jobs, qstring):
    """Execute a BigQuery query using a `jobs` Resource object. Returns a
    generator that yields a dict() of data corresponding to each returned row.
    If your query is going to generate 10 million rows, it should just keep on
    plugging until you've seen them all.

    """

    body = {"query": qstring}
    req = jobs.query(projectId=jobs.my_project_id, body=body)
    qres = req.execute()
    rows_seen = 0

    def get_total_rows(result):
        tr = result.get("totalRows")
        return sys.maxsize if tr is None else int(tr)

    colnames = None
    res = qres
    total_rows = get_total_rows(res)

    while rows_seen < total_rows or not res["jobComplete"]:
        req = jobs.getQueryResults(
            projectId=qres["jobReference"]["projectId"],
            jobId=qres["jobReference"]["jobId"],
            pageToken=res.get("pageToken"),
            startIndex=rows_seen,
        )
        res = req.execute()

        if "rows" not in res:
            print("[no rows, looping ...]", file=sys.stderr)
            time.sleep(3)  # looks like the API call doesn't block for us
            continue

        if colnames is None:
            try:
                colnames = [s["name"] for s in res["schema"]["fields"]]
            except KeyError as e:
                # grrr sometimes this happens still
                from pprint import pprint

                print("XXX bizzah KeyError:", file=sys.stderr)
                pprint(e, file=sys.stderr)
                print("XXX result:", file=sys.stderr)
                pprint(res, file=sys.stderr)
                print("XXX raising:", file=sys.stderr)
                raise

        for rowdata in res["rows"]:
            yield dict(zip(colnames, (cell["v"] for cell in rowdata["f"])))

        rows_seen += len(res["rows"])
        total_rows = get_total_rows(res)


def _format_string_literal(text):
    """
    The Google Python libraries do not seem to provide a function for this, and
    Googling does not yield anything helpful. Hopefully my attempt is not
    broken!
    """

    return '"' + text.replace('"', '\\"').replace("'", "\\'") + '"'


def _generate_repo_names(jobs, desc, query_template, extra_args=()):
    """
    Generate a set of repository names from some BigQuery query.

    The query template should contain a specifier of the form ``FROM
    `githubarchive.day.2*` WHERE _TABLE_SUFFIX BETWEEN {0} AND {1}``, which will
    be used to multiplex the query over the archive's day-by-day tables.
    Additional query parmeters should be numbered ``{2}``, etc., and be passed
    in ``extra_args``. The query should yield a result including a column named
    ``reponame`` with a GitHub repository name. These values will be filtered to
    make sure that they contain forward slashes, so don't get cute.

    (The ``day.2*`` form is needed to not match "views" in the table query such
    as ``day.yesterday``, which lead to BigQuery errors.)

    Commentary from many years ago that I don't remember the context for: "I'd
    kind of like to access aggregated monthly tables rather than a separate
    table for every single day, but presumably the by-day storage is decently
    efficient, and I don't see an easy way to query all by-month tables starting
    with 201501 (unless there's a way that I can turn that into a numerical
    test?). But we have to break the queries up into chunks to not look at too
    many tables at once (current maximum: 1000)."
    """

    # Construct the queries

    assert "2*" in query_template

    first_year = 2011  # start of githubarchive data set.
    next_year = time.localtime()[0] + 1
    queries = []

    def year_to_bound(y):
        s = str(y)
        assert s[0] == "2"
        return f"'{s[1:]}0101'"

    for year in range(first_year, next_year):
        y1 = year_to_bound(year)
        y2 = year_to_bound(year + 1)
        queries.append((year, query_template.format(y1, y2, *extra_args)))

    # Now run it.

    def runone(tup):
        print(f"[Querying for {desc} in {tup[0]} ...]", file=sys.stderr)
        return _run_bigquery(jobs, tup[1])

    seen = set()
    results = chain.from_iterable(runone(t) for t in queries)

    for r in results:
        name = r["reponame"]
        if "/" not in name:
            # Too lazy to dig into what's happening here, but there are
            # activity records where the reponame is just 'omegaplot' instead
            # of 'pkgw/omegaplot'. As far as I can tell, none of these add any
            # special information, so let's just ignore them
            continue
        if name in seen:
            continue
        seen.add(name)
        yield name


def get_repos_with_merged_prs_from_user(jobs, login):
    """
    Returns a set of GitHub repository names (of the format "owner/reponame") that
    have merged a PR from the user since 2011.
    """

    template = """#standardSQL
SELECT DISTINCT reponame FROM (
    SELECT reponame, evtaction, pruser, prmerged FROM (
        SELECT
            repo.name AS reponame,
            JSON_VALUE(payload, "$.action") AS evtaction,
            JSON_VALUE(payload, "$.pull_request.user.login") AS pruser,
            JSON_VALUE(payload, "$.pull_request.merged") AS prmerged
        FROM
            `githubarchive.day.2*`
        WHERE
            _TABLE_SUFFIX BETWEEN {0} AND {1} AND
            type = 'PullRequestEvent'
    ) WHERE
        evtaction = 'closed' AND
        pruser = {2} AND
        prmerged = 'true'
)
"""
    return _generate_repo_names(
        jobs, "merged PRs", template, (_format_string_literal(login),)
    )


def get_root_repos_with_pushes_from_user(gh, jobs, login):
    """
    Returns a set of GitHub repository names (of the format "owner/reponame") that
    a user has pushed to since 2011. The ``login`` argument is a GitHub username,
    e.g. ``"pkgw"``.

    This search filters out fork repos, since pushes to forks may represent updates
    to others' PRs or one-off work that isn't worth reporting. The search for merged
    PRs should pick up the vast majority of repos of interest. However, there might
    be repos of interest where I'm pushing directly to the main branch but haven't
    actually filed any PRs.

    """
    from github import UnknownObjectException

    template = """#standardSQL
SELECT DISTINCT reponame FROM (
    SELECT
        repo.name AS reponame
    FROM
        `githubarchive.day.2*`
    WHERE
        _TABLE_SUFFIX BETWEEN {0} AND {1} AND
        type = 'PushEvent' AND
        actor.login = {2}
)
"""

    def ensure_is_not_fork(reponame):
        if "/" not in reponame:
            print(
                f"[warning: repo name `{reponame}` looks invalid; skipping]",
                file=sys.stderr,
            )
            return False

        try:
            return not gh.get_repo(reponame).fork
        except UnknownObjectException:
            print(f"[no current repo `{reponame}`; skipping]", file=sys.stderr)
            return False
        except:
            print(f"[failed GitHub API query for `{reponame}`]", file=sys.stderr)
            raise

    repo_gen = _generate_repo_names(
        jobs, "root-repo pushes", template, (_format_string_literal(login),)
    )
    return filter(ensure_is_not_fork, repo_gen)


def get_github_service(authdir):
    """Create and return a PyGithub (v3) `Github` object. Much simpler to set up
    than BigQuery since we just assume a personal access token has been set
    up.

    """
    from github import Github

    token = read_secret_line(os.path.join(authdir, GH_CREDENTIALS_FILE))
    gh = Github(token, per_page=99)  # only up to 100/page is allowed
    return gh


def get_repo_commit_stats(gh, reponame, branch=None):
    """Get statistics for the logged-in user's commits in the named repository.
    The `reponame` should look something like "pkgw/bibtools". Returns a Holder.

    """
    from github import GithubObject
    from inifile import Holder

    repo = gh.get_repo(reponame)
    res = Holder(commits=0, lines=0)
    latest = None

    if branch is None:
        sha = GithubObject.NotSet
    else:
        sha = repo.get_branch(branch).commit.sha

    for c in repo.get_commits(sha=sha, author=gh.get_user()):
        res.commits += 1

        # I want to count the total lines committed, but this requires
        # fetching the full commit information for each commit, which is slow
        # and blows up my GitHup API rate limit. TODO: figure out alternative
        # metric?
        ### XXX res.lines += c.stats.total

        if latest is None:
            latest = c.commit.committer.date
        else:
            latest = max(latest, c.commit.committer.date)

    res.latest_date = latest
    return res


def github_list_size(paginated_list):
    # TODO: better way to do this, without fetching all of the data?
    n = 0
    for item in paginated_list:
        n += 1
    return n


def get_repo_impact_stats(gh, reponame):
    """Get statistics that try to get at the impact/popularity of a particular
    repository. The `reponame` should look something like "pkgw/bibtools".
    Returns a Holder.

    """
    from inifile import Holder
    from time import sleep

    repo = gh.get_repo(reponame)
    res = Holder()
    res.description = repo.description  # OK this isn't impact but it's handy

    # It can take GitHub a little while to compute the 'stats' items, in which
    # case the relevant binding functions will return None. We make these
    # requests first, then make other ones; the hope is that by the time we
    # come back and retry, the stats will have been computed.

    def retry(func, first_try):
        if first_try is not None:
            return first_try

        for i in range(20):
            result = func()
            if result is not None:
                return result
            sleep(3)
        raise Exception("function %r took too long" % func)

    contrib = repo.get_stats_contributors()

    res.commits = github_list_size(
        repo.get_commits()
    )  # this counts commits on main branch
    res.forks = github_list_size(repo.get_forks())
    res.stars = github_list_size(repo.get_stargazers())
    res.contributors = github_list_size(retry(repo.get_stats_contributors, contrib))
    return res
