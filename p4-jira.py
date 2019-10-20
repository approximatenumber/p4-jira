#!/usr/bin/env python3

import sys
import argparse
import re
import os
import subprocess
import logging
from jira import JIRA
from jira.exceptions import JIRAError
from dotenv import load_dotenv
load_dotenv()

# readonly user
P4USER = 'observer'
P4PASSWD = 'observer'
WORKING_PATH = '/opt/perforce/p4-jira'
ISSUE_KEY_RE = r'[A-Z0-9]{1,10}-[0-9]+'
LOG_FILE = 'p4jira.log'

# set it in .env file
JIRA_URL = os.getenv('JIRA_URL')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_PASSWORD = os.getenv('JIRA_PASSWORD')

my_env = os.environ.copy()
my_env['P4USER'] = P4USER
my_env['P4PASSWD'] = P4PASSWD

logging.basicConfig(level=logging.INFO,
                    filename=os.path.join(WORKING_PATH, LOG_FILE),
                    format="[%(levelname)8s] %(module)s: %(message)s")

def get_email_by_username(username):
    """Get user email by p4 username. Used in Jira comments to mark a user.
    We need to authenticate in Perforce and then 
    get some information from Perforce in one console session.
    So, we can call an external shell script for that instead of subprocess tweaks.
    """
    email = ""
    cmd = '''
        echo $P4PASSWD | p4 -u $P4USER login >/dev/null
        p4 -u $P4USER users 2>/dev/null
    '''
    all_users = subprocess.check_output(cmd, env=my_env, shell=True)
    for line in all_users.decode('utf-8').splitlines():
        # find email in line with username
        if [word for word in line.split() if word == username]:
            email = re.findall('<(.*)>', line)[0]
    return email

def get_change_description(change):
    """Get description of a submbitted change by its number"""
    command = 'p4 -Ztag -F %Description% change -o {}'.format(change)
    description = subprocess.check_output(command.split(), env=my_env)
    return description.decode('utf-8').strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('change', help='Change number')
    parser.add_argument('username', help='Change author\'s username')
    args = parser.parse_args()

    change = args.change
    username = args.username

    try:
        email = get_email_by_username(username)

        description = get_change_description(change)
        issue_keys = re.findall(ISSUE_KEY_RE, description)

        jira = JIRA(
            JIRA_URL, basic_auth=(JIRA_USER, JIRA_PASSWORD))

        for issue_key in issue_keys:
            if not email:
                jira_user = username
                logging.warning('Cannot find email of user %s' % username)
            else:
                jira_user = '[~{}]'.format(email)
            comment = '{} mentioned this issue in Perforce. Change: *{}*, description: _{}_'.format(
                jira_user, change, description)
            jira.add_comment(issue_key, comment)
            logging.info('Comment added to issue %s with description: %s' % (issue_key, description))
    except Exception as err:
        logging.error('Cannot process change %s by %s' % (change, username))
        logging.error(err)
        pass


if __name__ == '__main__':
    main()
