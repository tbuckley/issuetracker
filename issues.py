#!/usr/bin/python
"""Tool for generating reports based on Google Code Issue Tracker.

Usage:
  issues.py <project> [options]

Options:
  -h --help         Show this screen.
  --version         Show version.
  --authorize       Use logged-in client for requests.
  --label=<LABEL>   Filter issues to the given label.
  --display=<LIST>  Comma-separate list of things to show.

You can control what information is display using the --display flag.
* "count:all" -- print count for all matching issues
* "count:<prop>=<val>" -- print count for issues where prop has value
* "groups:all" -- print groups for all property functions
* "groups:<prop>" -- print group for specific property
* "quantiles:<prop>" -- print quantiles for specific property
* "graph:change" -- show how many bugs have been opened/closed over time
* "graph:<prop>" -- show how bugs changed for the given property over time

<prop> can be one of "owner", "priority", "milestone", "status", "type", 
"stars", "updated", "published", "label"
"""

import argparse
import datetime
from docopt import docopt
import httplib2
from oauth2client import tools
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from functools import partial

from query import IssuesQuery
import utils
from visualizers import ChangeTracker, GridTracker, print_groups_by_prop, \
    print_groups_by_list_prop, print_quantiles

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


PROPERTY_FUNCTIONS = {
    # <property>: (<property function>, <property type>)
    "owner": (utils.get_issue_owner, str),
    "priority": (utils.get_issue_priority, int),
    "milestone": (utils.get_issue_milestone, int),
    "status": (utils.get_issue_status, str),
    "type": (utils.get_issue_type, str),
    "stars": (utils.get_issue_stars, int),
    "updated": (utils.get_issue_updated_date, str),
    "published": (utils.get_issue_published_date, str),
    "label": (partial(utils.get_issue_labels_by_prefix, "Cr-"), list)
}
PROPERTY_GROUPING = {
    # <name>: (<printer function>, <sort by number of issues instead of property>)
    "owner": (print_groups_by_prop, True),
    "priority": (print_groups_by_prop, False),
    "milestone": (print_groups_by_prop, False),
    "status": (print_groups_by_prop, True),
    "type": (print_groups_by_prop, True),
    "stars": (print_groups_by_prop, False),
    "updated": (print_groups_by_prop, False),
    "published": (print_groups_by_prop, False),
    "label": (print_groups_by_list_prop, True),
}
GROUP_DEFAULTS = ["owner", "priority", "milestone", "status", "type", "stars", "updated",
                  "published", "label"]

assert set(PROPERTY_FUNCTIONS.keys()) == set(PROPERTY_GROUPING.keys())
assert set(PROPERTY_FUNCTIONS.keys()) == set(GROUP_DEFAULTS)

def print_title(title):
    """Print a section title."""
    print "\n== {title} ==".format(title=title)

def value_for_arg(arg, tipe, none_allowed=True):
    """Convert a string argument to the given type."""
    if none_allowed and arg.lower() == "none":
        return None
    return tipe(arg)

def create_pred_from_arg(arg):
    """Create a predicate based on an argument. Must be of the form propertyname=value."""
    (prop, value) = arg.split("=")
    (prop_fn, tipe) = PROPERTY_FUNCTIONS[prop]
    value = value_for_arg(value, tipe)
    return utils.issue_property_matches_p(prop_fn, value)

def generate_count_display(args):
    """Create a function to display a count."""
    title = args
    if args == "all":
        filter_pred = None
    else:
        filter_pred = create_pred_from_arg(args)
        
    def display(issues):
        """Display the issues."""
        if filter_pred is not None:
            issues = filter(filter_pred, issues)
        launches = filter(utils.issue_is_launch_p, issues)
        non_launches = filter(utils.not_p(utils.issue_is_launch_p), issues)
        print "{title}: {num_issues} issues, {num_launches} launches".format(
            title=title, num_issues=len(non_launches), num_launches=len(launches))

    return display

def generate_groups_display(prop, hint=3):
    """Create a function to display the groups."""
    title = prop
    (prop_fn, _) = PROPERTY_FUNCTIONS[prop]
    (print_fn, sort_by_issues) = PROPERTY_GROUPING[prop]

    def display(issues):
        """Display the issues."""
        print_title("Issues by {title}".format(title=title))
        print_fn(issues, prop_fn, hint=hint, sort_by_issues=sort_by_issues)

    return display

