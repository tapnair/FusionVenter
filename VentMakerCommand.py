import math
import adsk.core, adsk.fusion, traceback

from .Fusion360CommandBase import Fusion360CommandBase

# Ideas:
# TODO defer preview check box
# TODO setup debug time log and find the slow culprit
# TODO Flow Area for Circle
# TODO Flow area units
# TODO Other shapes, Arcs in grid?


def create_vent_sketch(center_point):
    # Get Component for feature
    target_component = center_point.parentSketch.parentComponent

    # Get point in world CS
    world_point = center_point.worldGeometry

    # Create a new sketch on the plane.
    sketches = target_component.sketches

    # Get target face for sketch
    target_face = target_component.findBRepUsingPoint(world_point, 1)

    sketch = sketches.add(target_face[0])

    for curve in sketch.sketchCurves:
        curve.isConstruction = True

    center_point_sketch = sketch.project(center_point)

    return sketch, center_point_sketch[0], target_component, target_face[0]


def rectangle_vents(vent_width, vent_height, vent_border, number_width, number_height, center_point, slot, radius_in):
    # Initialize a sketch
    sketch, center_point_sketch, target_component, target_face = create_vent_sketch(center_point)

    rect_width = (vent_width - ((number_width + 1.0) * vent_border)) / number_width
    rect_height = (vent_height - ((number_height + 1.0) * vent_border)) / number_height

    if slot:
        radius = min(rect_width, rect_height) / 2.0

    else:
        radius = radius_in

    vent_origin_x = center_point_sketch.geometry.x - vent_width / 2
    vent_origin_y = center_point_sketch.geometry.y - vent_height / 2

    for i in range(0, number_width):
        for j in range(0, number_height):
            # Draw a rectangle
            rect_center_point_x = (rect_width / 2 + vent_border) + i * (rect_width + vent_border) + vent_origin_x
            rect_center_point_y = (rect_height / 2 + vent_border) + j * (rect_height + vent_border) + vent_origin_y

            lines = sketch.sketchCurves.sketchLines
            rect = lines.addCenterPointRectangle(adsk.core.Point3D.create(rect_center_point_x,
                                                                          rect_center_point_y, 0),
                                                 adsk.core.Point3D.create(rect_center_point_x + rect_width / 2,
                                                                          rect_center_point_y + rect_height / 2, 0))
            if radius > 0:
                # Fillet Rectangle
                sketch.sketchCurves.sketchArcs.addFillet(rect[0], rect[0].endSketchPoint.geometry,
                                                         rect[1], rect[1].startSketchPoint.geometry, radius)
                sketch.sketchCurves.sketchArcs.addFillet(rect[1], rect[1].endSketchPoint.geometry,
                                                         rect[2], rect[2].startSketchPoint.geometry, radius)
                sketch.sketchCurves.sketchArcs.addFillet(rect[2], rect[2].endSketchPoint.geometry,
                                                         rect[3], rect[3].startSketchPoint.geometry, radius)
                sketch.sketchCurves.sketchArcs.addFillet(rect[3], rect[3].endSketchPoint.geometry,
                                                         rect[0], rect[0].startSketchPoint.geometry, radius)

    # Create Collection for all extrusion Profiles
    profiles_ = adsk.core.ObjectCollection.create()

    # Calculate the total flow area
    flow_area = 0.0

    # Get the profiles from the sketch
    for profile in sketch.profiles:
        area_props = profile.areaProperties()
        flow_area += area_props.area
        profiles_.add(profile)

    to_next_extrude(profiles_, target_component, target_face, center_point_sketch,
                    adsk.fusion.FeatureOperations.CutFeatureOperation)
    # ui.messageBox("Area = %f\n " % flow_area)

    return flow_area


