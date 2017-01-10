import math
import adsk.core, adsk.fusion, traceback

from .Fusion360CommandBase import Fusion360CommandBase
from .Fusion360DebugUtilities import perf_log, variable_message, perf_message

# Ideas:
# TODO defer preview check box
# TODO setup debug time log and find the slow culprit
# TODO Flow Area for Circle
# TODO Flow area units
# TODO Other shapes, Arcs in grid?

log = []


def create_vent_sketch(center_point):
    # Get Component for feature
    target_component = center_point.parentSketch.parentComponent
    perf_log(log, 'CVS', 'get parent')

    # Get point in world CS
    world_point = center_point.worldGeometry
    perf_log(log, 'CVS', 'world point')

    # Create a new sketch on the plane.
    sketches = target_component.sketches
    perf_log(log, 'CVS', 'Get Feature Reference', 'Sketches')

    # Get target face for sketch
    target_face = target_component.findBRepUsingPoint(world_point, 1)
    perf_log(log, 'CVS', 'find brep')

    try:
        sketch = sketches.add(target_face[0])
        perf_log(log, 'CVS', 'Create Sketch')

    except:
        adsk.core.Application.get().userInterface.messageBox('The point you selected does not lie on a valid face\n' +
                                                             'The Vent cannot be built')

    for curve in sketch.sketchCurves:
        curve.isConstruction = True
    perf_log(log, 'CVS', 'Set Construction')

    center_point_sketch = sketch.project(center_point)
    perf_log(log, 'CVS', 'project sketch')

    return sketch, center_point_sketch[0], target_component, target_face[0]


def rectangle_vents(vent_width, vent_height, vent_border, number_width, number_height, center_point, slot, radius_in):
    # Initialize a sketch
    sketch, center_point_sketch, target_component, target_face = create_vent_sketch(center_point)
    perf_log(log, 'RV', 'create_vent_sketch')

    rect_width = (vent_width - ((number_width + 1.0) * vent_border)) / number_width
    rect_height = (vent_height - ((number_height + 1.0) * vent_border)) / number_height
    perf_log(log, 'RV', 'Math')
    if slot:
        radius = min(rect_width, rect_height) / 2.0

    else:
        radius = radius_in
    perf_log(log, 'RV', 'Math')
    vent_origin_x = center_point_sketch.geometry.x - vent_width / 2
    vent_origin_y = center_point_sketch.geometry.y - vent_height / 2
    perf_log(log, 'RV', 'Math')

    lines = sketch.sketchCurves.sketchLines
    perf_log(log, 'RV', 'Get Feature References', 'Lines')

    for i in range(0, number_width):
        for j in range(0, number_height):

            # Draw a rectangle
            rect_center_point_x = (rect_width / 2 + vent_border) + i * (rect_width + vent_border) + vent_origin_x
            rect_center_point_y = (rect_height / 2 + vent_border) + j * (rect_height + vent_border) + vent_origin_y
            perf_log(log, 'RV', 'Math')

            rect = lines.addCenterPointRectangle(adsk.core.Point3D.create(rect_center_point_x,
                                                                          rect_center_point_y, 0),
                                                 adsk.core.Point3D.create(rect_center_point_x + rect_width / 2,
                                                                          rect_center_point_y + rect_height / 2, 0))
            perf_log(log, 'RV', 'Draw Line', 'Center Rectangle')

            if radius > 0:
                # Fillet Rectangle
                sketch.sketchCurves.sketchArcs.addFillet(rect[0], rect[0].endSketchPoint.geometry,
                                                         rect[1], rect[1].startSketchPoint.geometry, radius)
                perf_log(log, 'RV', 'Draw Fillet', 'Fillet 1')
                sketch.sketchCurves.sketchArcs.addFillet(rect[1], rect[1].endSketchPoint.geometry,
                                                         rect[2], rect[2].startSketchPoint.geometry, radius)
                perf_log(log, 'RV', 'Draw Fillet', 'Fillet 2')
                sketch.sketchCurves.sketchArcs.addFillet(rect[2], rect[2].endSketchPoint.geometry,
                                                         rect[3], rect[3].startSketchPoint.geometry, radius)
                perf_log(log, 'RV', 'Draw Fillet', 'Fillet 3')
                sketch.sketchCurves.sketchArcs.addFillet(rect[3], rect[3].endSketchPoint.geometry,
                                                         rect[0], rect[0].startSketchPoint.geometry, radius)
                perf_log(log, 'RV', 'Draw Fillet', 'Fillet 4')

    # Create Collection for all extrusion Profiles
    profiles_ = adsk.core.ObjectCollection.create()
    perf_log(log, 'RV', 'Create Collection')

    # Calculate the total flow area
    flow_area = 0.0
    for profile in sketch.profiles:
        area_props = profile.areaProperties()
        flow_area += area_props.area
        profiles_.add(profile)
    perf_log(log, 'RV', 'Calculate Flow Area')

    # Create extrude cut of profiles
    to_next_extrude(profiles_, target_component, target_face, center_point_sketch,
                    adsk.fusion.FeatureOperations.CutFeatureOperation, "Rectangle Cut")
    perf_log(log, 'RV', 'to_next_extrude')

    return flow_area


