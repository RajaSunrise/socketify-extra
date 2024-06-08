import argparse
import sys
import importlib
import inspect
import os
import pkgutil

class BaseCommand:
    help = ""
    name = None
    description = None
    usage = None

    def add_arguments(self, parser):
        pass

    def handle(self, args):
        pass

    def create_parser(self, subparser):
        parser = subparser.add_parser(
            name=self.name,
            description=self.description,
            usage= self.usage
        )
        parser.set_defaults(command=self.name)
        self.add_arguments(parser)
        return parser
    

def find_utility(management_dir=__package__[0]):
    command_dir = os.path.join(
        management_dir, "commands"
    )
    return [
        name
        for _, name, is_pkg in pkgutil.iter_modules([command_dir])
        if not is_pkg and not name.startswith("_")
    ]


class Utility:
    def __init__(self, argv=None):
        self.argv = argv or sys.argv[:]
    
    def get_command(self, command_name):
        command_classes = [
            cls for cls in BaseCommand.__subclasses__() if cls.name == command_name
        ]

        return command_classes[0]() if command_classes else None
    
    def create_subparser(self, subparser, command_name):
        modole = importlib.import_module(
            f".commands.{command_name}", package="socketify_extra.__main__"
        )
        for _, command_class in inspect.getmembers(modole, inspect.isclass):
             if(
                issubclass(command_class, BaseCommand)
                and command_class is not BaseCommand
             ):
              command_class().create_parser(subparser)

    
    def execute(self):
        parser = argparse.ArgumentParser(
            description="""
            socketify-extra for management Utility,
            socketify-extra used socketify for API and MVC,
            the concept socketify-extra is the same as socketify,
            only fixing bug from socketify
            """,
            usage="socketify-admin <command> [options]",
        )

        subparser = parser.add_subparsers(title="Command", dest="command")
        for command_name in find_utility():
            self.create_subparser(subparser, command_name)
        args = parser.parse_args(self.argv[1:])
        if not args.command:
           print(parser.print_help(), end="\n\n")
           parser.exit()
        command = self.get_command(args.command)
        command.handle(args)


def execute_command():
    manager = Utility()
    manager.execute()
    