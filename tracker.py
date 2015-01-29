"""Tool for generating reports based on Google Code Issue Tracker."""

import argparse
import httplib2
from oauth2client import tools
from oauth2client.tools import run_flow
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from urllib import urlencode
from urlparse import urlunsplit
import xml.etree.ElementTree as ET
from collections import namedtuple
import datetime
from math import ceil
import sys

CLIENT_SECRETS = 'client_secrets.json'
OAUTH2_STORAGE = 'oauth2.dat'
ISSUE_TRACKER_SCOPE = 'https://code.google.com/feeds/issues'

PROJECT = "chromium"
# LABEL = "cr-ui-settings"
# LABEL = "cr-ui-input-virtualkeyboard"
LABEL = "cr-ui-shell-touchview"

PageDetails = namedtuple("PageDetails", ["count", "limit", "offset"])

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

def get_xml_tree_for_url(client, url):
    """Get the xml tree for the given url."""
    (_, content) = client.request(url, "GET")
    return ET.fromstring(content)

def get_issues_page(client, project, label=None, can="open", start_index=1, q=None):
    """Return the issues page for the specified label/can."""
    query_dict = {
        "can": can,
        "start-index": start_index,
        "max-results": 100,
    }
    if label is not None:
        query_dict["label"] = label
    if q is not None:
        query_dict["q"] = q

    query = urlencode(query_dict)
    path = "/feeds/issues/p/{project}/issues/full".format(project=project)
    url = urlunsplit(("https", "code.google.com", path, query, ""))
    return get_xml_tree_for_url(client, url)

def get_next_page(client, page):
    """Get the next page of issues if one exists. Return None otherwise."""
    for child in page:
        if child.tag.endswith("link") and child.attrib["rel"] == "next":
            url = child.attrib["href"]
            return get_xml_tree_for_url(client, url)
    return None

def get_first_child_by_tag(page, tag):
    """Return the first child of `page` with the given tag."""
    for child in page:
        if child.tag.endswith(tag):
            return child

def get_issues_from_page(page):
    """Return a list of the issues from the given page."""
    entries = []
    for child in page:
        if child.tag.endswith("entry"):
            entries.append(child)
    return entries

def get_all_issues(client, project, verbose=False, **kwargs):
    """Get all issues for the given search."""
    page = get_issues_page(client, project, **kwargs)
    
    if verbose:
        details = get_details_for_page(page)
        num_pages = 0
        if details.limit > 0:
            num_pages = int(ceil(details.count / float(details.limit)))
        counter = 1
        print "Fetching {num_pages} pages...".format(num_pages=num_pages),
        sys.stdout.flush()

    issues = []
    while page is not None:
        if verbose:
            print "{counter} ".format(counter=counter),
            sys.stdout.flush()
            counter += 1
        issues += get_issues_from_page(page)
        page = get_next_page(client, page)
    if verbose:
        print
    return issues

def get_details_for_page(page):
    """Return the number of open issues."""
    count = int(get_first_child_by_tag(page, "totalResults").text)
    offset = int(get_first_child_by_tag(page, "startIndex").text)
    limit = int(get_first_child_by_tag(page, "itemsPerPage").text)
    return PageDetails(count=count, offset=offset, limit=limit)

def get_issue_owner(issue):
    """Get the owner for the given issue."""
    owner = get_first_child_by_tag(issue, "owner")
    if owner is None:
        return None
    username = get_first_child_by_tag(owner, "username")
    if username is None:
        return None
    return username.text

def get_issue_status(issue):
    """Get the owner for the given issue."""
    status = get_first_child_by_tag(issue, "status")
    if status is None:
        return None
    return status.text

def get_issue_id(issue):
    """Get the id for the given issue."""
    for child in issue:
        # if child.tag.endswith("id"):
        #     print child.tag
        if child.tag == "{http://schemas.google.com/projecthosting/issues/2009}id":
            return child.text
    return None

def get_text(elem):
    """Get the text for the element."""
    return elem.text

def has_tag(tag):
    """Return a predicate that tests if an element has the given tag."""
    def func(elem):
        """Test that an element has a specific tag."""
        return elem.tag.endswith(tag)
    return func

def get_issue_labels(issue):
    """Get the labels for an issue."""
    return map(get_text, filter(has_tag("label"), issue))

def get_labels_with_prefix(issue, prefix):
    """Get the labels with the given prefix. Prefix is removed."""
    labels = get_issue_labels(issue)
    matching_labels = filter(lambda label: label.startswith(prefix), labels)
    return map(lambda label: label[len(prefix):], matching_labels)

def get_issue_priority(issue):
    """Get the integer priority of the given issue. May be None."""
    priorities = get_labels_with_prefix(issue, "Pri-")
    if len(priorities) != 1:
        return None
    try:
        return int(priorities[0])
    except ValueError:
        return None

def get_issue_milestone(issue):
    """Get the integer priority of the given issue. May be None."""
    milestones = get_labels_with_prefix(issue, "M-")
    if len(milestones) != 1:
        return None
    try:
        return int(milestones[0])
    except ValueError:
        return None

