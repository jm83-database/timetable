"""Azure Functions timer for class preparation reminders."""

import logging
import os
from datetime import datetime, timezone

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import ClientSecretCredential, ManagedIdentityCredential

from config import Config
from services.cosmos_service import CosmosStorage
from services.reminder_sender import KOREA_TIME, run_reminder_cycle
from services.reminder_storage import CosmosReminderStorage


app = func.FunctionApp()


@app.timer_trigger(schedule='0 0 * * * *', arg_name='timer', use_monitor=True, run_on_startup=False)
def reminder_timer(timer: func.TimerRequest):
    verification = os.environ.get('REMINDER_VALIDATE_ONLY', '').lower() == 'true'
    if not verification and datetime.now(timezone.utc).astimezone(KOREA_TIME).hour < 9:
        return
    sender = 'elixirr@elixirr.co.kr'
    endpoint = os.environ['COSMOS_DB_ENDPOINT']
    credential = ManagedIdentityCredential(client_id=os.environ.get('AZURE_CLIENT_ID'))
    client = CosmosClient(endpoint, credential=credential)
    container = client.get_database_client(Config.COSMOS_DATABASE_NAME).get_container_client(Config.COSMOS_CONTAINER_NAME)
    if verification:
        courses = CosmosStorage(container).get_all_courses()
        reminders = CosmosReminderStorage(container)
        contacts = reminders.contacts()
        reminders.assignment('__verification__', '__verification__')
        reminders.deliveries('__verification__', '__verification__')
        logging.info('Reminder verification succeeded: %s courses, %s contacts', len(courses), len(contacts))
        return
    mail_credential = ClientSecretCredential(
        tenant_id=os.environ['MAIL_TENANT_ID'],
        client_id=os.environ['MAIL_CLIENT_ID'],
        client_secret=os.environ['MAIL_CLIENT_SECRET'],
    )
    token = mail_credential.get_token('https://graph.microsoft.com/.default').token
    count = run_reminder_cycle(CosmosStorage(container).get_all_courses(),
                               CosmosReminderStorage(container), sender, token)
    logging.info('Reminder cycle completed: %s attempts', count)