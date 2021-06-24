from preprocessing import Preprocessing
from inference import SemanticSegmentation
from post_segmentation_script import PostProcessing
import glob
import numpy as np
from measure import MeasureTree
import tkinter as tk
import tkinter.filedialog as fd
from other_parameters import other_parameters
if __name__ == '__main__':
    # root = tk.Tk()
    # point_clouds_to_process = fd.askopenfilenames(parent=root, title='Choose files', filetypes=[("LAS", "*.las"),
    #                                                                                             ("CSV", "*.csv")])
    # root.destroy()
    point_clouds_to_process = ['C:/Users/seank/Downloads/CULS/CULS/plot_1_annotated.las']
    for point_cloud in point_clouds_to_process:
        print(point_cloud)

        parameters = dict(input_point_cloud=point_cloud,
                          batch_size=20,
                          num_procs=20,
                          max_diameter=5,
                          slice_thickness=0.2,#default = 0.2
                          slice_increment=0.05,#default = 0.05
                          slice_clustering_distance=0.2, #default = 0.1
                          cleaned_measurement_radius=0.18,
                          minimum_CCI=0.3,
                          min_tree_volume=0.005,
                          ground_veg_cutoff_height=3,
                          canopy_mode='photogrammetry_mode',
                          Site='not_specified',
                          PlotID='not_specified',
                          plot_centre=None,
                          plot_radius=5,
                          UTM_zone_number=50,
                          UTM_zone_letter=None,
                          UTM_is_north=False,
                          run_from_start=1,
                          filter_noise=0,
                          low_resolution_point_cloud_hack_mode=0)

        parameters.update(other_parameters)

        # preprocessing1 = Preprocessing(parameters)
        # preprocessing1.preprocess_point_cloud()
        #
        # sem_seg = SemanticSegmentation(parameters)
        # sem_seg.inference()

        object_1 = PostProcessing(parameters)
        # object_1.process_point_cloud(point_cloud=sem_seg.output)
        object_1.process_point_cloud()
        #
        # del sem_seg

        # measure1 = MeasureTree(parameters)
        # measure1.run_measurement_extraction()
        # del measure1
