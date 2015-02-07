"""Class for querying the Google Code issue tracker."""

import httplib2
import copy
from urllib import urlencode
from urlparse import urlunsplit
import xml.etree.ElementTree as ET
from math import ceil
from multiprocessing import Pool
import datetime

from utils import get_first_child_by_tag

MAX_POOL_THREADS = 10

def count_for_page(page):
    """Get the count for the given page."""
    return int(get_first_child_by_tag(page, "totalResults").text)

def get_xml_tree_for_url(client, url):
    """Get the xml tree for the given url."""
    (_, content) = client.request(url, "GET")
    return ET.fromstring(content)

def get_next_page_url(page):
    """Get the url of the next page."""
    for child in page:
        if child.tag.endswith("link") and child.attrib["rel"] == "next":
            return child.attrib["href"]
    return None

def get_next_page(client, page):
    """Get the next page of issues if one exists. Return None otherwise."""
    url = get_next_page_url(page)
    if url is None:
        return None
    return get_xml_tree_for_url(client, url)

def get_issues_from_page(page):
    """Return a list of the issues from the given page."""
    entries = []
    for child in page:
        if child.tag.endswith("entry"):
            entries.append(child)
    return entries


def _fetch_page_args(args):
    """Helper function to call fetch_page on the query."""
    (query, offset, limit, authorize) = args
    if authorize is not None:
        query._client = authorize()
    return query.fetch_page(offset, limit)


def _fetch_changes_for_range(args):
    (query, start, end, authorize) = args
    opened_issues = query.opened_in_range(start, end).fetch_all_issues(authorize=authorize)
    closed_issues = query.closed_in_range(start, end).fetch_all_issues(authorize=authorize)
    return (start, opened_issues, closed_issues)

class IssuesQuery(object):
    """Query the Google Code issue tracker.

    IssueQuery is immutable, so you can create multiple requests from a base request.
        base_query = IssueQuery("myproject").opened_before(today - timedelta(5))
        johns_5d_old_issues = base_query.query("owner:johnsmith@google.com").fetch_all_issues()
        ui_5d_old_issues = base_query.label("Cr-UI").fetch_all_issues()
    """

    def __init__(self, project, client=None, params=None, query=None):
        if client is None:
            client = httplib2.Http()

        self._project = project
        self._client = client
        self._query = query.split(" ") if query is not None else []
        self._params = params or {"can": "open"}

    def _clone(self, project=None, client=None, params=None, query=None):
        """Clone this IssuesQuery with the provided differences."""
        if project is None:
            project = self._project
        if client is None:
            client = self._client
        if params is None:
            params = copy.deepcopy(self._params)
        if query is None:
            query = self._query
        return IssuesQuery(self._project, client=client, params=params, query=" ".join(query))

    def _update_params(self, key, value):
        """Update the params for this query."""
        params = copy.deepcopy(self._params)
        params[key] = value
        return self._clone(params=params)

    def can(self, can):
        """Limit the query to a specific set of issues."""
        assert can in ["all", "open", "owned", "reported", "starred", "new", "to-verify"]
        return self._update_params("can", can)

    def open(self):
        """Set can to open."""
        return self.can("open")

    def all(self):
        """Set can to all."""
        return self.can("all")

    def label(self, label):
        """Limit the query to issues with the given label."""
        return self._update_params("label", label)

    def query(self, query):
        """Set the search string for the query."""
        query_list = copy.copy(self._query)
        query_list.append(query)
        return self._clone(query=query_list)

    def _add_date_query(self, attribute, date):
        """Add a date query."""
        date_str = date.strftime("%Y/%m/%d")
        query = "{attribute}:{date}".format(attribute=attribute, date=date_str)
        return self.query(query)

    def opened_before(self, date):
        """Filter to issues opened before midnight at the start of the given date."""
        return self._add_date_query("opened-before", date)

    def opened_after(self, date):
        """Filter to issues opened after midnight at the start of the given date."""
        return self._add_date_query("opened-after", date)

    def opened_in_range(self, start_date, end_date):
        """Filter to issues opened between the midnights starting start_date and end_date."""
        return self.can("all").opened_after(start_date).opened_before(end_date)

    def closed_before(self, date):
        """Filter to issues closed before midnight at the start of the given date."""
        return self._add_date_query("closed-before", date)

    def closed_after(self, date):
        """Filter to issues closed after midnight at the start of the given date."""
        return self._add_date_query("closed-after", date)

    def closed_in_range(self, start_date, end_date):
        """Filter to issues closed between the midnights starting start_date and end_date."""
        return self.can("all").closed_after(start_date).closed_before(end_date)

    def to_url(self, offset=0, limit=25):
        """Convert this query to a URL."""
        params = copy.deepcopy(self._params)
        params["max-results"] = limit
        params["start-index"] = offset + 1  # 1-based indexing
        if len(self._query) > 0:
            params["q"] = " ".join(self._query)
        query = urlencode(params)
        path = "/feeds/issues/p/{project}/issues/full".format(project=self._project)
        return urlunsplit(("https", "code.google.com", path, query, ""))

    def fetch_page(self, offset=0, limit=25):
        """Fetch the issues page for the query using offset and limit."""
        url = self.to_url(offset=offset, limit=limit)
        return get_xml_tree_for_url(self._client, url)

    def fetch_all_issues(self, limit=25, verbose=False, authorize=None):
        """Fetch all issues for the query."""
        page = self.fetch_page(limit=limit)
        count = count_for_page(page)

        pages = [page]
        num_pages = int(ceil(float(count) / float(limit)))
        if num_pages > 1:
            pool = Pool(min(num_pages, MAX_POOL_THREADS))
            arg_gen = ((self, page*limit, limit, authorize) for page in range(1, num_pages))
            pages += pool.map(_fetch_page_args, arg_gen)
            pool.close()

        issues = []
        for page in pages:
            issues += get_issues_from_page(page)
        return issues

    def fetch_changes_for_range(self, start, end, days, authorize=None):
        date = start
        ranges = []
        while date < end:
            end_date = date + datetime.timedelta(days=days)
            ranges.append((date, end_date))
            date = date + datetime.timedelta(days=days)

        pool = Pool(min(len(ranges), MAX_POOL_THREADS))
        arg_gen = ((self, start, end, authorize) for (start, end) in ranges)
        changes = pool.map(_fetch_changes_for_range, arg_gen)
        pool.close()
        return changes

    def count(self):
        """Get the number of issues for the query."""
        page = self.fetch_page()
        return count_for_page(page)
