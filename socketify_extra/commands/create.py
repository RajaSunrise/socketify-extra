from pathlib import Path
from ..__main__ import BaseCommand


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_HANDLER = BASE_DIR / "templatetags"


class CreateProject(BaseCommand):
    name = "create"
    description = "create your project mvc or API"
    usage = "create [ mvc|api ]"

    def add_arguments(self, parser):
          parser.add_arguments(
            "project",
            choices=["mvc", "api"],
            help="Project of the app"
          )
    def handle(sekf, args):
        template_handler = TEMPLATE_HANDLER()
        template_handler.create_project_files(args)
    
    def _verbose(self, message: str):
       print(message)