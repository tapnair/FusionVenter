import adsk.core, adsk.fusion, traceback

handlers = [] 


# Removes the command control and definition 
def clean_up_nav_drop_down_command(cmd_id, dc_cmd_id):
    
    obj_array_nav = []
    drop_down_control = command_control_by_id_in_nav_bar(dc_cmd_id)
    command_control_nav = command_control_by_id_in_drop_down(cmd_id, drop_down_control)
        
    if command_control_nav:
        obj_array_nav.append(command_control_nav)
    
    command_definition_nav = command_definition_by_id(cmd_id)
    if command_definition_nav:
        obj_array_nav.append(command_definition_nav)
        
    for obj in obj_array_nav:
        destroy_object(obj)


# Finds command definition in active UI
def command_definition_by_id(cmd_id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    if not cmd_id:
        ui.messageBox('Command Definition:  ' + cmd_id + '  is not specified')
        return None
    command_definitions = ui.commandDefinitions
    command_definition = command_definitions.itemById(cmd_id)
    return command_definition


# Find command control by id in nav bar
def command_control_by_id_in_nav_bar(cmd_id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    if not cmd_id:
        ui.messageBox('Command Control:  ' + cmd_id + '  is not specified')
        return None
    
    toolbars_ = ui.toolbars
    nav_toolbar = toolbars_.itemById('NavToolbar')
    nav_toolbar_controls = nav_toolbar.controls
    cmd_control = nav_toolbar_controls.itemById(cmd_id)
    
    if cmd_control is not None:
        return cmd_control


# Get a command control in a Nav Bar Drop Down
def command_control_by_id_in_drop_down(cmd_id, drop_down_control):
    cmd_control = drop_down_control.controls.itemById(cmd_id)
    
    if cmd_control is not None:
        return cmd_control


# Destroys a given object
def destroy_object(obj_to_be_deleted):
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    if ui and obj_to_be_deleted:
        if obj_to_be_deleted.isValid:
            obj_to_be_deleted.deleteMe()
        else:
            ui.messageBox(obj_to_be_deleted.id + 'is not a valid object')


# Returns the id of a Toolbar Panel in the given Workspace
def toolbar_panel_by_id_in_workspace(workspace_id, toolbar_panel_id):
    app = adsk.core.Application.get()
    ui = app.userInterface
        
    all_workspaces = ui.workspaces
    this_workspace = all_workspaces.itemById(workspace_id)
    all_toolbar_panels = this_workspace.toolbarPanels
    toolbar_panel = all_toolbar_panels.itemById(toolbar_panel_id)
    
    return toolbar_panel


# Returns the Command Control from the given panel
def command_control_by_id_in_panel(cmd_id, toolbar_panel):
    
    app = adsk.core.Application.get()
    ui = app.userInterface
    
    if not cmd_id:
        ui.messageBox('Command Control:  ' + cmd_id + '  is not specified')
        return None
    
    cmd_control = toolbar_panel.controls.itemById(cmd_id)
    
    if cmd_control is not None:
        return cmd_control


# Base Class for creating Fusion 360 Commands
class Fusion360CommandBase:
    
    def __init__(self, cmd_def, debug):

        self.commandName = cmd_def.get('commandName', 'Default Command Name')
        self.commandDescription = cmd_def.get('commandDescription', 'Default Command Description')
        self.commandResources = cmd_def.get('commandResources', './resources')
        self.cmdId = cmd_def.get('cmdId', 'Default Command ID')
        self.workspace = cmd_def.get('workspace', 'FusionSolidEnvironment')
        self.toolbarPanelID = cmd_def.get('toolbarPanelID', 'SolidScriptsAddinsPanel')
        self.DC_CmdId = cmd_def.get('DC_CmdId', 'Default_DC_CmdId')
        self.DC_Resources = cmd_def.get('DC_Resources', './resources')
        self.command_in_nav_bar = cmd_def.get('command_in_nav_bar', False)
        self.debug = debug

        
        # global set of event handlers to keep them referenced for the duration of the command
        self.handlers = []
        
        try:
            self.app = adsk.core.Application.get()
            self.ui = self.app.userInterface

        except RuntimeError:
            if self.ui:
                self.ui.messageBox('Could not get app or ui: {}'.format(traceback.format_exc()))
    
    def on_preview(self, command, inputs, args):
        pass 

    def on_destroy(self, command, inputs, reason):
        pass   

    def on_input_changed(self, command, inputs, changed_input):
        pass

    def on_execute(self, command, inputs):
        pass

    def on_create(self, command, inputs):
        pass

    # TODO Continue variable cleanup from here
    def on_run(self):
        global handlers

        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            commandDefinitions_ = ui.commandDefinitions
            
            # Add command to drop down in nav bar
            if self.command_in_nav_bar:
                
                toolbars_ = ui.toolbars
                navBar = toolbars_.itemById('NavToolbar')
                toolbarControlsNAV = navBar.controls
                
                dropControl = toolbarControlsNAV.itemById(self.DC_CmdId) 
                
                if not dropControl:             
                    dropControl = toolbarControlsNAV.addDropDown(self.DC_CmdId, self.DC_Resources, self.DC_CmdId) 
                
                controls_to_add_to = dropControl.controls
                
                newControl_ = toolbarControlsNAV.itemById(self.cmdId)
            
            # Add command to workspace panel
            else:
                toolbarPanel_ = toolbar_panel_by_id_in_workspace(self.workspace, self.toolbarPanelID)
                controls_to_add_to = toolbarPanel_.controls               
                newControl_ = controls_to_add_to.itemById(self.cmdId)
            
            # If control does not exist, create it
            if not newControl_:
                commandDefinition_ = commandDefinitions_.itemById(self.cmdId)
                if not commandDefinition_:
                    commandDefinition_ = commandDefinitions_.addButtonDefinition(self.cmdId, self.commandName, self.commandDescription, self.commandResources)
                
                onCommandCreatedHandler_ = CommandCreatedEventHandler(self)
                commandDefinition_.commandCreated.add(onCommandCreatedHandler_)
                handlers.append(onCommandCreatedHandler_)
                
                newControl_ = controls_to_add_to.addCommand(commandDefinition_)
                newControl_.isVisible = True
        
        except:
            if ui:
                ui.messageBox('AddIn Start Failed: {}'.format(traceback.format_exc()))

    def onStop(self):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface

            # Remove command from nav bar
            if self.command_in_nav_bar:
                dropDownControl_ = command_control_by_id_in_nav_bar(self.DC_CmdId)
                commandControlNav_ = command_control_by_id_in_drop_down(self.cmdId, dropDownControl_)
                commandDefinitionNav_ = command_definition_by_id(self.cmdId)
                destroy_object(commandControlNav_)
                destroy_object(commandDefinitionNav_)
                
                if dropDownControl_.controls.count == 0:
                    commandDefinition_DropDown = command_definition_by_id(self.DC_CmdId)
                    destroy_object(dropDownControl_)
                    destroy_object(commandDefinition_DropDown)
            
            # Remove command from workspace panel
            else:
                toolbarPanel_ = toolbar_panel_by_id_in_workspace(self.workspace, self.toolbarPanelID)
                commandControlPanel_ = command_control_by_id_in_panel(self.cmdId, toolbarPanel_)
                commandDefinitionPanel_ = command_definition_by_id(self.cmdId)
                destroy_object(commandControlPanel_)
                destroy_object(commandDefinitionPanel_)

        except:
            if ui:
                ui.messageBox('AddIn Stop Failed: {}'.format(traceback.format_exc()))


class ExecutePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self, myObject):
        super().__init__()
        self.myObject_ = myObject
        self.args = None

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            command_ = args.firingEvent.sender
            inputs_ = command_.commandInputs
            if self.myObject_.debug:
                ui.messageBox('***Debug *** Preview: {} execute preview event triggered'.format(command_.parentCommandDefinition.id))

            # self.args.isValidResult = True
            self.myObject_.on_preview(command_, inputs_, args)
            # valid_result = True
        except:
            if ui:
                ui.messageBox('Input changed event failed: {}'.format(traceback.format_exc()))

class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, myObject):
        super().__init__()
        self.myObject_ = myObject
    def notify(self, args):
        # Code to react to the event.
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            command_ = args.firingEvent.sender
            inputs_ = command_.commandInputs
            reason_ = args.terminationReason
            if self.myObject_.debug:
                ui.messageBox('***Debug ***Command: {} destroyed'.format(command_.parentCommandDefinition.id))
                ui.messageBox("***Debug ***Reason for termination= " + str(reason_))
            self.myObject_.on_destroy(command_, inputs_, reason_)
            
        except:
            if ui:
                ui.messageBox('Input changed event failed: {}'.format(traceback.format_exc()))

