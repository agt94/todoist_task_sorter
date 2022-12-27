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

api_2 = TodoistAPI(get_token())
try:
    projects = api_2.get_projects()
    #print(projects)
except Exception as error:
    print(error)



class Todoist(object):
    def __init__(self):
        self.api = TodoistAPI(get_token())

        #print(dir(self.api))
        #self.api.sync()
        self.api.notes = self.api.get_tasks()
        self.api.projects = self.api.get_projects()
        print(self.api.projects)
        print(type(self.api.projects ))
        hospital_id = [project['id'] for project in self.api.projects if project['name'] == 'hospital']

        inbox_id = [project['id'] for project in self.api.projects if project['name'] == 'Inbox']

        self.inbox_id = inbox_id[0]
        self.hospital_id = hospital_id[0]
        print(inbox_id)
        print(hospital_id)

        hospital_label_ids = [label['id'] for label in self.api.state['labels'] if label['name'] == 'hospital']
        calendar_label_ids = [label['id'] for label in self.api.state['labels'] if label['name'] == 'calendar']
        to_calendar_label_ids = [label['id'] for label in self.api.state['labels'] if label['name'] == 'to_calendar']
        #in_calendar_label_ids = [label['id'] for label in self.api.state['labels'] if label['name'] == 'in_calendar']


        assert (len(hospital_label_ids) == 1)
        self.hospital_label_id = hospital_label_ids[0]
        self.hospital = self.get_hospital()

        calendar_project_id = [project['id'] for project in self.api.state['projects'] if project['name'] == 'calendar']
        self.calendar_project_id = calendar_project_id[0]
        self.calendar_label_id = calendar_label_ids[0]
        self.to_calendar_label_id = to_calendar_label_ids[0]
        #self.in_calendar_label_id = in_calendar_label_ids[0]
        self.calendar = self.get_calendar()
        self.tasks_in_calendar =self.get_tasks_calendar_project()
        self.missing_due = self.get_no_duedate()
# Funciones para asignar etiquetas de hospital a tareas con numeros de historia o palabras clave
    def get_hospital(self):
        hospital = []
        for item in self.api.state['items']:
            if re.search(r'[0-9]{5}|revis|AP |ap |PV |jefe |cultiv|cura|herida|biops|comit|coment', item['content']) and item['parent_id'] is None and self.hospital_label_id not in item['labels'] and self.inbox_id == item['project_id'] : #
                if re.search(r'http', item['content']):
                    pass
                else:
                    hospital.append(item)

        
        return hospital

    def update_hospital(self):
        for item in self.hospital:
            new_labels = item['labels']
            new_labels.append(self.hospital_label_id)
            item.update(labels=new_labels )
            
            item.move(project_id = self.hospital_id)
            self.api.commit()
        self.api.commit()