def get_issues_in_range(client, project, status, date, days=1, **kwargs):
    """Get the issues with the given status on the date. status = (opened|closed)."""
    end_date = date + datetime.timedelta(days=days)
    date_str = date.strftime("%Y/%m/%d")
    end_date_str = end_date.strftime("%Y/%m/%d")
    query_template = "{status}-after:{date} {status}-before:{end_date}"
    query = query_template.format(date=date_str, end_date=end_date_str, status=status)
    return get_all_issues(client, project, q=query, **kwargs)

def get_issues_opened_in_range(client, project, date, days=1, **kwargs):
    """Get the issues opened on the date."""
    return get_issues_in_range(client, project, "opened", date, days=days, can="all", **kwargs)

def get_issues_closed_in_range(client, project, date, days=1, **kwargs):
    """Get the issues closed on the date."""
    return get_issues_in_range(client, project, "closed", date, days=days, can="all", **kwargs)

def get_issues_open_on_date(client, project, date, **kwargs):
    """Get the issues that were open on the given date."""
    issues = []
    date_str = date.strftime("%Y/%m/%d")
    # Closed bugs that were filed before `date` and closed after `date`
    query = "opened-before:{date} closed-after:{date}".format(date=date_str)
    issues += get_all_issues(client, project, q=query, can="all", **kwargs)
    # Open bugs that were filed before `date`
    query = "opened-before:{date}".format(date=date_str)
    issues += get_all_issues(client, project, q=query, **kwargs)
    return issues

def get_num_issues(client, project, **kwargs):
    """Get the number of issues for the query."""
    page = get_issues_page(client, project, **kwargs)
    details = get_details_for_page(page)
    return details.count

def get_num_issues_open_on_date(client, project, date, **kwargs):
    """Get the issues that were open on the given date."""
    issues = 0
    date_str = date.strftime("%Y/%m/%d")
    # Closed bugs that were filed before `date` and closed after `date`
    query = "opened-before:{date} closed-after:{date}".format(date=date_str)
    issues += get_num_issues(client, project, q=query, can="all", **kwargs)
    # Open bugs that were filed before `date`
    query = "opened-before:{date}".format(date=date_str)
    issues += get_num_issues(client, project, q=query, **kwargs)
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
            key_ids = [get_issue_id(i) for i in key_issues]
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

def iterate_through_range(client, project, start, end, start_fn=None, iter_fn=None, days=1, **kwargs):
    """Iterate through the range."""
    date = start
    start_issues = get_issues_open_on_date(client, project, date, **kwargs)

    if start_fn is not None:
        start_fn(date, start_issues)

    while date < end:
        opened_issues = get_issues_opened_in_range(client, project, date, days=days, **kwargs)
        closed_issues = get_issues_closed_in_range(client, project, date, days=days, **kwargs)

        date = date + datetime.timedelta(days=days)

        if iter_fn is not None:
            iter_fn(date, opened_issues, closed_issues)


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
                    values.append("")
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


def print_open_close_rate(client, project, start, end, days=1, **kwargs):
    """Print the rate of open/closed bugs."""

    priority_tracker = GridTracker(get_issue_priority)
    status_tracker = GridTracker(get_issue_status)
    milestone_tracker = GridTracker(get_issue_milestone)
    change_tracker = ChangeTracker()

    def start_fn(*args, **kwargs):
        priority_tracker.start(*args, **kwargs)
        status_tracker.start(*args, **kwargs)
        milestone_tracker.start(*args, **kwargs)
        change_tracker.start(*args, **kwargs)

    def iter_fn(*args, **kwargs):
        priority_tracker.iter(*args, **kwargs)
        status_tracker.iter(*args, **kwargs)
        milestone_tracker.iter(*args, **kwargs)
        change_tracker.iter(*args, **kwargs)

    iterate_through_range(client, project, start, end, start_fn, iter_fn, days=days, **kwargs)

    priority_tracker.display()
    status_tracker.display()
    milestone_tracker.display()
    change_tracker.display()


def main():
    """Generate issues CSV."""
    http = _authorize()
    issues = get_all_issues(http, PROJECT, label=LABEL, verbose=True)
    
    print "\nTotal issues: {num_issues}".format(num_issues=len(issues))

    print "\n== Issues by owner =="
    print_groups(issues, get_issue_owner, hint=3)
    print "\n== Issues by priority =="
    print_groups(issues, get_issue_priority, hint=3)
    print "\n== Issues by milestone =="
    print_groups(issues, get_issue_milestone, hint=3)
    print "\n== Issues by status =="
    print_groups(issues, get_issue_status, hint=3)
    print "\n== Issues by priority over past 120 days =="
    start = datetime.date.today() - datetime.timedelta(days=120)
    end = datetime.date.today()
    print_open_close_rate(http, PROJECT, start, end, days=7, label=LABEL)
    
if __name__ == "__main__":
    main()