def generate_quantiles_display(prop, quantiles):
    """Create a function to display the quantiles."""

    (prop_fn, _) = PROPERTY_FUNCTIONS[prop]

    def display(issues):
        """Display the issues."""
        print_title("Quantiles for {prop}".format(prop=prop))
        print_quantiles(map(prop_fn, issues), quantiles, reverse=True)

    return display


class TrackerHelper(object):
    def __init__(self, start, end, step_days):
        self._start = start
        self._end = end
        self._days = step_days
        self._trackers = []
        self._first_run = True

    def run(self, query):
        """Run this tracker."""
        iterate_through_issue_range(query, self._start, self._end, self._days, self._trackers)

    def run_once(self, query):
        """Run this tracker once. Does nothing if already called."""
        if self._first_run:
            self.run(query)
            self._first_run = False

    def generate_change_function(self):
        """Create a function that tracks bugs opened/fixed over time."""
        tracker = ChangeTracker()
        self._trackers.append(tracker)
        def helper(query):
            self.run_once(query)
            print_title("Issues opened/fixed over past {days} days".format(days=self.days))
            tracker.display()
        return helper

    def generate_grid_function(self, prop):
        """Create a function that tracks a property over time."""
        (prop_fn, _) = PROPERTY_FUNCTIONS[prop]
        tracker = GridTracker(prop_fn)
        self._trackers.append(tracker)
        def helper(query):
            self.run_once(query)
            print_title("Issues by {prop} over past {days} days".format(prop=prop, days=self.days))
            tracker.display()
        return helper

    @property
    def days(self):
        """Get the number of days in the range."""
        return (self._end - self._start).days


class DisplayHelper(object):
    """Help display issues."""

    def __init__(self, displays, quantiles=None, group_hint=3, start=None, end=None, step_days=None):
        if quantiles is not None:
            self._quantiles = quantiles
        else:
            self._quantiles = [99, 90, 75, 50, 25, 0]
        self._group_hint = group_hint
        self._displays = displays
        self._tracker_start = start or datetime.date.today()
        self._tracker_end = end or self._tracker_start - datetime.timedelta(90)
        self._tracker_days = step_days or 7

    def display(self, query):
        """Display the given issues."""
        issues = query.fetch_all_issues()
        display_fns = self.generate_displays(self._displays)
        for display_fn in display_fns:
            if callable(display_fn):
                display_fn(issues)
            else:
                (func, arg) = display_fn
                if arg == "query":
                    func(query)
                elif arg == "issues":
                    func(issues)

    def generate_displays(self, displays):
        """Generate functions to display information about issues."""
        display_fns = []
        tracker_helper = TrackerHelper(self._tracker_start, self._tracker_end, self._tracker_days)

        for display in displays:
            (kind, args) = display.split(":", 1)
            
            if kind == "count":
                display_fn = generate_count_display(args)
                display_fns.append(display_fn)

            if kind == "groups":
                if args == "all":
                    for key in GROUP_DEFAULTS:
                        display_fn = generate_groups_display(key, hint=self._group_hint)
                        display_fns.append(display_fn)
                else:
                    display_fn = generate_groups_display(args, hint=self._group_hint)
                    display_fns.append(display_fn)

            if kind == "quantiles":
                display_fn = generate_quantiles_display(args, self._quantiles)
                display_fns.append(display_fn)

            if kind == "graph":
                if args == "change":
                    display_fn = tracker_helper.generate_change_function()
                    display_fns.append((display_fn, "query"))
                else:
                    display_fn = tracker_helper.generate_grid_function(args)
                    display_fns.append((display_fn, "query"))

        return display_fns


def main():
    """Generate issues CSV."""
    arguments = docopt(__doc__, version='Naval Fate 2.0')

    # Create an http client (authorized if necessary)
    http = _authorize() if arguments["--authorize"] else None

    # Build the base query to use
    query = IssuesQuery(arguments["<project>"], client=http)
    if arguments["--label"] is not None:
        query = query.label(arguments["--label"])

    # Create the display functions
    if arguments["--display"] is not None:
        displays = arguments["--display"].split(",")
    else:
        displays = ["count:all", "groups:all", "quantiles:published", "quantiles:updated", 
                    "graph:priority", "graph:change"]

    start = datetime.date.today() - datetime.timedelta(days=120)
    end = datetime.date.today()
    displayer = DisplayHelper(displays, start=start, end=end, step_days=7)

    # Dispaly
    displayer.display(query)
    
if __name__ == "__main__":
    main()
