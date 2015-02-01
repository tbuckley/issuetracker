"""Visualizers for issues."""

from abc import ABCMeta, abstractmethod

import utils


class IssueSet(object):
    """A set of issues. Issues can be added and remove."""
    
    def __init__(self, issues=None):
        self._issues = {}

        if issues is not None:
            for issue in issues:
                self.add(issue)

    def add(self, issue):
        """Add an issue to the set."""
        issue_id = utils.get_issue_id(issue)
        self._issues[issue_id] = issue

    def remove(self, issue):
        """Remove an issue from the set."""
        issue_id = utils.get_issue_id(issue)
        del self._issues[issue_id]

    @property
    def list(self):
        """Return the IssueSet as a python list."""
        return self._issues.values()


class Table(object):
    """Represents tabular data."""

    def __init__(self, headers=None):
        self._headers = headers
        self._rows = []

    def set_headers(self, headers):
        """Set the headers for the table."""
        self._headers = headers

    def add_row(self, row):
        """Add a row to the table."""
        self._rows.append(row)

    def __str__(self):
        table = []
        if self._headers is not None:
            table.append("\t".join([str(val) for val in self._headers]))
        for row in self._rows:
            table.append("\t".join([str(val) for val in row]))
        return "\n".join(table)


class HistoryTracker(object):
    """Abstract class for tracking how issues change over time."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def start(self, date, initial_issues):
        """Start the period.

        Arguments:
        - date: the first date included
        - initial_issues: the initial set of issues open on the given date
        """
        pass

    @abstractmethod
    def step(self, date, opened_issues, closed_issues):
        """Handle a time step.

        Arguments:
        - date: the next step in the time period
        - opened_issues: new issues that were created since the previous step
        - closed_issues: issues that were closed since the previous step

        Note that closed_issues and opened_issues may overlap if an issue was
        both opened and closed since the previous step.
        """
        pass


class ChangeTracker(HistoryTracker):
    """Track the number of new vs fixed issues over time."""

    def __init__(self):
        self._original_issues = None
        self._new_issues = None
        self._closed_original_issues = None
        self._tracker = []

    def start(self, date, start_issues):
        self._original_issues = set([utils.get_issue_id(i) for i in start_issues])
        self._new_issues = set()
        self._closed_original_issues = set()
        self._tracker.append((date, len(self._closed_original_issues), len(self._new_issues)))

    def step(self, date, opened_issues, closed_issues):
        opened_ids = set([utils.get_issue_id(i) for i in opened_issues])
        closed_ids = set([utils.get_issue_id(i) for i in closed_issues])
        closed_original = closed_ids.intersection(self._original_issues)
        self._closed_original_issues = self._closed_original_issues.union(closed_original)
        self._original_issues = self._original_issues.difference(closed_ids)
        self._new_issues = self._new_issues.union(opened_ids).difference(closed_ids)
        self._tracker.append((date, len(self._closed_original_issues), len(self._new_issues)))

    def display(self):
        """Print out the tracker."""
        table = Table(headers=["date", "fixed", "new"])
        for (date, fixed, new) in self._tracker:
            table.add_row([date.strftime("%Y/%m/%d"), fixed, new])
        print str(table)


class GridTracker(HistoryTracker):
    """Track how issues have changed over time. Split the issues on a given property.

    For instance, to see how issues have changed by priority:
        GridTracker(get_issue_priority)

        date    None    1   2
        2015-01-01  5   8   12
        2015-01-08  7   10  14
        ...
    """

    def __init__(self, prop_fn):
        self._prop_fn = prop_fn
        self._issue_set = None
        self._tracker = []

    def start(self, date, start_issues):
        """Start with the given set of issues."""
        self._issue_set = IssueSet(start_issues)
        self._tracker.append((date, utils.group_issues(start_issues, self._prop_fn)))

    def step(self, date, opened_issues, closed_issues):
        """Add an iteration with the opened/closed issues."""
        for issue in opened_issues:
            self._issue_set.add(issue)
        for issue in closed_issues:
            self._issue_set.remove(issue)
        self._tracker.append((date, utils.group_issues(self._issue_set.list, self._prop_fn)))

    def display(self):
        """Print out the tracker."""
        table = Table()

        # Join keys from each day to get headers
        keys = set()
        for (_, issues) in self._tracker:
            keys = keys.union(issues.keys())
        keys = list(keys)
        keys.sort()
        table.set_headers(["date"] + keys)

        # Print rows
        for (date, issues) in self._tracker:
            date_str = date.strftime("%Y/%m/%d")
            values = [len(issues.get(key, [])) for key in keys]
            table.add_row([date_str] + values)
        print str(table)


def print_groups(issues, prop_fn, hint=0):
    """Print the groups"""
    groups = utils.group_issues(issues, prop_fn)
    keys = groups.keys()
    keys.sort()
    for key in keys:
        key_issues = groups[key]
        print "{key}: {num_issues}".format(key=key, num_issues=len(key_issues)),
        if hint > 0:
            key_ids = [str(utils.get_issue_id(i)) for i in key_issues]
            if len(key_ids) > hint:
                print "["+" ".join(key_ids[:3])+"...]"
            else:
                print "["+" ".join(key_ids)+"]"
        else:
            print
