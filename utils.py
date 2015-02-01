"""Utilities for working with issues."""

from functools import partial

# TODO(tbuckley) write issue_property_compare_p

# General value helper functions

def process_pipeline(val, transforms):
    """Run the set of transforms on value. Abort if val is None."""
    if val is None:
        return None
    if len(transforms) == 0:
        return val
    transform = transforms[0]
    return process_pipeline(transform(val), transforms[1:])

def ensure_only_one(vals):
    """Ensure that vals contains only one value. Return it or None."""
    if len(vals) != 1:
        return None
    return vals[0]

def safely_cast_to_int(val):
    """Attempt to cast val to an int, returning None if error."""
    try:
        return int(val)
    except ValueError:
        return None

def get_date_for_issue_datestring(datetime):
    """Get the date for a Google Code Issue Tracker datetime."""
    (date, _) = datetime.split("T")
    return date

# ElemTree getters

def get_text(elem):
    """Get the text for the element."""
    return elem.text

def get_first_child_by_tag(page, tag):
    """Return the first child of `page` with the given tag."""
    for child in page:
        if child.tag.endswith(tag):
            return child

def get_single_property(tag, page):
    """Get the single element with the given tag."""
    return process_pipeline(page, [partial(filter, has_tag_p(tag)),
                                   ensure_only_one])

# Issue getters

def get_issue_text_property(tag, issue):
    """Return the text for the property with the given tag."""
    return process_pipeline(issue, [partial(get_single_property, tag),
                                    get_text])

def get_issue_int_property(tag, issue):
    """Return the int value for the property with the given tag."""
    return process_pipeline(issue, [partial(get_issue_text_property, tag),
                                    safely_cast_to_int])

def get_issue_date_property(tag, issue):
    """Return the date value for the property with the given tag."""
    return process_pipeline(issue, [partial(get_issue_text_property, tag),
                                    get_date_for_issue_datestring])

def get_issue_owner(issue):
    """Get the owner for the given issue."""
    return process_pipeline(issue, [partial(get_single_property, "owner"),
                                    partial(get_issue_text_property, "username")])

def get_issue_status(issue):
    """Get the owner for the given issue."""
    return get_issue_text_property("status", issue)

def get_issue_id(issue):
    """Get the id for the given issue."""
    id_tag = "{http://schemas.google.com/projecthosting/issues/2009}id"
    return get_issue_int_property(id_tag, issue)

def get_issue_stars(issue):
    """Get the number of stars for the given issue."""
    return get_issue_int_property("stars", issue)

def get_issue_updated_date(issue):
    """Get the date that the given issue was last updated."""
    return get_issue_date_property("updated", issue)

def get_issue_published_date(issue):
    """Get the date that the given issue was published."""
    return get_issue_date_property("published", issue)

def get_issue_labels(issue):
    """Get the labels for an issue."""
    return process_pipeline(issue, [partial(filter, has_tag_p("label")),
                                    partial(map, get_text)])

def get_issue_labels_by_prefix(prefix, issue):
    """Get the labels with the given prefix. Prefix is removed."""
    has_prefix_p = lambda label: label.startswith(prefix)
    remove_prefix = lambda label: label[len(prefix):]
    return process_pipeline(issue, [get_issue_labels,
                                    partial(filter, has_prefix_p),
                                    partial(map, remove_prefix)])

def get_single_label_text_value(prefix, issue):
    """Get the single label with the given prefix. Prefix is removed."""
    return process_pipeline(issue, [partial(get_issue_labels_by_prefix, prefix),
                                    ensure_only_one])

def get_single_label_int_value(prefix, issue):
    """Get the single label with the given prefix. Prefix is removed."""
    return process_pipeline(issue, [partial(get_single_label_text_value, prefix),
                                    safely_cast_to_int])

def get_issue_priority(issue):
    """Get the integer priority of the given issue. May be None."""
    return get_single_label_int_value("Pri-", issue)

def get_issue_milestone(issue):
    """Get the integer priority of the given issue. May be None."""
    return get_single_label_int_value("M-", issue)

def get_issue_type(issue):
    """Get the integer priority of the given issue. May be None."""
    return get_single_label_text_value("Type-", issue)

# General predicates

def not_p(pred_fn):
    """Negate the given predicate."""
    def pred(issue):
        """Negate the given predicate."""
        return not pred_fn(issue)
    return pred

# ElemTree predicates

def has_tag_p(tag):
    """Return a predicate that tests if an element has the given tag."""
    def pred(elem):
        """Test that an element has a specific tag."""
        return elem.tag.endswith(tag)
    return pred

# Issue predicates

def issue_property_matches_p(prop_fn, value):
    """Create a func to test that the prop value matches the given value."""
    def pred(issue):
        """Test that the issue matches the value."""
        return prop_fn(issue) == value
    return pred

def issue_property_lessthan_p(prop_fn, value):
    """Create a func to test that the prop value is less than the given value."""
    def pred(issue):
        """Test that the issue is less than the value."""
        return prop_fn(issue) < value
    return pred

def issue_has_label_p(label):
    """Return a pred that tests the issue has the given label."""
    def pred(issue):
        """Test that the issue has a given label."""
        labels = get_issue_labels(issue)
        return label in labels
    return pred

def issue_is_before_milestone_p(milestone):
    """Return predicate that tests if the issue is for a previous milestone."""
    return issue_property_lessthan_p(get_issue_milestone, milestone)

def issue_is_for_milestone_p(milestone):
    """Return predicate that tests if the issue is for the given milestone."""
    return issue_property_matches_p(get_issue_milestone, milestone)

def issue_is_launch_p(issue):
    """Return a predicate that tests if issue is a launch bug."""
    return issue_has_label_p("Type-Launch")(issue)

# Misc

def group_issues(issues, prop_fn):
    """Group issues by the given property function."""
    groups = {}
    for issue in issues:
        prop = prop_fn(issue)
        if prop not in groups:
            groups[prop] = []
        groups[prop].append(issue)
    return groups
