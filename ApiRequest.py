import json
import os
import sys
import requests
import todoist

config = []
with open(os.path.join(sys.path[0], 'config.json')) as configFile:
    config = json.load(configFile)


def main():
    fields = ['secret', 'databases', 'url', 'api']
    for field in fields:
        if field not in config['notion']:
            print("Config field is missing:", field)
            exit(1)

    todo_projects = getTodoistProjects()
    for database in config['notion']['databases']:
        project = normalizeNotionData(database)
        syncProject(project=project, todo_projects=todo_projects)


def syncProject(project: dict, todo_projects: dict):
    api = todoist.TodoistAPI(config['todoist']['secret'])

    if project['name'] in todo_projects:
        main_project = api.projects.get(project_id=todo_projects[project['name']]['id'])
        main_project = main_project['project']
    else:
        main_project = createTodoistProject(project=project, api=api)

    for epic in project['sub_projects']:
        if epic['name'] in todo_projects and \
                'parent_id' in todo_projects[epic['name']] and \
                todo_projects[epic['name']]['parent_id'] == main_project['id']:
            sub_project = api.projects.get_by_id(todo_projects[epic['name']]['id'])
            sub_project.delete()

        sub_project, sections = createTodoistProject(
            project=epic,
            api=api,
            statuses=project['statuses'],
            parent_id=main_project['id']
        )

        for story in epic['stories']:
            complete = False
            if 'complete' in project:
                complete = project['complete']

            createTodoistTask(
                task=story,
                api=api,
                statuses=project['statuses'],
                sections=sections,
                project_id=sub_project['id'],
                complete=complete
            )

    print('Committing project to Todoist')
    api.commit()
    api.reset_state()
    print('All Done')


def normalizeNotionData(database: dict):
    print(f"Getting notion database {database['name']}")
    notion_database = getNotionDatabase(database['id'], database['filter'])
    project = {
        'name': database['name'],
        'statuses': database['statuses'],
        'color': database['colors']['main'],
        'sub_projects': []
    }

    if 'complete' in database:
        project['complete'] = database['complete']

    for epic in notion_database['results']:
        sub_project = {
            'epic_id': epic['id'],
            'name': epic['properties']['Name']['title'][0]['plain_text'].replace(' |',
                                                                                 ':'),
            'color': database['colors']['sub'],
            'fields': database['fields']['epic'],
            'stories': []
        }

        print(f"Reviewing Epic {sub_project['name']}")

        notion_stories = getNotionChildren(db_id=database['id'], parent_id=epic['id'])
        for story in notion_stories['results']:
            task = {
                'story_id': story['id'],
                'name': story['properties']['Name']['title'][0]['plain_text'],
                'description': getNotionDescription(
                    story['properties']['Description']['rich_text']
                ),
                'end_date': '',
                'fields': database['fields']['story'],
                'status': '',
                'sub_tasks': []
            }

            print(f"Reviewing Story {task['name']}")

            if 'Status' in story['properties']:
                task['status'] = story['properties']['Status']['select']['name']

            if 'End Date' in story['properties']:
                task['end_date'] = story['properties']['End Date']['date']['start']

            notion_tasks = getNotionChildren(
                db_id=database['id'],
                parent_id=story['id']
            )

            for sub_task in notion_tasks['results']:
                status = ''

                if 'Status' in sub_task['properties']:
                    status = sub_task['properties']['Status']['select']['name']

                task['sub_tasks'].append({
                    'task_id': sub_task['id'],
                    'name': sub_task['properties']['Name']['title'][0]['plain_text'],
                    'description': getNotionDescription(
                        sub_task['properties']['Description']['rich_text']
                    ),
                    'fields': database['fields']['task'],
                    'status': status
                })

            sub_project['stories'].append(task)

        project['sub_projects'].append(sub_project)

    return project


def getNotionDescription(field):
    description = ''
    for item in field:
        if description:
            description += f" {item['plain_text']}"
        else:
            description = item['plain_text']

    return description


def getNotionDatabase(db_id: str, db_filter: dict):
    """
    Get Notion Database

    :param db_id:
    :param db_filter:
    :return: Notion Obj
    """
    endpoint = 'databases/' + db_id + '/query'

    options = {
        'data': json.dumps({'filter': db_filter})
    }

    return notionRequest(endpoint=endpoint, request_type='post', options=options)


def getNotionChildren(db_id: str, parent_id: str):
    endpoint = 'databases/' + db_id + '/query'

    options = {
        'data': json.dumps({
            'filter': {
                'property': 'Parent',
                'relation': {
                    'contains': parent_id
                }
            }
        })
    }

    return notionRequest(endpoint=endpoint, request_type='post', options=options)


def notionRequest(endpoint: str, request_type: str, options: dict):
    url = config['notion']['url'] + endpoint

    headers = {
        'Authorization': f"Bearer {config['notion']['secret']}",
        'Notion-Version': config['notion']['api'],
        'Content-Type': 'application/json'
    }

    return makeRequest(
        request_type=request_type,
        url=url,
        headers=headers,
        options=options
    )


def makeRequest(request_type: str, url: str, headers: dict, options: dict):
    if request_type == 'post':
        response = requests.post(url, headers=headers, data=options['data'])
        return response.json()

    return {}


def getTodoistProjects():
    projects = requests.get(
        "https://api.todoist.com/rest/v1/projects",
        headers={"Authorization": f"Bearer {config['todoist']['secret']}"}
    ).json()

    formatted = {}
    for project in projects:
        formatted[project['name']] = project

    return formatted


def createTodoistProject(project: dict, api, statuses=False, parent_id=False):
    if parent_id:
        print(f"Creating Sub-Project: {project['name']}")
        todoist_project = api.projects.add(
            project['name'],
            parent_id=parent_id,
            color=project['color']
        )
    else:
        print(f"Creating Project: {project['name']}")
        todoist_project = api.projects.add(project['name'], color=project['color'])

    if statuses:
        sections = {}
        for status in statuses:
            sections[status] = api.sections.add(status, project_id=todoist_project['id'])

        return todoist_project, sections

    return todoist_project


def createTodoistTask(task, api, statuses, sections, project_id, complete=False):
    print(f"Creating task {task['name']}")
    
    if complete and task['status'] in complete:
        item = api.quick.add(f"* {task['name']} @Notion-Issue")
    else:
        item = api.quick.add(f"* {task['name']} @Notion-Issue {task['end_date']}")

    item = api.items.get_by_id(item['id'])
    item.update(description=task['description'])

    if task['sub_tasks']:
        for sub_task in task['sub_tasks']:
            sub_item = api.quick.add(f"{sub_task['name']} @Task")

            print(f"Adding subtask {sub_task['name']} to {task['name']}")
            sub_item = api.items.get_by_id(sub_item['id'])
            sub_item.update(description=sub_task['description'])
            sub_item.move(parent_id=item['id'])

            if sub_task['status'] == 'Complete':
                sub_item.complete()

    section = statuses[0]
    if task['status']:
        section = task['status']

    print(f"Adding {task['name']} task to the project")
    item.move(project_id=project_id)
    print(f"Adding {task['name']} to section {section}")
    item.move(section_id=f"{sections[section]['id']}")


if __name__ == '__main__':
    main()