# Asignar la @calendar a tareas de alta prioridad para que mediante un applet ppuedan aparecer en calendario de Google y en widget.
    def get_calendar(self):
        calendar = []
        for item in self.api.state['items']:
            if (item['priority'] >2 or self.to_calendar_label_id in item['labels']) and item['due'] is not None and self.calendar_label_id not in item['labels'] and  self.calendar_project_id  != item['project_id']: #tareas prioritarias y que no tengan ya asignada esa etiqueta
                calendar.append(item)

        return calendar
    def get_tasks_calendar_project(self):
        tasks_in_calendar = []
        for item in self.api.state['items']:
            if self.calendar_project_id  == item['project_id'] and item['checked']== 0: #tareas en el proyecto calendar y no completadas
                tasks_in_calendar.append(item)

        return tasks_in_calendar

    def update_calendar(self):

        for item in self.calendar:
            #print(item['due'])
            #print(item['due']['date'])
            #print(item['due']['datetime'])
            #print(item['due']['is_recurring'])
            #print(item['due']['string'])
            #print(item['due']['lang'])
            try:

                ############### eliminar______________________________________________
                new_labels = item['labels']
                #new_labels.append(self.in_calendar_label_id)
                task = self.api.add_item(
                    content= item['content']+"_",
                    #due_date={"string": "today"},
                    date_string = item['due']['string'],
                    date_lang = 'es',
                    #due = {"string": "today"},
                    priority= item['priority'],
                    project_id = self.calendar_project_id,
                    labels = new_labels
                )
                due_date_long = {'date': item['due']['date'], 'is_recurring': item['due']['is_recurring'] ,'lang': item['due']['lang'],
                          'string':item['due']['string'], 'timezone': item['due']['timezone']

                          }
                #due_date = {"string": "today"}
                #task.update(due = due_date_long)
                self.api.commit()
                #print(task)############### eliminar______________________________________________
                new_labels = item['labels']
                new_labels.append(self.calendar_label_id)
                item.update(labels=new_labels)

            except Exception as error:
                print(error)
        self.api.commit()

    def delete_calendar(self): #closes tasks for which the parent task has been completed or changed name
        calendar_labelled_content = []
        calendar_labelled_notes = []
        for item in self.api.state['items']:
            if self.calendar_label_id in item['labels'] and  self.calendar_project_id != item['project_id']and item['checked']== 0:
                calendar_labelled_content.append(item['content'])
                calendar_labelled_notes.append(item)
                        
        #print(calendar_labelled_content)
        for item in self.tasks_in_calendar: #toma las tareas del proyecto calendar
           # print(item['content'])
            #print(len(self.tasks_in_calendar))
            #print(calendar_labelled_content)
            #print(item['content'][:-1] not in calendar_labelled_content)


            if item['content'][:-1] not in calendar_labelled_content:
               # print(item['content'])
                item.update(checked=1)
                #item.update(is_deleted=1)
                self.api.commit()


            else: #corregir cuando se reprograma una tarea a otra fecha para que le siga en el proyecto calendar

                original_twin = calendar_labelled_notes[calendar_labelled_content.index(item['content'][:-1])]
                if original_twin['due'] != item['due']:
                    #print(item['content'])
                    #print(item['due'])
                    #print(original_twin['content'])
                    #print(original_twin['due'])
                    item.update_date_complete(due=original_twin['due'])

        self.api.commit()

    def create_calendar(self):  # creates calendar tasks if parent task is updated
        calendar_labelled_content = []
        calendar_labelled_notes = []
        tasks_in_calendar_content = []
        self.tasks_in_calendar = self.get_tasks_calendar_project()

        for item in self.api.state['items']:
            if self.calendar_label_id in item['labels'] and self.calendar_project_id != item['project_id']and item['checked']== 0 and item['due'] is not None: #corrige el error al quitarle la fecha a una tarea parent pero nos dejamos la etiqueta calendar
                calendar_labelled_content.append(item['content'])
                calendar_labelled_notes.append(item)

        for item in self.tasks_in_calendar:
            tasks_in_calendar_content.append(item['content'])

        tasks_needing_calendar_copy = []
        for item in calendar_labelled_notes:

            if item['content']+"_" not in tasks_in_calendar_content:
                tasks_needing_calendar_copy.append(item)

        for item in tasks_needing_calendar_copy:
            new_labels = item['labels']
            try:
                task = self.api.add_item(
                    content=item['content'] + "_",

                    date_string=item['due']['string'],
                    date_lang='es',

                    priority=item['priority'],
                    project_id=self.calendar_project_id,
                    labels=new_labels
                )
            except Exception as error:
                print(error)
                print(item)
            #new_labels = item['labels']
            #new_labels.append(self.calendar_label_id)
            #task.update(labels=new_labels)
            self.api.commit()






    # Dar fecha a aquellas tareas que se hayan añadido a la bandeja de entrada pero que no sean subtareas.
    def get_no_duedate(self):
        missing_due = []

        for item in self.api.state['items']:
            if self.inbox_id == item['project_id']:

                if  item['parent_id'] is None and item['due'] is None: #sin fecha y que no sean subtasks
                    missing_due.append(item)

        return missing_due

    def update_missing_due(self):
        for item in self.missing_due:


                due_date = {"string": "today"}
                item.update(due=due_date)


        self.api.commit()

def main():
    todo = Todoist()
    todo.update_missing_due()
    todo.update_hospital()


    todo.update_calendar()

    todo.create_calendar()
    todo.delete_calendar()
    print("run succesfully!")

if __name__ == '__main__':
    main()
