from Notion import Notion
from Todoist import Todoist
from util import getJsonFile


class Main:
    def __init__(self):
        self.config = getJsonFile('config')
        self.todo = Todoist(self.config['todoist'])
        self.notion = Notion(self.config['notion'])

    def sync(self):
        for project in self.notion.getProjects():
            self.todo.setMainProject(project)
            self.todo.commit()

            for epic in project['sub_projects']:
                self.todo.setSubProject(epic)
                self.todo.commit()

                self.todo.setSetions(project['statuses'])
                self.todo.commit()

                for story in epic['stories']:
                    complete = False
                    task_tag = "Notion-Issue"

                    if 'complete' in project:
                        complete = project['complete']

                    if 'taskTag' in project:
                        task_tag = project['taskTag']

                    self.todo.createTodoistTask(
                        task=story,
                        statuses=project['statuses'],
                        complete=complete,
                        tag_name=task_tag
                    )

                    self.todo.commit()

            self.todo.resetState()
            print('All Done')


if __name__ == '__main__':
    main = Main()
    main.sync()
