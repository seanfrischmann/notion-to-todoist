from Notion import Notion
from Todoist import Todoist
from util import getJsonFile


class Main:
    def __init__(self):
        self.config = getJsonFile('config')
        self.todo = Todoist(self.config['todoist'])
        self.notion = Notion(self.config['notion'])

    def sync(self):
        for project in self.notion.get_projects():
            self.todo.set_main_project(project)

            for epic in project['sub_projects']:
                self.todo.set_sub_project(epic)
                self.todo.set_sections(project['statuses'])

                for story in epic['stories']:
                    complete = False
                    task_tag = "Notion-Issue"

                    if 'complete' in project:
                        complete = project['complete']

                    if 'taskTag' in project:
                        task_tag = project['taskTag']

                    self.todo.create_todoist_task(
                        task=story,
                        statuses=project['statuses'],
                        complete=complete,
                        tag_name=task_tag
                    )

            print('All Done')


if __name__ == '__main__':
    main = Main()
    main.sync()
