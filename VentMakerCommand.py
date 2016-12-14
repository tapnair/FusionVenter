import math
import adsk.core, adsk.fusion, traceback

from .Fusion360CommandBase import Fusion360CommandBase


def create_vent_sketch(center_point):
    app = adsk.core.Application.get()
    ui = app.userInterface

    # ui.messageBox("W = %d\n H = %d\n R = %d\n" % (rect_width, rect_height, radius))
    design = app.activeProduct

    # Get the root component of the active design.
    root_comp = design.rootComponent

    # Create a new sketch on the plane.
    sketches = root_comp.sketches

    sketch = sketches.add(center_point.parentSketch.referencePlane)

    for curve in sketch.sketchCurves:
        curve.isConstruction = True

    center_point_sketch = sketch.modelToSketchSpace(center_point.worldGeometry)

    return sketch, center_point_sketch


def rectangle_vents(vent_width, vent_height, vent_border, number_width, number_height, center_point):

    sketch, center_point_sketch = create_vent_sketch(center_point)

    rect_width = (vent_width - ((number_width + 1.0) * vent_border)) / number_width
    rect_height = (vent_height - ((number_height + 1.0) * vent_border)) / number_height
    radius = min(rect_width, rect_height) / 2.0

    vent_origin_x = center_point_sketch.x - vent_width / 2
    vent_origin_y = center_point_sketch.y - vent_height / 2

    for i in range(0, number_width):
        for j in range(0, number_height):

            # Draw a rectangle
            rect_center_point_x = (rect_width/2 + vent_border) + i * (rect_width + vent_border) + vent_origin_x
            rect_center_point_y = (rect_height/2 + vent_border) + j * (rect_height + vent_border) + vent_origin_y

            lines = sketch.sketchCurves.sketchLines
            rect = lines.addCenterPointRectangle(adsk.core.Point3D.create(rect_center_point_x,
                                                                          rect_center_point_y, 0),
                                                 adsk.core.Point3D.create(rect_center_point_x + rect_width/2,
                                                                          rect_center_point_y + rect_height/2, 0))
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

    # Create an extrusion input to be able to define the input needed for an extrusion
    # while specifying the profile and that a new component is to be created
    extrudes = sketch.parentComponent.features.extrudeFeatures
    ext_input = extrudes.createInput(profiles_, adsk.fusion.FeatureOperations.CutFeatureOperation)

    extent_all_ne = adsk.fusion.ThroughAllExtentDefinition.create(False)
    ext_input.setOneSideExtent(extent_all_ne, adsk.fusion.ExtentDirections.NegativeExtentDirection)

    # Create the extrusion.
    ext = extrudes.add(ext_input)

    ui.messageBox("Area = %f\n " % flow_area)


