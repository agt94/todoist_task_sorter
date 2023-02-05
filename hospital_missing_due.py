import os
import re
import logging
from datetime import datetime
#from dateutil import tz

from todoist_api_python.api import TodoistAPI
from uuid import uuid4
import requests
import csv
# from todoist.api import TodoistAPI
# from todoist.managers.notes import NotesManager
# from todoist.managers.items import ItemsManager
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TODOIST_DATE_FORMAT = "%Y-%m-%d"

red_dot = '\U0001f534'


def get_token():
    token = os.getenv('TODOIST_APIKEY')
    if not token:
        raise Exception('Please set the API token in environment variable.')
    return token

TOKEN = get_token()

#https://github.com/Doist/todoist-api-python/issues/8  move tasks to different project

class Todoist_program(object):
    def __init__(self):
        with open("quotes.csv", "r") as file:
            reader = csv.reader(file, delimiter='"')
            for row in reader:
                print(row)
        self.api = TodoistAPI(TOKEN)

        self.api.notes = self.api.get_tasks()
        self.api.projects = self.api.get_projects()
        self.api.labels = self.api.get_labels()
        self.api.sections = self.api.get_sections()
        self.testing_id = [project.id for project in self.api.projects if project.name == 'testing'][0]
        self.section_heaven_id = [section.id for section in self.api.sections if section.name == 'Heaven'][0]
        hospital_id = [project.id for project in self.api.projects if project.name == 'hospital']

        inbox_id = [project.id for project in self.api.projects if project.name == 'Inbox']
        calendar_id = [project.id for project in self.api.projects if project.name == 'calendar']
        self.inbox_id = inbox_id[0]
        self.hospital_id = hospital_id[0]
        self.calendar_project_id = calendar_id[0]

        self.hospital_label = 'hospital'
        hospital_label_ids = [label.id for label in self.api.labels if label.name == 'hospital']
        self.calendar_label = 'calendar'



        assert (len(hospital_label_ids) == 1)
        self.hospital_label_id = hospital_label_ids[0]


        self.hospital = self.get_hospital()

        self.missing_due = self.get_no_duedate()
        print("Missing due")
        print(self.missing_due)

        print("Test notes:")
        self.test_notes = self.get_test_notes()
        print(self.test_notes)
        ##### Moving tasks:
        section_id= self.section_heaven_id

    def move_task(self, task_id: str, project_id: str) -> bool:
        body = {
            "commands": [
                {
                    "type": "item_move",
                    "args": {"id": task_id, "project_id": project_id},
                    "uuid": uuid4().hex,
                },
            ],
        }
        response = requests.post(
            "https://api.todoist.com/sync/v9/sync",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json=body,
        )
        return response.ok
    def get_test_notes(self):
        test = []
        for item in self.api.notes:
            if item.project_id == self.testing_id: #
                test.append(item)
        return test

# Funciones para asignar etiquetas de hospital a tareas con numeros de historia o palabras clave

    def get_hospital(self):
        hospital = []
        for item in self.api.notes:
            if re.search(r'[0-9]{5}|revis|AP |ap |PV |jefe |cultiv|cura|herida|biops|comit|coment', item.content) and item.parent_id is None and self.hospital_label not in item.labels and self.inbox_id == item.project_id : #
                if re.search(r'http', item.content):
                    pass
                else:
                    hospital.append(item)
        return hospital

    def update_hospital(self):
        for item in self.hospital:
            new_labels = item.labels
            new_labels.append(self.hospital_label)
            self.api.update_task(task_id = item.id, labels = new_labels )
            self.move_task(task_id=item.id, project_id=self.hospital_id)
            #project_id = self.hospital_id  faltaría mover las tareas al proyecto hospital

    # Dar fecha a aquellas tareas que se hayan añadido a la bandeja de entrada pero que no sean subtareas.
    def get_no_duedate(self):
        missing_due = []

        for item in self.api.notes:
            if self.inbox_id == item.project_id:

                if item.parent_id is None and item.due is None: #sin fecha y que no sean subtasks en el Inbox
                    missing_due.append(item)

        return missing_due

    def update_missing_due(self):
        for item in self.missing_due:
            due_date = "today"
            self.api.update_task(task_id = item.id, due_string = due_date)

    def send_to_calendar(self):
        for item in self.api.notes:
            if ((item.priority >= 3 ) or (self.calendar_label in item.labels )) and self.calendar_project_id != item.project_id and item.due is not None :
                new_labels = item.labels
                new_labels.append(self.calendar_label)
                self.api.update_task(task_id=item.id, labels=new_labels)
                self.move_task(task_id=item.id, project_id=self.calendar_project_id)

def main():
    todo = Todoist_program()
    todo.update_missing_due()
    todo.update_hospital()
    todo.send_to_calendar()
    print("run succesfully!")

if __name__ == '__main__':
    main()
