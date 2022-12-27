import os
import re
import logging
from datetime import datetime
from dateutil import tz
#from todoist.api import TodoistAPI
#from todoist.managers.notes import NotesManager
#from todoist.managers.items import ItemsManager
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TODOIST_DATE_FORMAT = "%Y-%m-%d"

red_dot = '\U0001f534'

def get_token():
    token = os.getenv('TODOIST_APIKEY')
    if not token:
        raise Exception('Please set the API token in environment variable.')
    return token

from todoist_api_python.api import TodoistAPI

#https://github.com/Doist/todoist-api-python/issues/8  move tasks to different project

class Todoist_program(object):
    def __init__(self):
        self.api = TodoistAPI(get_token())

        #print(dir(self.api))
        #self.api.sync()
        self.api.notes = self.api.get_tasks()
        self.api.projects = self.api.get_projects()
        self.api.labels = self.api.get_labels()
        print(self.api.labels)
        print("Print inbox:")
        print((self.api.projects[0].name))
        print(type(self.api.projects ))

        hospital_id = [project.id for project in self.api.projects if project.name == 'hospital']

        inbox_id = [project.id for project in self.api.projects if project.name == 'Inbox']

        self.inbox_id = inbox_id[0]
        self.hospital_id = hospital_id[0]
        print(self.inbox_id)
        print(self.hospital_id)

        self.hospital_label = 'hospital'
        hospital_label_ids = [label.id for label in self.api.labels if label.name == 'hospital']
        self.calendar_label = 'calendar'



        assert (len(hospital_label_ids) == 1)
        self.hospital_label_id = hospital_label_ids[0]
        print("Print hospital label_id ")
        print(self.hospital_label_id)

        self.hospital = self.get_hospital()
        print(self.hospital)

        self.missing_due = self.get_no_duedate()
        print("Missing due")
        print(self.missing_due)

    def move_task(task, project_id: str = None, section_id: str = None, \
                  parent_id: str = None, order: int = None):
        """'Moves' a task to a different project/ section or parent by creating a \
            identical new one and deleting the old one.

        Args:
            task (TodoistAPI task object): task-object of the task to move.
            project_id (str, optional): Where the task should be moved to. \
                Defaults to None.
            section_id (str, optional): Where the task should be moved to. \
                Defaults to None.
            parent_id (str, optional): Where the task should be moved to. \
                Defaults to None.
            order (int, optional): Where the task should be moved to. \
                Defaults to None.

        Returns:
            task (TodoistAPI task object): If successful. Else returns None.
        """
        api = TodoistAPI(get_token())
        try:
            comments = api.get_comments(task_id=task.id)
        except Exception as error:
            print(error)
            return False
        else:
            try:
                new_task = api.add_task(
                    content=task.content,
                    description=task.description,
                    labels=task.labels,
                    priority=task.priority,
                    due=task.due,
                    assignee_id=task.assignee_id,
                    project_id=project_id,
                    section_id=section_id,
                    parent_id=parent_id,
                    order=order
                )
            except Exception as error:
                print(error)
                return False
            else:
                for comment in comments:
                    try:
                        created_comment = api.add_comment(
                            content=comment.content,
                            task_id=task.id,
                            attachment=comment.attachment
                        )
                    except Exception as error:
                        print(error)
                        return False
                    else:
                        try:
                            api.delete_task(task_id=task.id)
                        except Exception as error:
                            print(error)
                            return False
                        else:
                            return new_task

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
            #project_id = self.hospital_id  faltaría mover las tareas al proyecto hospital

    # Dar fecha a aquellas tareas que se hayan añadido a la bandeja de entrada pero que no sean subtareas.
    def get_no_duedate(self):
        missing_due = []

        for item in self.api.notes:
            if self.inbox_id == item.project_id:

                if  item.parent_id is None and item.due is None: #sin fecha y que no sean subtasks
                    missing_due.append(item)

        return missing_due

    def update_missing_due(self):
        for item in self.missing_due:
            due_date = {"string": "today"}
            self.api.update_task(task_id = item.id, due = due_date)


def main():
    todo = Todoist_program()
    todo.update_hospital()
    todo.update_missing_due()

    print("run succesfully!")

if __name__ == '__main__':
    main()
