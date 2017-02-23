# Importing sample Fusion Command
# Could import multiple Command definitions here
from .VentMakerCommand import VentMakerCommand

commands = []
command_definitions = []

# Define parameters for vent maker command
cmd = {
    'cmd_name': 'Vent Maker',
    'cmd_description': 'Demo Command 1 Description',
    'cmd_resources': './resources',
    'cmd_id': 'cmdID_ventMaker',
    'workspace': 'FusionSolidEnvironment',
    'toolbar_panel_id': 'SolidScriptsAddinsPanel',
    'class': VentMakerCommand
}
command_definitions.append(cmd)

# Set to True to display various useful messages when debugging your app
debug = False

# Don't change anything below here:
for cmd_def in command_definitions:
    command = cmd_def['class'](cmd_def, debug)
    commands.append(command)


def run(context):
    for run_command in commands:
        run_command.on_run()


def stop(context):
    for stop_command in commands:
        stop_command.on_stop()
