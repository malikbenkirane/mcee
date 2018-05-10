import sys
from mc_api import TaskAPI, db
from datetime import datetime, timedelta


def pretty_time_delta(seconds):

    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if days > 0:
        return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
    elif hours > 0:
        return '%dh%dm%ds' % (hours, minutes, seconds)
    elif minutes > 0:
        return '%dm%ds' % (minutes, seconds)
    else:
        return '%ds' % seconds


try:
    args = sys.argv[:]
    command = args[1]
except IndexError:
    command = ''

status = db.table('status')
tasks = db.table('tasks')
api = TaskAPI(status, tasks)

if 'project' not in api.status_document:
    api.reset(db)
default_project = api.status_document['project']


# defines the commands
def add_command():

    tags = []
    project = default_project
    score = 2
    description = []

    for arg in args[2:]:
        if arg[0] == '#':
            tags.append(arg[1:])
        elif arg[:4] == 'pro:':
            project = arg[4:]
        elif arg[:8] == 'project:':
            project = arg[8:]
        elif arg[:2] == '@:':
            project = arg[2:]
        # TODO '@@' to determine projects with the first letters
        elif arg[:1] == ':' and arg[-2:] == 'pt':
            score = arg[1:-2]
        else:
            description.append(arg)

    description = ' '.join(description)
    print('Adding task: "{}"'.format(description))
    print('Project: "{}"'.format(project))
    print('tags: {}'.format(tags))
    print('score: {}'.format(score))

    if len(description) > 0:
        taskid = api.add(
            description, project=project,
            tags=tags, score=int(score)
        )

    print()
    print('Your task have been added')
    print('New task id:  {}'.format(taskid))


def reset_command():

    print("Reseting database")
    api.resest(db)
    print("done")


def next_command():

    # Table fields: Description, id, added x time ago, picked
    # If a task is picked then also prints picjed task

    next_tasks = api.next()
    now = datetime.now()

    fields = [
        'tags',  'id', 'description', 'project',
        'time', 'score', 'totalpicks'
    ]
    table, maxlens = {
        field: [] for field in fields
    }, {
        field: 0 for field in fields
    }

    # adds picked task details

    picked_taskid = api.pickedid()
    if picked_taskid:
        next_tasks.append(api.get(picked_taskid))
        fields.append('now')
        table['now'] = []
        maxlens['now'] = 0

    # prepare data
    for task in next_tasks:

        row = {}

        # get description, id, tags, project, scores

        row['description'] = task['description']
        row['id'] = str(task['id'])
        row['tags'] = ' '.join(['#{}'.format(tag) for tag in task['tags']])
        project = str(task['project'])
        if project == 'None':
            project = ''
        row['project'] = project
        row['score'] = str(task['score'])

        row['time'] = 'ERR'
        # get datetime at creation (and compute X time ago)

        for state in task['history']:
            if state['status'] == 'new':
                row['time'] = pretty_time_delta(
                    (now - state['datetime']).total_seconds()
                )

        # this could be grouped above to loop once but it can still
        # for legibilty
        # FIXME should sort task['history'] list sorted by datetimes.
        # I assumed this is the case and that make sense with the front-end

        totalpick = timedelta(0)
        _picked = False

        for state in task['history']:
            if state['status'] == 'picked':
                _picked = True
                _picked_datetime = state['datetime']
            if _picked and state['status'] == 'dropped':
                _picked = False
                totalpick += state['datetime'] - _picked_datetime

        if _picked:
            totalpick += now - _picked_datetime
            if task['id'] == picked_taskid:
                row['now'] = pretty_time_delta(
                    (now - _picked_datetime).total_seconds()
                )

        if task['id'] != picked_taskid:
            row['now'] = ''

        row['totalpicks'] = pretty_time_delta(totalpick.total_seconds())

        # update column max width

        for field in fields:
            width = len(row[field])
            if width > maxlens[field]:
                maxlens[field] = width

        # filling the table with the values

        for field in fields:
            table[field].append(row[field])

    # setup the fields

    titles = [
        'tags', 'id', 'Description', 'project',
        'AGE', 'pts', 'TOT'
    ]

    if picked_taskid:
        titles.append('now..')

    display_zip = tuple(
        (field, title, maxlens[field])
        for field, title in zip(fields, titles)
        if maxlens[field] > 0
    )

    fields_to_display, titles, maxlens = tuple(zip(*display_zip))

    # fixs columns widths

    maxlens = tuple(
        max(maxlen, len(title))
        for maxlen, title in zip(maxlens, titles)
    )

    fmt_str = '  '.join(['{:>%d}'] * len(fields_to_display)) % maxlens

    # print emptyline
    print()

    # print titles
    print(fmt_str.format(*titles))

    def print_line():
        print(fmt_str.format(*['-' * maxlen for maxlen in maxlens]))

    # print header line
    print_line()

    # print table
    for row in range(len(next_tasks)):
        if table['id'][row] == str(picked_taskid):
            print()
            print(('{:>%d}' % maxlens[0]).format('..now'))
            print_line()
        values = (table[field][row] for field in fields_to_display)
        print(fmt_str.format(*tuple(values)))

    print()
    print('Your score: {}'.format(api.rewards()))
    print()

# TODO rewrite using functions
# elif command == 'pick':
#
#     if len(args[2:]) == 1:
#         pickid = args[2]
#         api.pick(pickid)
#
#
# elif command == 'drop':
#
#     api.drop()
#
#
# elif command == 'done':
#
#     api.done()
#
#
# elif command == 'score':
#
#     if len(args[2:]) == 1:
#         score = args[2]
#         api.score(score)


def pick_command():
    try:
        taskid = int(args[2])
        api.pick(taskid)
    except IndexError:
        print('.. 1 argument: task id please !')
    except ValueError:
        print('.. no such task id, try again')


def drop_command():
    api.drop()


def done_command():
    task_document = api.get(api.pickedid())
    print('-{} @:{}'.format(
        task_document['description'], task_document['project'])
    )
    print('You\'re done with task {}'.format(api.pickedid()))
    api.done()

# parses the command line
commands = {
    'next': {
        'shortcuts': ('', ),
        'action': next_command,
        'help': 'prints your tasks and stats (default command)'
    },
    'reset': {
        'action': reset_command,
        'help': '''do not use or you're sure you're sure
you want to delete everything permanantly'''
    }

}

if command in ('next', ''):
    next_command()

elif command in ('reset',):
    reset_command()

elif command in ('add', 'new'):
    add_command()

elif command in ('pick'):
    pick_command()

elif command in ('drop'):
    drop_command()

elif command in ('ok', 'done'):
    done_command()

elif command in ('help', '-h', '--help'):
    print('''commands:
          - help: prints this message
          - next: prints your tasks and stats (default command)
          - reset: do not use or you're sure you want to delete everything
                   permanantly
          - add: new: adds a new task, it parses all arguments the following
            > add @:projectname \\#tag :4pts description anywhere \\
              \\#lastcount @:thisproject
            | adds task 'description anywhere' 4pts,
            | project 'this project',
            | tags: #tag, #lastcount
            (but careful with escape characters into your shell)
          - pick <id>: picks that task
          - drop: drops picked task
          - ok: done: picked task is finished''')

else:
    print('unknown command, please try again or ask help command')