def to_next_extrude(profiles_, target_component, target_face, center_point_sketch, operation, name=''):
    # Get normal vector to face in opposite direction
    (normal_return, normal_vector) = target_face.evaluator.getNormalAtPoint(center_point_sketch.worldGeometry)
    normal_vector.scaleBy(-1.0)

    # Cast ray to determine next face
    hit_faces = target_component.findBRepUsingRay(center_point_sketch.worldGeometry, normal_vector, 1)

    # Check if source face is included in returned set, function of ray cast tolerance
    if hit_faces[0].tempId == target_face.tempId:
        next_face = hit_faces[1]
    else:
        next_face = hit_faces[0]
    perf_log(log, 'TNE', 'find face', name)

    # Create an extrusion input to be able to define the input needed for an extrusion
    extrudes = target_component.features.extrudeFeatures
    ext_input = extrudes.createInput(profiles_, operation)
    to_next_extent = adsk.fusion.ToEntityExtentDefinition.create(next_face, False)
    ext_input.setOneSideExtent(to_next_extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    perf_log(log, 'TNE', 'Setup Extrude', name)

    try:
        extrude_feature = extrudes.add(ext_input)
        perf_log(log, 'TNE', 'Create Extrude', name)

        return extrude_feature

    except Exception as e:
        # adsk.core.Application.get().userInterface.messageBox('Sorry it looks like your vent is not completely '
        #                                                      'terminated by the opposite face\n\n' + repr(e))
        raise


# Not currently used, would create a through all extrude
def through_all_extrude(profiles_, target_component, operation):
    # Create Boundary cutout feature
    extrudes = target_component.features.extrudeFeatures
    boundary_input = extrudes.createInput(profiles_, operation)
    extent_all_ne = adsk.fusion.ThroughAllExtentDefinition.create(False)
    boundary_input.setOneSideExtent(extent_all_ne, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    boundary_feature = extrudes.add(boundary_input)

    return boundary_feature


# Create extruded body for vent outline
def circle_boundary_extrude(vent_radius, center_point):
    # Create Boundary Sketch
    boundary_sketch, center_point_sketch, target_component, target_face = create_vent_sketch(center_point)
    perf_log(log, 'CBE', 'create_vent_sketch')

    # Create circle for vent boundary
    boundary_curve = boundary_sketch.sketchCurves.sketchCircles.addByCenterRadius(center_point_sketch, vent_radius)
    perf_log(log, 'CBE', 'Draw Circle')

    # Create extrude
    boundary_feature = to_next_extrude(boundary_sketch.profiles[0], target_component, target_face, center_point_sketch,
                                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation, 'Circle Boundary')
    perf_log(log, 'CBE', 'to_next_extrude')

    boundary_end_face = boundary_feature.endFaces[0]
    tool_body = [boundary_feature.bodies[0]]
    target_body = boundary_sketch.referencePlane.body
    perf_log(log, 'CBE', 'Get Feature References')

    return boundary_curve, boundary_end_face, tool_body, target_body


# Creates Sketch for hub-spoke
def hub_spoke_sketch(vent_radius, number_axial, number_radial, center_point, boundary_curve):
    # Create Vent sketch
    vent_sketch, vent_center_point, target_component, target_face = create_vent_sketch(center_point)
    perf_log(log, 'HSS', 'create_vent_sketch')

    vent_lines = vent_sketch.sketchCurves.sketchLines
    vent_circles = vent_sketch.sketchCurves.sketchCircles
    vent_constraints = vent_sketch.geometricConstraints
    vent_dims = vent_sketch.sketchDimensions
    perf_log(log, 'HSS', 'Get Feature References')

    # Reference circle from previous sketch
    project_curves = vent_sketch.project(boundary_curve)
    project_boundary = project_curves[0]
    perf_log(log, 'HSS', 'project sketch')

    center_point_geom = vent_center_point.geometry
    perf_log(log, 'HSS', 'Get Feature References')

    # Create first line
    # TODO possible option to rotate this?
    end_point = adsk.core.Point3D.create(0, vent_radius + center_point_geom.y, 0)
    perf_log(log, 'HSS', 'Create Point3D', 'Line 0')

    line_1 = vent_lines.addByTwoPoints(vent_center_point, end_point)
    perf_log(log, 'HSS', 'Draw Line', 'line 0')

    vent_constraints.addCoincident(line_1.endSketchPoint, project_boundary)
    perf_log(log, 'HSS', 'Add Constraint', 'Coincident Line 0')

    vent_constraints.addVertical(line_1)
    perf_log(log, 'HSS', 'Add Constraint', 'Vertical Line 0')

    # Create Collection for vent Profiles
    vent_profile_collection = adsk.core.ObjectCollection.create()
    perf_log(log, 'HSS', 'Create Collection')

    vent_profile_collection.add(target_component.createOpenProfile(line_1, False))
    perf_log(log, 'HSS', 'Add To Collection')

    # Build Axial lines
    for i in range(1, number_axial):
        angle = i * 2 * math.pi / number_axial + math.pi / 2
        perf_log(log, 'HSS', 'Math', 'Line-' + str(i))

        end_point = adsk.core.Point3D.create(vent_radius * math.cos(angle) + center_point_geom.x,
                                             vent_radius * math.sin(angle) + center_point_geom.y, 0)
        perf_log(log, 'HSS', 'Create Point3D', 'Line-' + str(i))

        line_2 = vent_lines.addByTwoPoints(vent_center_point, end_point)
        perf_log(log, 'HSS', 'Draw Line', 'Line-' + str(i))

        vent_constraints.addCoincident(line_2.endSketchPoint, project_boundary)
        perf_log(log, 'HSS', 'Add Constraint', 'Line-' + str(i))

        vent_dims.addAngularDimension(line_1, line_2,
                                      adsk.core.Point3D.create(1.5 * vent_radius * math.cos(angle / 2) +
                                                               center_point_geom.x,
                                                               1.5 * vent_radius * math.sin(angle / 2) +
                                                               center_point_geom.y,
                                                               0))
        perf_log(log, 'HSS', 'Add Dimension', 'Line-' + str(i))

        vent_profile_collection.add(target_component.createOpenProfile(line_2, False))
        perf_log(log, 'HSS', 'Add To Collection', 'Line-' + str(i))

        line_1 = line_2

    # Build Radial Circles:
    for j in range(1, number_radial):
        radial_step = j * vent_radius / number_radial
        new_circle = vent_circles.addByCenterRadius(vent_center_point, radial_step)
        perf_log(log, 'HSS', 'Draw Circle', 'Circle-' + str(j))

        vent_dims.addRadialDimension(new_circle, adsk.core.Point3D.create(center_point_geom.x,
                                                                          center_point_geom.y + radial_step, 0))
        perf_log(log, 'HSS', 'Add Dimension', 'Circle-' + str(j))

        vent_profile_collection.add(target_component.createOpenProfile(new_circle, False))
        perf_log(log, 'HSS', 'Add To Collection', 'Circle-' + str(j))

    project_boundary.isConstruction = True
    perf_log(log, 'HSS', 'Set Construction')

    return vent_profile_collection, target_component


# Create surface based vent Extrude:
def vent_thick_extrude(vent_border, target_component, vent_profile_collection, boundary_end_face):
    # Create Extrude
    extrudes = target_component.features.extrudeFeatures
    perf_log(log, 'VTE', 'Get Collection')

    vent_surf_input = extrudes.createInput(vent_profile_collection,
                                           adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    vent_surf_input.isSolid = False

    to_extent = adsk.fusion.ToEntityExtentDefinition.create(boundary_end_face, False)
    vent_surf_input.setOneSideExtent(to_extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)
    perf_log(log, 'VTE', 'Set Feature Input', 'Extrude')

    vent_surf_feature = extrudes.add(vent_surf_input)
    perf_log(log, 'VTE', 'Create Extrude', 'Surface')

    # Create thicken feature
    thicken_features = target_component.features.thickenFeatures
    tool_body = []
    thickness = adsk.core.ValueInput.createByReal(vent_border)

    faces = vent_surf_feature.faces
    perf_log(log, 'VTE', 'Get Feature References', 'Surface')

    for index, face in enumerate(faces):
        input_surfaces = adsk.core.ObjectCollection.create()
        perf_log(log, 'VTE', 'Create Collection')

        input_surfaces.add(face)
        thicken_input = thicken_features.createInput(input_surfaces, thickness, True,
                                                     adsk.fusion.FeatureOperations.NewBodyFeatureOperation, False)
        perf_log(log, 'VTE', 'Set Feature Input', 'Thicken ' + str(index))

        thickness_feature = thicken_features.add(thicken_input)
        perf_log(log, 'VTE', 'Create Thicken', 'Thicken ' + str(index))

        tool_body.append(thickness_feature.bodies[0])

    return tool_body


def vent_combine(target_body, tool_body, operation, name=''):
    combine_tools = adsk.core.ObjectCollection.create()
    perf_log(log, 'VTE', 'Create Collection')

    # Create Combine Features
    combine_features = target_body.parentComponent.features.combineFeatures

    for tool in tool_body:
        combine_tools.add(tool)
    combine_input = combine_features.createInput(target_body, combine_tools)
    combine_input.operation = operation
    perf_log(log, 'VC', 'Setup Combine', name)

    combine_features.add(combine_input)
    perf_log(log, 'VC', 'Create Combine', name)


def create_hub_spoke_vent(vent_radius, vent_border, number_axial, number_radial, center_point):
    perf_log(log, 'CSHV', 'Start_Hub_Spoke')

    # Create Circular Boundary sketch and Extrude
    boundary_curve, boundary_end_face, boundary_tool_body, target_body = \
        circle_boundary_extrude(vent_radius, center_point)
    perf_log(log, 'CSHV', 'Circle Boundary Extrude')

    # Create Hub and Spoke Sketch
    vent_profile_collection, target_component = \
        hub_spoke_sketch(vent_radius, number_axial, number_radial, center_point, boundary_curve)
    perf_log(log, 'CSHV', 'hub_spoke_sketch')

    # Create Thicken Extrude Feature
    thicken_tool_body = vent_thick_extrude(vent_border, target_component, vent_profile_collection, boundary_end_face)
    perf_log(log, 'CSHV', 'vent_thick_extrude')

    # Combine Boundary (Cut)
    operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    vent_combine(target_body, boundary_tool_body, operation, 'Cut Boundary')
    perf_log(log, 'CSHV', 'vent_combine')

    # Combine Thicken (Join)
    operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    vent_combine(target_body, thicken_tool_body, operation, 'Join Thicken')
    perf_log(log, 'CSHV', 'vent_combine')


def get_inputs(command_inputs):
    value_types = [adsk.core.BoolValueCommandInput.classType(), adsk.core.DistanceValueCommandInput.classType(),
                   adsk.core.FloatSliderCommandInput.classType(), adsk.core.FloatSpinnerCommandInput.classType(),
                   adsk.core.IntegerSliderCommandInput.classType(), adsk.core.IntegerSpinnerCommandInput.classType(),
                   adsk.core.ValueCommandInput.classType(), adsk.core.SliderCommandInput.classType()]

    list_types = [adsk.core.ButtonRowCommandInput.classType(), adsk.core.DropDownCommandInput.classType(),
                  adsk.core.RadioButtonGroupCommandInput.classType()]
    input_values = {}
    input_values.clear()

    center_input = command_inputs.itemById("center_input")
    if center_input.selectionCount > 0:
        input_values['center_point'] = center_input.selection(0).entity

    for command_input in command_inputs:
        if command_input.objectType in value_types:
            input_values[command_input.id] = command_input.value
            input_values[command_input.id + '_input'] = command_input

        elif command_input.objectType in list_types:
            input_values[command_input.id] = command_input.selectedItem.name
            input_values[command_input.id + '_input'] = command_input
        else:
            input_values[command_input.id] = command_input.name
            input_values[command_input.id + '_input'] = command_input

    return input_values


def change_inputs(command_inputs, vent_type):
    input_definitions = {'Common': ['center_input', 'vent_border', 'vent_type', 'flow_area'],
                         'Circular': ['vent_radius', 'number_axial', 'number_radial'],
                         'Slot': ['vent_width', 'vent_height', 'number_width', 'number_height'],
                         'Rectangular': ['vent_width', 'vent_height', 'number_width', 'number_height', 'radius']}

    for command_input in command_inputs:
        if command_input.id not in input_definitions['Common']:
            command_input.isVisible = False

        if command_input.id in input_definitions[vent_type]:
            command_input.isVisible = True


# The following will define a command in a tool bar panel
class VentMakerCommand(Fusion360CommandBase):
    # Runs when Fusion command would generate a preview after all inputs are valid or changed
    def on_preview(self, command, inputs, args):

        time_line = adsk.core.Application.get().activeProduct.timeline

        start_index = time_line.markerPosition

        log.clear()
        input_values = get_inputs(inputs)

        try:

            if input_values['vent_type'] == 'Rectangular':
                perf_log(log, 'onP', 'Rectangular')
                area = rectangle_vents(input_values['vent_width'], input_values['vent_height'],
                                       input_values['vent_border'],
                                       input_values['number_width'], input_values['number_height'],
                                       input_values['center_point'], False, input_values['radius'])
                inputs.itemById("flow_area").formattedText = str(area)

            elif input_values['vent_type'] == 'Circular':
                perf_log(log, 'onP', 'Circular')
                create_hub_spoke_vent(input_values['vent_radius'], input_values['vent_border'],
                                      input_values['number_axial'],
                                      input_values['number_radial'], input_values['center_point'])

            elif input_values['vent_type'] == 'Slot':
                perf_log(log, 'onP', 'Slot')
                area = rectangle_vents(input_values['vent_width'], input_values['vent_height'],
                                       input_values['vent_border'],
                                       input_values['number_width'], input_values['number_height'],
                                       input_values['center_point'], True, input_values['radius'])
                inputs.itemById("flow_area").formattedText = str(area)

            args.isValidResult = True

            end_index = time_line.markerPosition - 1

            time_line.timelineGroups.add(start_index, end_index)

            # Enable for debug logging
            # perf_message(log)

        except Exception as e:
            args.isValidResult = False
            adsk.core.Application.get().userInterface.messageBox('Sorry those inputs are invalid. \n \n' +
                                                                 'Please Try Again\n \n' + repr(e))
            # ui.messageBox('Vent Failed:\n {}'.format(traceback.format_exc()))

    # Runs when the command is destroyed.  Sometimes useful for cleanup after the fact
    def on_destroy(self, command, inputs, reason_):
        pass

    # Runs when when any input in the command dialog is changed
    def on_input_changed(self, command, inputs, changed_input):
        if changed_input.id == 'vent_type':
            input_values = get_inputs(inputs)
            change_inputs(inputs, input_values['vent_type'])

    # Runs when the user presses ok button
    def on_execute(self, command, inputs):
        pass

    # Runs when user selects your command from Fusion UI, Build UI here
    def on_create(self, command, inputs):

        app = adsk.core.Application.get()
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        units_manager = design.unitsManager

        default_units = units_manager.defaultLengthUnits

        # Common Inputs:
        vent_type_input = inputs.addDropDownCommandInput('vent_type', 'Vent Type: ',
                                                         adsk.core.DropDownStyles.LabeledIconDropDownStyle)
        vent_type_input.listItems.add('Circular', True)
        vent_type_input.listItems.add('Slot', False)
        vent_type_input.listItems.add('Rectangular', False)

        center_input = inputs.addSelectionInput('center_input', 'Center of Vent: ', 'Select Sketch Point')
        center_input.addSelectionFilter('SketchPoints')
        center_input.setSelectionLimits(1, 1)

        # Rectangle and Slot inputs
        inputs.addValueInput('vent_width', 'Total width of vent area', default_units,
                             adsk.core.ValueInput.createByString('10 in'))
        inputs.addValueInput('vent_height', 'Total height of vent area', default_units,
                             adsk.core.ValueInput.createByString('4 in'))
        inputs.addValueInput('vent_border', 'Border Thickness', default_units,
                             adsk.core.ValueInput.createByString('.1 in'))

        # Corner Radius for Rectangle Feature
        inputs.addValueInput('radius', 'Corner Radius (can be zero)', default_units,
                             adsk.core.ValueInput.createByString('.1 in'))

        inputs.addIntegerSpinnerCommandInput('number_width', 'Number in Width: ', 1, 99, 1, 3)
        inputs.addIntegerSpinnerCommandInput('number_height', 'Number in Height: ', 1, 99, 1, 6)

        # Hub and Spoke Vent
        inputs.addValueInput('vent_radius', 'Radius of vent area', default_units,
                             adsk.core.ValueInput.createByString('5 in'))

        inputs.addIntegerSpinnerCommandInput('number_radial', 'Number of Hubs: ', 1, 99, 1, 3)
        inputs.addIntegerSpinnerCommandInput('number_axial', 'Number of Spokes: ', 1, 99, 1, 5)

        inputs.addTextBoxCommandInput('flow_area', 'Total Air Flow Area (cm^2):', ' 0.0 ', 1, True)

        change_inputs(inputs, vent_type_input.selectedItem.name)



