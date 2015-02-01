# Issue Tracker

## Overview

Issue Tracker helps you to generate reports based on bugs in the Google Code Issue Tracker.

## Installation

##### Clone this project and install dependencies

1. `git clone ...`
2. `pip install httplib2 docopt oauth2client`


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

    issues.py <project> [--label=<LABEL>] [--milestone=<M>] [--authorize]

    Options:
	  -h --help        Show this screen.
	  --version        Show version.
	  --authorize      Use logged-in client for requests.
	  --label=<LABEL>  Filter issues to the given label.
	  --milestone=<M>  Show information for the given milestone.