def to_next_extrude(profiles_, target_component, target_face, center_point_sketch, operation):
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

    # Create an extrusion input to be able to define the input needed for an extrusion
    extrudes = target_component.features.extrudeFeatures
    ext_input = extrudes.createInput(profiles_, operation)
    to_next_extent = adsk.fusion.ToEntityExtentDefinition.create(next_face, False)
    ext_input.setOneSideExtent(to_next_extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    extrude_feature = extrudes.add(ext_input)

    return extrude_feature


def through_all_extrude(profiles_, target_component, operation):
    # Create Boundary cutout feature
    extrudes = target_component.features.extrudeFeatures
    boundary_input = extrudes.createInput(profiles_, operation)
    extent_all_ne = adsk.fusion.ThroughAllExtentDefinition.create(False)
    boundary_input.setOneSideExtent(extent_all_ne, adsk.fusion.ExtentDirections.PositiveExtentDirection)
    boundary_feature = extrudes.add(boundary_input)

    return boundary_feature


def circle_boundary_extrude(vent_radius, center_point):
    # Create Boundary cutout Sketch
    boundary_sketch, center_point_sketch, target_component, target_face = create_vent_sketch(center_point)
    boundary_curve = boundary_sketch.sketchCurves.sketchCircles.addByCenterRadius(center_point_sketch, vent_radius)

    boundary_feature = to_next_extrude(boundary_sketch.profiles[0], target_component, target_face, center_point_sketch,
                                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    boundary_end_face = boundary_feature.endFaces[0]
    tool_body = boundary_feature.bodies[0]
    target_body = boundary_sketch.referencePlane.body

    return boundary_curve, boundary_end_face, tool_body, target_body


def start_surface_sketch(center_point, boundary_curve):
    # Create Vent sketch
    vent_sketch, vent_center_point, target_component, target_face = create_vent_sketch(center_point)
    vent_lines = vent_sketch.sketchCurves.sketchLines
    vent_circles = vent_sketch.sketchCurves.sketchCircles
    vent_constraints = vent_sketch.geometricConstraints
    vent_dims = vent_sketch.sketchDimensions

    # Reference circle from previous sketch
    project_curves = vent_sketch.project(boundary_curve)
    project_boundary = project_curves[0]

    return vent_lines, vent_circles, vent_constraints, vent_dims, target_component, project_boundary, vent_center_point


def hub_spoke_sketch(vent_radius, number_axial, number_radial, center_point, boundary_curve):
    vent_lines, vent_circles, vent_constraints, vent_dims, target_component, project_boundary, vent_center_point = \
        start_surface_sketch(center_point, boundary_curve)

    center_point_geom = vent_center_point.geometry

    # Create first line
    # TODO possible option to rotate this?
    line_1 = vent_lines.addByTwoPoints(vent_center_point,
                                       adsk.core.Point3D.create(0, vent_radius + center_point_geom.y, 0))
    # line_1.startSketchPoint.merge(project_boundary.centerSketchPoint)

    vent_constraints.addCoincident(line_1.endSketchPoint, project_boundary)
    vent_constraints.addVertical(line_1)

    # Create Collection for vent Profiles
    vent_profile_collection = adsk.core.ObjectCollection.create()
    vent_profile_collection.add(target_component.createOpenProfile(line_1, False))

    # Build Axial lines
    for i in range(1, number_axial):
        angle = i * 2 * math.pi / number_axial + math.pi / 2
        line_2 = vent_lines.addByTwoPoints(vent_center_point,
                                           adsk.core.Point3D.create(vent_radius * math.cos(angle) + center_point_geom.x,
                                                                    vent_radius * math.sin(angle) + center_point_geom.y,
                                                                    0))

        # line_2.startSketchPoint.merge(project_boundary.centerSketchPoint)

        vent_constraints.addCoincident(line_2.endSketchPoint, project_boundary)

        vent_dims.addAngularDimension(line_1, line_2,
                                      adsk.core.Point3D.create(1.5 * vent_radius * math.cos(angle / 2) +
                                                               center_point_geom.x,
                                                               1.5 * vent_radius * math.sin(angle / 2) +
                                                               center_point_geom.y,
                                                               0))
        vent_profile_collection.add(target_component.createOpenProfile(line_2, False))
        line_1 = line_2

    # Build Radial Circles:
    for j in range(1, number_radial):
        radial_step = j * vent_radius / number_radial
        new_circle = vent_circles.addByCenterRadius(vent_center_point, radial_step)
        # new_circle.centerSketchPoint.merge(project_boundary.centerSketchPoint)
        vent_dims.addRadialDimension(new_circle, adsk.core.Point3D.create(center_point_geom.x,
                                                                          center_point_geom.y + radial_step, 0))
        vent_profile_collection.add(target_component.createOpenProfile(new_circle, False))

    project_boundary.isConstruction = True

    return vent_profile_collection, target_component


# Create surface based vent Extrude:
def vent_thick_extrude(vent_border, target_component, vent_profile_collection, boundary_end_face):
    # Create Extrude
    extrudes = target_component.features.extrudeFeatures

    vent_surf_input = extrudes.createInput(vent_profile_collection,
                                           adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    vent_surf_input.isSolid = False

    to_extent = adsk.fusion.ToEntityExtentDefinition.create(boundary_end_face, False)
    vent_surf_input.setOneSideExtent(to_extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)
    vent_surf_feature = extrudes.add(vent_surf_input)

    # Create thicken feature
    thicken_features = target_component.features.thickenFeatures
    input_surfaces = adsk.core.ObjectCollection.create()
    faces = vent_surf_feature.faces
    for face in faces:
        input_surfaces.add(face)

    thickness = adsk.core.ValueInput.createByReal(vent_border)
    thicken_input = thicken_features.createInput(input_surfaces, thickness, True,
                                                 adsk.fusion.FeatureOperations.NewBodyFeatureOperation, False)
    thickness_feature = thicken_features.add(thicken_input)
    tool_body = thickness_feature.bodies[0]

    return tool_body


def vent_combine(target_body, tool_body, operation):
    # Create Combine Features
    combine_features = target_body.parentComponent.features.combineFeatures
    combine_tools = adsk.core.ObjectCollection.create()
    combine_tools.add(tool_body)
    combine_input = combine_features.createInput(target_body, combine_tools)
    combine_input.operation = operation
    combine_features.add(combine_input)


def create_hub_spoke_vent(vent_radius, vent_border, number_axial, number_radial, center_point):
    # Create Circular Boundary sketch and Extrude
    boundary_curve, boundary_end_face, boundary_tool_body, target_body = \
        circle_boundary_extrude(vent_radius, center_point)

    # Create Hub and Spoke Sketch
    vent_profile_collection, target_component = \
        hub_spoke_sketch(vent_radius, number_axial, number_radial, center_point, boundary_curve)

    # Create Thicken Extrude Feature
    thicken_tool_body = vent_thick_extrude(vent_border, target_component, vent_profile_collection, boundary_end_face)

    # Combine Boundary (Cut)
    operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    vent_combine(target_body, boundary_tool_body, operation)

    # Combine Thicken (Join)
    operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    vent_combine(target_body, thicken_tool_body, operation)


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
    def onPreview(self, command, inputs, args):

        input_values = get_inputs(inputs)

        try:

            if input_values['vent_type'] == 'Rectangular':
                area = rectangle_vents(input_values['vent_width'], input_values['vent_height'], input_values['vent_border'],
                                       input_values['number_width'], input_values['number_height'],
                                       input_values['center_point'], False, input_values['radius'])
                inputs.itemById("flow_area").formattedText = str(area)

            elif input_values['vent_type'] == 'Circular':
                create_hub_spoke_vent(input_values['vent_radius'], input_values['vent_border'],
                                      input_values['number_axial'],
                                      input_values['number_radial'], input_values['center_point'])

            elif input_values['vent_type'] == 'Slot':
                area = rectangle_vents(input_values['vent_width'], input_values['vent_height'], input_values['vent_border'],
                                       input_values['number_width'], input_values['number_height'],
                                       input_values['center_point'], True, input_values['radius'])
                inputs.itemById("flow_area").formattedText = str(area)

            # TODO only if valid:
            args.isValidResult = True

        except:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox('Sorry those inputs are invalid. \n \n' +
                          'Ensure the values are appropriate and tha there is a clear path to the  termination face.\n'
                          + 'Better Error reporting coming soon!!!')

    # Runs when the command is destroyed.  Sometimes useful for cleanup after the fact
    def onDestroy(self, command, inputs, reason_):
        pass

    # Runs when when any input in the command dialog is changed
    def onInputChanged(self, command, inputs, changedInput):
        if changedInput.id == 'vent_type':
            input_values = get_inputs(inputs)
            change_inputs(inputs, input_values['vent_type'])

    # Runs when the user presses ok button
    def onExecute(self, command, inputs):
        pass

    # Runs when user selects your command from Fusion UI, Build UI here
    def onCreate(self, command, inputs):
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



