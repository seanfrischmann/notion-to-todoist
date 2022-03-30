import json


class Notion:

    def __init__(self, config):
        self.api = config['api']
        self.databases = config['databases']
        self.secret = config['secret']
        self.url = config['url']

    def getProjects(self):
        projects = []
        for database in self.databases:
            if "skip" in database and database["skip"]:
                continue

            print(f"Getting notion database {database['name']}")

            notion_database = self.getNotionDatabase(
                db_id=database['id'],
                db_filter=database['filter']
            )

            project = {
                'name': database['name'],
                'statuses': database['statuses'],
                'color': database['colors']['main'],
                'sub_projects': []
            }

            if 'taskTag' in database:
                project['taskTag'] = database['taskTag']

            if 'complete' in database:
                project['complete'] = database['complete']

            for epic in notion_database['results']:
                name = "Title"
                if "pageNameField" in database:
                    name = database["pageNameField"]

                sub_project = {
                    'epic_id': epic['id'],
                    'name': epic['properties'][name]['title'][0]['plain_text'].replace(
                        ' |', ':'),
                    'color': database['colors']['sub'],
                    'comment': self.createProperties(
                        fields=database['fields']['epic'],
                        properties=epic['properties']
                    ),
                    'stories': []
                }

                print(f"Reviewing Epic {sub_project['name']}")

                parent_field = "Parent"
                if "parentField" in database:
                    parent_field = database["parentField"]

                sub_filter = None
                if "subFilter" in database:
                    sub_filter = database["subFilter"]

                notion_stories = self.getNotionChildren(
                    db_id=database['id'],
                    parent_id=epic['id'],
                    parent_field=parent_field,
                    sub_filter=sub_filter
                )

                for story in notion_stories['results']:
                    task = {
                        'story_id': story['id'],
                        'name': story['properties'][name]['title'][0]['plain_text'],
                        'description':
                            self.createProperties(
                                fields=database['fields']['story'],
                                properties=story['properties'],
                                url=story['url']
                            ) + "\n" +
                            self.getField(field=story['properties']['Description'])
                        ,
                        'end_date': '',
                        'status': '',
                        'sub_tasks': [],
                        'url': story['url']
                    }

                    print(f"Reviewing Story {task['name']}")

                    if 'Status' in story['properties']:
                        task['status'] = story['properties']['Status']['select']['name']

                    if 'Start Date' in story['properties']:
                        task['start_date'] = story['properties']['Start Date']['date'][
                            'start']

                    notion_tasks = self.getNotionChildren(
                        db_id=database['id'],
                        parent_id=story['id']
                    )

                    for sub_task in notion_tasks['results']:
                        status = ''

                        if 'Status' in sub_task['properties']:
                            status = sub_task['properties']['Status']['select']['name']

                        task['sub_tasks'].append({
                            'task_id': sub_task['id'],
                            'name': sub_task['properties']['Name']['title'][0][
                                'plain_text'],
                            'description': self.getField(
                                field=sub_task['properties']['Description']
                            ),
                            'comment': self.createProperties(
                                fields=database['fields']['task'],
                                properties=sub_task['properties']
                            ),
                            'status': status,
                            'url': story['url'],
                        })

                    sub_project['stories'].append(task)

                project['sub_projects'].append(sub_project)

            projects.append(project)

        return projects

    def getNotionDatabase(self, db_id: str, db_filter: dict):
        endpoint = 'databases/' + db_id + '/query'

        options = {
            'data': json.dumps({'filter': db_filter})
        }

        return self.notionRequest(endpoint=endpoint, request_type='post', options=options)

    def getNotionChildren(
            self,
            db_id: str,
            parent_id: str,
            parent_field: str = "Parent",
            sub_filter=None
    ):
        endpoint = 'databases/' + db_id + '/query'
        children_filter = {
            'property': parent_field,
            'relation': {
                'contains': parent_id
            }
        }

        if sub_filter is not None:
            children_filter = {
                "and": [
                    children_filter,
                    sub_filter
                ]
            }

        options = {
            'data': json.dumps({
                'filter': children_filter
            })
        }

        return self.notionRequest(endpoint=endpoint, request_type='post', options=options)

    def notionRequest(self, endpoint: str, request_type: str, options: dict):
        url = self.url + endpoint

        headers = {
            'Authorization': f"Bearer {self.secret}",
            'Notion-Version': self.api,
            'Content-Type': 'application/json'
        }

        return self.makeRequest(
            request_type=request_type,
            url=url,
            headers=headers,
            options=options
        )

    @staticmethod
    def makeRequest(request_type: str, url: str, headers: dict, options: dict):
        import requests

        if request_type == 'post':
            response = requests.post(url, headers=headers, data=options['data'])
            return response.json()

        return {}

    def createProperties(self, fields, properties, url=False):
        content = ''

        if url:
            notionUrl = url.replace('https', 'notion')
            content = f" --- \n **Ticket:** [Open in Notion]({notionUrl})\n"

        for field in fields:
            if field in properties:
                value = self.getField(properties[field])
                content += (
                    f"**{field}:** {value}\n"
                )

        if content and url:
            content += " --- "
        elif content:
            content = f' --- \n {content} --- '

        return content

    def getField(self, field):
        if type(field) is list and field:
            field = field[0]
        elif type(field) is list:
            return ''

        if field['type'] == 'rich_text':
            return self.richTextField(field)

        elif field['type'] == 'select':
            return self.selectField(field)

        elif field['type'] == 'formula':
            return self.formulaField(field)

        elif field['type'] == 'rollup':
            return self.rollupField(field)

        elif field['type'] == 'date':
            return self.dateField(field)

        else:
            return field[field['type']]

    @staticmethod
    def richTextField(field):
        content = ''
        markdown = {
            'bold': '**',
            'italic': '__',
            'code': '`'
        }

        for item in field['rich_text']:
            text = item['text']['content']

            if 'annotations' in item:
                formatting = item['annotations']

                for option in formatting:
                    if option in markdown and formatting[option]:
                        text = f'{markdown[option]}{text}{markdown[option]}'

            if content:
                content += text
            else:
                content = text

        return content

    @staticmethod
    def selectField(field):
        if field['select'] is None:
            return '(empty)'

        return field['select']['name']


    @staticmethod
    def formulaField(field):
        return field['formula'][field['formula']['type']]

    @staticmethod
    def rollupField(field):
        return field['rollup'][field['rollup']['type']]

    @staticmethod
    def dateField(field):
        if (
                'start' in field['date'] and
                'end' in field['date'] and
                field['date']['start'] and
                field['date']['end']
        ):
            return field['date']['start'] + ' → ' + field['date']['end']

        elif 'start' in field['date'] and field['date']['start']:
            return field['date']['start']

        elif 'end' in field['date'] and field['date']['end']:
            return field['date']['end']

        return ''
