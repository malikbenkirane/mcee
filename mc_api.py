# Complete rewrite of `task.py`
from tinydb import TinyDB, Query
from tinydb_serialization import Serializer, SerializationMiddleware
from datetime import datetime


class DateTimeSerializer(Serializer):

    OBJ_CLASS = datetime

    def encode(self, obj):
        return obj.strftime('%Y-%m-%dT%H%M%S')

    def decode(self, s):
        return datetime.strptime(s, '%Y-%m-%dT%H%M%S')


serialization = SerializationMiddleware()
serialization.register_serializer(DateTimeSerializer(), 'TinyDate')
db = TinyDB('db.json', storage=serialization)  # this for test cases setup


# LOW LEVEL API

class TaskAPI():

    """Low level API to manage tasks"""

    def __init__(self, status, tasks, resetdb=None):
        self.status = status
        self.tasks = tasks
        if resetdb is not None:
            self.reset(resetdb)
        self.status_document = self.status.all()[0]

    def _status_update(self, document):
        self.status.update(document)
        self.status_document = self.status.all()[0]

    def add(self, description, project=None, score=1, tags=[]):
        """Adds a task."""
        taskid = self.nextid()
        self.tasks.insert({
            'description': description,
            'project': project,
            'id': taskid,
            'score': score,
            'status': 'new',
            'tags': tags,
            'history': [
                {'status': 'new', 'datetime': datetime.now()}
            ]
        })
        self._status_update({'nextid': taskid+1})
        return taskid

    def done(self):
        picked_task_document = self.get(self.pickedid())
        self._status_update({'picked': None})
        task_history = picked_task_document['history']
        task_history.append({'status': 'done', 'datetime': datetime.now()})
        self.tasks.update(
            {'status': 'done', 'history': task_history},
            doc_ids=[picked_task_document.doc_id]
        )

    def drop(self):
        picked_task_document = self.get(self.pickedid())
        self._status_update({'picked': None})
        task_history = picked_task_document['history']
        task_history.append({'status': 'dropped', 'datetime': datetime.now()})
        doc_id = picked_task_document.doc_id
        self.tasks.update(
            {'status': 'fresh', 'history': task_history},
            doc_ids=[doc_id]
        )

    def dropped(self):
        Task = Query()
        results = self.tasks.search(Task.status == 'fresh')
        return results

    def get(self, taskid):
        """Gets a task document by its id"""
        Task = Query()
        response = self.tasks.search(Task.id == taskid)
        if len(response) == 1:
            return response[0]
        raise ValueError

    def get_status(self):
        return self.status.all()[0]

    def next(self):
        """Returns 'new' and 'fresh' tasks."""
        Task = Query()

        def filter_fresh(x):
            return x in ('new', 'fresh')

        nexts = self.tasks.search(Task.status.test(filter_fresh))
        return nexts

    def nextid(self):
        """Returns the id for the next task.  See `help(add)` to add a task."""
        return self.status_document['nextid']

    def pick(self, taskid):
        """Sets the task by id picked.  And it drops any previously picked
        task."""
        task_document = self.get(taskid)
        doc_id = task_document.doc_id
        old_pick = self.status_document['picked']
        if old_pick is not None:
            self.drop()
        self._status_update({'picked': task_document['id']})
        task_history = task_document['history']
        task_history.append({'status': 'picked', 'datetime': datetime.now()})
        self.tasks.update(
            {'status': 'picked', 'history': task_history},
            doc_ids=[doc_id]
        )
        print('You switched from {}'.format(old_pick))
        task_description = task_document['description']
        print('To {} - "{}"'.format(taskid, task_description))
        return task_document

    def pickedid(self):
        """Return picked task id"""
        return self.status_document['picked']

    def project(self, projectname=None):

        if projectname is None:
            return self.status_document['project']

        # else:
        try:
            task_document = self.get(self.pickedid())
            task_history = task_document['history']
            task_history.append({
                'status': 'setproject', 'datetime': datetime.now(),
                'project': projectname
            })
            self.tasks.update(
                {'history': task_history, 'project': projectname},
                doc_ids=[task_document.doc_id]
            )
        finally:
            self._status_update({'project': projectname})

    def reset(self, db):
        """Hard resets the base.  CAUTION.  All data will be gone.
        :param db: confirms to choose the databes to resest"""
        status_tablename = self.status.name
        tasks_tablename = self.tasks.name
        db.purge_table(status_tablename)
        db.purge_table(tasks_tablename)
        self.status.insert({
            'picked': None,
            'nextid': 1,
            'project': None
        })

    def score(self, newscore):
        task_document = self.get(self.pickedid())
        task_history = task_document['history']
        task_history.append({'status': 'scored', 'datetime': datetime.now()})
        self.tasks.update(
            {'score': newscore, 'history': task_history},
            doc_ids=[task_document.doc_id]
        )

    def rewards(self):
        Task = Query()
        won = self.tasks.search(Task.status == 'done')
        total_reward = 0
        for task in won:
            total_reward += task['score']
        return total_reward
