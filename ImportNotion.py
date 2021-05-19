import csv
import todoist
import pprint as pp


def main():
    tickets = []
    print("\033[93m Make sure you file is in Downloads/notion/PageName.csv!\033[0m \n\n")
    project = {
        'name': input("Enter the top level page name:\n"),
        'tasks': {}
    }

    with open(f'../../Downloads/notion/{project["name"]}.csv', mode='r',
              encoding='utf-8-sig') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        line_count = 0
        for row in csv_reader:
            if row['Parent Name'] == project['name']:
                project['tasks'][row['Name']] = row
                project['tasks'][row['Name']]['subtasks'] = {}
            else:
                tickets.append(row)
            line_count += 1
        print(f'Processed {line_count} lines.')

    for key in project['tasks'].keys():
        for ticket in tickets:
            if ticket['Parent Name'] == key:
                project['tasks'][key]['subtasks'][ticket['Name']] = ticket

    createLeverageTodoistProject(project)


def createLeverageTodoistProject(project):
    api = todoist.TodoistAPI('579ee6ae923cad35b3f8818a363cac294d2b7d4a')

    print(f"Creating Project: {project['name']}")
    todoistProject = api.projects.add(project['name'])
    sections = {
        'To Do': api.sections.add('To Do', project_id=todoistProject['id']),
        'In Progress': api.sections.add('In Progress', project_id=todoistProject['id']),
        'Pending': api.sections.add('Pending', project_id=todoistProject['id']),
        'Pending Release': api.sections.add('Pending Release', project_id=todoistProject['id']),
        'Complete': api.sections.add('Complete', project_id=todoistProject['id'])
    }

    for key, task in project['tasks'].items():
        print(f"Creating task {key}")
        item = api.quick.add(f"* {key} @Notion-Issue {task['End Date']}",
                             note=(
                                 f"*** \n"
                                 f"**Created:** {task['Created']}\n"
                                 f"**Start Date:** {task['Start Date']}\n"
                                 f"**End Date:** {task['End Date']}"
                                 f"\n *** \n"
                                 f"**Duration:** {task['Duration']}\n"
                                 f"**Type:** {task['Type']}\n"
                                 f"**Story Points:** {task['Story Points']}"
                                 f"\n *** \n"
                                 f"#### Description \n{task['Description']}"
                                 f"\n *** "
                             ))

        if task['subtasks']:
            for subkey, subtask in task['subtasks'].items():
                subitem = api.quick.add(f"{subkey} @Task",
                                        note=(
                                            f"*** \n"
                                            f"**Created:** {subtask['Created']}\n"
                                            f"**Type:** {subtask['Type']}\n"
                                            f"**Story Points:** {subtask['Story Points']}"
                                            f"\n *** \n"
                                            f"#### Description \n{task['Description']}"
                                            f"\n *** "
                                        ))

                print(f"Adding subtask {subkey} to {key}")
                subitem = api.items.get_by_id(subitem['id'])
                subitem.move(parent_id=item['id'])

                if subtask['Status'] == 'Complete':
                    subitem.complete()

        item = api.items.get_by_id(item['id'])
        section = 'To Do'
        if task['Status']:
            section = task['Status']

        print(f"Adding {key} task to the project")
        item.move(project_id=todoistProject['id'])
        print(f"Adding {key} to section {section}")
        item.move(section_id=f"{sections[section]['id']}")

    print('Committing project to Todoist')
    api.commit()
    api.reset_state()
    print('All Done')


if __name__ == '__main__':
    main()
