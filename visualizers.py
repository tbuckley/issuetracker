"""Visualizers for issues."""

from abc import ABCMeta, abstractmethod

import utils

# class IssueSet(object):
    
#     def __init__(self, issues=None):
#         self._issues = {}

#         if issues is not None:
#             for issue in issues:
#                 self.add(issue)

#     def add(self, issue):
#         """Add an issue to the set."""
#         pass

#     def remove(self, issue):
#         """Remove an issue from the set."""
#         pass


# class Table(object):
#     def __init__(self, headers=None):
#         self._headers = headers

#     def set_headers(self, headers):
#         self._headers = headers

#     def add_row(self, row):
#         pass

#     def __str__(self):
#         pass


class HistoryTracker:
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
        print "\t".join(["date", "fixed", "new"])
        for (date, fixed, new) in self._tracker:
            print "\t".join([date.strftime("%Y/%m/%d"), str(fixed), str(new)])


def create_issue_dict(issues):
    issue_dict = {}
    for issue in issues:
        issue_dict[utils.get_issue_id(issue)] = issue
    return issue_dict

def issue_dict_remove(issue_dict, issue):
    del issue_dict[utils.get_issue_id(issue)]

def issue_dict_add(issue_dict, issue):
    issue_dict[utils.get_issue_id(issue)] = issue

class GridTracker(HistoryTracker):
    """Track issues over time."""

    def __init__(self, prop_fn):
        self._prop_fn = prop_fn
        self._issue_dict = None
        self._tracker = []

    def start(self, date, start_issues):
        """Start with the given set of issues."""
        self._issue_dict = create_issue_dict(start_issues)
        self._tracker.append((date, group_issues(start_issues, self._prop_fn)))

    def step(self, date, opened_issues, closed_issues):
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
            key_ids = [str(utils.get_issue_id(i)) for i in key_issues]
            if len(key_ids) > hint:
                print "["+" ".join(key_ids[:3])+"...]"
            else:
                print "["+" ".join(key_ids)+"]"
        else:
            print
