''' bot.py

    Grabs the latest count and list of identifiers add to the Arctic Data
    Center and pastes them into the #arctic Slack channel. Also creates tickets
    in RT for any registry-created objects that don't have tickets.
'''


import sys
import os.path
import json
import datetime
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv
import rt
import re

# Dynamic variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

LASTFILE_PATH = os.environ.get("LASTFILE_PATH")
MN_BASE_URL = os.environ.get("MN_BASE_URL")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
RT_URL = os.environ.get("RT_URL")
RT_USER = os.environ.get("RT_USER")
RT_PASS = os.environ.get("RT_PASS")

# Token handling code: Try to load the token at bot initialization
# and leave it set to None if the token file is not found or not readable
TOKEN_PATH = os.environ.get("TOKEN_PATH")
TOKEN = None

if os.path.exists(TOKEN_PATH):
    with open(TOKEN_PATH, 'rb') as f:
        TOKEN = f.read()

# Log in to RT
TRACKER = rt.Rt("{}/REST/1.0/".format(RT_URL), RT_USER, RT_PASS)

if TRACKER.login() is False:
    send_message("I failed to log into RT. Something's wrong!")
    raise Exception("Failed to log in to RT.")

# Hard-coded variables
PID_STARTSWITH = "arctic-data."
PID_STARTSWITH_ALT = "autogen."
EML_FMT_ID = "eml://ecoinformatics.org/eml-2.1.1"


# General functions

def now():
    return datetime.datetime.utcnow().isoformat()


def get_last_run():
    last_run = None

    path = os.path.join(os.path.dirname(__file__), LASTFILE_PATH)

    if os.path.isfile(path):
        with open(path, "r") as f:
            last_run = f.read().splitlines()[0]
    else:
        last_run = now()

    return last_run


def save_last_run(to_date):
    with open(os.path.join(os.path.dirname(__file__), LASTFILE_PATH), "w") as f:
        f.write(to_date)


# Slack functions

def send_message(message):
    return requests.post(SLACK_WEBHOOK_URL, data=json.dumps({'text': message}))


def test_slack():
    """Send a test message to slack."""

    print("Sending a test message...")

    r = requests.post(SLACK_WEBHOOK_URL, data=json.dumps({'text': "Testing"}))

    if r.status_code != 200:
        print("Status: {}".format(r.status_code))
        print("Response: {}".format(r.text))

    r


def create_list_objects_message(count, url):
    url_esc = url.replace('&', '&amp;')  # Slack says escape ambersands

    message = None

    # Deal with plural forms of strings
    if count == 1:
        objects = "object"
        was = "was"
    else:
        objects = "objects"
        was = "were"

    template = ("Hey: {} {} {} just modified. "
                "Just thought I'd let you know. "
                "You can see more detail at {}.")

    message = template.format(count, objects, was, url_esc)

    return message


def create_tickets_message(tickets):
    message = "The following tickets were just created or updated:\n"

    for ticket in set(tickets):
        ticket_info = TRACKER.get_ticket(ticket)
        ticket_url = "{}/Ticket/Display.html?id={}".format(RT_URL, ticket)
        line = "- {} {}\n".format(ticket_info['Subject'], ticket_url)
        message += line

    return message

def create_list_objects_url(from_date, to_date):
    return ("{}/object?fromDate={}&toDate={}").format(MN_BASE_URL,
                                                      from_date,
                                                      to_date)


# Member Node functions

def list_objects(url):
    response = requests.get(url)

    try:
        xmldoc = ET.fromstring(response.content)
    except ET.ParseError as err:
        print("Error while parsing list_objects() response.")
        print("Error: {}".format(err))
        print("Response content:")
        print(response.content)

        raise

    return xmldoc


def get_count(doc):
    attrs = doc.findall('.')[0].items()
    count = [attr[1] for attr in attrs if attr[0] == 'count'][0]

    return int(count)


def get_object_identifiers(doc):
    return [o.find('identifier').text for o in doc.findall("objectInfo")]


def get_metadata(doc):
    metadata = []

    # Filter to EML 2.1.1 objects
    for o in doc.findall("objectInfo"):
        format_id = o.find('formatId').text
        pid = o.find('identifier').text

        if format_id == EML_FMT_ID and (pid.startswith(PID_STARTSWITH) or pid.startswith(PID_STARTSWITH_ALT)):
            metadata.append(o.find('identifier').text)

    return metadata

def get_dataset_title(pid):
    # Stop now if the token isn't set up
    if TOKEN is None:
        return None

    # Grab the doc
    req = requests.get("/".join([MN_BASE_URL, 'object', pid]),
                        headers = { "Authorization" : " ".join( ["Bearer", str(TOKEN)] )})

    if req.status_code != 200:
        return None

    doc = ET.fromstring(req.text)
    titles = doc.findall(".//title")

    if len(titles) < 1:
        return None
    else:
        return titles[0].text[0:40]
    
