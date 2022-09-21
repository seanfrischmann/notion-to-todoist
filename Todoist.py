import todoist


class Todoist:
    def __init__(self, config):
        self.api = todoist.TodoistAPI(config['secret'])
        self.main_project = dict()
        self.secret = config['secret']
        self.sections = dict()
        self.sub_project = dict()
        self.projects = self.getProjects()

    def getProjects(self):
        import requests

        projects = requests.get(
            "https://api.todoist.com/rest/v1/projects",
            headers={"Authorization": f"Bearer {self.secret}"}
        ).json()

        formatted = {}
        for project in projects:
            formatted[project['name']] = project

        return formatted

    def setMainProject(self, project: dict):
        if project['name'] in self.projects:
            main_project = self.api.projects.get(
                project_id=self.projects[project['name']]['id']
            )

            main_project = main_project['project']
        else:
            main_project = self.createTodoistProject(project=project)

        self.main_project = main_project

    def setSubProject(self, project: dict):
        if (
            project['name'] in self.projects and
            'parent_id' in self.projects[project['name']] and
            self.projects[project['name']]['parent_id'] == self.main_project['id']
        ):
            sub_project = self.api.projects.get_by_id(
                self.projects[project['name']]['id']
            )
            sub_project.delete()

        self.commit()
        sub_project = self.createTodoistProject(
            project=project,
            parent_id=self.main_project['id']
        )

        self.sub_project = sub_project

    def setSetions(self, statuses):
        sections = {}
        for status in statuses:
            sections[status] = self.api.sections.add(
                status,
                project_id=self.sub_project['id']
            )

        self.sections = sections

    def createTodoistProject(self, project: dict, statuses=False, parent_id=False):
        if parent_id:
            print(f"Creating Sub-Project: {project['name']}")
            todoist_project = self.api.projects.add(
                project['name'],
                parent_id=parent_id,
                color=project['color'],
            )

            if project['comment']:
                self.api.project_notes.add(
                    project_id=todoist_project['id'],
                    content=project['comment']
                )
        else:
            print(f"Creating Project: {project['name']}")
            todoist_project = self.api.projects.add(
                project['name'],
                color=project['color']
            )

        return todoist_project

    def createTodoistTask(self, task, statuses, complete=False, tag_name="Notion-Issue"):
        print(f"Creating task {task['name']}")

        if complete and task['status'] in complete:
            item = self.api.quick.add(f"* {task['name']} @{tag_name}")
        else:
            item = self.api.quick.add(
                f"* {task['name']} @{tag_name} {task['start_date']}"
            )

        item = self.api.items.get_by_id(item['id'])
        item.update(description=task['description'])

        if task['sub_tasks']:
            for sub_task in task['sub_tasks']:
                sub_item = self.api.quick.add(f"{sub_task['name']} @{tag_name}")

                print(f"Adding subtask {sub_task['name']} to {task['name']}")
                sub_item = self.api.items.get_by_id(sub_item['id'])
                sub_item.update(description=sub_task['description'])
                sub_item.move(parent_id=item['id'])

                if 'comment' in sub_task:
                    self.api.notes.add(sub_item['id'], content=sub_task['comment'])

                if sub_task['status'] == 'Complete':
                    sub_item.complete()

        section = statuses[0]
        if task['status']:
            section = task['status']

        print(f"Adding {task['name']} task to the project")
        item.move(project_id=self.sub_project['id'])
        if section in self.sections:
            print(f"Adding {task['name']} to section {section}")
            item.move(section_id=f"{self.sections[section]['id']}")

        if 'comment' in task and task['comment']:
            self.api.notes.add(item['id'], content=task['comment'])

    def commit(self):
        self.api.commit()

    def resetState(self):
        self.main_project = dict()
        self.sections = dict()
        self.sub_project = dict()
        self.api.reset_state()
