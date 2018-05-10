from pprint import pprint
from mc_api import TaskAPI, db
from random import randint


# TODO task_commands decorator
# def task_commands(f, )

def dummy_message_test(commands):
    print()
    print('\n'.join(commands))
    print()
    print("(you would see if there is an error)")
    print()
    print(">> results ")
    print()


def deftest_reset(t, db):
    print('mc reset hard db.json')
    t.reset(db)


def deftest_add(t):
    task_commands = (
        'mc add test task description pro:test score:3',
        'mc add test taks with tags #first #last #notlast score:3 pro:test',
        'mc add description alone'
    )
    dummy_message_test(task_commands)
    t.add(
        'test task decription',
        project='test', score=3,
        tags=[]
    )
    t.add(
        'test task with tags',
        project='test', score=3,
        tags=['first', 'last', 'notleast']
    )
    t.add('description alone')
    assert t.nextid() == 4
    pprint(t.tasks.all())


def deftest_get(t, tid):
    task_commands = (
        'mc get {}'.format(tid),
    )
    dummy_message_test(task_commands)
    print(t.get(tid))


def deftest_picked(t):
    task_commands = (
        'mc picked [id]'
    )
    dummy_message_test(task_commands)
    print(t.picked())


def api_test(resetdb=None):
    """Makes an API instance for testing.  If None is passed the test tables
    will not be reset."""

    # test tables
    test_status = db.table('test_status')
    test_tasks = db.table('test_tasks')

    # api instance
    api = TaskAPI(test_status, test_tasks, resetdb)

    return api


def test_suite_100():
    api_test(db)


def test_suite_101():
    api = api_test(db)
    deftest_add(api)


def test_suite_102():
    # get test
    api = api_test()
    for i in range(1, 4):  # tasks from 1 to 3
        pprint(deftest_get(api, i))
    # results = [deftest_get(api, i) for i in range(1, 4)]  # tasks 1 to 3
    # pprint(results)


def deftest_pick(t, tid):
    task_commands = (
        'mc pick {}'.format(tid),
    )
    dummy_message_test(task_commands)
    task_to_pick = tid
    picked_task = t.pick(task_to_pick)
    assert(t.pickedid() == picked_task['id'])
    pprint(t.get_status())


def test_suite_103():
    # pick test
    api = api_test()
    task_to_pick = randint(1, 4)  # random task from id 1 to 3
    deftest_pick(api, task_to_pick)


def deftest_done(t):
    task_commands = (
        'mc done',
    )
    dummy_message_test(task_commands)
    taskid = t.pickedid()
    t.done()
    pprint(t.get(taskid))


def test_suite_104():
    # done test
    api = api_test()
    deftest_done(api)


def deftest_drop(t):
    task_commands = (
        'mc drop',
    )
    dummy_message_test(task_commands)
    taskid = t.pickedid()
    t.drop()
    pprint(t.get(taskid))


def test_suite_105():
    # drop test: pick task 1 and drop it
    api = api_test(db)
    deftest_add(api)
    api.pick(1)
    deftest_drop(api)


def deftest_dropped(t):
    task_commands = (
        'mc [list] dropped',
    )
    dummy_message_test(task_commands)
    pprint(t.dropped())


def test_suite_106():
    # list all dropped (ran after suite 105)
    api = api_test()
    deftest_dropped(api)


def deftest_score(t, tid, newscore):
    task_commands = (
        'mc pick {}'.format(tid),
        'mc score {}'.format(newscore)
    )
    dummy_message_test(task_commands)
    t.pick(tid)
    t.score(newscore)
    pprint(t.get(tid))


def test_suite_107():
    api = api_test()
    deftest_score(api, 1, 2)


def deftest_project(t, tid, projectname):
    task_commands = (
        'mc set project {}'.format(projectname),
    )
    dummy_message_test(task_commands)
    t.pick(tid)
    t.project(projectname)
    pprint(t.get(tid))
    pprint(t.status_document)


def test_suite_108():
    api = api_test()
    deftest_project(api, 2, 'awesome')
