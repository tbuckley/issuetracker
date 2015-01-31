"""Class for querying the Google Code issue tracker."""

import httplib2
import copy
from urllib import urlencode
from urlparse import urlunsplit
import xml.etree.ElementTree as ET

def get_first_child_by_tag(page, tag):
    """Return the first child of `page` with the given tag."""
    for child in page:
        if child.tag.endswith(tag):
            return child

def count_for_page(page):
    """Get the count for the given page."""
    return int(get_first_child_by_tag(page, "totalResults").text)

def get_xml_tree_for_url(client, url):
    """Get the xml tree for the given url."""
    (_, content) = client.request(url, "GET")
    return ET.fromstring(content)

def get_next_page(client, page):
    """Get the next page of issues if one exists. Return None otherwise."""
    for child in page:
        if child.tag.endswith("link") and child.attrib["rel"] == "next":
            url = child.attrib["href"]
            return get_xml_tree_for_url(client, url)
    return None

def get_issues_from_page(page):
    """Return a list of the issues from the given page."""
    entries = []
    for child in page:
        if child.tag.endswith("entry"):
            entries.append(child)
    return entries


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

    def closed_before(self, date):
        """Filter to issues closed before midnight at the start of the given date."""
        return self._add_date_query("closed-before", date)

    def closed_after(self, date):
        """Filter to issues closed after midnight at the start of the given date."""
        return self._add_date_query("closed-after", date)

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

    def fetch_all_issues(self, limit=25, verbose=False):
        """Fetch all issues for the query."""
        page = self.fetch_page(limit=limit)

        issues = []
        while page is not None:
            issues += get_issues_from_page(page)
            page = get_next_page(self._client, page)
        if verbose:
            print
        return issues

    def count(self):
        """Get the number of issues for the query."""
        page = self.fetch_page()
        return count_for_page(page)