class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, myObject):
        super().__init__()
        self.myObject_ = myObject
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            command_ = args.firingEvent.sender
            inputs_ = command_.commandInputs
            changedInput_ = args.input 
            if self.myObject_.debug:
                ui.messageBox('***Debug ***Input: {} changed event triggered'.format(command_.parentCommandDefinition.id))
                ui.messageBox('***Debug ***The Input: {} was the command'.format(changedInput_.id))
   
            self.myObject_.on_input_changed(command_, inputs_, changedInput_)
        except:
            if ui:
                ui.messageBox('Input changed event failed: {}'.format(traceback.format_exc()))

class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, myObject):
        super().__init__()
        self.myObject_ = myObject
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            command_ = args.firingEvent.sender
            inputs_ = command_.commandInputs
            if self.myObject_.debug:
                ui.messageBox('***Debug ***command: {} executed successfully'.format(command_.parentCommandDefinition.id))
            self.myObject_.on_execute(command_, inputs_)
            
        except:
            if ui:
                ui.messageBox('command executed failed: {}'.format(traceback.format_exc()))

class CommandCreatedEventHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, myObject):
        super().__init__()
        self.myObject_ = myObject
    def notify(self, args):
        try:
            global handlers
            
            app = adsk.core.Application.get()
            ui = app.userInterface
            command_ = args.command
            inputs_ = command_.commandInputs
            
            onExecuteHandler_ = CommandExecuteHandler(self.myObject_)
            command_.execute.add(onExecuteHandler_)
            handlers.append(onExecuteHandler_)
            
            onInputChangedHandler_ = InputChangedHandler(self.myObject_)
            command_.inputChanged.add(onInputChangedHandler_)
            handlers.append(onInputChangedHandler_)
            
            onDestroyHandler_ = DestroyHandler(self.myObject_)
            command_.destroy.add(onDestroyHandler_)
            handlers.append(onDestroyHandler_)
            
            onExecutePreviewHandler_ = ExecutePreviewHandler(self.myObject_)
            command_.executePreview.add(onExecutePreviewHandler_)
            handlers.append(onExecutePreviewHandler_)
            
            if self.myObject_.debug:
                ui.messageBox('***Debug ***Panel command created successfully')
            
            self.myObject_.on_create(command_, inputs_)
        except:
                if ui:
                    ui.messageBox('Panel command created failed: {}'.format(traceback.format_exc()))