def circle_vents(vent_radius, vent_border, number_axial, number_radial, center_point):

    # Create Boundary cutout Sketch
    circle_cut_sketch, circle_cut_center_point = create_vent_sketch(center_point)
    ref_circle_1 = circle_cut_sketch.sketchCurves.sketchCircles.addByCenterRadius(circle_cut_center_point, vent_radius)

    # Target component for features
    target_component = circle_cut_sketch.parentComponent
    target_body = circle_cut_sketch.referencePlane.body

    # Create Boundary cutout feature
    extrudes = target_component.features.extrudeFeatures
    circle_cut_input = extrudes.createInput(circle_cut_sketch.profiles[0],
                                            adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extent_all_ne = adsk.fusion.ThroughAllExtentDefinition.create(False)
    circle_cut_input.setOneSideExtent(extent_all_ne, adsk.fusion.ExtentDirections.NegativeExtentDirection)
    vent_outline_feature = extrudes.add(circle_cut_input)

    # Create Vent sketch
    vent_sketch, vent_center_point = create_vent_sketch(center_point)
    vent_lines = vent_sketch.sketchCurves.sketchLines
    vent_circles = vent_sketch.sketchCurves.sketchCircles
    vent_constraints = vent_sketch.geometricConstraints
    vent_dims = vent_sketch.sketchDimensions

    # Reference circle from previous sketch
    project_curves = vent_sketch.project(ref_circle_1)
    ref_circle_2 = project_curves[0]

    # Create Collection for vent Profiles
    vent_profile_collection = adsk.core.ObjectCollection.create()

    #Create first line
    # TODO possible option to rotate this?
    line_1 = vent_lines.addByTwoPoints(vent_center_point,
                                       adsk.core.Point3D.create(0, vent_radius + vent_center_point.y, 0))
    line_1.startSketchPoint.merge(ref_circle_2.centerSketchPoint)

    vent_constraints.addCoincident(line_1.endSketchPoint, ref_circle_2)
    vent_constraints.addVertical(line_1)

    vent_profile_collection.add(target_component.createOpenProfile(line_1))

    # Build Axial lines
    for i in range(1, number_axial):
        angle = i * 2 * math.pi / number_axial + math.pi / 2
        line_2 = vent_lines.addByTwoPoints(vent_center_point,
                                           adsk.core.Point3D.create(vent_radius * math.cos(angle) + vent_center_point.x,
                                                                    vent_radius * math.sin(angle) + vent_center_point.y,
                                                                    0))

        line_2.startSketchPoint.merge(ref_circle_2.centerSketchPoint)

        vent_constraints.addCoincident(line_2.endSketchPoint, ref_circle_2)

        vent_dims.addAngularDimension(line_1, line_2,
                                      adsk.core.Point3D.create(1.5 * vent_radius * math.cos(angle/2) +
                                                               vent_center_point.x,
                                                               1.5 * vent_radius * math.sin(angle/2) +
                                                               vent_center_point.y,
                                                               0))
        vent_profile_collection.add(target_component.createOpenProfile(line_2))
        line_1 = line_2

    # Build Radial Circles:
    for j in range(1, number_radial):
        radial_step = j * vent_radius/number_radial
        new_circle = vent_circles.addByCenterRadius(vent_center_point, radial_step)
        new_circle.centerSketchPoint.merge(ref_circle_2.centerSketchPoint)
        vent_dims.addRadialDimension(new_circle, adsk.core.Point3D.create(vent_center_point.x,
                                                                          vent_center_point.y + radial_step, 0))
        vent_profile_collection.add(target_component.createOpenProfile(new_circle))

    ref_circle_2.isConstruction = True

    # Create Surface Extrude:
    # extrudes = target_component.features.extrudeFeatures
    vent_surf_input = extrudes.createInput(vent_profile_collection,
                                           adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    vent_surf_input.isSolid = False
    # distance = adsk.core.ValueInput.createByReal(-1)
    # extent_distance= adsk.fusion.adsk.fusion.DistanceExtentDefinition.create(distance)

    to_extent = adsk.fusion.ToEntityExtentDefinition.create(vent_outline_feature.endFaces[0], False)
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

    # Create Combine Features
    combine_features = target_component.features.combineFeatures
    combine_cut_tools = adsk.core.ObjectCollection.create()
    combine_cut_tools.add(vent_outline_feature.bodies[0])
    combine_cut_input = combine_features.createInput(target_body, combine_cut_tools)
    combine_cut_input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combine_features.add(combine_cut_input)

    combine_join_tools = adsk.core.ObjectCollection.create()
    combine_join_tools.add(thickness_feature.bodies[0])
    combine_join_input = combine_features.createInput(target_body, combine_join_tools)
    combine_join_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combine_features.add(combine_join_input)


def get_inputs(command_inputs):
    value_types = [adsk.core.BoolValueCommandInput.classType(),  adsk.core.DistanceValueCommandInput.classType(),
                   adsk.core.FloatSliderCommandInput.classType(), adsk.core.FloatSpinnerCommandInput.classType(),
                   adsk.core.IntegerSliderCommandInput.classType(), adsk.core.IntegerSpinnerCommandInput.classType(),
                   adsk.core.ValueCommandInput.classType(), adsk.core.SliderCommandInput.classType()]
    input_values = {}
    input_values.clear()

    center_input = command_inputs.itemById("center_input")
    if center_input.selectionCount > 0:
        input_values['center_point'] = center_input.selection(0).entity

    for command_input in command_inputs:
        if command_input.objectType in value_types:
            input_values[command_input.id] = command_input.value

    return input_values


# The following will define a command in a tool bar panel
class VentMakerCommand(Fusion360CommandBase):
    
    # Runs when Fusion command would generate a preview after all inputs are valid or changed
    def onPreview(self, command, inputs, args):
        input_values = get_inputs(inputs)
        # rectangle_vents(input_values['vent_width'], input_values['vent_height'], input_values['vent_border'],
        #                 input_values['number_width'], input_values['number_height'],
        #                 input_values['center_point'])

        circle_vents(input_values['vent_radius'], input_values['vent_border'], input_values['number_axial'],
                     input_values['number_radial'], input_values['center_point'])

        #TODO only if valid:
        args.isValidResult = True

    # Runs when the command is destroyed.  Sometimes useful for cleanup after the fact
    def onDestroy(self, command, inputs, reason_):    
        pass
    
    # Runs when when any input in the command dialog is changed
    def onInputChanged(self, command, inputs, changedInput):
        pass
    
    # Runs when the user presses ok button
    def onExecute(self, command, inputs):
        input_values = get_inputs(inputs)
        rectangle_vents(input_values['vent_width'], input_values['vent_height'], input_values['vent_border'],
                        input_values['number_width'], input_values['number_height'],
                        input_values['center_point'])

    # Runs when user selects your command from Fusion UI, Build UI here
    def onCreate(self, command, inputs):
        app = adsk.core.Application.get()
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        units_manager = design.unitsManager

        default_units = units_manager.defaultLengthUnits

        # Create a few inputs in the UI
        inputs.addValueInput('vent_width', 'Total width of vent area', default_units,
                             adsk.core.ValueInput.createByString('10 in'))
        inputs.addValueInput('vent_height', 'Total height of vent area', default_units,
                             adsk.core.ValueInput.createByString('4 in'))
        inputs.addValueInput('vent_border', 'Border around vents', default_units,
                             adsk.core.ValueInput.createByString('.1 in'))

        inputs.addIntegerSpinnerCommandInput('number_width', 'Number in Width: ', 1, 99, 1, 3)
        inputs.addIntegerSpinnerCommandInput('number_height', 'Number in Height: ', 1, 99, 1, 6)

        # selection_input = inputs.addSelectionInput('selectionInput', 'Face for Vent: ', 'Select one')
        # selection_input.addSelectionFilter('PlanarFaces')
        # selection_input.setSelectionLimits(1, 1)

        # Create a few inputs in the UI
        inputs.addValueInput('vent_radius', 'Radius of vent area', default_units,
                             adsk.core.ValueInput.createByString('5 in'))

        # inputs.addValueInput('vent_depth', 'Depth of vent', default_units,
        #                      adsk.core.ValueInput.createByString('1 in'))

        inputs.addIntegerSpinnerCommandInput('number_radial', 'Number in Radial: ', 1, 99, 1, 3)
        inputs.addIntegerSpinnerCommandInput('number_axial', 'Number in Axial: ', 1, 99, 1, 5)

        center_input = inputs.addSelectionInput('center_input', 'Center of Vent: ', 'Select Sketch Point')
        center_input.addSelectionFilter('SketchPoints')
        center_input.setSelectionLimits(1, 1)