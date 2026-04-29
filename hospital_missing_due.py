import os
import re
import json
import logging
from datetime import datetime, time, timezone
from uuid import uuid4
import requests
import csv
import random

from todoist_api_python.api import TodoistAPI

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TODOIST_DATE_FORMAT = "%Y-%m-%d"
red_dot = "\U0001f534"


def get_token():
    token = os.getenv("TODOIST_APIKEY")
    if not token:
        raise Exception("Please set the API token in environment variable TODOIST_APIKEY.")
    return token


TOKEN = get_token()


def flatten_paginated(iterator):
    """Flatten paginated results from todoist-api-python v3.x/v4.x."""
    items = []
    for page in iterator:
        items.extend(page)
    return items


def due_has_time(due):
    """In current Todoist SDK models, due.date is date-only or datetime-with-time."""
    return isinstance(due.date, datetime)


class Todoist_program(object):
    def __init__(self):
        self.random_quote = self.load_random_quote()
        if self.random_quote:
            print(self.random_quote)

        self.api = TodoistAPI(TOKEN)
        self.refresh_cache()

        self.testing_id = self.get_project_id("testing")
        self.section_heaven_id = self.get_section_id("Heaven")
        self.hospital_id = self.get_project_id("hospital")
        self.inbox_id = self.get_project_id("Inbox")
        self.alexa_id = self.get_project_id("Alexa")
        self.alexa_id_2 = self.get_project_id("Alexa2")
        self.nidito_id = self.get_project_id("Nidito 🏡")
        self.calendar_project_id = self.get_project_id("calendar")

        self.hospital_label = "hospital"
        self.calendar_label = "calendar"

        hospital_label_ids = [label.id for label in self.api.labels if label.name == "hospital"]
        alexa_label_ids = [label.id for label in self.api.labels if label.name == "Alexa"]

        assert len(alexa_label_ids) == 1
        self.alexa_label = alexa_label_ids[0]
        print(self.alexa_label)

        assert len(hospital_label_ids) == 1
        self.hospital_label_id = hospital_label_ids[0]

        self.hospital = self.get_hospital()
        self.missing_due = self.get_no_duedate()

        print("Missing due")
        print(self.missing_due)

        print("Test notes:")
        self.test_notes = self.get_test_notes()

    def load_random_quote(self):
        quotes = []
        try:
            with open("quotes.csv", "r", encoding="utf-8", newline="") as file:
                reader = csv.reader(file, delimiter='"')
                for row in reader:
                    if row:
                        quotes.append(row)
        except FileNotFoundError:
            logger.warning("quotes.csv not found; quote update skipped.")
            return None

        if len(quotes) > 1:
            quotes = quotes[1:]

        return random.choice(quotes) if quotes else None

    def refresh_cache(self):
        """Refresh local snapshots after API writes."""
        self.api.notes = flatten_paginated(self.api.get_tasks())
        self.api.projects = flatten_paginated(self.api.get_projects())
        self.api.labels = flatten_paginated(self.api.get_labels())
        self.api.sections = flatten_paginated(self.api.get_sections())

    def get_project_id(self, name):
        matches = [project.id for project in self.api.projects if project.name == name]
        if not matches:
            raise ValueError(f"Todoist project not found: {name}")
        return matches[0]

    def get_section_id(self, name):
        matches = [section.id for section in self.api.sections if section.name == name]
        if not matches:
            raise ValueError(f"Todoist section not found: {name}")
        return matches[0]

    def sync_command(self, command_type, args):
        """Run one Todoist Sync API v1 command and fail loudly if Todoist reports an error."""
        command_uuid = str(uuid4())
        command = {
            "type": command_type,
            "uuid": command_uuid,
            "args": args,
        }

        response = requests.post(
            "https://api.todoist.com/api/v1/sync",
            headers={"Authorization": f"Bearer {TOKEN}"},
            data={"commands": json.dumps([command])},
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        status = payload.get("sync_status", {}).get(command_uuid)

        if status != "ok":
            raise RuntimeError(
                f"Todoist sync command failed. "
                f"command={command_type}, args={args}, status={status}, payload={payload}"
            )

        return payload

    def move_task(self, task_id: str, project_id: str) -> bool:
        self.sync_command(
            "item_move",
            {
                "id": str(task_id),
                "project_id": str(project_id),
            },
        )
        return True

    def get_test_notes(self):
        test = []
        for item in self.api.notes:
            if item.project_id == self.testing_id:
                test.append(item)
        return test

    def get_calendar_tasks(self):
        calendar = []
        for item in self.api.notes:
            if item.project_id == self.calendar_project_id:
                calendar.append(item)
        return calendar

    def assign_time_to_calendar_tasks(self):
        self.refresh_cache()
        self.calendar_tasks = self.get_calendar_tasks()

        for item in self.calendar_tasks:
            if (
                item.parent_id is None
                and item.due
                and item.due.date
                and not due_has_time(item.due)
                and not item.content.strip().endswith("_")
                and item.due.date.year > 2024
                and item.due.is_recurring is False
            ):
                due_dt = datetime.combine(item.due.date, time(8, 45, 0), tzinfo=timezone.utc)
                self.api.update_task(task_id=item.id, due_datetime=due_dt)

    def assign_random_quote(self):
        if not self.random_quote:
            return

        for item in self.api.notes:
            if re.search(r"📜 DQ:", item.content):
                print(item.id)
                print(item.content)
                quote = self.random_quote[0].replace('"', "").replace("'", "")
                print(quote)
                self.api.update_task(task_id=item.id, content="📜 DQ: " + quote)

    def assign_imr_icon(self):
        for item in self.api.notes:
            if item.content == "IMR":
                self.api.update_task(task_id=item.id, content="💼 IMR")

    def assign_VILANOVA_icon(self):
        for item in self.api.notes:
            if item.content == "VILANOVA":
                self.api.update_task(task_id=item.id, content="🟢 VILANOVA")
            if item.content == "DKV" or item.content == "DKV Meridiana":
                self.api.update_task(task_id=item.id, content="🔴 " + item.content)

    def get_hospital(self):
        hospital = []
        for item in self.api.notes:
            if (
                re.search(
                    r"[0-9]{5}|revis|AP |ap |PV |jefe |cultiv|cura|herida|biops|comit|coment",
                    item.content,
                )
                and item.parent_id is None
                and self.hospital_label not in (item.labels or [])
                and self.inbox_id == item.project_id
            ):
                if re.search(r"http", item.content):
                    pass
                else:
                    hospital.append(item)
        return hospital

    def update_hospital(self):
        moved = 0
        for item in self.hospital:
            labels = list(item.labels or [])

            if self.hospital_label not in labels:
                labels.append(self.hospital_label)
                self.api.update_task(task_id=item.id, labels=labels)

            self.move_task(task_id=item.id, project_id=self.hospital_id)
            moved += 1

        if moved:
            self.refresh_cache()

        return moved

    def get_no_duedate(self):
        missing_due = []

        for item in self.api.notes:
            if self.inbox_id == item.project_id:
                if item.parent_id is None and item.due is None:
                    missing_due.append(item)

        for item in self.api.notes:
            if self.alexa_id == item.project_id and item.due is None:
                missing_due.append(item)
            if self.alexa_id_2 == item.project_id and item.due is None:
                missing_due.append(item)

        return missing_due

    def update_missing_due(self):
        updated = 0
        for item in self.missing_due:
            self.api.update_task(task_id=item.id, due_string="today")
            updated += 1

        if updated:
            self.refresh_cache()

        return updated

    def send_to_calendar(self):
        self.refresh_cache()

        moved = 0
        for item in list(self.api.notes):
            labels = list(item.labels or [])

            should_move = (
                (item.priority == 4 or self.calendar_label in labels)
                and item.project_id not in {self.nidito_id, self.calendar_project_id}
                and item.due is not None
            )

            if not should_move:
                continue

            if self.calendar_label not in labels:
                labels.append(self.calendar_label)
                self.api.update_task(task_id=item.id, labels=labels)

            self.move_task(task_id=item.id, project_id=self.calendar_project_id)
            moved += 1
            logger.info("Moved task to calendar: %s | %s", item.id, item.content)

        if moved:
            self.refresh_cache()

        print(f"Moved to calendar: {moved}")
        return moved


def main():
    todo = Todoist_program()

    todo.update_missing_due()
    todo.update_hospital()
    todo.assign_random_quote()
    # todo.assign_imr_icon()
    # todo.assign_VILANOVA_icon()
    todo.send_to_calendar()
    todo.assign_time_to_calendar_tasks()

    print("run successfully!")


if __name__ == "__main__":
    main()
