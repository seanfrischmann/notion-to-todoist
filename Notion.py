import functools
import json
import pprint


class Notion:

    def __init__(self, config):
        self.api = config['api']
        self.databases = config['databases']
        self.secret = config['secret']
        self.url = config['url']

    def get_projects(self):
        projects = []
        for database in self.databases:
            if "skip" in database and database["skip"]:
                continue

            print(f"Getting notion database {database['name']}")

            notion_database = self.get_notion_database(
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
                        ' |', ':'
                    ),
                    'color': database['colors']['sub'],
                    'comment': self.create_properties(
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

                override_filter = None
                if "overrideFilter" in database:
                    override_filter = database["overrideFilter"]

                db_id = database['id']
                if database['parentDBID']:
                    db_id = database['parentDBID']

                notion_stories = self.get_notion_children(
                    db_id=db_id,
                    parent_id=epic['id'],
                    parent_field=parent_field,
                    sub_filter=sub_filter,
                    override_filter=override_filter
                )

                for story in notion_stories['results']:
                    story_name = name
                    if database['storyName']:
                        story_name = database['storyName']

                    task = {
                        'story_id': story['id'],
                        'name': story['properties'][story_name]['title'][0]['plain_text'],
                        'description':
                            self.create_properties(
                                fields=database['fields']['story'],
                                properties=story['properties'],
                                url=story['url']
                            ) + "\n" +
                            self.get_field(field=story['properties']['Summary'])
                        ,
                        'end_date': '',
                        'status': '',
                        'sub_tasks': [],
                        'url': story['url']
                    }

                    print(f"Reviewing Story {task['name']}")
                    task['comments'] = [self.rich_text_field(comment) for comment in
                                        self.get_page_comments(story['id'])]

                    if 'Status' in story['properties']:
                        task['status'] = story['properties']['Status']['status']['name']

                    task['start_date'] = ''
                    if (
                            'Start Date' in story['properties']
                            and story['properties']['Start Date']['date']
                    ):
                        task['start_date'] = \
                            story['properties']['Start Date']['date']['start']

                    parent_field = "Parent"
                    if database['taskParent']:
                        parent_field = database['taskParent']
                    notion_tasks = self.get_notion_children(
                        db_id=db_id,
                        parent_id=story['id'],
                        parent_field=parent_field
                    )

                    for sub_task in notion_tasks['results']:
                        status = ''

                        if 'Status' in sub_task['properties']:
                            status = sub_task['properties']['Status']['status']['name']

                        task['sub_tasks'].append(
                            {
                                'task_id': sub_task['id'],
                                'comments':
                                    [self.rich_text_field(comment) for comment in
                                     self.get_page_comments(sub_task['id'])],
                                'name': sub_task['properties'][story_name]['title'][0][
                                    'plain_text'],
                                'description':
                                    self.create_properties(
                                        fields=database['fields']['task'],
                                        properties=sub_task['properties'],
                                        url=sub_task['url']
                                    ) + "\n" +
                                    self.get_field(
                                        field=sub_task['properties']['Summary']
                                    ),
                                'status': status,
                                'url': sub_task['url'],
                            }
                        )

                    sub_project['stories'].append(task)

                project['sub_projects'].append(sub_project)

            projects.append(project)

        return projects

    def get_notion_database(self, db_id: str, db_filter: dict):
        endpoint = 'databases/' + db_id + '/query'

        options = {
            'data': json.dumps({'filter': db_filter})
        }

        return self.notion_request(endpoint=endpoint, request_type='post', options=options)

    def get_notion_children(
            self,
            db_id: str,
            parent_id: str,
            parent_field: str = "Parent",
            sub_filter=None,
            override_filter=None

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

        if override_filter is not None:
            children_filter = override_filter

        options = {
            'data': json.dumps(
                {
                    'filter': children_filter
                }
            )
        }

        return self.notion_request(endpoint=endpoint, request_type='post', options=options)

    def get_page_comments(self, story_id: str):
        return self.notion_request(
            endpoint='comments',
            request_type='get',
            options={'block_id': story_id}
        )['results']

    def notion_request(self, endpoint: str, request_type: str, options: dict):
        url = self.url + endpoint

        headers = {
            'Authorization': f"Bearer {self.secret}",
            'Notion-Version': self.api,
            'Content-Type': 'application/json'
        }

        return self.make_request(
            request_type=request_type,
            url=url,
            headers=headers,
            options=options
        )

    @staticmethod
    def make_request(request_type: str, url: str, headers: dict, options: dict):
        import requests

        if request_type == 'post':
            response = requests.post(url, headers=headers, data=options['data'])
            return response.json()
        elif request_type == 'get':
            response = requests.get(url, params=options, headers=headers)
            return response.json()

        return {}

    def create_properties(self, fields, properties, url=False):
        content = ''

        if url:
            notion_url = url.replace('https', 'notion')
            content = f"**Ticket:** [Open in Notion]({notion_url})\n"

        for field in fields:
            if field in properties:
                value = self.get_field(properties[field])
                content += (
                    f"**{field}:** {value}\n"
                )

        if content and url:
            content += " \n--- "
        elif content:
            content = f'{content} \n --- '

        return content

    def get_field(self, field):
        if type(field) is list and field:
            field = field[0]
        elif type(field) is list:
            return ''

        if field['type'] == 'rich_text':
            return self.rich_text_field(field)

        elif field['type'] == 'select':
            return self.select_field(field)

        elif field['type'] == 'status':
            return self.select_field(field, 'status')

        elif field['type'] == 'formula':
            return self.formula_field(field)

        elif field['type'] == 'rollup':
            return self.rollup_field(field)

        elif field['type'] == 'date':
            return self.date_field(field)

        elif field['type'] == 'unique_id':
            return f"{field['unique_id']['prefix']}-{field['unique_id']['number']}"

        elif field['type'] == 'multi_select':
            return functools.reduce(
                lambda carry, cur: f"`{cur['name']}`" if carry == '' else f"{carry}, `{cur['name']}`",
                field['multi_select'],
                ''
            )

        elif field['type'] == 'people':
            return functools.reduce(
                lambda carry, cur: f"`{cur['name']}`" if carry == '' else f"{carry}, `{cur['name']}`",
                field['people'],
                ''
            )

        else:
            return field[field['type']]

    @staticmethod
    def rich_text_field(field):
        content = ''
        markdown = {
            'bold': '**',
            'italic': '__',
            'code': '`'
        }

        for item in field['rich_text']:
            if item['type'] == 'mention':
                mention = item['mention']

                if mention['type'] == 'page':
                    id = f'{mention["page"]["id"]}'.replace('-', '')
                    text = (
                        f'[Open in Notion](notion://www.notion.so/{id})'
                        f' | [Open in Browser](https://www.notion.so/{id})'
                    )

                else:
                    text = mention[mention['type']]['name']
            else:
                text = item['text']['content']

            if 'annotations' in item:
                formatting = item['annotations']

                for option in formatting:
                    if option in markdown and formatting[option]:
                        text = f'{markdown[option]}{text}{markdown[option]}'

            href = item['href']
            if href:
                text = f'[{text}]({href})'

            if content:
                content += text
            else:
                content = text

        return content

    @staticmethod
    def select_field(field, type='select'):
        if field[type] is None:
            return '(empty)'

        return field[type]['name']

    @staticmethod
    def formula_field(field):
        return field['formula'][field['formula']['type']]

    @staticmethod
    def rollup_field(field):
        return field['rollup'][field['rollup']['type']]

    @staticmethod
    def date_field(field):
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
