import csdl_alpha as csdl
import numpy as np

from lsdo_geo.core.parameterization.parameterization_solver import (
    ParameterizationSolver,
)
from lsdo_geo.core.parameterization.free_form_deformation_functions import (
    construct_tight_fit_ffd_block,
)
from lsdo_geo.core.parameterization.volume_sectional_parameterization import (
    VolumeSectionalParameterization,
    VolumeSectionalParameterizationInputs
)

from lsdo_geo.splines.b_splines.b_spline import BSpline
from lsdo_geo.splines.b_splines.b_spline_space import BSplineSpace

import lsdo_geo

recorder = csdl.Recorder(inline=True)
recorder.start()

geometry = lsdo_geo.import_geometry(
    "lsdo_geo/splines/b_splines/sample_geometries/rectangular_wing.stp",
    parallelize=False,
)
geometry.refit(parallelize=False)
# geometry.plot()


# region Key locations
leading_edge_left = geometry.project(np.array([0.0, -4.0, 0.0]))
leading_edge_right = geometry.project(np.array([0.0, 4.0, 0.0]))
trailing_edge_left = geometry.project(np.array([1.0, -4.0, 0.0]))
trailing_edge_right = geometry.project(np.array([1.0, 4.0, 0.0]))
leading_edge_center = geometry.project(np.array([0.0, 0.0, 0.0]))
trailing_edge_center = geometry.project(np.array([1.0, 0.0, 0.0]))
# endregion

# region Mesh definitions
# region Wing Camber Surface
num_spanwise = 19
num_chordwise = 5
points_to_project_on_leading_edge = np.linspace(np.array([0., -4., 1.]), np.array([0., 4., 1.]), num_spanwise)
points_to_project_on_trailing_edge = np.linspace(np.array([1., -4., 1.]), np.array([1., 4., 1.]), num_spanwise)

leading_edge_parametric = geometry.project(points_to_project_on_leading_edge, direction=np.array([0., 0., -1.]))
leading_edge_physical = geometry.evaluate(leading_edge_parametric)
trailing_edge_parametric = geometry.project(points_to_project_on_trailing_edge, direction=np.array([0., 0., -1.]))
trailing_edge_physical = geometry.evaluate(trailing_edge_parametric)

chord_surface = csdl.linear_combination(leading_edge_physical, trailing_edge_physical, num_chordwise).value.reshape((num_chordwise, num_spanwise, 3))
upper_surface_wireframe_parametric = geometry.project(chord_surface + np.array([0., 0., 1]), direction=np.array([0., 0., -1.]), plot=False)
lower_surface_wireframe_parametric = geometry.project(chord_surface - np.array([0., 0., 1]), direction=np.array([0., 0., -1.]), plot=False)
upper_surface_wireframe = geometry.evaluate(upper_surface_wireframe_parametric)
lower_surface_wireframe = geometry.evaluate(lower_surface_wireframe_parametric)
camber_surface = csdl.linear_combination(upper_surface_wireframe, lower_surface_wireframe, 1).reshape((num_chordwise, num_spanwise, 3))
# geometry.plot_meshes([camber_surface])
# endregion

# endregion

# region Parameterization

# region Create Parameterization Objects


parameterization_solver = ParameterizationSolver()

