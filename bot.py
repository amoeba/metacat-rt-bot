''' bot.py

    Grabs the latest count and list of identifiers add to the Arctic Data
    Center and pastes them into the #arctic Slack channel. More details to come.
'''


import os.path
import datetime
import requests
from xml.etree import ElementTree

# Config
LASTFILE_PATH = "LASTFILE"
MAXITEMS = 3


def list_objects(from_date, to_date):
    url = "https://arcticdata.io/metacat/d1/mn/v2/object?fromDate={}&toDate={}".format(from_date, to_date)
    response = requests.get(url)
    return ElementTree.fromstring(response.content)


def get_count(doc):
    attrs = doc.findall('.')[0].items()
    count = [attr[1] for attr in attrs if attr[0] == 'count'][0]

    return count


def get_object_identifiers(doc):
    return [o.find('identifier').text for o in doc.findall("objectInfo")]


def get_last_run():
    last_run = None

    if os.path.isfile("LASTRUN"):
        print("Loading LASTRUN from disk.")
        with open("LASTRUN", "r") as f:
            last_run = f.read()
    else:
        print("Setting LASTRUN to now()")
        last_run = now()

    return last_run


def now():
    return datetime.datetime.utcnow().isoformat()


def main():
    from_date = get_last_run()
    to_date = now()

    # Debug
    print("Running from {} to {}.".format(from_date, to_date))
    #

    doc = list_objects(from_date, to_date)
    print(get_count(doc))
    print(get_object_identifiers(doc))

    print("Saving LASTRUN")
    with open("LASTRUN", "w") as f:
        f.write(to_date)


if __name__ == "__main__":
    main()
