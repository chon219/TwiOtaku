import traceback
import logging
import time
from StringIO import StringIO
from threading import Thread
from Queue import Queue, Empty

import db
import twitter
from worker import Job
from config import OAUTH_CONSUMER_KEY, OAUTH_CONSUMER_SECRET

def cron_start(queues):
  cron_queue = Queue()
  for _ in range(5):
    t = Thread(target=cron_job, args=(cron_queue, ))
    t.setDaemon(True)
    t.start()
  for user in db.get_all_users():
    if user['access_key'] and user['access_secret']:
      tl = user['timeline'] & ~db.MODE_EVENT
      c = 0
      while tl:
        if tl & 1:
          c += 1
        tl >>= 1
      interval = c * 15 # 3600 / ( 240 / c ) I choose 240 per hour because 240 can be exactly divided by 1,2,3,4
      if interval and user['last_update'] < int(time.time() + 1 - interval): # add 1 second for avoiding clock deviation
        user['last_update'] = int(time.time())
        db.update_user(id=user['id'], last_update=user['last_update'])
        cron_queue.put((queues.get(user['jid'], Queue()), user)) # we can abandon data if we don't need, just throw a useless Queue
  cron_queue.join()


def cron_job(cron_queue):
  while True:
    try:
      queue, user = cron_queue.get(True, 3)
    except Empty:
      return
    jid = user['jid']

    api = twitter.Api(consumer_key=OAUTH_CONSUMER_KEY,
                      consumer_secret=OAUTH_CONSUMER_SECRET,
                      access_token_key=user['access_key'],
                      access_token_secret=user['access_secret'])
    try:
      screen_name = api.verify_credentials()['screen_name']
    except twitter.TwitterAuthenticationError:
      db.update_user(jid=jid, access_key=None, access_secret=None)
      return
    if screen_name != user['screen_name']:
      user['screen_name'] = screen_name
      db.update_user(jid=jid, screen_name=screen_name)

    logger = logging.getLogger('cron')

    try:
      if user['timeline'] & db.MODE_DM:
        data = api.get_direct_messages(since_id=user['last_dm_id'])
        if data and isinstance(data, list) and isinstance(data[0], twitter.DirectMessage):
          user['last_dm_id'] = data[0]['id_str']
          db.update_user(jid=jid, last_dm_id=user['last_dm_id'])
          queue.put(Job(jid, data=data, allow_duplicate=False, always=False))
    except BaseException:
      err = StringIO()
      traceback.print_exc(file=err)
      logger.error(err.getvalue())

    try:
      if user['timeline'] & db.MODE_MENTION:
        data = api.get_mentions(since_id=user['last_mention_id'])
        if data and isinstance(data, list) and isinstance(data[0], twitter.Status):
          user['last_mention_id'] = data[0]['id_str']
          db.update_user(jid=jid, last_mention_id=user['last_mention_id'])
          queue.put(Job(jid, data=data, allow_duplicate=False, always=False))
    except BaseException:
      err = StringIO()
      traceback.print_exc(file=err)
      logger.error(err.getvalue())

    try:
      if user['timeline'] & db.MODE_LIST:
        if user['list_user'] and user['list_id']:
          try:
            data = api.get_list_statuses(user=user['list_user'], id=user['list_id'], since_id=user['last_list_id'])
          except twitter.TwitterNotFoundError:
            user['timeline'] &= ~db.MODE_LIST
            db.update_user(id=user['id'], timeline=user['timeline'])
            queue.put(Job(user['jid'], title='List %s/%s not exists, disable List update.' % (user['list_user'], user['list_name'])))
          else:
            if data and isinstance(data, list) and isinstance(data[0], twitter.Status):
              user['last_list_id'] = data[0]['id_str']
              db.update_user(jid=jid, last_list_id=user['last_list_id'])
              queue.put(Job(jid, data=data, allow_duplicate=False, always=False))
    except BaseException:
      err = StringIO()
      traceback.print_exc(file=err)
      logger.error(err.getvalue())

    try:
      if user['timeline'] & db.MODE_HOME:
        data = api.get_home_timeline(since_id=user['last_home_id'])
        if data and isinstance(data, list) and isinstance(data[0], twitter.Status):
          user['last_home_id'] = data[0]['id_str']
          db.update_user(jid=jid, last_home_id=user['last_home_id'])
          queue.put(Job(jid, data=data, allow_duplicate=False, always=False))
    except BaseException:
      err = StringIO()
      traceback.print_exc(file=err)
      logger.error(err.getvalue())

    cron_queue.task_done()
