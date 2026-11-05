"""Transactional plan state plus a hash-linked append-only application audit."""
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from pulse.intelligence.engine import content_hash


class WorkflowConflict(ValueError):
    pass


class WorkflowUnavailable(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class WorkflowStore:
    def __init__(self, path):
        self.path = path

    def connect(self):
        conn = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
                    version INTEGER NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS plan_events (
                    plan_id TEXT NOT NULL REFERENCES plans(id), version INTEGER NOT NULL,
                    body TEXT NOT NULL, event_hash TEXT NOT NULL,
                    PRIMARY KEY(plan_id, version));
            ''')
            return conn
        except (OSError, sqlite3.Error) as exc:
            if conn is not None:
                conn.close()
            raise WorkflowUnavailable('Workflow storage is unavailable') from exc

    def check(self):
        conn = self.connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise WorkflowUnavailable('Workflow storage integrity check failed')
            conn.rollback()
        finally:
            conn.close()

    def _read(self, conn, plan_id):
        try:
            return self._read_checked(conn, plan_id)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise WorkflowUnavailable('Workflow record integrity check failed') from exc

    def _read_checked(self, conn, plan_id):
        row = conn.execute('SELECT * FROM plans WHERE id=?', (plan_id,)).fetchone()
        if row is None:
            raise LookupError('Plan not found')
        body = json.loads(row['body'])
        events, previous, after = [], None, None
        for index, event in enumerate(conn.execute('SELECT body,event_hash FROM plan_events WHERE plan_id=? ORDER BY version', (plan_id,)), 1):
            value = json.loads(event['body'])
            if value['version'] != index or value['plan_id'] != plan_id or value['previous_hash'] != previous or content_hash(value) != event['event_hash'] or value['before_hash'] != after:
                raise WorkflowUnavailable('Workflow audit integrity check failed')
            events.append({**value, 'event_hash': event['event_hash']})
            previous, after = event['event_hash'], value['after_hash']
        if body['id'] != plan_id or content_hash(body) != row['body_hash'] or row['version'] != body['version'] or len(events) != body['version'] or after != row['body_hash']:
            raise WorkflowUnavailable('Workflow plan integrity check failed')
        return body, events

    def _write(self, conn, body, before, action, actor, details, previous):
        digest = content_hash(body)
        event = {'plan_id': body['id'], 'version': body['version'], 'action': action,
                 'actor': actor, 'recorded_at': body['updated_at'], 'details': details,
                 'before_hash': content_hash(before) if before else None,
                 'after_hash': digest, 'previous_hash': previous}
        conn.execute('UPDATE plans SET version=?,body=?,body_hash=? WHERE id=?',
                     (body['version'], json.dumps(body), digest, body['id']))
        conn.execute('INSERT INTO plan_events(plan_id,version,body,event_hash) VALUES (?,?,?,?)',
                     (body['id'], body['version'], json.dumps(event), content_hash(event)))
        return {**event, 'event_hash': content_hash(event)}

    def create(self, body, request_key, request_hash, actor):
        conn = self.connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('SELECT id,request_hash FROM plans WHERE request_key=?', (request_key,)).fetchone()
            if existing:
                if existing['request_hash'] != request_hash:
                    raise WorkflowConflict('Idempotency key was already used for another request')
                result, _ = self._read(conn, existing['id'])
            else:
                body = {**body, 'id': str(uuid4()), 'version': 1, 'state': 'draft', 'created_at': now(), 'updated_at': now()}
                conn.execute('INSERT INTO plans VALUES (?,?,?,?,?,?)', (body['id'], request_key, request_hash, 1, '{}', ''))
                self._write(conn, body, None, 'created', actor, {'simulation_id': body['simulation_id']}, None)
                result = body
            conn.commit()
            return result
        except sqlite3.Error as exc:
            conn.rollback()
            raise WorkflowUnavailable('Workflow transaction could not be saved') from exc
        finally:
            conn.close()

    def get(self, plan_id):
        conn = self.connect()
        try:
            conn.execute('BEGIN')
            body, events = self._read(conn, plan_id)
            return {**body, 'audit': events}
        except (sqlite3.Error, json.JSONDecodeError, KeyError) as exc:
            raise WorkflowUnavailable('Workflow records could not be read') from exc
        finally:
            conn.close()

    def list(self, investigation_id):
        conn = self.connect()
        try:
            conn.execute('BEGIN')
            ids = [r['id'] for r in conn.execute('SELECT id FROM plans ORDER BY rowid DESC')]
            rows = [self._read(conn, key)[0] for key in ids]
            return [r for r in rows if r['investigation_id'] == investigation_id]
        except (sqlite3.Error, json.JSONDecodeError, KeyError) as exc:
            raise WorkflowUnavailable('Workflow records could not be read') from exc
        finally:
            conn.close()

    def mutate(self, plan_id, expected_version, actor, action, update):
        conn = self.connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            before, events = self._read(conn, plan_id)
            if before['version'] != expected_version:
                raise WorkflowConflict('Plan changed. Reload before continuing.')
            body = json.loads(json.dumps(before))
            details = update(body)
            body.update(version=before['version'] + 1, updated_at=now())
            event = self._write(conn, body, before, action, actor, details, events[-1]['event_hash'])
            conn.commit()
            return {**body, 'audit': events + [event]}
        except sqlite3.Error as exc:
            conn.rollback()
            raise WorkflowUnavailable('Workflow transaction could not be saved') from exc
        finally:
            conn.close()