# RT functions

def ticket_find(pid):
    # Strip version stringn from PID
    # i.e. arctic-data.X.Y => arctic-data.X
    # so a new ticket isn't created for updates
    tokens = pid.split('.')
    pid_noversion = '.'.join(tokens[0:(len(tokens)-1)])

    title = '{}'.format(pid_noversion)
    results = TRACKER.search(Queue='arcticdata', Subject__like=title)
    ids = [t['id'].replace('ticket/', '') for t in results]

    if len(ids) > 0:
        return ids[0]
    else:
        return None


def ticket_create(pid):
    # Try to get extra metadata about the pid
    title = get_dataset_title(pid)
    last_name = get_last_name(pid)

    # Produce a nicer title in the event submitter or title are None
    if title is None and last_name is None:
        subject = pid
    
    # title + PID
    if title is not None and last_name is None:
        subject = "{} ({})".format(title, pid)

    # last_name + PID
    if title is None and last_name is not None:
        subject = "{} ({})".format(last_name, pid)
    
    # last_name + title + PID
    if title is not None and last_name is not None:
        subject = "{} - {} ({})".format(last_name, title, pid)
    
    ticket = TRACKER.create_ticket(Queue='arcticdata',
                                   Subject=subject,
                                   Text=create_ticket_text(pid))

    return ticket


def create_ticket_text(pid):
    template = """A new submission just came in. View it here: https://arcticdata.io/catalog/#view/{}. This ticket was automatically created by the submissions bot because the PID {} was created/modified. See https://github.nceas.ucsb.edu/KNB/arctic-data/blob/master/docs/handling-submissions.md for more information on what to do. If you aren't sure why this ticket was created, please see the README at https://github.nceas.ucsb.edu/KNB/submissions-bot.")"""

    return template.format(pid, pid)


def ticket_reply(ticket_id, identifier):
    TRACKER.comment(ticket_id,
                    text="PID {} was updated and needs moderation. If you aren't sure why this comment was made, please see the README at https://github.nceas.ucsb.edu/KNB/submissions-bot.".format(identifier))


def create_or_update_tickets(identifiers):
    tickets = []

    if len(identifiers) <= 0:
        return tickets

    for identifier in identifiers:
        ticket = ticket_find(identifier)

        if ticket is None:
            tickets.append(ticket_create(identifier))
        else:
            ticket_reply(ticket, identifier)
            tickets.append(ticket)

    return tickets


def get_sysmeta_submitter(pid):
    req = requests.get("/".join([MN_BASE_URL, 'meta', pid]),
                        headers = { "Authorization" : " ".join( ["Bearer", str(TOKEN)] )})

    if req.status_code != 200:
        return None

    doc = ET.fromstring(req.text)
    submitters = doc.findall(".//submitter")

    if len(submitters) < 1:
        return None
    else:
        return submitters[0].text

def get_last_name(pid):
    last_name = None

    # Try to get the sysmeta submitter
    submitter = get_sysmeta_submitter(pid)

    if submitter is None:
        return None

    if re.search('orcid', submitter):
        last_name = get_last_name_orcid(submitter)
    elif submitter.lower().startswith('uid='):
        last_name = get_last_name_dn(submitter)

    return last_name

def get_last_name_dn(subject):
    '''todo'''
    tokens = dict([part.lower().split('=') for part in subject.split(',')])

    if 'uid' in tokens:
        return tokens['uid']
    else:
        return subject
    
def get_last_name_orcid(subject):
    orcid_id = parse_orcid_id(subject)
    
    req = requests.get("/".join(["http://pub.orcid.org", orcid_id]),
                       headers={'Accept':'application/orcid+json'})
    
    if req.status_code != 200:
        return subject

    resp = req.json()

    return resp['orcid-profile']['orcid-bio']['personal-details']['family-name']['value']

def parse_orcid_id(value):
    match = re.search("\d{4}-\d{4}-\d{4}-[\dX]{4}", value)

    if match is None:
        return value
    else:
        return match.group(0)

def main():
    # Process arguments
    args = sys.argv

    if len(args) == 2:
        if args[1] == "-t" or args[1] == "--test":
            test_slack()

            return

    from_date = get_last_run()
    to_date = now()

    url = create_list_objects_url(from_date, to_date)
    doc = list_objects(url)
    count = get_count(doc)

    if count > 0:
        pids = get_metadata(doc)
        tickets = create_or_update_tickets(pids)

        if len(tickets) > 0:
            send_message(create_tickets_message(tickets))

    save_last_run(to_date)


if __name__ == "__main__":
    main()
