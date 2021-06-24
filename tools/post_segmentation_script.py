import numpy as np
from matplotlib import pyplot as plt
import matplotlib
from matplotlib.patches import Circle, PathPatch
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from skimage.measure import LineModelND, CircleModel, ransac, EllipseModel
import mpl_toolkits.mplot3d.art3d as art3d
import math
import pandas as pd
from scipy import stats, spatial
import time
from scipy.interpolate import griddata
import warnings
from sklearn import metrics
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN, OPTICS
from copy import deepcopy
from skimage.measure import LineModelND, CircleModel, ransac
import glob
from scipy.spatial import ConvexHull, convex_hull_plot_2d
from scipy.spatial.distance import euclidean
from math import sin, cos, pi
import random
import os
from sklearn.neighbors import NearestNeighbors
from tools import load_file, save_file
warnings.filterwarnings("ignore", category=RuntimeWarning)


class PostProcessing:
    def __init__(self, parameters):
        self.post_processing_time_start = time.time()
        self.parameters = parameters
        self.filename = self.parameters['input_point_cloud'].replace('\\', '/')
        self.output_dir = os.path.dirname(os.path.realpath(self.filename)).replace('\\', '/') + '/' + \
                          self.filename.split('/')[-1][:-4] + '_FSCT_output/'
        self.filename = self.filename.split('/')[-1]
        if self.parameters['plot_radius'] != 0:
            self.filename = self.filename[:-4] + '_' + str(self.parameters['plot_radius']) + '_m_crop.las'

        self.noise_class_label = parameters['noise_class']
        self.terrain_class_label = parameters['terrain_class']
        self.vegetation_class_label = parameters['vegetation_class']
        self.cwd_class_label = parameters['cwd_class']
        self.stem_class_label = parameters['stem_class']

    def subsample_point_cloud(self, X, min_spacing):
        print("Subsampling...")
        neighbours = NearestNeighbors(n_neighbors=2, algorithm='kd_tree', metric='euclidean').fit(X[:, :3])
        distances, indices = neighbours.kneighbors(X[:, :3])
        X_keep = X[distances[:, 1] >= min_spacing]
        i1 = [distances[:, 1] < min_spacing][0]
        i2 = [X[indices[:, 0], 2] < X[indices[:, 1], 2]][0]
        X_check = X[np.logical_and(i1, i2)]

        while np.shape(X_check)[0] > 1:
            neighbours = NearestNeighbors(n_neighbors=2, algorithm='kd_tree', metric='euclidean').fit(X_check[:, :3])
            distances, indices = neighbours.kneighbors(X_check[:, :3])
            X_keep = np.vstack((X_keep, X_check[distances[:, 1] >= min_spacing, :]))
            i1 = [distances[:, 1] < min_spacing][0]
            i2 = [X_check[indices[:, 0], 2] < X_check[indices[:, 1], 2]][0]
            X_check = X_check[np.logical_and(i1, i2)]

        X = X_keep
        return X

    def make_DTM(self, clustering_epsilon=0.1, min_cluster_points=500, smoothing_radius=1, crop_dtm=False):
        print("Making DTM...")
        """
        This function will generate a Digital Terrain Model (DTM) based on the terrain labelled points.
        """
        print(self.terrain_points.shape)
        if self.terrain_points.shape[0] <= 10000:
            self.terrain_points_subsampled = self.subsample_point_cloud(self.terrain_points, 0.01)
            if self.terrain_points_subsampled.shape[0] <= 2:
                self.terrain_points_subsampled = self.terrain_points

        else:
            self.terrain_points_subsampled = self.terrain_points

        # Cluster terrain_points using DBSCAN
        clustered_terrain_points = self.clustering(self.terrain_points_subsampled[:, :3], clustering_epsilon)

        # Initialise terrain and noise cluster arrays
        terrain_clusters = np.zeros((0, self.terrain_points_subsampled.shape[1]))
        self.noise_points = np.zeros((0, self.terrain_points_subsampled.shape[1]))

        # Check that terrain clusters are greater than min_cluster_points, keep those that are.
        for group in range(0, int(np.max(clustered_terrain_points[:, -1])) + 1):
            cluster = self.terrain_points_subsampled[clustered_terrain_points[:, -1] == group]
            if np.shape(cluster)[0] >= min_cluster_points:
                terrain_clusters = np.vstack((terrain_clusters, cluster))
            else:
                self.noise_points = np.vstack((self.noise_points, cluster))
        self.noise_points = np.vstack(
                (self.noise_points, self.terrain_points_subsampled[clustered_terrain_points[:, -1] == -1]))

        self.terrain_points_subsampled = terrain_clusters
        print("Terrain shape", self.terrain_points_subsampled.shape)
        self.noise_points[:, -1] = self.noise_class_label  # make sure these points get the noise class label.

        if self.terrain_points_subsampled.shape[0] == 0:
            """If there are no terrain points after subsampling, undo the subsampling. We still need some points."""
            self.terrain_points_subsampled = self.terrain_points

        kdtree = spatial.cKDTree(self.terrain_points_subsampled[:, :2], leafsize=1000)
        xmin = np.floor(np.min(self.terrain_points_subsampled[:, 0])) - 3
        ymin = np.floor(np.min(self.terrain_points_subsampled[:, 1])) - 3
        xmax = np.ceil(np.max(self.terrain_points_subsampled[:, 0])) + 3
        ymax = np.ceil(np.max(self.terrain_points_subsampled[:, 1])) + 3
        x_points = np.linspace(xmin, xmax, int(np.ceil((xmax - xmin) / self.parameters['fine_grid_resolution'])) + 1)
        y_points = np.linspace(ymin, ymax, int(np.ceil((ymax - ymin) / self.parameters['fine_grid_resolution'])) + 1)

        grid_points = np.zeros((0, 3))
        for x in x_points:
            for y in y_points:
                indices = []
                radius = self.parameters['fine_grid_resolution']
                while len(indices) < 100 and radius <= 5:
                    indices = kdtree.query_ball_point([x, y], r=radius)
                    # print("Indices",len(indices),'radius',radius)
                    radius += self.parameters['fine_grid_resolution']

                if len(indices) > 0:
                    z = np.percentile(self.terrain_points_subsampled[indices, 2], 50)
                    grid_points = np.vstack((grid_points, np.array([[x, y,
                                                                     z]])))  # np.array([[np.median(self.terrain_points[indices,0]),np.median(self.terrain_points[indices,1]),z]]) ))

        if crop_dtm:
            kdtree2 = spatial.cKDTree(self.point_cloud[:, :2], leafsize=10000)
            inds = [len(i) > 0 for i in
                    kdtree2.query_ball_point(grid_points[:, :2], r=self.parameters['fine_grid_resolution'] * 3)]
            # print(inds)
            grid_points = grid_points[inds, :]

        if smoothing_radius > 0:
            kdtree2 = spatial.cKDTree(grid_points, leafsize=1000)
            results = kdtree2.query_ball_point(grid_points, r=smoothing_radius)
            smoothed_Z = np.zeros((0, 1))
            for i in results:
                smoothed_Z = np.vstack((smoothed_Z, np.nanmean(grid_points[i, 2])))
            grid_points[:, 2] = np.squeeze(smoothed_Z)

        grid_points = self.clustering(grid_points, eps=self.parameters['fine_grid_resolution'] * 3, min_samples=15)

        rejected_grid_points = grid_points[grid_points[:, -1] != 0, :-1]
        grid_points = grid_points[grid_points[:, -1] >= 0, :-1]
        if rejected_grid_points.shape[0] > 0:
            kdtree3 = spatial.cKDTree(grid_points[:, :2], leafsize=1000)
            results = kdtree3.query_ball_point(rejected_grid_points[:, :2],
                                               r=self.parameters['fine_grid_resolution'] * 3)

            corrected_grid_points = np.hstack((rejected_grid_points[:, :2], np.atleast_2d(
                np.array([np.nanmedian(grid_points[i, 2]) for i in results])).T))
            grid_points = np.vstack((grid_points, corrected_grid_points))
            print(np.any(np.isnan(grid_points)))
        return grid_points

    def get_heights_above_DTM(self, points):
        grid = griddata((self.DTM[:, 0], self.DTM[:, 1]), self.DTM[:, 2], points[:, 0:2], method='linear',
                        fill_value=np.median(self.DTM[:, 2]))
        points[:, -1] = points[:, 2] - grid
        return points

    def clustering(self, points, eps=0.05, min_samples=2):
        print("Clustering...")
        db = DBSCAN(eps=eps, min_samples=min_samples, metric='euclidean', algorithm='kd_tree', n_jobs=-1).fit(
                points[:, :3])
        # db = OPTICS(eps=eps, min_cluster_size=min_samples,metric='euclidean', algorithm='kd_tree',cluster_method="dbscan",leaf_size=10000,n_jobs=-1).fit(points[:,:3])
        return np.hstack((points, np.atleast_2d(db.labels_).T))

    def process_point_cloud(self, point_cloud=np.zeros((0, 1))):
        if point_cloud.shape[0] == 0:
            print("Loading segmented point cloud...")
            self.point_cloud = load_file(self.output_dir+self.filename)
        else:
            self.point_cloud = point_cloud

        self.number_of_points = self.point_cloud.shape[0]
        self.point_cloud = np.hstack(
                (self.point_cloud, np.zeros((self.point_cloud.shape[0], 1))))  # add height above DTM column
        # print('Point cloud shape:',np.shape(self.point_cloud))
        self.label_index = np.shape(self.point_cloud)[1] - 2
        self.point_cloud[:, self.label_index] = self.point_cloud[:, self.label_index] + 1  # index offset since noise_class was removed from inference.

        # Generate first run digital terrain model based on "terrain_points" then save DTM.csv
        self.terrain_points = self.point_cloud[self.point_cloud[:, -2] == self.terrain_class_label]  # -2 is now the class label as we added the height above DTM column.
        self.DTM = self.make_DTM(smoothing_radius=3 * self.parameters['fine_grid_resolution'], crop_dtm=True)
        save_file(self.output_dir + 'DTM.csv', self.DTM)
        self.convexhull = spatial.ConvexHull(self.terrain_points[:, :2])
        self.convex_hull_points = self.terrain_points[self.convexhull.vertices, :2]
        self.plot_area_estimate = self.convexhull.volume  # volume is area in 2d...
        print("Plot area is approximately", self.plot_area_estimate, "m^2 or", self.plot_area_estimate / 10000, 'ha')

        self.post_processing_time_end = time.time()
        self.post_processing_time = self.post_processing_time_end - self.post_processing_time_start
        print("Post-processing took", self.post_processing_time, 'seconds')

        self.point_cloud = self.get_heights_above_DTM(self.point_cloud)  # Add a height above DTM column to the point clouds.

        self.terrain_points = self.point_cloud[self.point_cloud[:, -2] == self.terrain_class_label]  # -2 is now the class label as we added the height above DTM column.
        self.terrain_points_rejected = np.vstack((self.terrain_points[self.terrain_points[:, -1] <= -0.1],
                                                  self.terrain_points[self.terrain_points[:, -1] > 0.1]))
        self.terrain_points = self.terrain_points[np.logical_and(self.terrain_points[:, -1] > -0.1, self.terrain_points[:, -1] < 0.1)]

        save_file(self.output_dir + 'terrain_points.las', self.terrain_points)

        self.stem_points = self.point_cloud[self.point_cloud[:,
                                            -2] == self.stem_class_label]  # -2 is now the class label as we added the height above DTM column.
        self.stem_points_rejected = self.stem_points[self.stem_points[:, -1] <= 0.05]
        self.stem_points = self.stem_points[self.stem_points[:, -1] > 0.05]
        save_file(self.output_dir + 'stem_points.las', self.stem_points)

        self.vegetation_points = self.point_cloud[self.point_cloud[:,
                                                  -2] == self.vegetation_class_label]  # -2 is now the class label as we added the height above DTM column.
        self.vegetation_points_rejected = self.vegetation_points[self.vegetation_points[:, -1] <= 0.05]
        self.vegetation_points = self.vegetation_points[self.vegetation_points[:, -1] > 0.05]
        save_file(self.output_dir + 'vegetation_points.las', self.vegetation_points)

        self.cwd_points = self.point_cloud[self.point_cloud[:,
                                           -2] == self.cwd_class_label]  # -2 is now the class label as we added the height above DTM column.
        self.cwd_points_rejected = np.vstack(
                (self.cwd_points[self.cwd_points[:, -1] <= 0.05], self.cwd_points[self.cwd_points[:, -1] >= 10]))
        self.cwd_points = self.cwd_points[np.logical_and(self.cwd_points[:, -1] > 0.05, self.cwd_points[:, -1] < 3)]
        save_file(self.output_dir + 'cwd_points.las', self.cwd_points)

        self.cleaned_pc = np.vstack((self.terrain_points, self.vegetation_points, self.cwd_points, self.stem_points))
        save_file(self.output_dir + self.filename[:, :-4] + 'cleaned.las', self.cleaned_pc)

        times = pd.read_csv(self.output_dir + 'run_times.csv', index_col=None)
        times['Post_processing_time (s)'] = self.post_processing_time
        times.to_csv(self.output_dir + 'run_times.csv', index=False)
        print("Post processing took", self.sem_seg_total_time, 's')
        print("Post processing done.")
