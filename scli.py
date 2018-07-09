import sys
from mc_api import TaskAPI, db, time_analytics
from datetime import datetime, timedelta
import copy


def format_time_analytics(first, totaltime_picked, lastpick_time):
    ft_current = 'Current Session has last {}'\
        .format(pretty_time_delta(lastpick_time.total_seconds()))
    if not first:
        return 'Total picking time {} long.\n'\
            .format(pretty_time_delta(totaltime_picked.total_seconds()))\
            + ft_current
    else:
        return ft_current


def pretty_time_delta(seconds):

    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if days > 0:
        # for a prettier display
        # but there may be a need of more precise display
        # e.g. ~1d +1/2 or ~2d
        if hours > 12:
            return '%dd~' % (days + 1)
        else:
            return '%dd~' % days
        # return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
    elif hours > 0:
        # return '%dh%dm%ds' % (hours, minutes, seconds)
        return '%dh%dm' % (hours, minutes)
    elif minutes > 0:
        # rounds up arbitrarely
        if seconds > 45:
            return '%dm' % (minutes + 1)
        else:
            return '%dm' % minutes
    # else:
    #     return '%ds' % seconds
    elif seconds == 0:
        return '0'
    else:
        return '<1m'


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
current_project = api.status_document['project']


def record_action(action):

    def wrapper(*args, **kwargs):

        action(*args, **kwargs)

        status_document = api.get_status()
        status_history = []
        if 'commands_history' in status_document:
            status_history = status_document['commands_history']
        status_history.append({
            'command': action.__name__,
            'datetime': datetime.now(),
            'args': args
        })
        api._status_update({'commands_history': status_history})

    return wrapper


# defines the commands
# @record_action
def add_command():

    tags = []
    project = current_project
    score = 1
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
        elif arg[:1] == ':' and arg[-3:] == 'pts':
            score = arg[1:-3]
        else:
            description.append(arg)

    description = ' '.join(description)
    message_first = 'Adding task: "{}"'.format(description)
    print('+' * len(message_first))
    print(message_first)
    print('Project: "{}"'.format(project))
    print('tags: {}'.format(tags))

    print('reward: {} pt{}'.format(score, 's' if int(score) > 1 else ''))

    if len(description) > 0:
        taskid = api.add(
            description, project=project,
            tags=tags, score=int(score)
        )

    print()
    print('Your task has been added')
    print('New task id:  {}'.format(taskid))


# @record_action
def archive_command():

    api.archive()


# @record_action
def reset_command():

    print("Reseting database")
    api.resest(db)
    print("done")


# @record_action
def score_command():

    if args[2].isdigit():
        score = int(args[2])
        api.score(score)
        print("Reward has been set to {} pt{}".format(
            score, 's' if score > 1 else ''
        ))


# table commands

# @record_action
def archives_command():
    print_table(api.archives)


# no record: most used command (loss in disk space)
# @record_action
def next_command():
    print_table(api.next, noprint=['done'])


# @record_action
def sumup_command():
    print_table(api.next, noprint=['totalpicks', 'ratio'])


# @record_action
def unpick_command():
    pid = api.pickedid()
    if pid:
        print('Resetting task {} last pick'.format(pid))
        api.drop()
        task = api.get(pid)
        task['history'] = task['history'][-1]
    else:
        print('No picked task')


# @record_action
def dropped_command():
    print_table(api.dropped)


# @record_action
def previously_command():
    print_table(api.previously)


