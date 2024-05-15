import numpy as np
import csdl_alpha as csdl
import lsdo_function_spaces as lfs
from lsdo_geo.core.geometry.geometry import Geometry
from typing import Union
import scipy.sparse as sps

from dataclasses import dataclass
@dataclass
class FFDBlock(lfs.Function):
    '''
    Free-form deformation block class.

    Parameters
    ----------
    Function class. This class is used to represent a function in a given function space. The function space is used to evaluate the function at
    given coordinates, refit the function, and project points onto the function.

    Attributes
    ----------
    space : lfs.FunctionSpace
        The function space in which the function resides.
    coefficients : csdl.Variable -- shape=coefficients_shape
        The coefficients of the function.
    name : str = None
        If applicable, the name of the function.
    embedded_entities : list[Union[csdl.Variable,Geometry,lfs.Function,lfs.FunctionSet]]
    '''
    embedded_entities : list[Union[csdl.Variable,Geometry,lfs.Function,lfs.FunctionSet]] = None

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.embedded_entities, list):
            self.embedded_entities = [self.embedded_entities]

        self.basis_matrices = []
        self.embed_entities(entities=self.embedded_entities)
        

    def embed_entities(self, entities:list[csdl.Variable,np.ndarray,Geometry,lfs.Function,lfs.FunctionSet]):
        for entity in entities:
            if isinstance(entity, np.ndarray):
                embedded_points = entity
            elif isinstance(entity, csdl.Variable):
                embedded_points = entity.value
            elif isinstance(entity, lfs.Function):
                embedded_points = entity.coefficients.value
            elif isinstance(entity, Geometry) or isinstance(entity, lfs.FunctionSet):
                embedded_points = []
                for function in entity.functions:
                    embedded_points.append(function.coefficients.value)
            else:
                raise ValueError(f'Unsupported entity type: {type(entity)}')

            if not isinstance(embedded_points, list):
                embedded_points_parametric_coordinates = self.project(points=embedded_points)
                entity_basis_matrix = self.space.compute_basis_matrix(parametric_coordinates=embedded_points_parametric_coordinates, 
                                                                expand_map_for_physical=False)
                self.basis_matrices.append(entity_basis_matrix)
            else:
                entity_basis_matrices = []
                for points in embedded_points:
                    embedded_points_parametric_coordinates = self.project(points=points)
                    entity_basis_matrix = self.space.compute_basis_matrix(parametric_coordinates=embedded_points_parametric_coordinates)
                    entity_basis_matrices.append(entity_basis_matrix)
                self.basis_matrices.append(entity_basis_matrices)



    def evaluate_ffd(self, coefficients:csdl.Variable, plot:bool=False) -> csdl.Variable:
        '''
        Takes in the FFD block coefficients and evaluates the embedded points.

        Parameters
        ----------
        coefficients : csdl.Variable
            The coefficients of the FFD block.
        plot : bool
            A boolean on whether or not to plot the FFD block.

        Returns
        -------
        updated_points : csdl.Variable
            The embedded points.
        '''
        # Perform update
        self.coefficients = coefficients

        outputs = []
        for basis_matrix in self.basis_matrices:
            if not isinstance(basis_matrix, list):
                updated_points = basis_matrix @ self.coefficients
                outputs.append(updated_points)
            else:
                updated_points = []
                for entity_basis_matrix in basis_matrix:
                    if isinstance(coefficients, csdl.Variable) and sps.issparse(entity_basis_matrix):
                        coefficients_reshaped = coefficients.reshape((entity_basis_matrix.shape[1], coefficients.size//entity_basis_matrix.shape[1]))
                        # NOTE: TEMPORARY IMPLEMENTATION SINCE CSDL ONLY SUPPORTS SPARSE MATVECS AND NOT MATMATS
                        values = csdl.Variable(value=np.zeros((entity_basis_matrix.shape[0], coefficients_reshaped.shape[1])))
                        for i in range(coefficients_reshaped.shape[1]):
                            coefficients_column = coefficients_reshaped[:,i].reshape((coefficients_reshaped.shape[0],1))
                            values = values.set(csdl.slice[:,i], csdl.sparse.matvec(entity_basis_matrix, coefficients_column).reshape(
                                (entity_basis_matrix.shape[0],)))
                    else:
                        values = entity_basis_matrix @ coefficients.reshape((entity_basis_matrix.shape[1], -1))
                    updated_points.append(values)
                outputs.append(updated_points)

        if plot:
            outputs_to_plot = []
            for entity_points in outputs:
                if isinstance(entity_points, list):
                    for entity_entity_points in entity_points:
                        outputs_to_plot.append(entity_entity_points.value)
                else:
                    outputs_to_plot.append(entity_points.value)
            self.plot(plot_embedded_points=True, embedded_points=outputs_to_plot, opacity=0.3, show=True)

        if len(outputs) == 1:
            return outputs[0]
        else:
            return outputs
        

    # def evaluate_as_function(self, parametric_coordinates:np.ndarray, parametric_derivative_orders:list[tuple]=None, coefficients:csdl.Variable=None,
    #              plot:bool=False) -> csdl.Variable:
    #     '''
    #     Evaluates the function.

    #     Parameters
    #     ----------
    #     parametric_coordinates : np.ndarray -- shape=(num_points, num_parametric_dimensions)
    #         The coordinates at which to evaluate the function.
    #     parametric_derivative_order : tuple = None -- shape=(num_points,num_parametric_dimensions)
    #         The order of the parametric derivatives to evaluate.
    #     coefficients : csdl.Variable = None -- shape=coefficients_shape
    #         The coefficients of the function.
    #     plot : bool = False
    #         Whether or not to plot the function with the points from the result of the evaluation.
        

    #     Returns
    #     -------
    #     function_values : csdl.Variable
    #         The function evaluated at the given coordinates.
    #     '''
    #     return super().evaluate(parametric_coordinates=parametric_coordinates, parametric_derivative_orders=parametric_derivative_orders,
    #                      coefficients=coefficients, plot=plot)
        

    def plot(self, plot_embedded_points:bool=True, embedded_points:list=None,
             opacity:float=0.3, color:str='#00629B', surface_texture:str="",
             additional_plotting_elements:list=[], show:bool=True):
        '''
        Plots the FFD block and optionally the points embedded within.
        '''
        plotting_elements = additional_plotting_elements.copy()

        plotting_elements = super().plot(point_types=['evaluated_points'], opacity=opacity, color=color,
                                         surface_texture=surface_texture, additional_plotting_elements=plotting_elements, show=False)
        plotting_elements = super().plot(point_types=['coefficients'], plot_types=['point_cloud'], opacity=opacity, color=color,
                                         surface_texture=surface_texture, additional_plotting_elements=plotting_elements, show=False)

        if plot_embedded_points:
            if embedded_points is None:
                embedded_points = []
                for entity in self.embedded_entities:
                    if isinstance(entity, np.ndarray):
                        embedded_points.append(entity)
                    elif isinstance(entity, csdl.Variable):
                        embedded_points.append(entity.value)
                    elif isinstance(entity, lfs.Function):
                        embedded_points.append(entity.coefficients.value)
                    elif isinstance(entity, lfs.FunctionSet):
                        for function in entity.functions:
                            embedded_points.append(function.coefficients.value)
                    else:
                        raise ValueError(f'Unsupported entity type: {type(entity)}')
            
            for i, entity_points in enumerate(embedded_points):
                # if isinstance(entity, np.ndarray) or isinstance(entity, csdl.Variable):
                # NOTE: I am intentionally plotting everything as a point cloud because that is specifically what the FFD block is operating on.
                # if isinstance(entity_points, list):
                #     for entity_entity_points in entity_points:
                #         plotting_elements = lfs.plot_points(points=entity_entity_points, opacity=1., color='#182B49',
                #                                         additional_plotting_elements=plotting_elements, show=False)
                # else:
                plotting_elements = lfs.plot_points(points=entity_points, opacity=1., color='#182B49',
                                                    additional_plotting_elements=plotting_elements, show=False)

        if show:
            # plotter = vedo.Plotter()
            # plotter.show(plotting_elements, f'Free Form Deformation Block: {self.name}', axes=1, viewup="z", interactive=True)
            if self.name is not None:
                lfs.show_plot(plotting_elements, f'Free Form Deformation Block: {self.name}', axes=1, interactive=True)
            else:
                lfs.show_plot(plotting_elements, 'Free Form Deformation Block', axes=1, interactive=True)
            return plotting_elements
        else:
            return plotting_elements
    


if __name__ == "__main__":
    pass

