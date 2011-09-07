import os

import apsw

MODE_NONE = 0
MODE_DM = 1
MODE_MENTION = 2
MODE_HOME = 4
MODE_LIST = 8
MODE_EVENT = 16

TYPE_STATUS = 0
TYPE_DM = 1

DB_PATH = os.path.dirname(__file__) + os.sep + 'twiotaku.db'

_conn_db = None
_cache = dict()

def init():
  global _conn_db
  if not _conn_db:
    _conn_db = apsw.Connection(DB_PATH)
    cursor = _conn_db.cursor()
    sql = dict(
      id_lists="""CREATE TABLE "id_lists" (
                "uid"  INTEGER NOT NULL,
                "short_id"  INTEGER NOT NULL,
                "long_id"  TEXT NOT NULL,
                "type"  INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX "id_lists_uid_longid_type"
                ON "id_lists" ("uid", "long_id", "type");
                CREATE INDEX "is_lists_uid_shortid_type"
                ON "id_lists" ("uid", "short_id");
                """,
      users="""CREATE TABLE "users" (
            "id"  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "jid"  TEXT NOT NULL,
            "screen_name"  TEXT,
            "access_key"  TEXT,
            "access_secret"  TEXT,
            "list_user"  TEXT,
            "list_id"  TEXT,
            "list_name"  TEXT,
            "last_home_id"  TEXT,
            "last_mention_id"  TEXT,
            "last_dm_id"  TEXT,
            "last_list_id"  TEXT,
            "last_update"  INTEGER NOT NULL DEFAULT 0,
            "timeline"  INTEGER NOT NULL DEFAULT 3,
            "id_list_ptr"  INTEGER NOT NULL DEFAULT 0,
            "blocked_ids"  TEXT,
            "list_ids"  TEXT
            );
            CREATE UNIQUE INDEX "users_id"
            ON "users" ("id");
            CREATE UNIQUE INDEX "users_jid"
            ON "users" ("jid");
            """,
      statuses="""CREATE TABLE "statuses" (
              "id"  TEXT NOT NULL,
              "json"  BLOB NOT NULL,
              "type"  INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY ("id") ON CONFLICT REPLACE
              );
              CREATE UNIQUE INDEX "status_id"
              ON "statuses" ("id", "type");
              """,
      invites="""CREATE TABLE "invites" (
            "id"  TEXT NOT NULL,
            "create_time"   INTEGER NOT NULL,
            PRIMARY KEY ("id") ON CONFLICT FAIL
            );
            CREATE UNIQUE INDEX "invite_id"
            ON "invites" ("id");
            """,
      )
    for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';"):
      t = t[0]
      if t in sql:
        del(sql[t])
    begin_transaction()
    for v in sql.itervalues():
      cursor.execute(v)
    end_transaction()
  return _conn_db


def get_user_from_jid(jid):
  cursor = _conn_db.cursor()
  user = dict()
  for u in cursor.execute('SELECT * FROM users WHERE jid=?', (jid, )):
    d = cursor.getdescription()
    for i in range(len(d)):
      user[d[i][0]] = u[i]
  return user


def update_user(id=None, jid=None, **kwargs):
  if id is None and jid is None:
    raise TypeError('The method takes at least one argument.')
  if kwargs:
    cursor = _conn_db.cursor()
    cols = list()
    values = list()
    for k, v in kwargs.iteritems():
      cols.append('%s=?' % k)
      values.append(v)
    if id:
      cond = 'id=?'
      values.append(id)
    else:
      cond = 'jid=?'
      values.append(jid)
    sql = 'UPDATE users SET %s WHERE %s' % (','.join(cols), cond)
    cursor.execute(sql, values)


def add_user(jid):
  cursor = _conn_db.cursor()
  sql = 'INSERT INTO users (jid) VALUES(?)'
  cursor.execute(sql, (jid,))


def get_all_users():
  cursor = _conn_db.cursor()
  sql = 'SELECT * FROM users'
  d = None
  for u in cursor.execute(sql):
    if d is None:
      d = cursor.getdescription()
    user = dict()
    for i in range(len(d)):
      user[d[i][0]] = u[i]
    yield user


def get_invite_code(invide_code):
  cursor = _conn_db.cursor()
  for u in cursor.execute('SELECT id, create_time FROM invites WHERE id=?', (invide_code, )):
    return u
  return None, None


def add_invite_code(invite_code, create_time):
  cursor = _conn_db.cursor()
  sql = 'INSERT INTO invites (id, create_time) VALUES(?,?)'
  cursor.execute(sql, (invite_code, create_time))


def delete_invite_code(invite_code):
  cursor = _conn_db.cursor()
  sql = 'DELETE FROM invites WHERE id=?'
  cursor.execute(sql, (invite_code,))


def begin_transaction():
  cursor = _conn_db.cursor()
  cursor.execute('BEGIN TRANSACTION')


def end_transaction():
  cursor = _conn_db.cursor()
  cursor.execute('END TRANSACTION')


def commit_transaction():
  cursor = _conn_db.cursor()
  cursor.execute('COMMIT')


def get_short_id_from_long_id(uid, long_id, single_type):
  cursor = _conn_db.cursor()
  sql = 'SELECT short_id FROM id_lists WHERE uid=? AND long_id=? AND type=?'
  for x in cursor.execute(sql, (uid, long_id, single_type)):
    return x[0]


def get_long_id_from_short_id(uid, short_id):
  cursor = _conn_db.cursor()
  sql = 'SELECT long_id, type FROM id_lists WHERE uid=? AND short_id=?'
  for x in cursor.execute(sql, (uid, short_id)):
    return x[0], x[1]
  return None, None


def update_long_id_from_short_id(uid, short_id, long_id, single_type):
  cursor = _conn_db.cursor()
  sql = 'DELETE FROM id_lists WHERE uid=? AND short_id=?'
  cursor.execute(sql, (uid, short_id))
  sql = 'INSERT INTO id_lists (uid, short_id, long_id, type) VALUES(?, ?, ?, ?)'
  cursor.execute(sql, (uid, short_id, long_id, single_type))