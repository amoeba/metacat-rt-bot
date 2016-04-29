''' bot.py

    Grabs the latest count and list of identifiers add to the Arctic Data
    Center and pastes them into the #arctic Slack channel. More details to come.
'''


import os.path
import json
import datetime
from xml.etree import ElementTree
import requests
from dotenv import load_dotenv
import rt

# Dynamic variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

LASTFILE_PATH = os.environ.get("LASTFILE_PATH")
BASE_URL = os.environ.get("BASE_URL")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
USERS = os.environ.get("USERS")
RT_URL = os.environ.get("RT_URL")
RT_USER = os.environ.get("RT_USER")
RT_PASS = os.environ.get("RT_PASS")
RT_TICKET_OWNER = os.environ.get("RT_TICKET_OWNER")

# Hard-coded variables
PID_STARTSWITH = "arctic-data."
EML_FMT_ID = "eml://ecoinformatics.org/eml-2.1.1"


def send_message(message):
    return requests.post(SLACK_WEBHOOK_URL, data=json.dumps({'text': message}))


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

    template = ("Hey {}, {} {} {} just modified. "
                "Just thought I'd let you know. "
                "You can see more detail at {}.")

    message = template.format(USERS, count, objects, was, url_esc)

    return message


def create_tickets_message(tickets):
    message = "The following tickets were just created:\n"

    for ticket in tickets:
        ticket_url = "{}/Ticket/Display.html?id={}".format(RT_URL, ticket)
        line = "- {}\n".format(ticket_url)
        message += line

    return message


def create_list_objects_url(from_date, to_date):
    return ("{}/object?fromDate={}&toDate={}").format(BASE_URL,
                                                      from_date,
                                                      to_date)


def list_objects(url):
    response = requests.get(url)

    try:
        xmldoc = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as err:
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

        if format_id == EML_FMT_ID and pid.startswith(PID_STARTSWITH):
            metadata.append(o.find('identifier').text)

    return metadata


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


def create_or_update_tickets(identifiers):
    if len(identifiers) <= 0:
        return None

    tracker = rt.Rt("{}/REST/1.0/".format(RT_URL), RT_USER, RT_PASS)

    if tracker.login() is False:
        send_message("Hey @bryce, I failed to log into RT. Something's wrong!")
        raise Exception("Failed to log in to RT.")

    tickets = []

    for identifier in identifiers:
        ticket = ticket_find(tracker, identifier)

        if ticket is None:
            tickets.append(ticket_create(tracker, identifier))
        else:
            ticket_reply(tracker, ticket)

    return tickets


def ticket_find(tracker, pid):
    title = 'Submission: {}'.format(pid)
    results = tracker.search(Queue='arcticdata', Subject__like=title)
    ids = [t['id'].replace('ticket/', '') for t in results]

    if len(ids) > 0:
        return ids[0]
    else:
        return None


def ticket_create(tracker, pid):
    ticket = tracker.create_ticket(Queue='arcticdata',
                                   Subject="New submission: {}".format(pid),
                                   Owner=RT_TICKET_OWNER,
                                   Text=("This ticket was automatically created by the "
                                         "listobjects bot because the PID {} was modified. "
                                         "See https://github.nceas.ucsb.edu/KNB/arctic-data/"
                                         "blob/master/docs/handling-submissions.md for more "
                                         "information on what to do.").format(pid))

    return ticket


def ticket_reply(tracker, ticket_id):
    tracker.reply(ticket_id,
                  text="PID {} was updated and needs moderation.")


def main():
    from_date = get_last_run()
    to_date = now()

    url = create_list_objects_url(from_date, to_date)
    doc = list_objects(url)
    count = get_count(doc)

    if count > 0:
        send_message(create_list_objects_message(count, url))

        tickets = create_or_update_tickets(get_metadata(doc))
        send_message(create_tickets_message(tickets))

    save_last_run(to_date)


if __name__ == "__main__":
    main()