num_ffd_sections = 11
# ffd_block = construct_ffd_block_around_entities(name='ffd_block', entities=geometry, num_coefficients=(2,num_ffd_sections,2), order=(2,2,2))
num_wing_secctions = 2
ffd_block = construct_tight_fit_ffd_block(
    name="ffd_block",
    entities=geometry,
    num_coefficients=(2, (num_ffd_sections // num_wing_secctions + 1), 2),
    order=(2, 2, 2),
)
# ffd_block = construct_ffd_block_around_entities(name='ffd_block', entities=geometry, num_coefficients=(2,num_ffd_sections,2), order=(2,2,2))
ffd_block.coefficients.name = "ffd_block_coefficients"
# ffd_block.plot()

ffd_sectional_parameterization = VolumeSectionalParameterization(
    name="ffd_sectional_parameterization",
    parameterized_points=ffd_block.coefficients,
    principal_parametric_dimension=1,
    parameterized_points_shape=ffd_block.coefficients_shape,
)
# ffd_sectional_parameterization.plot()

# ffd_sectional_parameterization.add_sectional_stretch(name='chord_stretching', axis=0)
# ffd_sectional_parameterization.add_sectional_translation(name='wingspan_stretching', axis=1)
# ffd_sectional_parameterization.add_sectional_translation(name='sweep_translation', axis=0)

space_of_linear_3_dof_b_splines = BSplineSpace(
    name="linear_2_dof_space", order=(2,), parametric_coefficients_shape=(3,)
)
space_of_linear_2_dof_b_splines = BSplineSpace(
    name="linear_2_dof_space", order=(2,), parametric_coefficients_shape=(2,)
)

chord_stretching_b_spline = BSpline(
    name="chord_stretching_b_spline",
    space=space_of_linear_3_dof_b_splines,
    coefficients=csdl.Variable(
        shape=(3,),
        value=np.zeros(
            3,
        ),
        name="chord_stretching_b_spline_coefficients",
    ),
    # coefficients=csdl.Variable(shape=(3,), value=np.array([-.1, 10., 5.]), name='chord_stretching_b_spline_coefficients'),                                                                                                                                                                                                                        
    num_physical_dimensions=1,
)

wingspan_stretching_b_spline = BSpline(
    name="wingspan_stretching_b_spline",
    space=space_of_linear_2_dof_b_splines,
    # coefficients=csdl.Variable(shape=(2,), value=np.zeros(2,), name='wingspan_stretching_b_spline_coefficients'),
    coefficients=csdl.Variable(
        shape=(2,),
        value=np.array([0.0, 0.0]),
        name="wingspan_stretching_b_spline_coefficients",
    ),
    num_physical_dimensions=1,
)

sweep_translation_b_spline = BSpline(
    name="sweep_translation_b_spline",
    space=space_of_linear_3_dof_b_splines,
    # coefficients=csdl.Variable(shape=(3,), value=np.zeros(3,), name='sweep_translation_b_spline_coefficients'),
    coefficients=csdl.Variable(
        shape=(3,),
        value=np.array([2.0, 0.0, 2.0]),
        name="sweep_translation_b_spline_coefficients",
    ),
    num_physical_dimensions=1,
)
# sweep_translation_b_spline.plot()

twist_b_spline = BSpline(
    name="twist_translation_b_spline",
    space=space_of_linear_3_dof_b_splines,
    # coefficients=csdl.Variable(shape=(3,), value=np.zeros(3,), name='twist_translation_b_spline_coefficients'),
    coefficients=csdl.Variable(
        shape=(3,),
        value=np.array([15, 0., 15]),
        name="twist_translation_b_spline_coefficients",
    ),
    num_physical_dimensions=1,
)

parameterization_solver.declare_state(
    "chord_stretching_b_spline_coefficients", chord_stretching_b_spline.coefficients
)
parameterization_solver.declare_state(
    "wingspan_stretching_b_spline_coefficients",
    wingspan_stretching_b_spline.coefficients,
)
# endregion

# region Evaluate Parameterization To Define Parameterization Forward Model For Parameterization Solver
parametric_b_spline_inputs = np.linspace(0.0, 1.0, num_ffd_sections).reshape((-1, 1))
chord_stretch_sectional_parameters = chord_stretching_b_spline.evaluate(
    parametric_b_spline_inputs
)
wingspan_stretch_sectional_parameters = wingspan_stretching_b_spline.evaluate(
    parametric_b_spline_inputs
)
sweep_translation_sectional_parameters = sweep_translation_b_spline.evaluate(
    parametric_b_spline_inputs
)

twist_sectional_parameters = twist_b_spline.evaluate(
    parametric_b_spline_inputs
)

# sectional_parameters = {
#     "chord_stretching": chord_stretch_sectional_parameters,
#     "wingspan_stretching": wingspan_stretch_sectional_parameters,
#     "sweep_translation": sweep_translation_sectional_parameters,
# }
# ffd_sectional_parameterization.add_sectional_stretch(name='chord_stretching', axis=0)
# ffd_sectional_parameterization.add_sectional_translation(name='wingspan_stretching', axis=1)
# ffd_sectional_parameterization.add_sectional_translation(name='sweep_translation', axis=0)

# sectional_parameters = VolumeSectionalParameterizationInputs(
#     stretches={0: chord_stretch_sectional_parameters},
#     translations={1: wingspan_stretch_sectional_parameters, 0: sweep_translation_sectional_parameters},
# )

sectional_parameters = VolumeSectionalParameterizationInputs()
sectional_parameters.add_sectional_stretch(axis=0, stretch=chord_stretch_sectional_parameters)
sectional_parameters.add_sectional_translation(axis=1, translation=wingspan_stretch_sectional_parameters)
sectional_parameters.add_sectional_translation(axis=0, translation=sweep_translation_sectional_parameters)

ffd_coefficients = ffd_sectional_parameterization.evaluate(sectional_parameters)

geometry_coefficients = ffd_block.evaluate(ffd_coefficients)

geometry.assign_coefficients(geometry_coefficients)

parameterization_inputs = {}

wingspan = csdl.norm(
    geometry.evaluate(leading_edge_right) - geometry.evaluate(leading_edge_left)
)
root_chord = csdl.norm(
    geometry.evaluate(trailing_edge_center) - geometry.evaluate(leading_edge_center)
)
tip_chord_left = csdl.norm(
    geometry.evaluate(trailing_edge_left) - geometry.evaluate(leading_edge_left)
)
tip_chord_right = csdl.norm(
    geometry.evaluate(trailing_edge_right) - geometry.evaluate(leading_edge_right)
)

d_wingspan_dx = csdl.derivative.reverse(wingspan, [wingspan_stretching_b_spline.coefficients, chord_stretching_b_spline.coefficients])
print(d_wingspan_dx)
for key, value in d_wingspan_dx.items():
    print(key, value.value)
# from csdl_alpha.src.operations.derivative.utils import verify_derivatives_inline
# verify_derivatives_inline([wingspan], [wingspan_stretching_b_spline.coefficients, chord_stretching_b_spline.coefficients])
# d_root_chord_dx = csdl.derivative.reverse(root_chord, [wingspan_stretching_b_spline.coefficients, chord_stretching_b_spline.coefficients])
# print(d_root_chord_dx)
# for key, value in d_root_chord_dx.items():
#     print(key, value.value)

d_wingspan_d_wingspan_stretch = d_wingspan_dx[wingspan_stretching_b_spline.coefficients]
test_output = d_wingspan_d_wingspan_stretch*10
print(test_output.value)

d2_wingspan_dx2 = csdl.derivative.reverse(d_wingspan_dx[wingspan_stretching_b_spline.coefficients], [wingspan_stretching_b_spline.coefficients, chord_stretching_b_spline.coefficients])
for key, value in d2_wingspan_dx2.items():
    print(key, value.value)
csdl.get_current_recorder().print_graph_structure()
csdl.get_current_recorder().visualize_graph('my_graph')
exit()
# parameterization_solver.declare_input(name="wingspan", input=wingspan)
# parameterization_solver.declare_input(name="root_chord", input=root_chord)
# parameterization_solver.declare_input(name="tip_chord_left", input=tip_chord_left)
# parameterization_solver.declare_input(name="tip_chord_right", input=tip_chord_right)
# endregion

# # region Evaluate Parameterization Solver
# parameterization_inputs["wingspan"] = csdl.Variable(
#     name="wingspan", shape=(1,), value=np.array([6.0])
# )
# parameterization_inputs["root_chord"] = csdl.Variable(
#     name="root_chord", shape=(1,), value=np.array([2.0])
# )
# parameterization_inputs["tip_chord_left"] = csdl.Variable(
#     name="tip_chord_left", shape=(1,), value=np.array([0.5])
# )
# parameterization_inputs["tip_chord_right"] = csdl.Variable(
#     name="tip_chord_right", shape=(1,), value=np.array([0.5])
# )
# # geometry.plot()

# parameterization_solver_states = parameterization_solver.evaluate(
#     inputs=parameterization_inputs
# )
# # endregion


# region Evaluate Parameterization Forward Model Using Solver States
# parametric_b_spline_inputs = np.linspace(0.0, 1.0, num_ffd_sections).reshape((-1, 1))
# chord_stretching_b_spline.coefficients = parameterization_solver_states[
#     "chord_stretching_b_spline_coefficients"
# ]
# wingspan_stretching_b_spline.coefficients = parameterization_solver_states[
#     "wingspan_stretching_b_spline_coefficients"
# ]

chord_stretch_sectional_parameters = chord_stretching_b_spline.evaluate(
    parametric_b_spline_inputs
)
wingspan_stretch_sectional_parameters = wingspan_stretching_b_spline.evaluate(
    parametric_b_spline_inputs
)
sweep_translation_sectional_parameters = sweep_translation_b_spline.evaluate(
    parametric_b_spline_inputs
)

# sectional_parameters = {
#     "chord_stretching": chord_stretch_sectional_parameters,
#     "wingspan_stretching": wingspan_stretch_sectional_parameters,
#     "sweep_translation": sweep_translation_sectional_parameters,
# }
sectional_parameters = VolumeSectionalParameterizationInputs()
sectional_parameters.add_sectional_stretch(axis=0, stretch=chord_stretch_sectional_parameters)
sectional_parameters.add_sectional_translation(axis=1, translation=wingspan_stretch_sectional_parameters)
sectional_parameters.add_sectional_translation(axis=0, translation=sweep_translation_sectional_parameters)
sectional_parameters.add_sectional_rotation(axis=1, rotation=twist_sectional_parameters)

ffd_coefficients = ffd_sectional_parameterization.evaluate(sectional_parameters)

geometry_coefficients = ffd_block.evaluate(ffd_coefficients)

geometry.assign_coefficients(geometry_coefficients)

rotation_axis_origin = geometry.evaluate(geometry.project(np.array([0.5, 0., 0.5])))
rotation_axis_vector = geometry.evaluate(geometry.project(np.array([0.5, 1., 0.5])))
rotation_angles = 45
geometry.rotate(rotation_axis_origin, rotation_axis_vector, rotation_angles)

parameterization_inputs = {}

wingspan = csdl.norm(
    geometry.evaluate(leading_edge_right) - geometry.evaluate(leading_edge_left)
)
root_chord = csdl.norm(
    geometry.evaluate(trailing_edge_center) - geometry.evaluate(leading_edge_center)
)
tip_chord_left = csdl.norm(
    geometry.evaluate(trailing_edge_left) - geometry.evaluate(leading_edge_left)
)
tip_chord_right = csdl.norm(
    geometry.evaluate(trailing_edge_right) - geometry.evaluate(leading_edge_right)
)

upper_surface_wireframe = geometry.evaluate(upper_surface_wireframe_parametric)
lower_surface_wireframe = geometry.evaluate(lower_surface_wireframe_parametric)
camber_surface = csdl.linear_combination(
    upper_surface_wireframe, lower_surface_wireframe, 1
).reshape((num_chordwise, num_spanwise, 3))
# endregion

# region Print and Plot Geometric Outputs
# geometry.plot()
# geometry.plot_meshes([camber_surface])

print("Wingspan: ", wingspan.value)
print("Root Chord: ", root_chord.value)
print("Tip Chord Left: ", tip_chord_left.value)
print("Tip Chord Right: ", tip_chord_right.value)
# endregion

# endregion

# recorder.visualize_graph('my_graph')