# Issue Tracker

## Overview

Issue Tracker helps you to generate reports based on bugs in the Google Code Issue Tracker.

## Installation

##### Clone this project and install dependencies

	$ git clone git@github.com:tbuckley/issuetracker.git
	$ cd issuetracker
	$ chmod +x issues.py
	$ pip install httplib2 docopt oauth2client


##### Get your client ID

To see all issues visible to your account, you must create a Client ID:

1. Create a new project in the [Google Developer Console](console.developers.google.com)
2. On the APIs tab, enable the Project Hosting API (must be internal)
3. On the Credentials tab, create a new client ID:
    * Application type: web application
    * Authorized javascript origins: http://localhost:8080
    * Authorized redirect URIs: http://localhost:8080/
4. For your new client ID, click "Download JSON". Move the file to the same folder as the Issue Tracker code
and name the file `client_secrets.json`
5. On the Consent Screen tab, ensure that you have filled out the required fields.


## Usage

Run `./issues.py --help` to see how you can use it:

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

By default, various useful pieces of information will be shown. However, you can configure
what is shown using the `--display` flag. For example, to show just a count of all bugs and untriaged bugs:

	./issues.py chromium --display=count:all,count:status=Untriaged
