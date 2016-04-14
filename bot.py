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

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

LASTFILE_PATH = os.environ.get("LASTFILE_PATH")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS"))
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
USERS = os.environ.get("USERS")


def send_message(message):
    return requests.post(SLACK_WEBHOOK_URL, data=json.dumps({'text': message}))


def create_message(count, identifiers, url):
    cap = count
    if (count > MAX_ITEMS):
        cap = MAX_ITEMS

    identifiers_fmt = ["- {}".format(identifier) for identifier in identifiers]
    identifiers_string = "\n".join(identifiers_fmt[:MAX_ITEMS])
    url_esc = url.replace('&', '&amp;')  # Slack says escape ambersands

    message = None

    if (count == 1):
        message = "Hey {}, {} object was just modified: {}. Just thought I'd let you know. You can see more detail at {}.".format(USERS,
                                                                                                                                  count,
                                                                                                                                  identifiers[0],
                                                                                                                                  url_esc)
    else:
        message = "Hey {}, {} objects were just modified. Here are the first {}:\n\n{}\n\nJust thought I'd let you know. You can see more detail at {}.".format(USERS,
                                                                                                                                                                count,
                                                                                                                                                                cap,
                                                                                                                                                                identifiers_string,
                                                                                                                                                                url_esc)
    return message


def create_list_objects_url(from_date, to_date):
    return "https://arcticdata.io/metacat/d1/mn/v2/object?fromDate={}&toDate={}".format(from_date, to_date)


def list_objects(url):
    response = requests.get(url)
    return ElementTree.fromstring(response.content)


def get_count(doc):
    attrs = doc.findall('.')[0].items()
    count = [attr[1] for attr in attrs if attr[0] == 'count'][0]

    return int(count)


def get_object_identifiers(doc):
    return [o.find('identifier').text for o in doc.findall("objectInfo")]


def get_last_run():
    last_run = None

    path = os.path.join(os.path.dirname(__file__), LASTFILE_PATH)

    if os.path.isfile(path):
        with open(path, "r") as f:
            last_run = f.read().splitlines()[0]
    else:
        last_run = now()

    return last_run


def now():
    return datetime.datetime.utcnow().isoformat()


def main():
    from_date = get_last_run()
    to_date = now()

    url = create_list_objects_url(from_date, to_date)
    doc = list_objects(url)
    count = get_count(doc)
    identifiers = get_object_identifiers(doc)

    print(url)
    print(count)

    if (count > 0):
        send_message(create_message(count, identifiers, url))

    with open(os.path.join(os.path.dirname(__file__), LASTFILE_PATH), "w") as f:
        f.write(to_date)


if __name__ == "__main__":
    main()
