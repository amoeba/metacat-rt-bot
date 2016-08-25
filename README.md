# submissions-bot

Alerts a Slack channel (via webhook) of recently-modified objects from
[`listObjects()`](http://jenkins-1.dataone.org/jenkins/job/API%20Documentation%20-%20trunk/ws/api-documentation/build/html/apis/MN_APIs.html#MNRead.listObjects) and creates tickets in
[RT](https://www.bestpractical.com/rt-and-rtir) for new submissions and comments on already-created tickets.


## Dependencies

- I have developed and tested this with Python 3.5.1
- Extra packages (install via requirements.txt):
  - [requests](http://docs.python-requests.org/en/master/)
  - [python-dotenv](https://github.com/theskumar/python-dotenv)
  - [python-rt](https://gitlab.labs.nic.cz/labs/python-rt)

## Setup

- Run `pip install -r requirements.txt`
- Create a file called `.env` in the same directory as the script

  Include the following variables:

  ```
  LASTFILE_PATH=LASTRUN             # Determines where the bot stores its state
  BASE_URL="{}"                     # Member Node base URL
  SLACK_WEBHOOK_URL="{URL}"         # Your Slack webhook URL
  USERS="@you @me @everyone"        # Who you want to direct the message to
  RT_URL="https://your-org.com/rt"  # The URL of your RT install
  RT_USER="you"                     # Your RT username
  RT_PASS="{PASSWORD}"              # Your RT password
  RT_TICKET_OWNER="someone"         # RT username to assign new tickets to
  ```

## Running

Run `python bot.py`
