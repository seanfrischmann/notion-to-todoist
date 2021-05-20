import json
import os
import sys

import todoist

from Notion import Notion

config = []
with open(os.path.join(sys.path[0], 'config.json')) as configFile:
    config = json.load(configFile)


def dumpToFile(name, data):
    with open(f"{name}.json", 'w') as outfile:
        json.dump(data, outfile)


def main():
    fields = ['secret', 'databases', 'url', 'api']
    for field in fields:
        if field not in config['notion']:
            print("Config field is missing:", field)
            exit(1)

    notion = Notion(config['notion'])
    todo_projects = getTodoistProjects()

    for project in notion.getProjects():
        syncProject(project=project, todo_projects=todo_projects)


def syncProject(project: dict, todo_projects: dict):
    api = todoist.TodoistAPI(config['todoist']['secret'])

    if project['name'] in todo_projects:
        main_project = api.projects.get(project_id=todo_projects[project['name']]['id'])
        main_project = main_project['project']
    else:
        main_project = createTodoistProject(project=project, api=api)

    api.commit()

    for epic in project['sub_projects']:
        if epic['name'] in todo_projects and \
                'parent_id' in todo_projects[epic['name']] and \
                todo_projects[epic['name']]['parent_id'] == main_project['id']:
            sub_project = api.projects.get_by_id(todo_projects[epic['name']]['id'])
            sub_project.delete()

        api.commit()

        sub_project, sections = createTodoistProject(
            project=epic,
            api=api,
            statuses=project['statuses'],
            parent_id=main_project['id']
        )

        api.commit()

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

            api.commit()

    print('Committing project to Todoist')
    api.commit()
    api.reset_state()
    print('All Done')


def getTodoistProjects():
    import requests

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
            color=project['color'],
        )

        if project['comment']:
            api.project_notes.add(
                project_id=todoist_project['id'],
                content=project['comment']
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

            if sub_task['comment']:
                api.notes.add(sub_item['id'], content=sub_task['comment'])

            if sub_task['status'] == 'Complete':
                sub_item.complete()

    section = statuses[0]
    if task['status']:
        section = task['status']

    print(f"Adding {task['name']} task to the project")
    item.move(project_id=project_id)
    print(f"Adding {task['name']} to section {section}")
    item.move(section_id=f"{sections[section]['id']}")

    if task['comment']:
        api.notes.add(item['id'], content=task['comment'])


if __name__ == '__main__':
    main()
