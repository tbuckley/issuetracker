"""Tool for generating reports based on Google Code Issue Tracker.

Usage:
  issues.py <project> [--label=<LABEL>] [--milestone=<M>] [--authorize]

Options:
  -h --help        Show this screen.
  --version        Show version.
  --authorize      Use logged-in client for requests.
  --label=<LABEL>  Filter issues to the given label.
  --milestone=<M>  Show information for the given milestone.
"""

import argparse
import datetime
from docopt import docopt
import httplib2
from oauth2client import tools
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow

from query import IssuesQuery
import utils
import visualizers

CLIENT_SECRETS = 'client_secrets.json'
OAUTH2_STORAGE = 'oauth2.dat'
ISSUE_TRACKER_SCOPE = 'https://code.google.com/feeds/issues'


def _authorize():
    """Return authenticated http client.

    _authorize will try to read credentials from OAUTH2_STORAGE. If
    credentials do not exist, _authorize will open a sign-in flow. The
    authorized http client will have access to the scope ISSUE_TRACKER_SCOPE,
    and will read oauth tokens from CLIENT_SECRETS.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[tools.argparser])
    flags = parser.parse_args([])

    # Perform OAuth 2.0 authorization.
    flow = flow_from_clientsecrets(CLIENT_SECRETS, scope=ISSUE_TRACKER_SCOPE)
    storage = Storage(OAUTH2_STORAGE)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, flags)
    http = httplib2.Http()
    auth_http = credentials.authorize(http)
    return auth_http


def get_issues_in_range(query, status, date, days=1):
    """Get the issues with the given status on the date. status = (opened|closed)."""
    assert status in ["opened", "closed"]
    end_date = date + datetime.timedelta(days=days)
    query = query.can("all")
    if status == "opened":
        query = query.opened_after(date).opened_before(end_date)
    elif status == "closed":
        query = query.closed_after(date).closed_before(end_date)
    return query.fetch_all_issues()

def get_issues_opened_in_range(query, date, days=1):
    """Get the issues opened on the date."""
    return get_issues_in_range(query, "opened", date, days=days)

def get_issues_closed_in_range(query, date, days=1):
    """Get the issues closed on the date."""
    return get_issues_in_range(query, "closed", date, days=days)

def get_issues_open_on_date(query, date):
    """Get the issues that were open on the given date."""
    issues = []
    # Closed bugs that were filed before `date` and closed after `date`
    closed_bugs_query = query.can("all").opened_before(date).closed_after(date)
    issues += closed_bugs_query.fetch_all_issues()
    # Open bugs that were filed before `date`
    open_bugs_query = query.opened_before(date)
    issues += open_bugs_query.fetch_all_issues()
    return issues

def iterate_through_issue_range(query, start, end, days, trackers):
    """Iterate through the range.

    Calls the trackers with the set of issues that existed at the start of the
    time range, then at each timestep with the sets of issues that have been
    opened and closed since the previous step.

    Arguments:
    - query: the query to track over time
    - start: the start of the time period (date.date)
    - end: the end of the time period (date.date)
    - days: the number of days to include in each interval
    - trackers: a list of HistoryTracker objects
    """
    date = start
    start_issues = get_issues_open_on_date(query, date)

    for tracker in trackers:
        tracker.start(date, start_issues)

    while date < end:
        opened_issues = get_issues_opened_in_range(query, date, days=days)
        closed_issues = get_issues_closed_in_range(query, date, days=days)

        date = date + datetime.timedelta(days=days)

        for tracker in trackers:
            tracker.step(date, opened_issues, closed_issues)

def print_issues_summary(name, issues):
    """Print summary about the given set of issues."""
    launches = filter(utils.issue_is_launch_p, issues)
    non_launches = filter(utils.not_p(utils.issue_is_launch_p), issues)
    print "{name}: {num_issues} issues, {num_launches} launches".format(
        name=name, num_issues=len(non_launches), num_launches=len(launches))

def print_pre_milestone_summary(milestone, issues):
    """Print info about the milestone."""
    milestone_issues = filter(utils.issue_is_before_milestone_p(milestone), issues)
    name = "Pre-M{milestone}".format(milestone=milestone)
    print_issues_summary(name, milestone_issues)

def print_milestone_summary(milestone, issues):
    """Print info about the milestone."""
    milestone_issues = filter(utils.issue_is_for_milestone_p(milestone), issues)
    name = "M{milestone}".format(milestone=milestone)
    print_issues_summary(name, milestone_issues)


def main():
    """Generate issues CSV."""
    arguments = docopt(__doc__, version='Naval Fate 2.0')

    http = _authorize() if arguments["--authorize"] else None
    query = IssuesQuery(arguments["<project>"], client=http)
    if arguments["--label"] is not None:
        query = query.label(arguments["--label"])

    issues = query.fetch_all_issues()
    
    # Print simple metrics
    print_issues_summary("All", issues)

    # Print milestone summaries
    if arguments["--milestone"] is not None:
        milestone = int(arguments["--milestone"])
        print_pre_milestone_summary(milestone, issues)
        print_milestone_summary(milestone, issues)
        print_milestone_summary(milestone+1, issues)

    # Print breakdowns across various metrics
    print "\n== Issues by owner =="
    visualizers.print_groups(issues, utils.get_issue_owner, hint=3)
    print "\n== Issues by priority =="
    visualizers.print_groups(issues, utils.get_issue_priority, hint=3)
    print "\n== Issues by milestone =="
    visualizers.print_groups(issues, utils.get_issue_milestone, hint=3)
    print "\n== Issues by status =="
    visualizers.print_groups(issues, utils.get_issue_status, hint=3)
    print "\n== Issues by type =="
    visualizers.print_groups(issues, utils.get_issue_type, hint=3)
    print "\n== Issues by stars =="
    visualizers.print_groups(issues, utils.get_issue_stars, hint=3)
    print "\n== Issues by updated =="
    visualizers.print_groups(issues, utils.get_issue_updated_date, hint=3)
    print "\n== Issues by published =="
    visualizers.print_groups(issues, utils.get_issue_published_date, hint=3)

    # Print graph data
    priority_tracker = visualizers.GridTracker(utils.get_issue_priority)
    change_tracker = visualizers.ChangeTracker()
    start = datetime.date.today() - datetime.timedelta(days=120)
    end = datetime.date.today()
    iterate_through_issue_range(query, start, end, 7, [priority_tracker, change_tracker])
    print "\n== Issues by priority over past 120 days =="
    priority_tracker.display()
    print "\n== Issues opened/fixed over past 120 days =="
    change_tracker.display()
    
if __name__ == "__main__":
    main()
