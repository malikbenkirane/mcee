# Complete rewrite of `task.py`
from tinydb import TinyDB, Query
from tinydb_serialization import Serializer, SerializationMiddleware
from datetime import datetime, timedelta


class DateTimeSerializer(Serializer):

    OBJ_CLASS = datetime

    def encode(self, obj):
        return obj.strftime('%Y-%m-%dT%H%M%S')

    def decode(self, s):
        return datetime.strptime(s, '%Y-%m-%dT%H%M%S')


serialization = SerializationMiddleware()
serialization.register_serializer(DateTimeSerializer(), 'TinyDate')
db = TinyDB('/home/void/recess/devel/mcee/db.json', storage=serialization)  # this for test cases setup

# LOW LEVEL API
def record_action(action):

    def wrapper(*args, **kwargs):

        values = action(*args, **kwargs)

        # add history entry

        api = args[0]
        status_document = api.get_status()
        status_history = []
        if 'api_history' in status_document:
            status_history = status_document['api_history']
        history_document = {
                'api_call': action.__name__, 'datetime': datetime.now()
        }
        # FIXME what to add to the history ?
#       if len(args) > 1:
#           history_document['args'] = args[1:]
#       if len(kwargs) > 0:
#           history_document['kwargs'] = kwargs
        status_history.append(history_document)

        # record history entry

        api._status_update({'api_history': status_history})

        return values

    return wrapper


def time_analytics(task_history):
    """Returns a triplet. First uplet is True if this is the first session and
    False if not. Second and third are the total pick time and last pick
    timing.

    About task cycles:

    # (new) -> (picked) <-> (dropped) <-> (picked) (<)*-> (done)
    # *: the api doesn't check the status to pick the task
    #    (this way a task could be done and rewarded twice)
    """
    totaltime_picked = timedelta(0)
    lastpick_time = timedelta(0)
    cycle_count = 0  # to count if task cycles are respected
    # FIXME I assume the datetimes appears in chronological order
    for event in task_history:
        if event['status'] == 'picked':
            cycle_count += 1
            start = event['datetime']
            # print('debug: picked')
        if event['status'] in ('dropped', 'done'):
            cycle_count -= 1
            lastpick_time = event['datetime'] - start
            totaltime_picked += lastpick_time
            # print('debug: dropped')
        event['datetime']
    # print('debug: cycle_count %d' % cycle_count)
    if cycle_count == 1:
        lastpick_time = datetime.now() - start
        totaltime_picked += lastpick_time
    return \
        (totaltime_picked.total_seconds() == lastpick_time.total_seconds()), \
        totaltime_picked, lastpick_time


class TaskAPI():

    """Low level API to manage tasks"""

    def __init__(self, status, tasks, resetdb=None):
        self.status = status
        self.tasks = tasks
        if resetdb is not None:
            self.reset(resetdb)
        self.status_document = self.status.all()[0]

    def _status_update(self, document):
        """Updates status document with `document`"""
        self.status.update(document)
        self.status_document = self.status.all()[0]

    # Actions
    # -------

    # @record_action
    def add(self, description, project=None, score=1, tags=[]):
        """Adds a task."""
        taskid = self.nextid()
        if project is None:
            status_document = self.get_status()
            project = status_document['project']
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

    # @record_action
    def archive(self):
        """Forgets about picked task and drops it"""
        task_document = self.get(self.pickedid())
        task_history = task_document['history']
        task_history.append({'status': 'archived', 'datetime': datetime.now()})
        self.drop()
        self.tasks.update(
                {'status': 'archive', 'history': task_history},
                doc_ids=[task_document.doc_id]
        )

    # @record_action
    def archives(self):
        """Returns all archived tasks."""
        Task = Query()
        return self.tasks.search(Task.status == 'archive')

    # @record_action
    def done(self):
        """Marks picked task as done"""
        picked_task_document = self.get(self.pickedid())
        self._status_update({'picked': None})
        task_history = picked_task_document['history']
        task_history.append({'status': 'done', 'datetime': datetime.now()})
        self.tasks.update(
            {'status': 'done', 'history': task_history},
            doc_ids=[picked_task_document.doc_id]
        )
        return time_analytics(task_history)

    # @record_action
    def drop(self):
        """Drops picked task and returns total time the task have been
        picked time and the time the last session has last."""
        picked_task_document = self.get(self.pickedid())
        self._status_update({'picked': None})
        task_history = picked_task_document['history']
        task_history.append({'status': 'dropped', 'datetime': datetime.now()})
        doc_id = picked_task_document.doc_id
        self.tasks.update(
            {'status': 'fresh', 'history': task_history},
            doc_ids=[doc_id]
        )
        return time_analytics(task_history)

    # @record_action
    def dropped(self):
        """Returns all tasks marked fresh"""
        Task = Query()
        results = self.tasks.search(Task.status == 'fresh')
        return results

    # @record_action
    def freshstart(self):
        """Marks all done tasks with a no score flag."""
        Task = Query()
        done = self.tasks.search(Task.status == 'done')
        now = datetime.now()
        for task in done:
            if 'noscore' in task:
                freshstack = task['noscore']
                freshstack.append(now)
            else:
                freshstack = [now]
            self.tasks.update({'noscore': freshstack}, doc_ids=[task.doc_id])

    # @record_action
    def get(self, taskid):
        """Gets a task document by its id"""
        Task = Query()
        response = self.tasks.search(Task.id == taskid)
        if len(response) == 1:
            return response[0]
        raise ValueError

    # Do not decorate me with record_action
    # The reason is this funciton is used
    def get_status(self):
        """Returns the status document"""
        return self.status.all()[0]

    # @record_action
    def next(self):
        """Returns 'new' and 'fresh' tasks."""
        Task = Query()

        def filter_fresh(x):
            return x in ('new', 'fresh')

        nexts = self.tasks.search(Task.status.test(filter_fresh))
        return nexts

    # @record_action
    def previously(self):
        """Returns all but 'new' and 'fresh' (and 'picked') tasks.
        Exact opposite of `self.next()`"""
        Task = Query()

        def filter_previous(x):
            """Filters tasks neihter new nor fresh."""
            return x not in ('new', 'fresh', 'picked')

        previous = self.tasks.search(Task.status.test(filter_previous))
        return previous

    # @record_action
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
        print('You switched')
        task_description = task_document['description']
        print('To {} - "{}"'.format(taskid, task_description))
        return task_document

    # @record_action
    def project(self, projectname=None):
        """Sets project in status anyway and to the picked task
        if there is one."""

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
            return self.status_document['project']

    # @record_action
    def pickedid(self):
        """Return picked task id"""
        return self.status_document['picked']

    @record_action
    def score(self, newscore):
        """Set rewards for the picked task."""
        task_document = self.get(self.pickedid())
        task_history = task_document['history']
        task_history.append({'status': 'scored', 'datetime': datetime.now()})
        self.tasks.update(
            {'score': newscore, 'history': task_history},
            doc_ids=[task_document.doc_id]
        )

    @record_action
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

    # Useful
    # ------

    def rewards(self):
        """Returns total score"""
        Task = Query()
        won = self.tasks.search(Task.status == 'done')
        total_reward = 0
        for task in won:
            if ('noscore' in task and len(task['noscore']) == 0) or \
                    'noscore' not in task:
                total_reward += int(task['score'])
        return total_reward

    def nextid(self):
        """Returns the id for the next task.  See `help(add)` to add a task."""
        return self.status_document['nextid']
