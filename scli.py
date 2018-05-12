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
    print()
    message_first = 'Adding task: "{}"'.format(description)
    print('-' * len(message_first))
    print(message_first)
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
        values = (table[field][row] for field in fields_to_display)
        if table['id'][row] == str(picked_taskid):
            # print picked task
            print()
            print(('{:>%d}' % maxlens[0]).format('#picked'))
            print(fmt_str.format(*tuple(values)))
            print()
        else:
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
    # TODO describe the picked task a little more than default message


def drop_command():
    api.drop()


def done_command():
    task_document = api.get(api.pickedid())
    print('-\n{} @:{}\n- done.'.format(
        task_document['description'], task_document['project'])
    )
    print('You\'re done with task {}'.format(api.pickedid()))
    api.done()


# parses the command line
class Commands():

    def help(self):
        print('commands:')
        print()
        maxcmdlen = max(len(cmd) for cmd in self.commands)
        prefmt = '    {cmd:%d}  {helpmsg}{aliases}' % maxcmdlen
        for command in self.commands:
            cmdinfo = self.commands[command]
            shortcuts_str = ''
            if 'shortcuts' in cmdinfo:
                shortcuts_str = ', '.join(cmdinfo['shortcuts'])
            if len(shortcuts_str) > 0:
                shortcuts_str = '\n   (aliases: {})'.format(shortcuts_str)
            print(prefmt.format(
                cmd=command,
                aliases=shortcuts_str,
                helpmsg=cmdinfo['help']
            ))
        print()

    def show_examples(self):
        print('examples:')
        print()
        print('\n'.join(self.examples))
        print()
        print("If you are using commands in a shell", end=' ')
        print("you may need to escape some characters.")

    def __init__(self):
        self.commands = {
            'help':  {
                'action': self.help,
                'help': 'Print this message'
            },
            'showme': {
                'action': self.show_examples,
                'help': 'Show some examples'
            }
        }
        self.examples = []

    def register(self, name, action,
                 shortcuts=[], helpmsg='', examples=[], groups=False):
        command = {}
        if len(shortcuts) > 0:
            command['shortcuts'] = tuple(s for s in shortcuts)
        self.examples += examples
        command['action'] = action
        command['help'] = helpmsg
        command['groups'] = groups
        self.commands[name] = command

    def parse(self, query):
        matched = False
        for cmd in self.commands:
            cmdinfo = self.commands[cmd]
            if query == cmd:
                matched = True
                break
            elif 'shortcuts' in cmdinfo:
                if query in cmdinfo['shortcuts']:
                    matched = True
                    break
        if matched:
            cmdinfo['action']()
        else:
            print('unknown command, try again or try help command')


cli = Commands()
cli.register('next', next_command, shortcuts=[''],
             helpmsg='Print your tasks and stats', groups=False)
cli.register('done', done_command, shortcuts=['finish', '-', 'ok'],
             helpmsg='This is for when you\'re done with the picked task')
cli.register('reset', reset_command, shortcuts=[],
             helpmsg='You want to delete everything permanantly')
cli.register('pick', pick_command, shortcuts=['now', ':'],
             helpmsg='Pick the task giving an id')
cli.register('drop', drop_command,
             helpmsg='Drop the picked task if there is one')

add_examples = '''\
> add my task @:projectname description #tag could be anywhere
> add another task #moretag #tagged :4pts\
'''
add_examples.split('\n')

cli.register('add', add_command, shortcuts=['new'],
             help='Add new task parsing all arguments (see examples)',
             examples=[add_examples])

cli.parse(command)
#    print('''commands:
#     TEST - help: prints this message
#     TEST - next: prints your tasks and stats (default command)
#          - reset: do not use or you're sure you want to delete everything
#                   permanantly
#          - add: new: adds a new task, it parses all arguments the following
#            > add @:projectname \\#tag :4pts description anywhere \\
#              \\#lastcount @:thisproject
#            | adds task 'description anywhere' 4pts,
#            | project 'this project',
#            | tags: #tag, #lastcount
#            (but careful with escape characters into your shell)
#          - pick <id>: picks that task
#          - drop: drops picked task
#          - ok: done: picked task is finished''')
