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
import httplib2
from oauth2client import tools
from oauth2client.tools import run_flow
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
import datetime
from docopt import docopt
from query import IssuesQuery

CLIENT_SECRETS = 'client_secrets.json'
OAUTH2_STORAGE = 'oauth2.dat'
ISSUE_TRACKER_SCOPE = 'https://code.google.com/feeds/issues'


def _authorize():
    """Return authenticated http client.

    _authorize will try to read credentials from OAUTH2_STORAGE. If
    credentials do not exist, _authorize will open a sign-in flow.
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




# def get_all_issues(client, project, verbose=False, **kwargs):
#     """Get all issues for the given search."""
#     page = get_issues_page(client, project, **kwargs)
    
#     if verbose:
#         details = get_details_for_page(page)
#         num_pages = 0
#         if details.limit > 0:
#             num_pages = int(ceil(details.count / float(details.limit)))
#         counter = 1
#         print "Fetching {num_pages} pages...".format(num_pages=num_pages),
#         sys.stdout.flush()

#     issues = []
#     while page is not None:
#         if verbose:
#             print "{counter} ".format(counter=counter),
#             sys.stdout.flush()
#             counter += 1
#         issues += get_issues_from_page(page)
#         page = get_next_page(client, page)
#     if verbose:
#         print
#     return issues



# Issue helpers

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

def group_issues(issues, prop_fn):
    """Group issues by owner."""
    groups = {}
    for issue in issues:
        prop = prop_fn(issue)
        if prop not in groups:
            groups[prop] = []
        groups[prop].append(issue)
    return groups

def print_groups(issues, prop_fn, hint=0):
    """Print the groups"""
    groups = group_issues(issues, prop_fn)
    keys = groups.keys()
    keys.sort()
    for key in keys:
        key_issues = groups[key]
        print "{key}: {num_issues}".format(key=key, num_issues=len(key_issues)),
        if hint > 0:
            key_ids = [str(get_issue_id(i)) for i in key_issues]
            if len(key_ids) > hint:
                print "["+" ".join(key_ids[:3])+"...]"
            else:
                print "["+" ".join(key_ids)+"]"
        else:
            print

def create_issue_dict(issues):
    issue_dict = {}
    for issue in issues:
        issue_dict[get_issue_id(issue)] = issue
    return issue_dict

def issue_dict_remove(issue_dict, issue):
    del issue_dict[get_issue_id(issue)]

def issue_dict_add(issue_dict, issue):
    issue_dict[get_issue_id(issue)] = issue

def iterate_through_range(query, start, end, start_fn=None, iter_fn=None, days=1):
    """Iterate through the range."""
    date = start
    start_issues = get_issues_open_on_date(query, date)

    if start_fn is not None:
        start_fn(date, start_issues)

    while date < end:
        opened_issues = get_issues_opened_in_range(query, date, days=days)
        closed_issues = get_issues_closed_in_range(query, date, days=days)

        date = date + datetime.timedelta(days=days)

        if iter_fn is not None:
            iter_fn(date, opened_issues, closed_issues)

def is_for_earlier_milestone_p(milestone):
    """Return predicate that tests if the issue is for a previous milestone."""
    return issue_property_lessthan_p(get_issue_milestone, milestone)

def is_for_milestone_p(milestone):
    """Return predicate that tests if the issue is for the given milestone."""
    return issue_property_matches_p(get_issue_milestone, milestone)

def is_launch_p():
    """Return a predicate that tests if issue is a launch bug."""
    return issue_has_label("Type-Launch")

class GridTracker(object):
    """Track issues over time."""

    def __init__(self, prop_fn):
        self._prop_fn = prop_fn
        self._issue_dict = None
        self._tracker = []

    def start(self, date, start_issues):
        """Start with the given set of issues."""
        self._issue_dict = create_issue_dict(start_issues)
        self._tracker.append((date, group_issues(start_issues, self._prop_fn)))

    def iter(self, date, opened_issues, closed_issues):
        """Add an iteration with the opened/closed issues."""
        for issue in opened_issues:
            issue_dict_add(self._issue_dict, issue)
        for issue in closed_issues:
            issue_dict_remove(self._issue_dict, issue)
        issues = self._issue_dict.values()
        self._tracker.append((date, group_issues(issues, self._prop_fn)))

    def display(self):
        """Print out the tracker."""
        keys = set()
        for (date, issues) in self._tracker:
            keys = keys.union(set(issues.keys()))
        keys = list(keys)

        # Print headers
        print "\t".join(["date"]+[str(key) for key in keys])

        # Print rows
        for (date, issues) in self._tracker:
            values = [date.strftime("%Y/%m/%d")]
            for key in keys:
                if key in issues:
                    values.append(str(len(issues[key])))
                else:
                    values.append("0")
            print "\t".join(values)


class ChangeTracker(object):
    """Track issues over time."""

    def __init__(self):
        self._original_issues = None
        self._new_issues = None
        self._closed_original_issues = None
        self._tracker = []

    def start(self, date, start_issues):
        """Start with the given set of issues."""
        self._original_issues = set([get_issue_id(i) for i in start_issues])
        self._new_issues = set()
        self._closed_original_issues = set()
        self._tracker.append((date, len(self._closed_original_issues), len(self._new_issues)))

    def iter(self, date, opened_issues, closed_issues):
        """Add an iteration with the opened/closed issues."""
        opened_ids = set([get_issue_id(i) for i in opened_issues])
        closed_ids = set([get_issue_id(i) for i in closed_issues])
        closed_original = closed_ids.intersection(self._original_issues)
        self._closed_original_issues = self._closed_original_issues.union(closed_original)
        self._original_issues = self._original_issues.difference(closed_ids)
        self._new_issues = self._new_issues.union(opened_ids).difference(closed_ids)
        self._tracker.append((date, len(self._closed_original_issues), len(self._new_issues)))

    def display(self):
        """Print out the tracker."""
        print "\t".join(["date", "fixed", "new"])
        for (date, fixed, new) in self._tracker:
            print "\t".join([date.strftime("%Y/%m/%d"), str(fixed), str(new)])


def print_open_close_rate(query, start, end, days=1):
    """Print the rate of open/closed bugs."""

    priority_tracker = GridTracker(get_issue_priority)
    # status_tracker = GridTracker(get_issue_status)
    # milestone_tracker = GridTracker(get_issue_milestone)
    change_tracker = ChangeTracker()

    trackers = [priority_tracker, change_tracker]

    def start_fn(*args, **kwargs):
        for tracker in trackers:
            tracker.start(*args, **kwargs)

    def iter_fn(*args, **kwargs):
        for tracker in trackers:
            tracker.iter(*args, **kwargs)

    iterate_through_range(query, start, end, start_fn, iter_fn, days=days)

    for tracker in trackers:
        tracker.display()

def print_issues_summary(name, issues):
    """Print summary about the given set of issues."""
    launches = filter(is_launch_p(), issues)
    non_launches = filter(notp(is_launch_p()), issues)
    print "{name}: {num_issues} issues, {num_launches} launches".format(
        name=name, num_issues=len(non_launches), num_launches=len(launches))

def print_pre_milestone_summary(milestone, issues):
    """Print info about the milestone."""
    milestone_issues = filter(issue_property_lessthan_p(get_issue_milestone, milestone), issues)
    name = "Pre-M{milestone}".format(milestone=milestone)
    print_issues_summary(name, milestone_issues)

def print_milestone_summary(milestone, issues):
    """Print info about the milestone."""
    milestone_issues = filter(is_for_milestone_p(milestone), issues)
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
    print_groups(issues, get_issue_owner, hint=3)
    print "\n== Issues by priority =="
    print_groups(issues, get_issue_priority, hint=3)
    print "\n== Issues by milestone =="
    print_groups(issues, get_issue_milestone, hint=3)
    print "\n== Issues by status =="
    print_groups(issues, get_issue_status, hint=3)
    print "\n== Issues by stars =="
    print_groups(issues, get_issue_stars, hint=3)
    print "\n== Issues by updated =="
    print_groups(issues, get_issue_updated_date, hint=3)
    print "\n== Issues by published =="
    print_groups(issues, get_issue_published_date, hint=3)

    # Print graph data
    print "\n== Issues by priority over past 120 days =="
    start = datetime.date.today() - datetime.timedelta(days=120)
    end = datetime.date.today()
    print_open_close_rate(query, start, end, days=7)
    
if __name__ == "__main__":
    main()