def print_table(api_func, noprint=[]):
    # noprint : field list not to display

    # Table fields: Description, id, added x time ago, picked
    # If a task is picked then also prints picjed task

    next_tasks = api_func()
    now = datetime.now()

    fields = [
        'id', 'description', 'project', 'tags',
        'time', 'score', 'totalpicks', 'ratio', 'done'
    ]
    if len(noprint) > 0:
        fields, index = zip(
            *(
                (field, i) for i, field in enumerate(fields)
                if field not in noprint
            )
        )
        fields = list(fields)
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

        # get description, id

        row['description'] = task['description']
        row['id'] = str(task['id'])

        # task tags

        if picked_taskid:
            tags = copy.deepcopy(task['tags'])
            if picked_taskid == task['id']:
                tags.insert(0, '')
        else:
            tags = task['tags']
        row['tags'] = ' '.join(['#{}'.format(tag) for tag in tags])
        project = str(task['project'])

        # task project

        if project == 'None':
            project = ''
        row['project'] = project

        # task score

        row['score'] = str(task['score'])

        # time analytics TODO replace with use of time_analytics from mc_api

        row['time'] = 'ERR'
        # get datetime at creation (and compute X time ago)

        # has the task been done yet ?

        done = 0
        for state in task['history']:
            if state['status'] == 'done':
                done += 1
        row['done'] = 'X' if done == 1 else ' '
        if done > 1:
            row['done'] = str(done)

        # task age (time field)

        task_age = 0
        for state in task['history']:
            if state['status'] == 'new':
                task_age = (now - state['datetime']).total_seconds()
                row['time'] = pretty_time_delta(task_age)

        # this could be grouped above to loop once but it can still
        # for legibilty
        # FIXME should sort task['history'] list sorted by datetimes.
        # I assumed this is the case and that make sense with the front-end

        # task total picked time (tatalpicks field)

        totalpick = timedelta(0)
        _picked = False

        for state in task['history']:
            if state['status'] == 'picked':
                _picked = True
                _picked_datetime = state['datetime']
            if _picked and state['status'] in ('dropped', 'done'):
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

        row['ratio'] = ''
        if task_age > 0:
            # TODO feature: customize ration factor
            ratio_factor = 10
            ratio = ratio_factor * totalpick.total_seconds() / task_age
            if ratio > 0:
                row['ratio'] = '{:.2f}'.format(ratio)

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
        'id', 'Description', 'project', 'tags',
        'AGE', 'pts', 'TOT', 'ratio', 'X'
    ]
    if len(noprint) > 0:
        titles = [title for i, title in enumerate(titles) if i in index]

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
            print(fmt_str.format(*tuple(values)))
            print()
        else:
            print(fmt_str.format(*tuple(values)))

    print()
    print('Your score: {}'.format(api.rewards()))
    print()

    return fields


# @record_action
def pick_command():
    try:
        taskid = int(args[2])
        api.pick(taskid)
    except IndexError:
        picked_task_id = api.pickedid()
        if picked_task_id is None:
            print('.. 1 arg at least > or 1 task picked, try again')
        else:
            task_document = api.get(picked_task_id)
            print('> "{description}"{project}{tags}'.format(
                description=task_document['description'],
                project='' if task_document['project'] is None
                else ' @:' + task_document['project'],
                tags='' if len(task_document['tags']) == 0
                else ' #' + ' #'.join(task_document['tags'])
            ))
            # print('is the task you picked,')
            if 'history' in task_document:
                print(format_time_analytics(
                    *time_analytics(task_document['history'])
                ))
    except ValueError:
        print('.. no such task id, try again')
    # TODO describe the picked task a little more than default message


def freshstart_command():
    lastscore = api.rewards()
    if lastscore > 0:
        api.freshstart()
        print('Last score : %d' % lastscore)
        print('New score : 0')
        print('It\'s a fresh start')
    else:
        print('Do at least one task to ask freshstart')


# @record_action
def project_command():

    projectname = None
    if len(args) > 2:
        projectname = ' '.join(args[2:])
        print('Setting project.')
    curproject = api.project(projectname)
    print('Current project : %s' % curproject)


# @record_action
def drop_command():
    print('You dropping task {}'.format(api.pickedid()))
    print(format_time_analytics(*api.drop()))


# @record_action
def done_command():
    try:
        task_document = api.get(api.pickedid())
        message = '{} @:{}'.format(
            task_document['description'], task_document['project']
        )
        print('-'*len(message))
        print(message)
        print('-'*len(message)+' done.')
        # print('You\'re done with task {}'.format(api.pickedid()))
        print(format_time_analytics(*api.done()))
        score = task_document['score']
        print('You earned %d point%s' % (score, 's' if score > 1 else ''))
    except ValueError:
        print('No task has been picked')


