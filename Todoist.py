from typing import Optional

from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Project


class Todoist:
    main_project: Project
    sub_project: Project
    sections: dict

    def __init__(self, config):
        self.secret = config['secret']
        self.api = TodoistAPI(self.secret)
        self.projects = self.get_projects()

    def get_projects(self):
        import requests

        projects = self.api.get_projects()

        formatted = {}
        for project in projects:
            formatted[project.name] = project

        return formatted

    def set_main_project(self, project: dict):
        if project['name'] in self.projects:
            main_project = self.projects[project['name']]
        else:
            main_project = self.create_todoist_project(project=project)

        self.main_project = main_project

    def set_sub_project(self, project: dict):
        if (
                project['name'] in self.projects and
                self.projects[project['name']].parent_id == self.main_project.id
        ):
            self.api.delete_project(
                project_id=self.projects[project['name']].id
            )

        sub_project = self.create_todoist_project(
            project=project,
            parent_id=self.main_project.id
        )

        self.sub_project = sub_project

    def set_sections(self, statuses):
        sections = {}
        for status in statuses:
            sections[status] = self.api.add_section(
                name=status,
                project_id=self.sub_project.id
            )

        self.sections = sections

    def create_todoist_project(
            self,
            project: dict,
            parent_id: Optional[str] = None
    ):
        if parent_id:
            print(f"Creating Sub-Project: {project['name']}")
            todoist_project = self.api.add_project(
                name=project['name'],
                parent_id=parent_id,
                color=project['color'],
            )

            if project['comment']:
                self.api.add_comment(
                    project_id=todoist_project.id,
                    content=project['comment']
                )
        else:
            print(f"Creating Project: {project['name']}")
            todoist_project = self.api.add_project(
                name=project['name'],
                color=project['color']
            )

        return todoist_project

    def create_todoist_task(self, task, statuses, complete=False, tag_name="Notion-Issue"):
        print(f"Creating task {task['name']}")

        section = statuses[0]
        if task['status']:
            section = task['status']

        if complete and task['status'] in complete:
            item = self.api.add_task(
                content=task['name'],
                description=task['description'],
                labels=[tag_name],
                section_id=self.sections[section].id,
                project_id=self.sub_project.id
            )
        else:
            item = self.api.add_task(
                content=task['name'],
                description=task['description'],
                labels=[tag_name],
                section_id=self.sections[section].id,
                due_string=task['start_date'],
                project_id=self.sub_project.id
            )

        if 'comment' in task and task['comment']:
            self.api.add_comment(task_id=item.id, content=task['comment'])

        if task['sub_tasks']:
            for sub_task in task['sub_tasks']:
                print(f"Adding subtask {sub_task['name']} to {task['name']}")
                sub_item = self.api.add_task(
                    content=sub_task['name'],
                    description=sub_task['description'],
                    labels=[tag_name],
                    parent_id=item.id
                )

                if 'comment' in sub_task:
                    self.api.add_comment(task_id=sub_item.id, content=sub_task['comment'])

                if sub_task['status'] == 'Complete':
                    self.api.close_task(task_id=sub_item.id)
