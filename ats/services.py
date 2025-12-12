from django.db import transaction
from .models import Application, ApplicationHistory
from .workflow import validate_transition


def change_application_stage(application, new_stage, actor):

    if not validate_transition(application.stage, new_stage):
        raise ValueError("Invalid workflow stage transition")

    with transaction.atomic():
        old_stage = application.stage

        application.stage = new_stage
        application.save()

        ApplicationHistory.objects.create(
            application=application,
            previous_stage=old_stage,
            new_stage=new_stage,
            changed_by=actor,
        )