# parses the command line
class Commands():

    def help(self):
        print('commands:')
        print()
        maxcmdlen = max(len(cmd) for cmd in self.commands)
        # TODO aliases in stack before command name
        # maxshtlrn = max(len(sht) for shortcuts in map( in self.commands
        # for sht in self.commands[cmd]['shortcuts']
        # if 'shortcuts' in self.commands[cmd])
        prefmt = '    {cmd:%d}  {helpmsg}{aliases}' % maxcmdlen
        for command in self.commands:
            cmdinfo = self.commands[command]
            shortcuts_str = ''
            if 'shortcuts' in cmdinfo:
                shortcuts_str = ', '.join(cmdinfo['shortcuts'])
            if len(shortcuts_str) > 0:
                shortcuts_str = (
                    '\n    {:%d}  (aliases: {})' % maxcmdlen
                ).format('', shortcuts_str)
            print(prefmt.format(
                cmd=command,
                aliases=shortcuts_str,
                helpmsg=cmdinfo['help']
            ), end='\n'*2)
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
                 shortcuts=[], helpmsg='', examples=[],
                 group_shortener=None, groups=0):
        command = {}
        if len(shortcuts) > 0:
            command['shortcuts'] = tuple(s for s in shortcuts)
        self.examples += examples
        command['action'] = action
        command['help'] = helpmsg
        command['groups'] = groups
        if group_shortener is not None:
            command['group_shortener'] = group_shortener
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
            # if query.isdigit():
                # if all(arg.isdigit() for arg in args[1:-1]):
                    # if
            print('unknown command, try again or try help command')


# new cli instance

cli = Commands()

# register commands next, done, reset, pick, drop
# TODO ... comment
# shortcuts=[''] is to define the default command

cli.register('archive', archive_command, shortcuts=['forget'],
             helpmsg='Arhcive picked task')
cli.register('archives', archives_command,
             helpmsg='Print archived tasks')
cli.register('done', done_command, shortcuts=['finish', '-', 'ok'],
             helpmsg='This is for when you\'re done with the picked task',
             groups=1)
cli.register('drop', drop_command, shortcuts=['pause'],
             helpmsg='Drop the picked task if there is one')
cli.register('drops', dropped_command, shortcuts=['fresh', 'dropped'],
             helpmsg='Print only dropped tasks (already picked)')
cli.register('freshstart', freshstart_command,
             helpmsg='Reset the score to zero (but keep a trace)')
cli.register('next', next_command, shortcuts=[],
             helpmsg='Print your tasks and stats',
             groups=0)
cli.register('pick', pick_command, shortcuts=['picked', 'now', ':', 'p'],
             helpmsg='Pick the task giving an id',
             groups=1, group_shortener='')
cli.register('previously', previously_command, shortcuts=['previous', 'old'],
             helpmsg='Print all tasks but new or fresh tasks')
cli.register('project', project_command, shortcuts=['pro'],
             helpmsg='Get projectname or set projectname with args')
cli.register('reset-hard', reset_command, shortcuts=[],
             helpmsg='You want to delete everything permanantly')
cli.register('score', score_command,
             helpmsg='Set reward score for the picked task')
cli.register('sumup', sumup_command, shortcuts=[''],
             helpmsg='Less than next')
cli.register('unpick', unpick_command, shortcuts=['fix-pick'],
             helpmsg='Fix picked task left as picked. \
             The task is reset like if it was not not picked.')

# TODO tag command
# TODO bang operator .. continue

# register add command

add_examples = '''\
> add my task @:projectname description #tag could be anywhere
> add another task #moretag #tagged :4pts\
'''
add_examples.split('\n')

cli.register('add', add_command, shortcuts=['new'],
             helpmsg='Add new task parsing all arguments (see examples)',
             examples=[add_examples])

# invoke parse command

cli.parse(command)
